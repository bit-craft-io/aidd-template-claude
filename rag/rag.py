"""RAG の共通部品: 分割・埋め込み・DB 操作・検索。

標準ライブラリのみ(DB を使う関数だけ、psycopg を、関数の中で読み込む)。
設計書: docs/design/rag-minimal-pipeline.md
"""
import fnmatch
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass

DATABASE_URL = os.environ.get("RAG_DATABASE_URL", "postgresql://rag:rag@127.0.0.1:5432/rag")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "bge-m3")
EMBED_DIM = int(os.environ.get("RAG_EMBED_DIM", "1024"))
MAX_CHUNK = 1500
BATCH = 16

_HEADING = re.compile(r"^#{1,3} +(.*\S)\s*$")
_FENCE = re.compile(r"^ {0,3}(```|~~~)")


@dataclass(frozen=True)
class Chunk:
    path: str
    heading: str
    text: str


def doc_type_of(path):
    """docs からの相対パスから、文書の種類を決める。"""
    p = path.replace("\\", "/")
    if p.startswith("decisions/shared/"):
        return "shared"
    if re.fullmatch(r"decisions/adr-[^/]*\.md", p):
        return "adr"
    if p.startswith("design/"):
        return "design"
    if p.startswith("superpowers/plans/"):
        return "plan"
    return "other"


def _sections(text):
    """見出し(#〜###)で区切った (見出し, 本文) の列。コードのかこみの中の # は、見出しにしない。"""
    sections, heading, lines, in_fence = [], "", [], False
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _FENCE.match(line):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m and lines:
            sections.append((heading, "\n".join(lines)))
            lines = []
        if m:
            heading = m.group(1)
        lines.append(line)
    if lines:
        sections.append((heading, "\n".join(lines)))
    return sections


def _cut(section, limit=MAX_CHUNK):
    """長い節を、段落(空行)で、limit 以内に切る。1 つの段落が limit を超えても、割らない。"""
    if len(section) <= limit:
        return [section]
    out, buf = [], ""
    for para in section.split("\n\n"):
        if buf and len(buf) + 2 + len(para) > limit:
            out.append(buf)
            buf = ""
        buf = f"{buf}\n\n{para}" if buf else para
    if buf:
        out.append(buf)
    return out


def split_markdown(path, text):
    """1 つの文書を、断片に分ける。各断片の先頭に、[パス] の行を付ける。"""
    chunks = []
    for heading, body in _sections(text.lstrip("﻿")):
        for part in _cut(body):
            if part.strip():
                chunks.append(Chunk(path, heading, f"[{path}]\n{part}"))
    return chunks


def iter_markdown(docs_dir, excludes=()):
    """docs_dir 配下の *.md を、(相対パス, 本文) で、パスの順に返す。excludes は fnmatch。"""
    found = []
    for root, _dirs, files in os.walk(docs_dir):
        for name in files:
            if not name.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(root, name), docs_dir).replace(os.sep, "/")
            if any(fnmatch.fnmatch(rel, pat) for pat in excludes):
                continue
            found.append(rel)
    for rel in sorted(found):
        with open(os.path.join(docs_dir, rel), encoding="utf-8", errors="replace") as f:
            yield rel, f.read()


def embed(texts, model=None, url=None, batch=BATCH):
    """Ollama の /api/embed で、埋め込みを得る。失敗は、RuntimeError(案内つき)。"""
    model = model or EMBED_MODEL
    url = url or OLLAMA_URL
    vectors = []
    for i in range(0, len(texts), batch):
        body = json.dumps({"model": model, "input": texts[i:i + batch]}).encode()
        req = urllib.request.Request(f"{url}/api/embed", body, {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as res:
                vectors += json.load(res)["embeddings"]
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200]
            raise RuntimeError(f"Ollama がエラーを返した({e.code}): {detail}") from e
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            raise RuntimeError(f"Ollama に繋がらぬ({url}): {e}。`make rag-up` を実行したか") from e
    return vectors


def vec_literal(v):
    """pgvector の文字列表現('[0.1,0.2,...]')。SQL 側で ::vector に直す。"""
    return "[" + ",".join(repr(float(x)) for x in v) + "]"


def connect(url=None):
    """DB に繋ぐ。失敗は、RuntimeError(案内つき)。"""
    import psycopg

    try:
        return psycopg.connect(url or DATABASE_URL)
    except psycopg.OperationalError as e:
        raise RuntimeError(f"DB に繋がらぬ: {e}。`make rag-up` を実行したか") from e


def current_commit(path="."):
    """path のリポジトリの、短縮したコミット。分からなければ "unknown"。"""
    try:
        out = subprocess.run(
            ["git", "-C", path, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else "unknown"


def replace_project(conn, project, rows):
    """同じ project の行を全て消し、rows を入れる。一つのトランザクション。失敗すれば、元のまま。

    rows: (content, metadata, vector) の列。
    """
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge WHERE metadata->>'project' = %s", (project,))
            cur.executemany(
                "INSERT INTO knowledge (content, metadata, embedding) VALUES (%s, %s::jsonb, %s::vector)",
                [(c, json.dumps(m, ensure_ascii=False), vec_literal(v)) for c, m, v in rows],
            )


def ingest(conn, docs_dir, project, excludes=(), commit=None, embed_fn=None):
    """docs_dir の Markdown を、断片に分け、埋め込み、project の行として置き換える。"""
    embed_fn = embed_fn or embed
    commit = commit or current_commit(docs_dir)
    chunks = []
    for rel, text in iter_markdown(docs_dir, excludes):
        chunks += split_markdown(rel, text)
    if not chunks:
        raise RuntimeError(f"取り込む Markdown が無い: {docs_dir}")
    vectors = embed_fn([c.text for c in chunks])
    bad = [len(v) for v in vectors if len(v) != EMBED_DIM]
    if bad:
        raise RuntimeError(
            f"埋め込みの次元が違う(期待 {EMBED_DIM}、実際 {bad[0]})。RAG_EMBED_MODEL と、表の次元を確かめよ"
        )
    rows = [
        (
            c.text,
            {
                "project": project,
                "path": c.path,
                "heading": c.heading,
                "doc_type": doc_type_of(c.path),
                "commit": commit,
                "model": EMBED_MODEL,
            },
            v,
        )
        for c, v in zip(chunks, vectors)
    ]
    replace_project(conn, project, rows)
    by_type = {}
    for _c, m, _v in rows:
        by_type[m["doc_type"]] = by_type.get(m["doc_type"], 0) + 1
    return {"files": len({c.path for c in chunks}), "chunks": len(rows), "by_doc_type": by_type}


@dataclass(frozen=True)
class Hit:
    score: float
    project: str
    path: str
    heading: str
    doc_type: str
    content: str


_SEARCH_SQL = """
SELECT content, metadata, 1 - (embedding <=> %s::vector) AS score
FROM knowledge
WHERE (%s::text IS NULL OR metadata->>'project' = %s::text)
  AND (%s::text IS NULL OR metadata->>'doc_type' = %s::text)
ORDER BY embedding <=> %s::vector
LIMIT %s
"""


def search(conn, question, project=None, doc_type=None, k=5, embed_fn=None):
    """問いに近い断片を、近い順に k 件返す。project・doc_type で、絞り込める。"""
    if not question.strip():
        raise ValueError("問いが空である")
    embed_fn = embed_fn or embed
    qv = vec_literal(embed_fn([question])[0])
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SET LOCAL hnsw.ef_search = 100")
            cur.execute(_SEARCH_SQL, (qv, project, project, doc_type, doc_type, qv, k))
            rows = cur.fetchall()
    return [
        Hit(
            score=float(score),
            project=meta.get("project", ""),
            path=meta.get("path", ""),
            heading=meta.get("heading", ""),
            doc_type=meta.get("doc_type", ""),
            content=content,
        )
        for content, meta, score in rows
    ]


def _one_line(text, limit):
    if text.startswith("[") and "\n" in text:
        text = text.split("\n", 1)[1]  # 先頭の [パス] の行は、見出しの行に出ているため省く
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit] + "…"


def format_hits(hits, full=False):
    """検索の結果を、人が読む形にする。"""
    if not hits:
        return "(該当なし)"
    lines = []
    for i, h in enumerate(hits, 1):
        head = f"[{i}] score={h.score:.3f}  {h.doc_type}  {h.project}:{h.path}"
        if h.heading:
            head += f"  # {h.heading}"
        body = h.content if full else _one_line(h.content, 160)
        lines.append(f"{head}\n    {body}")
    return "\n".join(lines)


def clamp_k(k, lo=1, hi=20):
    """件数を、lo〜hi に丸める。数でなければ、既定の 5。"""
    try:
        k = int(k)
    except (TypeError, ValueError):
        return 5
    return max(lo, min(hi, k))


def _strip_path_line(text):
    """断片の先頭の [パス] の行を省く。"""
    return text.split("\n", 1)[1] if text.startswith("[") and "\n" in text else text


def get_document(conn, path, project=None):
    """path の文書の全文(断片を、取り込みの順に、空行でつないだ物)。無ければ None。

    同じ path が、複数のプロジェクトに在り、project が無いときは、ValueError(候補を示す)。
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT metadata->>'project' FROM knowledge "
            "WHERE metadata->>'path' = %s "
            "AND (%s::text IS NULL OR metadata->>'project' = %s::text) ORDER BY 1",
            (path, project, project),
        )
        projects = [r[0] for r in cur.fetchall()]
        if not projects:
            return None
        if len(projects) > 1:
            raise ValueError(f"複数のプロジェクトに在る: {', '.join(projects)}。project を指定せよ")
        cur.execute(
            "SELECT content FROM knowledge "
            "WHERE metadata->>'path' = %s AND metadata->>'project' = %s ORDER BY id",
            (path, projects[0]),
        )
        return "\n\n".join(_strip_path_line(r[0]) for r in cur.fetchall())


def list_sources(conn, doc_type=None):
    """取り込み済みの、プロジェクト・文書の種類ごとの、文書数・断片数・コミット・モデル。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT metadata->>'project', metadata->>'doc_type', "
            "count(DISTINCT metadata->>'path'), count(*), "
            "max(metadata->>'commit'), max(metadata->>'model') "
            "FROM knowledge WHERE (%s::text IS NULL OR metadata->>'doc_type' = %s::text) "
            "GROUP BY 1, 2 ORDER BY 1, 2",
            (doc_type, doc_type),
        )
        return [
            {"project": p, "doc_type": t, "files": f, "chunks": c, "commit": cm, "model": m}
            for p, t, f, c, cm, m in cur.fetchall()
        ]


def format_sources(rows):
    """list_sources の結果を、人が読む形にする。"""
    if not rows:
        return "(取り込み済みの文書なし)"
    return "\n".join(
        f"{r['project']}  {r['doc_type']}  文書 {r['files']}・断片 {r['chunks']}  "
        f"commit={r['commit']}  model={r['model']}"
        for r in rows
    )
