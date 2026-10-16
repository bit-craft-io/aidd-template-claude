# RAG の最小の通し Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/` の Markdown を、PostgreSQL(pgvector)に取り込み、問いに近い断片を、出所つきで返す仕組みと、待ち受けの MCP サーバ(`127.0.0.1` のみ)を、`make rag-up` の一つで動かし、Claude Code から、ツールとして呼べるようにする。

**Architecture:** `rag/compose.yaml` に、`db`(pgvector)・`ollama`(`bge-m3`)・`mcp`(待ち受けの MCP サーバ)の三つのサービスを置く。Python(標準ライブラリ + `psycopg`)の共通部品 `rag/rag.py` に、分割・埋め込み・DB 操作・検索・文書の取得・一覧を持たせ、`ingest.py`・`search.py`・`eval.py`・`mcp_server.py` が、その薄い殻になる。Makefile の `rag-*` 目標が、コンテナと Python を束ねる。

**Tech Stack:** Docker Compose、`pgvector/pgvector:pg16`、`ollama/ollama`、Python 3.12(標準ライブラリ、`unittest`)、`psycopg`(v3)、MCP の Python SDK(`mcp`。MCP サーバのイメージにのみ入れる)、GNU Make。

**Spec:** `docs/design/rag-minimal-pipeline.md`

## Global Constraints

設計書の全体の決まり。全ての Task の要求に、暗黙に含まれる。

- 埋め込みモデルは `bge-m3`、次元は 1024。外部の API には、断片を送らない
- 文書の分け方は、見出し(`#`〜`###`)で区切り、長い節は、段落(空行)で 1500 字以内に切る。各断片の先頭に `[パス]` の行を付ける
- 表は `knowledge(id, content, metadata JSONB, embedding VECTOR(1024))`、索引は HNSW(`vector_cosine_ops`)
- `metadata` の項目は `project`・`path`・`heading`・`doc_type`・`commit`・`model`
- ポートは、DB が `127.0.0.1:5432`、Ollama が `127.0.0.1:11434`、MCP サーバが `127.0.0.1:8000`(URL は `http://127.0.0.1:8000/mcp`)。いずれも `127.0.0.1` のみに公開
- 設定の環境変数は `RAG_DATABASE_URL`(既定 `postgresql://rag:rag@127.0.0.1:5432/rag`)、`OLLAMA_URL`(既定 `http://127.0.0.1:11434`)、`RAG_EMBED_MODEL`(既定 `bge-m3`)
- `GPU` は、`1`・`true`・`yes` のとき有効。`0`・`false`・空は無効
- 取り込みは、同じ `project` の行を、一つのトランザクションで、全て置き換える
- MCP のツールは、`search_knowledge`・`get_document`・`list_sources` の三本で、いずれも読み取り専用。認証は付けない(`127.0.0.1` のみ)。評価は、MCP に出さぬ
- 手元の Python の依存は `psycopg`(v3)のみ。`venv`(`rag/.venv`)に入れる。MCP の SDK(`mcp`)は、MCP サーバのイメージにのみ入れる(`rag/requirements-mcp.txt`)。`psycopg` は、DB を使う関数の中で読み込む(単体テストを、依存なしで動かすため)
- 表記は、文章・題で「PostgreSQL」、拡張で「pgvector」。`postgres`・`pg` は、単独では使わない(識別子の `pg16` を除く)
- ひな形に、特定のリポジトリ・プロジェクトの名を、書かない(質問集 `docs/rag/eval-questions.md` は、②の後で外す物ゆえ除く)
- **コミットは、ユーザーが頼んだときだけ**行う(`.claude/rules/git.md`)。各 Task の末尾の「コミットの区切り」は、ユーザーが `/git commit` で行うときの案であり、実行者が、自分で `git commit` しない。設計書・計画書の変更は、実装のコミットと分ける

## 外への通信・ディスクを使う手順

次の手順は、外への通信やディスクを使う。**実行の前に、ユーザーの了承を得る**。

| 手順 | 通信先 | 規模 |
|---|---|---|
| コンテナのイメージの取得(Task 1) | Docker のレジストリ | `pgvector/pgvector:pg16`、`ollama/ollama`(数百 MB〜数 GB) |
| モデルの取得(Task 1) | Ollama のレジストリ | `bge-m3` 約 1.2GB |
| Python の依存の導入(Task 3) | PyPI | `psycopg[binary]` |
| MCP の SDK の確認(Task 6 の Step 1)と、MCP サーバのイメージの作成(Task 6 の Step 6) | PyPI、Docker のレジストリ | `mcp` ほか、`python:3.12-slim`(数百 MB) |

## Review Focus

設計書が含意するが、どの Task の既存のテストにも出ぬ、使う人に害になりやすい入力・状況。上が、最も起きやすい。各行に、その担当の Task で、テストを足してある。

1. **コードのかこみ(` ``` `)の中の `#` で始まる行** — シェルのコメントなどを、見出しと誤って、節を割らぬこと(Task 2 の `test_hash_in_code_fence_is_not_heading`)
2. **空の文書・見出しの無い文書・CRLF 改行・BOM 付き** — 落ちず、改行や BOM が、断片に混ざらぬこと(Task 2 の `test_empty_document`・`test_no_heading_document`・`test_crlf_and_bom`)
3. **Ollama が停止しているとき** — スタックトレースだけでなく、「Ollama に繋がらぬ」と、`make rag-up` への案内が出ること(Task 2 の `test_unreachable_ollama_has_hint`)
4. **取り込みの途中で失敗したとき・同じ `project` を繰り返し取り込んだとき** — 失敗したら、既存の行が消えず、繰り返しても、件数が変わらぬこと(Task 3 の `test_failure_keeps_old_rows`・`test_ingest_twice_keeps_count`)
5. **`GPU=0`・`GPU=false`・未指定** — GPU の定義を、重ねぬこと(Task 1 の `make -n` の確認)

---

### Task 1: コンテナと Makefile の目標(DB・Ollama・モデル)

設計書のゴール 1・6 を担う。

**Files:**
- Create: `rag/compose.yaml`
- Create: `rag/compose.gpu.yaml`
- Create: `rag/sql/init.sql`
- Modify: `Makefile`(`help` の変数の説明に追記、ファイル末尾に `rag-up`・`rag-down`・`rag-destroy` を追加)

**Interfaces:**
- Consumes: なし
- Produces: `make rag-up [GPU=1]`・`make rag-down`・`make rag-destroy [YES=1]`。DB `127.0.0.1:5432`(表 `knowledge` あり)、Ollama `127.0.0.1:11434`(`bge-m3` あり)。Makefile の変数 `RAG_DIR`・`RAG_MODEL`・`RAG_COMPOSE`・`RAG_PY`・`RAG_PROJECT`・`RAG_ONLY`・`DOCS`・`K`・`QFILE`(後の Task が使う)

- [ ] **Step 1: 表の定義を書く**

`rag/sql/init.sql`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge (
    id        SERIAL PRIMARY KEY,
    content   TEXT,
    metadata  JSONB,
    embedding VECTOR(1024)
);

CREATE INDEX IF NOT EXISTS knowledge_embedding_idx
    ON knowledge USING hnsw (embedding vector_cosine_ops);
```

- [ ] **Step 2: コンテナの定義を書く**

`rag/compose.yaml`:

```yaml
name: rag

services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: rag
      POSTGRES_PASSWORD: rag
      POSTGRES_DB: rag
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - rag-db-data:/var/lib/postgresql/data
      - ./sql:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rag -d rag"]
      interval: 3s
      timeout: 3s
      retries: 20

  ollama:
    image: ollama/ollama:0.31.1
    environment:
      OLLAMA_KEEP_ALIVE: 24h
    ports:
      - "127.0.0.1:11434:11434"
    volumes:
      - rag-ollama-models:/root/.ollama
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 3s
      timeout: 5s
      retries: 20

volumes:
  rag-db-data:
  rag-ollama-models:
```

`rag/compose.gpu.yaml`:

```yaml
services:
  ollama:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

- [ ] **Step 3: 定義が正しいか確かめる(通信なし)**

Run: `docker compose -f rag/compose.yaml config -q && docker compose -f rag/compose.yaml -f rag/compose.gpu.yaml config -q && echo OK`
Expected: `OK`(エラーなし)

- [ ] **Step 4: Makefile の `help` の変数の説明に、RAG の変数を足す**

`Makefile` の、次の行の**直前**に、5 行を挿入する。

挿入先の行(現在の 31 行目):

```make
	@printf '\nExample:\n  make new NAME=my-project\n'
```

その直前に挿入する内容:

```make
	@printf '\nVariables (for "rag-*"):\n'
	@printf '  GPU\t1 (or true/yes) lets the ollama container use the NVIDIA GPU (rag-up)\n'
	@printf '  PROJECT\tProject name stored in the DB (rag-ingest; default: this directory name)\n'
	@printf '  DOCS\tDirectory of Markdown to ingest (rag-ingest; default: docs)\n'
	@printf '  Q\tQuestion (rag-search)\n'
```

- [ ] **Step 5: Makefile の末尾に、RAG の目標を足す**

`Makefile` の末尾(`new` の最後の行 `@echo "Next: cd $(TARGET), then set up git (see README)."` の後)に、空行を一つ置いて、次を追加する。

```make

# ---- RAG (design: docs/design/rag-minimal-pipeline.md) ----
RAG_DIR     := rag
RAG_MODEL   ?= bge-m3
RAG_GPU     := $(filter 1 true yes,$(GPU))
RAG_COMPOSE := docker compose -f $(RAG_DIR)/compose.yaml$(if $(RAG_GPU), -f $(RAG_DIR)/compose.gpu.yaml)
RAG_PY      := $(RAG_DIR)/.venv/bin/python
DOCS        ?= docs
K           ?= 5
QFILE       ?= docs/rag/eval-questions.md
RAG_PROJECT := $(if $(filter command line,$(origin PROJECT)),$(PROJECT),$(notdir $(CURDIR)))
RAG_ONLY    := $(if $(filter command line,$(origin PROJECT)),--project "$(PROJECT)")

.PHONY: rag-up rag-down rag-destroy

rag-up: ## Start the RAG containers (db, ollama) and pull the model (GPU=1: use the NVIDIA GPU)
	@$(RAG_COMPOSE) up -d --wait
	@if $(RAG_COMPOSE) exec -T ollama ollama list | grep -q '^$(RAG_MODEL)'; then \
	  echo "model $(RAG_MODEL): already present"; \
	else \
	  echo "pulling $(RAG_MODEL) (first time only; about 1.2GB download)"; \
	  $(RAG_COMPOSE) exec -T ollama ollama pull $(RAG_MODEL); \
	fi
	@echo "RAG is up. db: 127.0.0.1:5432  ollama: 127.0.0.1:11434"

rag-down: ## Stop the RAG containers (data is kept)
	@$(RAG_COMPOSE) down

rag-destroy: ## Stop the RAG containers and DELETE their data (db, models)
	@if [ -z "$(YES)" ]; then \
	  read -r -p "Delete the RAG containers and ALL their data (db, models)? [y/N] " ans; \
	  case "$$ans" in [Yy]|[Yy][Ee][Ss]) ;; *) echo "Aborted."; exit 1;; esac; \
	fi
	@$(RAG_COMPOSE) down -v
```

- [ ] **Step 6: `GPU` の判定を確かめる(通信なし。Review Focus 5)**

Run:

```bash
for v in "" "GPU=0" "GPU=false" "GPU=1" "GPU=true" "GPU=yes"; do
  n=$(make -n rag-up $v | grep -c 'compose.gpu.yaml')
  echo "[$v] compose.gpu.yaml の出現: $n"
done
```

Expected: 空・`GPU=0`・`GPU=false` は `0`、`GPU=1`・`GPU=true`・`GPU=yes` は `1` 以上

- [ ] **Step 7: `help` に目標が出ることを確かめる**

Run: `make help | grep -E 'rag-(up|down|destroy)|GPU'`
Expected: 3 つの目標と、`GPU` の説明が出る

- [ ] **Step 8: 手元の Ollama を止め、ポートを空ける**

コンテナは、既定のポート(DB が 5432、Ollama が 11434)を使う。手元の `ollama serve`(11434)や、別の PostgreSQL(5432)が動いていると、衝突する。また、手元の Ollama が GPU のメモリを持っていると、コンテナと奪い合う。

Run: `pgrep -a ollama; ss -ltn | grep -E ':(5432|11434)\b' || echo "5432・11434: 空き"`
Expected: 動いていれば、そのプロセスの番号と、待受が出る。**この会話で起こした `ollama serve`** であることを確かめ、`kill <番号>` で止める。別の用途で動かしている物(別の PostgreSQL、常駐の Ollama など)なら、止めずに、ユーザーに確認する。

再び確かめる。Run: `ss -ltn | grep -E ':(5432|11434)\b' || echo "5432・11434: 空き"`
Expected: `5432・11434: 空き`

- [ ] **Step 9: 起動する(外への通信あり。実行の前に了承を得る)**

Run: `make rag-up GPU=1`
Expected: イメージの取得、コンテナの起動、`pulling bge-m3 ...`(初回)、最後に `RAG is up. db: 127.0.0.1:5432  ollama: 127.0.0.1:11434`

イメージ `ollama/ollama:0.31.1` が無く、取得に失敗したら、`rag/compose.yaml` の該当の行を、実在する版(または `latest`)に改め、その旨を、設計書の「要確認」に追記する。

- [ ] **Step 10: DB の表を確かめる**

Run: `docker compose -f rag/compose.yaml exec -T db psql -U rag -d rag -c '\d knowledge'`
Expected: 列 `id`・`content`・`metadata`・`embedding vector(1024)` と、索引 `knowledge_embedding_idx`(`hnsw`)が出る

- [ ] **Step 11: 埋め込みが 1024 次元で返ることを確かめる**

Run:

```bash
curl -s http://127.0.0.1:11434/api/embed -d '{"model":"bge-m3","input":"テスト"}' \
  | python3 -I -c "import sys,json; print(len(json.load(sys.stdin)['embeddings'][0]))"
```

Expected: `1024`

- [ ] **Step 12: Ollama のコンテナが GPU を使っているか確かめる(ゴール 6)**

Run: `docker compose -f rag/compose.yaml logs ollama | grep -E 'library=(CUDA|cpu)'`
Expected: `library=CUDA` が出る。`library=cpu` なら、GPU が使えておらぬ。その場合は、`docker info | grep -i runtimes` と、`rag/compose.gpu.yaml` を重ねて起動したか(`GPU=1`)を確かめ、原因を調べる。直らぬときは、ユーザーに報告して止まる。

- [ ] **Step 13: 止めて、再び起動しても、データが残ることを確かめる**

Run: `make rag-down && make rag-up GPU=1`
Expected: 2 回目は `model bge-m3: already present`(再取得しない)

**コミットの区切り**(ユーザーが `/git commit` で行う案):
`rag/compose.yaml`・`rag/compose.gpu.yaml`・`rag/sql/init.sql`・`Makefile` →
`feat(rag): make rag-up で、DB と Ollama(bge-m3)を起動する`

---

### Task 2: 共通部品(分割・埋め込み)と単体テスト

設計書の取り込みの 1〜4 の核を担う。DB を使わぬ部分。

**Files:**
- Create: `rag/rag.py`
- Create: `rag/tests/test_rag.py`
- Create: `rag/tests/__init__.py`(空。`unittest discover` が、`rag/tests` を、取り込める物と見なすために要る)

**Interfaces:**
- Consumes: なし(標準ライブラリのみ)
- Produces(`rag/rag.py`):
  - 定数 `DATABASE_URL: str`・`OLLAMA_URL: str`・`EMBED_MODEL: str`・`EMBED_DIM: int`・`MAX_CHUNK: int`・`BATCH: int`
  - `@dataclass(frozen=True) class Chunk: path: str; heading: str; text: str`
  - `doc_type_of(path: str) -> str`
  - `split_markdown(path: str, text: str) -> list[Chunk]`
  - `iter_markdown(docs_dir: str, excludes=()) -> Iterator[tuple[str, str]]`(相対パス、本文)
  - `embed(texts: list[str], model=None, url=None, batch=BATCH) -> list[list[float]]`(失敗は `RuntimeError`)
  - `vec_literal(v) -> str`

- [ ] **Step 1: 失敗するテストを書く**

`rag/tests/test_rag.py`:

```python
import os
import tempfile
import unittest

import rag


class DocTypeTest(unittest.TestCase):
    def test_shared(self):
        self.assertEqual(rag.doc_type_of("decisions/shared/x.md"), "shared")

    def test_adr(self):
        self.assertEqual(rag.doc_type_of("decisions/adr-0001-x.md"), "adr")

    def test_non_adr_in_decisions_is_other(self):
        self.assertEqual(rag.doc_type_of("decisions/notes.md"), "other")

    def test_design(self):
        self.assertEqual(rag.doc_type_of("design/10-x.md"), "design")

    def test_plan_including_archive(self):
        self.assertEqual(rag.doc_type_of("superpowers/plans/archive/2026-09/x.md"), "plan")

    def test_other(self):
        self.assertEqual(rag.doc_type_of("brainstorming-intake.md"), "other")


class SplitMarkdownTest(unittest.TestCase):
    def test_splits_at_headings(self):
        text = "# 題\n前文\n\n## A\naaa\n\n## B\nbbb\n"
        chunks = rag.split_markdown("design/x.md", text)
        self.assertEqual([c.heading for c in chunks], ["題", "A", "B"])
        self.assertTrue(all(c.path == "design/x.md" for c in chunks))
        self.assertTrue(all(c.text.startswith("[design/x.md]\n") for c in chunks))

    def test_h4_does_not_split(self):
        text = "## 節\nあ\n\n#### 小見出し\nい\n"
        chunks = rag.split_markdown("x.md", text)
        self.assertEqual(len(chunks), 1)
        self.assertIn("小見出し", chunks[0].text)

    def test_hash_in_code_fence_is_not_heading(self):
        text = "## 手順\n```bash\n# コメント\nls\n```\n## 次\nzzz\n"
        chunks = rag.split_markdown("x.md", text)
        self.assertEqual([c.heading for c in chunks], ["手順", "次"])
        self.assertIn("# コメント", chunks[0].text)

    def test_empty_document(self):
        self.assertEqual(rag.split_markdown("x.md", ""), [])
        self.assertEqual(rag.split_markdown("x.md", "\n\n  \n"), [])

    def test_no_heading_document(self):
        chunks = rag.split_markdown("x.md", "ただの文\n")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].heading, "")

    def test_crlf_and_bom(self):
        chunks = rag.split_markdown("x.md", "﻿# 題\r\n本文\r\n")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].heading, "題")
        self.assertIn("本文", chunks[0].text)
        self.assertNotIn("\r", chunks[0].text)
        self.assertNotIn("﻿", chunks[0].text)

    def test_long_section_is_cut_by_paragraph(self):
        para = "あ" * 800
        text = "## 長い\n\n" + "\n\n".join([para, para, para])
        chunks = rag.split_markdown("x.md", text)
        self.assertGreaterEqual(len(chunks), 3)
        for c in chunks:
            body = c.text.split("\n", 1)[1]
            self.assertLessEqual(len(body), rag.MAX_CHUNK)

    def test_single_long_paragraph_is_not_split(self):
        chunks = rag.split_markdown("x.md", "## 長い\n" + "い" * 3000)
        self.assertEqual(len(chunks), 1)


class IterMarkdownTest(unittest.TestCase):
    def test_walks_md_only_and_applies_excludes(self):
        with tempfile.TemporaryDirectory() as d:
            for rel in ["a.md", "sub/b.md", "c.txt", "tmpl/t.md"]:
                p = os.path.join(d, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    f.write("x")
            got = [rel for rel, _ in rag.iter_markdown(d, excludes=["tmpl/*"])]
            self.assertEqual(got, ["a.md", "sub/b.md"])


class VecLiteralTest(unittest.TestCase):
    def test_literal(self):
        self.assertEqual(rag.vec_literal([1, 0.5]), "[1.0,0.5]")


class EmbedTest(unittest.TestCase):
    def test_empty_input_needs_no_network(self):
        self.assertEqual(rag.embed([]), [])

    def test_unreachable_ollama_has_hint(self):
        with self.assertRaises(RuntimeError) as cm:
            rag.embed(["x"], url="http://127.0.0.1:9")
        self.assertIn("Ollama に繋がらぬ", str(cm.exception))
        self.assertIn("make rag-up", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `python3 -m unittest discover -s rag/tests -t rag -v`
Expected: `ModuleNotFoundError: No module named 'rag'`(まだ `rag/rag.py` が無い)で失敗

- [ ] **Step 3: 共通部品を書く**

`rag/rag.py`:

```python
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
```

- [ ] **Step 4: テストが通ることを確かめる**

Run: `python3 -m unittest discover -s rag/tests -t rag -v`
Expected: 全てのテストが `ok`(`FAILED` が無い)

**コミットの区切り**(ユーザーが `/git commit` で行う案):
`rag/rag.py`・`rag/tests/test_rag.py` →
`feat(rag): 文書の分割と埋め込みの共通部品を追加する`

---

### Task 3: 取り込み(DB への置き換え)

設計書のゴール 2・4 を担う。

**Files:**
- Modify: `rag/rag.py`(末尾に、`connect`・`current_commit`・`replace_project`・`ingest` を追加)
- Create: `rag/ingest.py`
- Create: `rag/requirements.txt`
- Create: `rag/tests/test_db.py`
- Modify: `Makefile`(`rag-ingest` と、`venv` の用意を追加)

**Interfaces:**
- Consumes: Task 1 の DB(表あり)、Task 2 の `Chunk`・`split_markdown`・`iter_markdown`・`embed`・`vec_literal`・`doc_type_of`・`EMBED_DIM`・`EMBED_MODEL`・`DATABASE_URL`
- Produces(`rag/rag.py`):
  - `connect(url=None)`(psycopg の接続。失敗は `RuntimeError`)
  - `current_commit(path=".") -> str`
  - `replace_project(conn, project: str, rows: list[tuple[str, dict, list[float]]]) -> None`
  - `ingest(conn, docs_dir: str, project: str, excludes=(), commit=None, embed_fn=None) -> dict`(`{"files": int, "chunks": int, "by_doc_type": dict[str, int]}`)
  - `rag/ingest.py` のコマンド、`make rag-ingest`、`make rag-venv`(`rag/.venv` を作る。印 `rag/.venv/.ready` に、作った場所の絶対パスを記し、場所が違えば作り直す)

- [ ] **Step 1: 依存を書く**

`rag/requirements.txt`:

```
psycopg[binary]>=3.2
```

- [ ] **Step 2: Makefile に、`rag-ingest` と、`venv` の用意を足す**

`Makefile` の `.PHONY: rag-up rag-down rag-destroy` の行を、次に改める。

```make
.PHONY: rag-up rag-down rag-destroy rag-venv rag-ingest
```

そして、`rag-destroy` の定義の後(ファイルの末尾)に、空行を一つ置いて、追加する。

```make

# The venv is tied to its location. A venv copied by `make new` carries the old location in its marker,
# so it is rebuilt here (every new project builds its own venv).
rag-venv:
	@if [ ! -f $(RAG_DIR)/.venv/.ready ] \
	  || [ "$$(cat $(RAG_DIR)/.venv/.ready)" != "$(abspath $(RAG_DIR))" ] \
	  || [ $(RAG_DIR)/requirements.txt -nt $(RAG_DIR)/.venv/.ready ]; then \
	  echo "setting up $(RAG_DIR)/.venv (python venv + psycopg)"; \
	  rm -rf $(RAG_DIR)/.venv; \
	  python3 -m venv $(RAG_DIR)/.venv && \
	  $(RAG_DIR)/.venv/bin/pip install -q -r $(RAG_DIR)/requirements.txt && \
	  echo "$(abspath $(RAG_DIR))" > $(RAG_DIR)/.venv/.ready; \
	fi

rag-ingest: rag-venv ## Ingest Markdown into the DB (PROJECT=name DOCS=dir)
	@$(RAG_PY) $(RAG_DIR)/ingest.py --docs "$(DOCS)" --project "$(RAG_PROJECT)" $(foreach e,$(EXCLUDE),--exclude "$(e)")
```

- [ ] **Step 3: 依存を導入する(外への通信あり。実行の前に了承を得る)**

Run: `make -n rag-ingest | head -3`(通信なしで、手順を確かめる)
Expected: `python3 -m venv rag/.venv` と、`pip install` が出る

Run: `make rag-venv`
Expected: `setting up rag/.venv (python venv + psycopg)` と出て、`rag/.venv` が出来、`psycopg` が入る。2 回目の `make rag-venv` は、何も出さぬ(作り直さぬ)。次で確かめる。

Run: `rag/.venv/bin/python -c "import psycopg; print(psycopg.__version__)"`
Expected: 版の番号(3.2 以上)が出る

複製された `venv` を、作り直すことを確かめる(`make new` が複製した `rag/.venv` を想定。再び、外への通信がある)。

Run:

```bash
echo "/somewhere/else/rag" > rag/.venv/.ready
make rag-venv
cat rag/.venv/.ready
echo "$(cd rag && pwd)"
```

Expected: `setting up rag/.venv ...` と出て作り直され、最後の 2 行(印の内容と、`rag` の絶対パス)が、同じになる

- [ ] **Step 4: 失敗する DB のテストを書く**

`rag/tests/test_db.py`:

```python
import os
import tempfile
import unittest

import rag


def _conn_or_skip():
    try:
        import psycopg
    except ImportError as e:
        raise unittest.SkipTest(f"psycopg が無い(make rag-venv が要る): {e}")
    try:
        conn = rag.connect()
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM knowledge LIMIT 1")
        conn.rollback()
        return conn
    except (RuntimeError, psycopg.Error) as e:  # DB に繋がらぬ、または表が無い
        raise unittest.SkipTest(f"DB が使えぬ(make rag-up が要る): {e}")


def fake_embed(texts):
    """決まった次元のベクトル。Ollama を使わずに、取り込みの流れを確かめる。"""
    return [[0.01 * (len(t) % 7 + 1) + i * 1e-4 for i in range(rag.EMBED_DIM)] for t in texts]


def write_docs(d, files):
    for rel, text in files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)


class IngestTest(unittest.TestCase):
    def setUp(self):
        self.conn = _conn_or_skip()

    def tearDown(self):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge WHERE metadata->>'project' LIKE 'unittest-%'")
        self.conn.commit()
        self.conn.close()

    def count(self, project):
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM knowledge WHERE metadata->>'project' = %s", (project,))
            n = cur.fetchone()[0]
        self.conn.rollback()
        return n

    def test_ingest_writes_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            write_docs(d, {"decisions/adr-0001-x.md": "# 題\n本文\n", "design/y.md": "# 設計\n本文\n"})
            stats = rag.ingest(self.conn, d, "unittest-a", commit="abc1234", embed_fn=fake_embed)
        self.assertEqual(stats["files"], 2)
        self.assertEqual(stats["chunks"], 2)
        self.assertEqual(stats["by_doc_type"], {"adr": 1, "design": 1})
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT metadata FROM knowledge WHERE metadata->>'project' = 'unittest-a' "
                "AND metadata->>'path' = 'decisions/adr-0001-x.md'"
            )
            meta = cur.fetchone()[0]
        self.conn.rollback()
        self.assertEqual(meta["heading"], "題")
        self.assertEqual(meta["doc_type"], "adr")
        self.assertEqual(meta["commit"], "abc1234")
        self.assertEqual(meta["model"], rag.EMBED_MODEL)

    def test_ingest_twice_keeps_count(self):
        with tempfile.TemporaryDirectory() as d:
            write_docs(d, {"a.md": "# A\n本文\n", "b.md": "# B\n本文\n"})
            rag.ingest(self.conn, d, "unittest-b", embed_fn=fake_embed)
            first = self.count("unittest-b")
            rag.ingest(self.conn, d, "unittest-b", embed_fn=fake_embed)
            second = self.count("unittest-b")
        self.assertEqual(first, 2)
        self.assertEqual(second, first)

    def test_other_project_is_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            write_docs(d, {"a.md": "# A\n本文\n"})
            rag.ingest(self.conn, d, "unittest-c1", embed_fn=fake_embed)
            rag.ingest(self.conn, d, "unittest-c2", embed_fn=fake_embed)
            rag.ingest(self.conn, d, "unittest-c1", embed_fn=fake_embed)
        self.assertEqual(self.count("unittest-c1"), 1)
        self.assertEqual(self.count("unittest-c2"), 1)

    def test_failure_keeps_old_rows(self):
        with tempfile.TemporaryDirectory() as d:
            write_docs(d, {"a.md": "# A\n本文\n"})
            rag.ingest(self.conn, d, "unittest-d", embed_fn=fake_embed)
        before = self.count("unittest-d")
        bad_rows = [("x", {"project": "unittest-d"}, [0.1] * 3)]  # 次元が違う: 挿入で失敗する
        with self.assertRaises(Exception):
            rag.replace_project(self.conn, "unittest-d", bad_rows)
        self.conn.rollback()
        self.assertEqual(self.count("unittest-d"), before)

    def test_wrong_dimension_from_ollama_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            write_docs(d, {"a.md": "# A\n本文\n"})
            with self.assertRaises(RuntimeError) as cm:
                rag.ingest(self.conn, d, "unittest-e", embed_fn=lambda ts: [[0.1] * 3 for _ in ts])
        self.assertIn("次元", str(cm.exception))

    def test_no_markdown_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                rag.ingest(self.conn, d, "unittest-f", embed_fn=fake_embed)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5: テストが失敗することを確かめる**

Run: `rag/.venv/bin/python -m unittest discover -s rag/tests -t rag -p 'test_db.py' -v`
Expected: `AttributeError: module 'rag' has no attribute 'connect'`(などの失敗。`ingest` が未実装)。DB が止まっていれば、`skipped` になる。その場合は、`make rag-up GPU=1` で起こしてから、やり直す。

- [ ] **Step 6: 取り込みの部品を、`rag/rag.py` の末尾に足す**

```python


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
```

- [ ] **Step 7: 取り込みのコマンドを書く**

`rag/ingest.py`:

```python
#!/usr/bin/env python3
"""docs/ の Markdown を、DB に取り込む(同じ project の行は、置き換える)。"""
import argparse
import os
import sys
import time

import rag


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", default="docs", help="Markdown の場所(既定: docs)")
    ap.add_argument("--project", default=os.path.basename(os.getcwd()),
                    help="DB に記すプロジェクト名(既定: このディレクトリの名)")
    ap.add_argument("--exclude", action="append", default=[],
                    help="除くパス(docs からの相対。fnmatch)。複数可")
    a = ap.parse_args(argv)
    started = time.time()
    try:
        with rag.connect() as conn:
            stats = rag.ingest(conn, a.docs, a.project, a.exclude)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"project={a.project} files={stats['files']} chunks={stats['chunks']} "
          f"time={time.time() - started:.1f}s")
    for k, v in sorted(stats["by_doc_type"].items()):
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8: テストが通ることを確かめる**

Run: `rag/.venv/bin/python -m unittest discover -s rag/tests -t rag -v`
Expected: `test_rag.py` と `test_db.py` の全てが `ok`(`skipped` や `FAILED` が無い。DB が止まっていれば、`make rag-up GPU=1` で起こす)

- [ ] **Step 9: 実際の `docs/` を、取り込む**

Run: `make rag-ingest`
Expected: `project=bc.aidd-template-claude files=<数> chunks=<数> time=<秒>s` と、`doc_type` ごとの件数。エラーなし。

- [ ] **Step 10: 繰り返しても件数が変わらぬことを確かめる(ゴール 4)**

Run:

```bash
make rag-ingest | head -1
docker compose -f rag/compose.yaml exec -T db psql -U rag -d rag -t -c "SELECT count(*) FROM knowledge"
make rag-ingest | head -1
docker compose -f rag/compose.yaml exec -T db psql -U rag -d rag -t -c "SELECT count(*) FROM knowledge"
```

Expected: 2 回の `chunks=` と、2 回の件数が、全て同じ

- [ ] **Step 11: Ollama が止まっているときの表示を確かめる(Review Focus 3)**

Run: `OLLAMA_URL=http://127.0.0.1:9 make rag-ingest`
Expected: `Error: Ollama に繋がらぬ(http://127.0.0.1:9): ... 。`make rag-up` を実行したか`(スタックトレースなし)。続けて、`SELECT count(*)` が、直前と同じ(既存の行が、消えておらぬ)

- [ ] **Step 12: DB の中身を見る目標 `rag-status` を足す**

利用者が、データが出来ておるかを、手軽に確かめるための目標(「利用者の確認の手順」の B で使う)。`Makefile` の末尾に、空行を一つ置いて、追加する。

```make

.PHONY: rag-status
rag-status: ## Show what is in the DB (files and chunks per project and type)
	@$(RAG_COMPOSE) exec -T db psql -U rag -d rag \
	  -c "SELECT metadata->>'project' AS project, metadata->>'doc_type' AS doc_type, count(DISTINCT metadata->>'path') AS files, count(*) AS chunks, max(metadata->>'commit') AS commit, max(metadata->>'model') AS model FROM knowledge GROUP BY 1, 2 ORDER BY 1, 2" \
	  -c "SELECT count(*) AS total_chunks FROM knowledge"
```

Run: `make rag-status`
Expected: プロジェクト・種類ごとの表と、`total_chunks` が出る。他のプロジェクトが無ければ、`total_chunks` は、直前の `make rag-ingest` の `chunks=` の値と一致する

**コミットの区切り**(ユーザーが `/git commit` で行う案):
`rag/rag.py`・`rag/ingest.py`・`rag/requirements.txt`・`rag/tests/test_db.py`・`Makefile` →
`feat(rag): docs/ を DB に取り込む(同じ project は置き換える)。rag-status で、件数を見る`

---

### Task 4: 検索

設計書のゴール 5 を担う。

**Files:**
- Modify: `rag/rag.py`(末尾に、`Hit`・`search`・`format_hits` を追加)
- Create: `rag/search.py`
- Modify: `rag/tests/test_db.py`(検索のテストを追加)
- Modify: `Makefile`(`rag-search` を追加)

**Interfaces:**
- Consumes: Task 3 の `connect`・`ingest`・`vec_literal`・`embed`・DB(`knowledge` 表)
- Produces:
  - `@dataclass(frozen=True) class Hit: score: float; project: str; path: str; heading: str; doc_type: str; content: str`
  - `search(conn, question: str, project=None, doc_type=None, k=5, embed_fn=None) -> list[Hit]`(空の問いは `ValueError`)
  - `format_hits(hits: list[Hit], full=False) -> str`
  - `rag/search.py` のコマンド、`make rag-search Q="..." [K=5] [PROJECT=名前] [TYPE=種類]`

- [ ] **Step 1: 失敗するテストを書く**

`rag/tests/test_db.py` の末尾(`if __name__ == "__main__":` の**前**)に、追加する。

```python
def axis_embed(texts):
    """語で、軸を決める(猫=0、犬=1、それ以外=2)。順位が、予想できる、決まったベクトル。"""
    out = []
    for t in texts:
        v = [0.0] * rag.EMBED_DIM
        v[0 if "猫" in t else 1 if "犬" in t else 2] = 1.0
        out.append(v)
    return out


class SearchTest(unittest.TestCase):
    def setUp(self):
        self.conn = _conn_or_skip()
        self.d = tempfile.TemporaryDirectory()
        write_docs(self.d.name, {
            "neko.md": "# 猫\n猫の話です。\n",
            "inu.md": "# 犬\n犬の話です。\n",
            "tori.md": "# 鳥\n鳥の話です。\n",
        })
        rag.ingest(self.conn, self.d.name, "unittest-s1", embed_fn=axis_embed)
        rag.ingest(self.conn, self.d.name, "unittest-s2", embed_fn=axis_embed)

    def tearDown(self):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge WHERE metadata->>'project' LIKE 'unittest-%'")
        self.conn.commit()
        self.conn.close()
        self.d.cleanup()

    def test_nearest_is_first_with_source(self):
        hits = rag.search(self.conn, "猫について", k=3, embed_fn=axis_embed)
        self.assertEqual(hits[0].path, "neko.md")
        self.assertEqual(hits[0].heading, "猫")
        self.assertAlmostEqual(hits[0].score, 1.0, places=3)
        self.assertGreaterEqual(hits[0].score, hits[-1].score)

    def test_k_limits_results(self):
        self.assertEqual(len(rag.search(self.conn, "猫", k=2, embed_fn=axis_embed)), 2)

    def test_project_filter(self):
        hits = rag.search(self.conn, "猫", project="unittest-s2", k=10, embed_fn=axis_embed)
        self.assertTrue(hits)
        self.assertTrue(all(h.project == "unittest-s2" for h in hits))

    def test_doc_type_filter(self):
        hits = rag.search(self.conn, "猫", doc_type="adr", k=10, embed_fn=axis_embed)
        self.assertEqual(hits, [])  # 取り込んだ物は、全て other

    def test_empty_question_is_rejected(self):
        with self.assertRaises(ValueError):
            rag.search(self.conn, "  ", embed_fn=axis_embed)

    def test_format_hits(self):
        hits = rag.search(self.conn, "猫", k=1, embed_fn=axis_embed)
        text = rag.format_hits(hits)
        self.assertIn("neko.md", text)
        self.assertIn("# 猫", text)
        self.assertEqual(rag.format_hits([]), "(該当なし)")
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `rag/.venv/bin/python -m unittest discover -s rag/tests -t rag -p 'test_db.py' -k SearchTest -v`
Expected: `AttributeError: module 'rag' has no attribute 'search'` で失敗

- [ ] **Step 3: 検索を、`rag/rag.py` の末尾に足す**

```python


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
```

- [ ] **Step 4: 検索のコマンドを書く**

`rag/search.py`:

```python
#!/usr/bin/env python3
"""問いに近い断片を、DB から探して返す。"""
import argparse
import json
import sys
from dataclasses import asdict

import rag


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("question", help="問い")
    ap.add_argument("--project", help="このプロジェクトの断片だけを探す")
    ap.add_argument("--doc-type", help="adr / design / plan / shared / other のみ")
    ap.add_argument("--k", type=int, default=5, help="返す件数(既定 5)")
    ap.add_argument("--json", action="store_true", help="JSON で出す")
    ap.add_argument("--full", action="store_true", help="本文の全体を出す")
    a = ap.parse_args(argv)
    try:
        with rag.connect() as conn:
            hits = rag.search(conn, a.question, a.project, a.doc_type, a.k)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps([asdict(h) for h in hits], ensure_ascii=False, indent=2))
    else:
        print(rag.format_hits(hits, full=a.full))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Makefile に、`rag-search` を足す**

`.PHONY: rag-up rag-down rag-destroy rag-venv rag-ingest` の行を、次に改める。

```make
.PHONY: rag-up rag-down rag-destroy rag-venv rag-ingest rag-search
```

`rag-ingest` の定義の後(ファイルの末尾)に、空行を一つ置いて、追加する。

```make

rag-search: rag-venv ## Search the DB (Q="question" [K=5] [PROJECT=name] [TYPE=adr|design|plan|shared|other])
	@test -n "$$Q" || { echo 'Error: Q is required. Usage: make rag-search Q="question"'; exit 1; }
	@$(RAG_PY) $(RAG_DIR)/search.py "$$Q" --k "$(K)" $(RAG_ONLY) $(if $(TYPE),--doc-type "$(TYPE)")
```

(`Q` は、環境変数として渡るため、`"$$Q"` で参照する。問いの中の記号を、シェルが解釈せぬようにするため。)

- [ ] **Step 6: テストが通ることを確かめる**

Run: `rag/.venv/bin/python -m unittest discover -s rag/tests -t rag -v`
Expected: 全てが `ok`

- [ ] **Step 7: 実際に検索する(ゴール 5)**

Run: `make rag-search Q="共通の決定を、なぜ shared に置くのか"`
Expected: 近さ(`score`)、種類、`プロジェクト:パス`、見出し、本文の冒頭が、5 件出る。取り込んだ `docs/` に関係する断片が、上位に出る。

Run: `make rag-search Q='引用符 "と $HOME と `date` を含む問い'`
Expected: エラーにならず、結果(または `(該当なし)` でなく、5 件)が出る(記号が、シェルに解釈されておらぬこと)

Run: `make rag-search` (`Q` なし)
Expected: `Error: Q is required. ...` で止まる

**コミットの区切り**(ユーザーが `/git commit` で行う案):
`rag/rag.py`・`rag/search.py`・`rag/tests/test_db.py`・`Makefile` →
`feat(rag): 問いに近い断片を、出所つきで返す検索を追加する`

---

### Task 5: 文書の取得・一覧・件数の丸め(MCP のツールの中身)

設計書の MCP サーバの、`get_document`・`list_sources` と、`search_knowledge` の件数の丸めの、中身を担う。DB と標準ライブラリのみで書き、MCP の SDK には依らぬ(単体で確かめるため)。

**Files:**
- Modify: `rag/rag.py`(末尾に、`clamp_k`・`get_document`・`list_sources`・`format_sources` を追加)
- Modify: `rag/tests/test_db.py`(文書の取得・一覧のテストを追加)
- Create: `rag/tests/test_tools.py`(DB を使わぬテスト)

**Interfaces:**
- Consumes: Task 2〜4 の `ingest`・`search`・`connect`・`vec_literal`・`format_hits`
- Produces(`rag/rag.py`):
  - `clamp_k(k, lo=1, hi=20) -> int`(数でなければ 5)
  - `get_document(conn, path: str, project: str | None = None) -> str | None`(無ければ `None`。複数のプロジェクトに在り、`project` が無ければ `ValueError`)
  - `list_sources(conn, doc_type: str | None = None) -> list[dict]`(キー: `project`・`doc_type`・`files`・`chunks`・`commit`・`model`)
  - `format_sources(rows: list[dict]) -> str`

- [ ] **Step 1: 失敗するテストを書く(DB を使わぬ分)**

`rag/tests/test_tools.py`:

```python
import unittest

import rag


class ClampKTest(unittest.TestCase):
    def test_within_range(self):
        self.assertEqual(rag.clamp_k(5), 5)

    def test_below_is_raised(self):
        self.assertEqual(rag.clamp_k(0), 1)
        self.assertEqual(rag.clamp_k(-3), 1)

    def test_above_is_cut(self):
        self.assertEqual(rag.clamp_k(1000), 20)

    def test_not_a_number_uses_default(self):
        self.assertEqual(rag.clamp_k(None), 5)
        self.assertEqual(rag.clamp_k("x"), 5)


class FormatSourcesTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(rag.format_sources([]), "(取り込み済みの文書なし)")

    def test_rows(self):
        rows = [{"project": "p", "doc_type": "adr", "files": 2, "chunks": 5,
                 "commit": "abc1234", "model": "bge-m3"}]
        text = rag.format_sources(rows)
        for word in ["p", "adr", "2", "5", "abc1234", "bge-m3"]:
            self.assertIn(word, text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 失敗するテストを書く(DB を使う分)**

`rag/tests/test_db.py` の末尾(`if __name__ == "__main__":` の**前**)に、追加する。

```python
class DocumentToolsTest(unittest.TestCase):
    def setUp(self):
        self.conn = _conn_or_skip()
        self.d = tempfile.TemporaryDirectory()
        write_docs(self.d.name, {
            "design/a.md": "# 題\n前文\n\n## 一\naaa\n\n## 二\nbbb\n",
            "decisions/adr-0001-x.md": "# ADR\n本文\n",
        })
        rag.ingest(self.conn, self.d.name, "unittest-g1", commit="c1", embed_fn=fake_embed)
        rag.ingest(self.conn, self.d.name, "unittest-g2", commit="c2", embed_fn=fake_embed)

    def tearDown(self):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge WHERE metadata->>'project' LIKE 'unittest-%'")
        self.conn.commit()
        self.conn.close()
        self.d.cleanup()

    def test_get_document_joins_chunks_in_order(self):
        text = rag.get_document(self.conn, "design/a.md", project="unittest-g1")
        self.assertIn("前文", text)
        self.assertLess(text.index("aaa"), text.index("bbb"))
        self.assertNotIn("[design/a.md]", text)

    def test_get_document_unknown_path_is_none(self):
        self.assertIsNone(rag.get_document(self.conn, "no/such.md", project="unittest-g1"))

    def test_get_document_ambiguous_project_is_rejected(self):
        with self.assertRaises(ValueError) as cm:
            rag.get_document(self.conn, "design/a.md")
        self.assertIn("unittest-g1", str(cm.exception))

    def test_list_sources(self):
        rows = [r for r in rag.list_sources(self.conn) if r["project"] == "unittest-g1"]
        by_type = {r["doc_type"]: r for r in rows}
        self.assertEqual(by_type["design"]["files"], 1)
        self.assertEqual(by_type["design"]["chunks"], 3)
        self.assertEqual(by_type["adr"]["commit"], "c1")
        self.assertEqual(by_type["adr"]["model"], rag.EMBED_MODEL)

    def test_list_sources_filter(self):
        rows = rag.list_sources(self.conn, doc_type="adr")
        self.assertTrue(rows)
        self.assertTrue(all(r["doc_type"] == "adr" for r in rows))
```

- [ ] **Step 3: テストが失敗することを確かめる**

Run: `rag/.venv/bin/python -m unittest discover -s rag/tests -t rag -p 'test_tools.py' -v`
Expected: `AttributeError: module 'rag' has no attribute 'clamp_k'` などで失敗

- [ ] **Step 4: 実装を、`rag/rag.py` の末尾に足す**

```python


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
```

- [ ] **Step 5: テストが通ることを確かめる**

Run: `rag/.venv/bin/python -m unittest discover -s rag/tests -t rag -v`
Expected: 全てが `ok`(DB が動いていれば、`DocumentToolsTest` も通る。止まっていれば、`skipped`。その場合は、`make rag-up GPU=1` で起こしてから、やり直す)

**コミットの区切り**(ユーザーが `/git commit` で行う案):
`rag/rag.py`・`rag/tests/test_db.py`・`rag/tests/test_tools.py` →
`feat(rag): 文書の取得・一覧・件数の丸めを追加する`

---

### Task 6: MCP サーバ(待ち受け)

設計書のゴール 7・8 を担う。

**Files:**
- Create: `rag/requirements-mcp.txt`
- Create: `rag/Dockerfile`
- Create: `rag/.dockerignore`
- Create: `rag/mcp_server.py`
- Create: `rag/mcp_check.py`
- Modify: `rag/compose.yaml`(`mcp` サービスを追加)
- Modify: `Makefile`(`rag-up` を、イメージを作る形に改め、`rag-mcp-check` を追加)
- Modify: `.mcp.json`(`rag` サーバの接続先を追加)

**Interfaces:**
- Consumes: Task 5 の `rag.search`・`rag.get_document`・`rag.list_sources`・`rag.format_hits`・`rag.format_sources`・`rag.clamp_k`、Task 1 の `compose.yaml`
- Produces:
  - コンテナ `mcp`(`127.0.0.1:8000`、URL `http://127.0.0.1:8000/mcp`)。ツール `search_knowledge(query, doc_type=None, project=None, k=5)`・`get_document(path, project=None)`・`list_sources(doc_type=None)`(いずれも、文字列を返す。読み取り専用)
  - `make rag-mcp-check`(手順を、通しで確かめる)

- [ ] **Step 1: MCP の SDK の API を、実物で確かめる(外への通信あり。実行の前に了承を得る)**

設計書の「確かめていない点」に挙げた、SDK の書き方を、書く前に、確かめる。一時領域に、使い捨ての `venv` を作る。

Run:

```bash
SPIKE=/tmp/claude-1000/mcp-spike
python3 -m venv $SPIKE && $SPIKE/bin/pip install -q 'mcp>=1.9,<2' && $SPIKE/bin/python - <<'EOF'
import inspect
from importlib.metadata import version
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import Settings
print("mcp", version("mcp"))
print("Settings:", sorted(Settings.model_fields))
print("run:", inspect.signature(FastMCP.run))
EOF
```

Expected: `Settings` の項目に、`host`・`port`・`stateless_http`・`json_response` が含まれ、`run` が `transport` を取る。

食い違えば(項目が無い、名前が違う)、Step 2 の `mcp_server.py` の、`FastMCP(...)` の引数と `mcp.run(...)` の書き方を、実物に合わせて直し、設計書の「確かめていない点」に、確かめた結果(版と、正しい書き方)を書き足す。確かめ終えたら、`rm -rf /tmp/claude-1000/mcp-spike` で消す。

- [ ] **Step 2: イメージと、サーバの定義を書く**

`rag/requirements-mcp.txt`:

```
mcp>=1.9,<2
```

`rag/Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements-mcp.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-mcp.txt
COPY rag.py mcp_server.py ./
EXPOSE 8000
CMD ["python", "mcp_server.py"]
```

`rag/.dockerignore`(`.venv` などを、作成の文脈に含めぬため。大きい):

```
.venv
tests
__pycache__
*.pyc
```

`rag/mcp_server.py`:

```python
"""RAG の MCP サーバ(待ち受け)。rag.py の関数を、読み取り専用のツールとして包む薄い殻。

設計書: docs/design/rag-minimal-pipeline.md
"""
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

import rag

mcp = FastMCP(
    "rag",
    host=os.environ.get("MCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("MCP_PORT", "8000")),
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
def search_knowledge(
    query: str,
    doc_type: Optional[str] = None,
    project: Optional[str] = None,
    k: int = 5,
) -> str:
    """設計の判断の前に、関連する過去の設計書・追記・ADR を探し、近い断片を、出所つきで返す。

    使う場面: 設計の対話で詰めるとき。依頼内容(仕様の変更・不具合・仕様の漏れ)を判断するとき。Task を作るとき。
    使わぬ場面: コードの細部の確認。git の最新の状態の確認。
    返す物は、参考である。設計書・計画書への追記や、仕様の変更は、人が承認する。

    Args:
        query: 問い。日本語の文でよい(例: 「このテーブルの列を、なぜ、この型にしたのか」)。
        doc_type: adr / design / plan / shared / other のいずれかで絞る(任意)。
        project: プロジェクト名で絞る(任意)。
        k: 返す件数(1〜20。既定 5)。
    """
    with rag.connect() as conn:
        hits = rag.search(conn, query, project, doc_type, rag.clamp_k(k))
    return rag.format_hits(hits, full=True)


@mcp.tool()
def get_document(path: str, project: Optional[str] = None) -> str:
    """断片で足りぬとき、文書の全文を取る。

    path は、search_knowledge の結果に出る、docs からの相対パス。
    同じ path が、複数のプロジェクトに在るときは、project を指定する。
    """
    with rag.connect() as conn:
        text = rag.get_document(conn, path, project)
    return text if text is not None else f"(見つからぬ: {path})"


@mcp.tool()
def list_sources(doc_type: Optional[str] = None) -> str:
    """取り込み済みの、プロジェクトと文書の種類ごとの、文書数・断片数・取り込み時のコミット・モデルを返す。

    どの知識が、どれほど古いかを、確かめるときに使う。
    """
    with rag.connect() as conn:
        return rag.format_sources(rag.list_sources(conn, doc_type))


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

`rag/mcp_check.py`:

```python
#!/usr/bin/env python3
"""MCP サーバの手順を、通しで確かめる: 初期化 → ツールの一覧 → 検索の呼び出し。標準ライブラリのみ。"""
import argparse
import json
import sys
import urllib.error
import urllib.request

HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
EXPECTED_TOOLS = ["get_document", "list_sources", "search_knowledge"]


def rpc(url, method, params=None, id_=None):
    """JSON-RPC を、1 回送る。id_ が無ければ、通知(応答は読まず、None を返す)。"""
    body = {"jsonrpc": "2.0", "method": method}
    if id_ is not None:
        body["id"] = id_
    if params is not None:
        body["params"] = params
    req = urllib.request.Request(url, json.dumps(body).encode(), HEADERS)
    with urllib.request.urlopen(req, timeout=120) as res:
        ctype = res.headers.get("Content-Type", "")
        raw = res.read().decode("utf-8")
    if id_ is None or not raw.strip():
        return None
    if "text/event-stream" in ctype:
        for line in raw.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        raise RuntimeError("応答に data の行が無い")
    return json.loads(raw)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    ap.add_argument("--query", default="設計の判断の理由を、どこに残すか")
    a = ap.parse_args(argv)
    try:
        init = rpc(a.url, "initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "rag-mcp-check", "version": "0"},
        }, 1)
        print("initialize:", init["result"]["serverInfo"])
        rpc(a.url, "notifications/initialized")
        tools = rpc(a.url, "tools/list", {}, 2)["result"]["tools"]
        names = sorted(t["name"] for t in tools)
        print("tools:", names)
        if names != EXPECTED_TOOLS:
            raise RuntimeError(f"ツールが違う: {names}(期待 {EXPECTED_TOOLS})")
        res = rpc(a.url, "tools/call",
                  {"name": "search_knowledge", "arguments": {"query": a.query, "k": 3}}, 3)["result"]
        text = "".join(c.get("text", "") for c in res.get("content", []))
        print("search_knowledge:", "ERROR" if res.get("isError") else "ok")
        print(text[:600])
        if res.get("isError"):
            raise RuntimeError("検索の呼び出しが、エラーを返した")
    except (urllib.error.URLError, ConnectionError, RuntimeError, KeyError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: `mcp` サービスを、`compose.yaml` に足す**

`rag/compose.yaml` の、トップレベルの `volumes:` の行の**直前**(`ollama` の `healthcheck` の後)に、空行を一つ置いて、挿入する。

```yaml

  mcp:
    build: .
    environment:
      RAG_DATABASE_URL: postgresql://rag:rag@db:5432/rag
      OLLAMA_URL: http://ollama:11434
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      db:
        condition: service_healthy
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import socket; socket.create_connection(('127.0.0.1', 8000), 2)"]
      interval: 3s
      timeout: 5s
      retries: 20
```

Run: `docker compose -f rag/compose.yaml config -q && docker compose -f rag/compose.yaml -f rag/compose.gpu.yaml config -q && echo OK`
Expected: `OK`

- [ ] **Step 4: Makefile を改める**

`Makefile` の `rag-up` の、次の行を、

```make
	@$(RAG_COMPOSE) up -d --wait
```

次に改める(MCP サーバのイメージを、作りつつ起動する。変更が無ければ、作成は、キャッシュで速い)。

```make
	@$(RAG_COMPOSE) up -d --build --wait
```

同じく、`rag-up` の最後の行を、

```make
	@echo "RAG is up. db: 127.0.0.1:5432  ollama: 127.0.0.1:11434"
```

次に改める。

```make
	@echo "RAG is up. db: 127.0.0.1:5432  ollama: 127.0.0.1:11434  mcp: http://127.0.0.1:8000/mcp"
```

ファイルの末尾に、空行を一つ置いて、追加する。

```make

.PHONY: rag-mcp-check
rag-mcp-check: ## Check the MCP server end to end (initialize, tools/list, a search call)
	@python3 $(RAG_DIR)/mcp_check.py
```

(`.PHONY` を、目標の隣に別に宣言する。これまでの `.PHONY` の行を、書き換えずに済む。)

Run: `make help | grep -E 'rag-mcp-check|rag-up'`
Expected: 2 つの目標が出る

- [ ] **Step 5: ポートが空いていることを確かめる**

Run: `ss -ltn | grep -E ':(5432|11434|8000)\b' || echo "5432・11434・8000: 空き"`
Expected: `5432・11434・8000: 空き`(動いている物があれば、この会話で起こした物か確かめ、止める。別の物なら、ユーザーに確認する。コンテナが、すでに起動していれば、それらは、`rag` のコンテナゆえ、そのままでよい)

- [ ] **Step 6: 起動する(外への通信あり。実行の前に了承を得る)**

ベースのイメージ(`python:3.12-slim`)の取得と、`pip` による依存の導入が、イメージの作成で行われる。

Run: `make rag-up GPU=1`
Expected: `mcp` のイメージが作られ、三つのコンテナが起動し、最後に `RAG is up. db: ... mcp: http://127.0.0.1:8000/mcp` が出る

Run: `docker compose -f rag/compose.yaml ps`
Expected: `db`・`ollama`・`mcp` が、いずれも `healthy`

- [ ] **Step 7: MCP の手順を、通しで確かめる(ゴール 7)**

DB に、検索の対象が無ければ、取り込んでおく。

Run: `make rag-ingest`
Expected: 取り込みが、エラーなく終わる

Run: `make rag-mcp-check`
Expected: `initialize: {'name': 'rag', ...}`、`tools: ['get_document', 'list_sources', 'search_knowledge']`、`search_knowledge: ok` と、検索の結果の冒頭が出る。終了コード 0

通らなければ、`docker compose -f rag/compose.yaml logs mcp` を読む。「Invalid Host header」の類が出たら、待ち受けの Host の検査(DNS 再束縛の対策)が、`127.0.0.1:8000` 宛てを拒んでおる。SDK の設定(許可する Host の指定)を、実物で確かめて直し、設計書の「確かめていない点」に、結果を書く。

- [ ] **Step 8: 他の二つのツールと、失敗の様子を確かめる**

Run:

```bash
python3 - <<'EOF'
import json, sys
sys.path.insert(0, "rag")
import mcp_check as m
url = "http://127.0.0.1:8000/mcp"
m.rpc(url, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}, 1)
for name, args in [("list_sources", {}), ("get_document", {"path": "no/such.md"}), ("search_knowledge", {"query": "x", "k": 1000})]:
    r = m.rpc(url, "tools/call", {"name": name, "arguments": args}, 9)["result"]
    print(name, "isError=", r.get("isError"), "|", "".join(c.get("text", "") for c in r["content"])[:100].replace("\n", " "))
EOF
```

Expected: `list_sources` は、取り込み済みの一覧。`get_document` は `(見つからぬ: no/such.md)`。`search_knowledge`(`k=1000`)は、エラーにならず、20 件以下で返る

Ollama が止まっているときの表示を確かめる(Review Focus の、停止時の案内)。

Run: `docker compose -f rag/compose.yaml stop ollama && make rag-mcp-check; echo "exit=$?"; docker compose -f rag/compose.yaml start ollama`
Expected: `search_knowledge: ERROR` と、本文に `Ollama に繋がらぬ` が出て、`exit=1`。サーバ自体は、落ちておらぬ(`docker compose -f rag/compose.yaml ps` で `mcp` が動いておる)。最後の `start` で、`ollama` を戻す

- [ ] **Step 9: 待ち受けが、`127.0.0.1` のみであることを確かめる**

Run: `ss -ltn | grep -E ':8000\b'`
Expected: `127.0.0.1:8000` のみ(`0.0.0.0:8000` ではない)

- [ ] **Step 10: `.mcp.json` に、接続先を書く**

`.mcp.json` の中身を、次に改める(現在は、`{"mcpServers": {}}` の形)。

```json
{
  "mcpServers": {
    "rag": { "type": "http", "url": "http://127.0.0.1:8000/mcp" }
  }
}
```

Run: `python3 -m json.tool .mcp.json >/dev/null && echo "JSON: OK"`
Expected: `JSON: OK`

- [ ] **Step 11: Claude Code から見えることを確かめる(ゴール 8。利用者が行う)**

実行者は、この手順を、代わりに行えぬ(Claude Code の、再起動と、MCP サーバの承認が要る)。利用者に、次を依頼する。

1. Claude Code を、再起動する(または、このプロジェクトで、開き直す)。
2. `.mcp.json` の `rag` サーバを、承認する(初回の求めに従う)。
3. `/mcp` で、`rag` が接続済みで、三つのツール(`search_knowledge`・`get_document`・`list_sources`)が見えることを確かめる。
4. Claude Code に、「`search_knowledge` で、設計の判断の理由を、どこに残すかを、探して」と頼み、結果が返ることを確かめる。

`.mcp.json` の書式(`"type": "http"`)が違い、接続できぬときは、Claude Code の表示と、`claude mcp add --help` で、正しい書式を確かめ、`.mcp.json` と、設計書の「確かめていない点」を直す。

- [ ] **Step 12: 全体のテストを、確かめる**

Run: `make rag-test`
Expected: 全ての単体テストが `ok`

**コミットの区切り**(ユーザーが `/git commit` で行う案):
`rag/requirements-mcp.txt`・`rag/Dockerfile`・`rag/.dockerignore`・`rag/mcp_server.py`・`rag/mcp_check.py`・`rag/compose.yaml`・`Makefile`・`.mcp.json` →
`feat(rag): 待ち受けの MCP サーバを追加する(search_knowledge ほか三つ)`

---

### Task 7: 質問集の評価(ゴール 3 の確認)

設計書のゴール 3 を担う。

**Files:**
- Create: `rag/eval.py`
- Create: `rag/tests/test_eval.py`
- Modify: `Makefile`(`rag-eval` を追加)

**Interfaces:**
- Consumes: Task 3・4 の `rag.connect`・`rag.search`、`docs/rag/eval-questions.md` の表(列: `# / 内容 / 難所 / 質問 / 期待 / 出典`。出典欄の「同上」は、直前の質問の出典)
- Produces(`rag/eval.py`):
  - `load_questions(path) -> list[dict]`(キー: `n`・`content`・`hard`・`q`・`expect`・`sources`)
  - `rank_of(sources: list[str], paths: list[str]) -> int | None`(1 始まり)
  - `summarize(rows: list[tuple[dict, int | None]], k: int) -> dict`(キー: `total`・`top1`・`top3`・`topk`・`by_hard`)
  - コマンド `rag/eval.py <質問集> [--k 5] [--project 名前] [--min-topk N]`(`N` 未満なら、終了コード 1)、`make rag-eval`

- [ ] **Step 1: 失敗するテストを書く**

`rag/tests/test_eval.py`:

```python
import importlib
import os
import tempfile
import unittest

evalmod = importlib.import_module("eval")

SAMPLE = """\
| 軸 | 札 | 意味 |
|---|---|---|
| 内容 | 仕様 | 何を |

| # | 内容 | 難所 | 質問 | 期待する答えの要点 | 出典 |
|---|---|---|---|---|---|
| 1 | 理由 | 基本 | なぜか | 理由 | `docs/decisions/adr-0001-x.md` |
| 2 | 仕様 | 基本 | 型は | 型 | 同上 |
| 3 | 仕様 | 答えが無い | 配布は | 無い | — |
| 4 | 理由 | 横断 | 食い違いは | 差 | `docs/decisions/adr-0005-y.md`、`docs/design/09-z.md` |
"""


class LoadQuestionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        self.tmp.write(SAMPLE)
        self.tmp.close()
        self.qs = evalmod.load_questions(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_reads_only_question_rows(self):
        self.assertEqual([q["n"] for q in self.qs], [1, 2, 3, 4])

    def test_fields(self):
        q = self.qs[0]
        self.assertEqual((q["content"], q["hard"], q["q"]), ("理由", "基本", "なぜか"))

    def test_sources_strip_docs_prefix(self):
        self.assertEqual(self.qs[0]["sources"], ["decisions/adr-0001-x.md"])

    def test_same_as_above_inherits(self):
        self.assertEqual(self.qs[1]["sources"], ["decisions/adr-0001-x.md"])

    def test_no_source(self):
        self.assertEqual(self.qs[2]["sources"], [])

    def test_multiple_sources(self):
        self.assertEqual(self.qs[3]["sources"], ["decisions/adr-0005-y.md", "design/09-z.md"])


class RankTest(unittest.TestCase):
    def test_rank_is_one_based(self):
        self.assertEqual(evalmod.rank_of(["a.md"], ["b.md", "a.md"]), 2)

    def test_rank_none_when_absent(self):
        self.assertIsNone(evalmod.rank_of(["a.md"], ["b.md"]))

    def test_any_of_sources_counts(self):
        self.assertEqual(evalmod.rank_of(["a.md", "c.md"], ["c.md"]), 1)


class SummarizeTest(unittest.TestCase):
    def test_counts(self):
        rows = [
            ({"hard": "基本"}, 1),
            ({"hard": "基本"}, None),
            ({"hard": "横断"}, 3),
        ]
        s = evalmod.summarize(rows, k=5)
        self.assertEqual((s["total"], s["top1"], s["top3"], s["topk"]), (3, 1, 2, 2))
        self.assertEqual(s["by_hard"], {"基本": (1, 2), "横断": (1, 1)})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `python3 -m unittest discover -s rag/tests -t rag -p 'test_eval.py' -v`
Expected: `ModuleNotFoundError: No module named 'eval'` で失敗

- [ ] **Step 3: 評価を書く**

`rag/eval.py`:

```python
#!/usr/bin/env python3
"""質問集を、DB に対して回し、「出典の文書が、上位 k 件に入るか」を数える。"""
import argparse
import re
import sys

import rag


def load_questions(path):
    """質問集の Markdown の表から、質問を読む(6 列の行のみ。出典欄の「同上」は、直前の質問の出典)。"""
    qs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 6 or not cells[0].isdigit():
                continue
            n, content, hard, q, expect, src = cells
            paths = re.findall(r"`([^`]+\.md)`", src)
            if "同上" in src and qs:
                paths = ["docs/" + p for p in qs[-1]["sources"]] + paths
            qs.append({
                "n": int(n), "content": content, "hard": hard, "q": q, "expect": expect,
                "sources": [p.replace("docs/", "", 1) for p in paths],
            })
    return qs


def rank_of(sources, paths):
    """paths(検索の結果の順)の中で、出典のいずれかが、初めて現れる順位(1 始まり)。無ければ None。"""
    for i, p in enumerate(paths, 1):
        if p in sources:
            return i
    return None


def summarize(rows, k):
    """rows: (質問, 順位) の列(出典のある質問のみ)。"""
    by_hard = {}
    for q, rank in rows:
        hit, total = by_hard.get(q["hard"], (0, 0))
        by_hard[q["hard"]] = (hit + (1 if rank else 0), total + 1)
    return {
        "total": len(rows),
        "top1": sum(1 for _, r in rows if r and r <= 1),
        "top3": sum(1 for _, r in rows if r and r <= 3),
        "topk": sum(1 for _, r in rows if r and r <= k),
        "by_hard": by_hard,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("qfile", help="質問集(Markdown)")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--project", help="このプロジェクトの断片だけを探す")
    ap.add_argument("--min-topk", type=int, help="上位 k 件の当たりが、これ未満なら、終了コード 1")
    a = ap.parse_args(argv)
    try:
        qs = load_questions(a.qfile)
        if not qs:
            raise RuntimeError(f"質問が読めぬ: {a.qfile}")
        rows, table = [], []
        with rag.connect() as conn:
            for q in qs:
                hits = rag.search(conn, q["q"], a.project, None, a.k)
                paths = [h.path for h in hits]
                if q["sources"]:
                    rank = rank_of(q["sources"], paths)
                    rows.append((q, rank))
                    shown = str(rank) if rank else "圏外"
                else:
                    shown = "対象外"
                table.append((q, shown, paths[0] if paths else "-"))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print("| # | 内容 | 難所 | 出典の順位(上位k内) | 1位の文書 |")
    print("|---|---|---|---|---|")
    for q, shown, first in table:
        print(f"| {q['n']} | {q['content']} | {q['hard']} | {shown} | {first} |")
    s = summarize(rows, a.k)
    print(f"\n当たり: top1={s['top1']}/{s['total']}  top3={s['top3']}/{s['total']}  "
          f"top{a.k}={s['topk']}/{s['total']}")
    print(f"難所別(top{a.k}内): " + ", ".join(f"{k} {h}/{t}" for k, (h, t) in s["by_hard"].items()))
    if a.min_topk is not None and s["topk"] < a.min_topk:
        print(f"Error: top{a.k} の当たりが {s['topk']} で、基準 {a.min_topk} に届かぬ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: テストが通ることを確かめる**

Run: `python3 -m unittest discover -s rag/tests -t rag -p 'test_eval.py' -v`
Expected: 全てが `ok`

- [ ] **Step 5: Makefile に、`rag-eval` を足す**

`.PHONY: rag-up rag-down rag-destroy rag-venv rag-ingest rag-search` の行を、次に改める。

```make
.PHONY: rag-up rag-down rag-destroy rag-venv rag-ingest rag-search rag-eval
```

ファイルの末尾に、空行を一つ置いて、追加する。

```make

rag-eval: rag-venv ## Run the evaluation questions against the DB (QFILE=path K=5 [PROJECT=name])
	@$(RAG_PY) $(RAG_DIR)/eval.py "$(QFILE)" --k "$(K)" $(RAG_ONLY)
```

- [ ] **Step 6: 質問集の題材を取り込み、評価する(ゴール 3)**

質問集 `docs/rag/eval-questions.md` の「題材」の節に書かれた `docs/`(質問集が指す、他のプロジェクトの `docs/`)を、`DOCS` と `PROJECT` に指定して取り込む。場所は、質問集を読んで、確かめる。

Run: `make rag-ingest DOCS=<題材の docs の場所> PROJECT=eval-corpus`
Expected: `files=31 chunks=816` に近い値(題材の `develop` 枝の先頭が、質問集に記した `eebbe43` から進んでいれば、多少ずれる)

Run: `make rag-eval PROJECT=eval-corpus K=5`
Expected: 表と、`当たり: top1=.../11 top3=.../11 top5=.../11` が出る。**top5 が 10/11 以上**(試験では 11/11)。

top5 が 10 未満なら、原因を調べる(取り込みの断片の数が、試験の 816 件と合うか、`doc_type`・`project` の絞り込みが、効いておらぬか、HNSW の近似による取りこぼしか)。直らぬときは、ユーザーに報告して止まる。

Run: `rag/.venv/bin/python rag/eval.py docs/rag/eval-questions.md --project eval-corpus --min-topk 10; echo "exit=$?"`
Expected: `exit=0`

- [ ] **Step 7: 評価用の取り込みを、後始末する**

Run: `docker compose -f rag/compose.yaml exec -T db psql -U rag -d rag -c "DELETE FROM knowledge WHERE metadata->>'project' = 'eval-corpus'"`
Expected: `DELETE <件数>`(評価用の行を、残さぬ)

**コミットの区切り**(ユーザーが `/git commit` で行う案):
`rag/eval.py`・`rag/tests/test_eval.py`・`Makefile` →
`feat(rag): 質問集の評価(出典が上位に入るか)を追加する`

---

### Task 8: 使い方の README と、全体の確認

**Files:**
- Create: `rag/README.md`

**Interfaces:**
- Consumes: Task 1〜7 の目標とコマンド
- Produces: `rag/README.md`(実行の手順。設計書は、前提だけを述べ、手順は README に置く)

- [ ] **Step 1: README を書く**

`rag/README.md`:

````markdown
# rag/ — docs の知識を引く、最小の RAG

`docs/` の Markdown を、PostgreSQL(pgvector)に取り込み、問いに近い断片を、出所つきで返す。
埋め込みは、手元のコンテナで動く `bge-m3`(Ollama)で行い、外部の API には、何も送らない。
待ち受けの MCP サーバ(`127.0.0.1:8000`)も、同じコンテナ群で動き、Claude Code が、ツールとして呼べる。
設計: `docs/design/rag-minimal-pipeline.md`

## 前提

- Docker(Compose)と、Python 3(`venv` を使える)
- Ollama の導入は、不要(コンテナで動く)
- `GPU=1` を使うには、NVIDIA のドライバと、Docker の NVIDIA 用の実行環境が要る

## 使い方

```
make rag-up                 # DB・Ollama・MCP サーバを起動し、bge-m3 を用意する(GPU を使うなら: make rag-up GPU=1)
make rag-ingest             # docs/ を取り込む(PROJECT=名前、DOCS=場所 で変えられる)
make rag-status             # DB に入っている物(プロジェクト・種類ごとの件数)を見る
make rag-search Q="問い"    # 近い断片を探す(K=件数、PROJECT=名前、TYPE=adr|design|plan|shared|other)
make rag-eval               # 質問集で、検索の当たりを測る(QFILE=質問集、K=件数)
make rag-mcp-check          # MCP サーバの手順(初期化 → ツールの一覧 → 検索)を、通しで確かめる
make rag-test               # 単体テスト(DB・Ollama が無ければ、DB を使う分は、飛ばされる)
make rag-down               # 止める(データは残る)
make rag-destroy            # 止めて、データも消す(確認あり)
```

初回の `make rag-up` は、イメージの取得・作成と、モデルの取得(外への通信、約 1.2GB)を行う。2 回目以降は、取得しない。

## MCP サーバ

`make rag-up` で、`http://127.0.0.1:8000/mcp` に、MCP サーバが待ち受ける(`127.0.0.1` のみ。認証なし)。
リポジトリ直下の `.mcp.json` に、`rag` サーバの接続先が書いてあり、Claude Code は、それを読んで繋ぐ(初回は、承認を求められる)。

| ツール | 働き |
|---|---|
| `search_knowledge` | 問いに近い断片を、出所つきで返す(`doc_type`・`project` で絞れる) |
| `get_document` | 文書の全文を返す |
| `list_sources` | 取り込み済みの、プロジェクト・種類ごとの件数とコミット |

いずれも読み取り専用。取り込みは、`make rag-ingest` で行う。

## 設定

環境変数で、接続先を変えられる。

| 変数 | 既定 | 内容 |
|---|---|---|
| `RAG_DATABASE_URL` | `postgresql://rag:rag@127.0.0.1:5432/rag` | DB の接続先 |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | 埋め込みの問い合わせ先 |
| `RAG_EMBED_MODEL` | `bge-m3` | 埋め込みモデル |
| `MCP_HOST` / `MCP_PORT` | `0.0.0.0` / `8000` | MCP サーバの待ち受け(コンテナ内) |

コンテナは、開発用で、`127.0.0.1` のみに公開する。既定の資格情報は、開発専用である。

## つまずいたとき

| 症状 | 見る所 |
|---|---|
| `Ollama に繋がらぬ` | `make rag-up` を実行したか。`docker compose -f rag/compose.yaml ps` で、`ollama` が `healthy` か |
| `DB に繋がらぬ` | 同上(`db` が `healthy` か) |
| MCP サーバに繋がらぬ | `docker compose -f rag/compose.yaml ps` で、`mcp` が `healthy` か。`docker compose -f rag/compose.yaml logs mcp` を読む。`make rag-mcp-check` で、手順を確かめる |
| ポートが使用中 | `5432`・`11434`・`8000` を、別の物が使っておらぬか(`ss -ltn \| grep -E ':(5432\|11434\|8000)\b'`)。使っていれば、先に止める |
| `GPU=1` でも遅い | `docker compose -f rag/compose.yaml logs ollama \| grep library=` が `library=CUDA` か |
| モデルを変えたい | 次元が変わるなら、`rag/sql/init.sql` と `RAG_EMBED_DIM` も、合わせる。全件の取り直しが要る |
````

- [ ] **Step 2: `rag-test` の目標を、Makefile に足す**

`.PHONY: rag-up rag-down rag-destroy rag-venv rag-ingest rag-search rag-eval` の行を、次に改める。

```make
.PHONY: rag-up rag-down rag-destroy rag-venv rag-ingest rag-search rag-eval rag-test
```

ファイルの末尾に、空行を一つ置いて、追加する。

```make

rag-test: rag-venv ## Run the unit tests of rag/ (DB tests are skipped if the DB is down)
	@$(RAG_PY) -m unittest discover -s $(RAG_DIR)/tests -t $(RAG_DIR) -v
```

- [ ] **Step 3: 全体を、通しで確かめる**

Run: `make rag-test`
Expected: 全ての単体テストが `ok`

Run: `make rag-down && make rag-up GPU=1 && make rag-ingest && make rag-search Q="ADR を書くのは、どんなときか" && make rag-mcp-check`
Expected: 止める → 起動(モデルは、取得済みと出る)→ 取り込み → 検索 → MCP の手順が、いずれもエラーなく通る

Run: `make help`
Expected: `rag-up`・`rag-down`・`rag-destroy`・`rag-ingest`・`rag-search`・`rag-eval`・`rag-test`・`rag-mcp-check`・`rag-status` の全てと、RAG の変数の説明が出る

- [ ] **Step 4: 既存の機能を壊しておらぬことを確かめる**

`make new` は、変えておらぬ。ひな形に `rag/.venv` が在れば、複製先へ入るが、印の場所が違うため、複製先で `make rag-ingest` などを行うと、作り直される(Task 3 の Step 3 で確かめた)。

Run: `rm -rf /tmp/claude-1000/rag-plan-check && make new NAME=zz-check DEST=/tmp/claude-1000/rag-plan-check YES=1 && ls /tmp/claude-1000/rag-plan-check/zz-check/rag`
Expected: 複製が成功し、複製先に `rag/` が入っておる

Run: `f=/tmp/claude-1000/rag-plan-check/zz-check/rag/.venv/.ready; [ -f "$f" ] && [ "$(cat $f)" != "$(cd /tmp/claude-1000/rag-plan-check/zz-check/rag && pwd)" ] && echo "場所が違う印(複製先で作り直される)" || echo "印なし、または一致"`
Expected: ひな形に `rag/.venv` が在れば、`場所が違う印(複製先で作り直される)`。無ければ、`印なし、または一致`

Run: `rm -rf /tmp/claude-1000/rag-plan-check`

- [ ] **Step 5: ひな形に、固有名が無いことを確かめる**

除きたい名(質問集の「題材」の節に書かれたプロジェクト名と、ほかに、ひな形へ残したくないリポジトリ名)を、ユーザーに確かめ、`|` でつないで、変数に入れる。名前そのものは、本書に書かぬ(確認の手順が、固有名を含まぬようにするため)。

Run: `NAMES='<除きたい名1>|<除きたい名2>'; grep -rnEi "$NAMES" rag/ Makefile docs/design/rag-minimal-pipeline.md docs/superpowers/plans/2026-10-15-rag-minimal-pipeline.md || echo "なし"`
Expected: `なし`

Run: `grep -rnE '\bpostgres\b|\bpg\b' rag/ docs/design/rag-minimal-pipeline.md || echo "なし"`
Expected: `なし`(`pg16`・`pg_isready` は、`\b` の境で、単独の語として当たらぬ。当たったら、識別子かを確かめる)

- [ ] **Step 6: 後始末の確認**

手元の Ollama(11434)は、Task 1 で止めてある。コンテナ(`mcp` を含む)は、動かしたままでよい(止めるなら、`make rag-down`)。Claude Code からの確認(Task 6 の Step 11)は、利用者の結果を待つ。`git status --short` で、意図せぬ変更が無いことを確かめる。

**コミットの区切り**(ユーザーが `/git commit` で行う案):
`rag/README.md`・`Makefile` →
`docs(rag): 使い方の README と、rag-test の目標を追加する`

---

## 利用者の確認の手順(実装の後)

実装者の確認とは別に、**利用者(ユーザー)が、自分で確かめる**ための手順。上から順に、確かめる層が深くなる。各段で、期待どおりでなければ、次へ進まず、「困ったとき」の手を試し、直らなければ、実装者に報告する。

(実装者は、A〜D を、実装の中で確かめておく。E〜G は、Claude Code の操作を要するため、利用者が行う。)

### A. コンテナが、動いておるか

Run: `docker compose -f rag/compose.yaml ps`
Expected: `db`・`ollama`・`mcp` の三つが、いずれも `healthy`

困ったとき: `make rag-up`(足りぬ物を起こす)。`healthy` にならぬ物は、`docker compose -f rag/compose.yaml logs <db|ollama|mcp>` を読む。

### B. DB に、データが出来ておるか

Run: `make rag-status`
Expected: プロジェクト・種類(`adr`・`design`・`plan`・`shared`・`other`)ごとの、文書数・断片数・コミット・モデル(`bge-m3`)の表と、`total_chunks` が出る。件数が 0、または表が空なら、まだ取り込んでおらぬ。

困ったとき: `make rag-ingest`(取り込む)。他のプロジェクトの文書も入れたければ、`make rag-ingest DOCS=<場所> PROJECT=<名前>`。

### C. 検索が、人の手で通るか(MCP を介さず)

Run: `make rag-search Q="設計の判断の理由を、どこに残すか"`
Expected: 近さ(`score`)・種類・`プロジェクト:パス`・見出し・本文の冒頭が、5 件出る。ADR や設計書の断片が、上位に出る。

### D. MCP サーバの手順が、通るか

Run: `make rag-mcp-check`
Expected: `tools: ['get_document', 'list_sources', 'search_knowledge']`、`search_knowledge: ok`、終了コード 0

### E. Claude Code が、MCP サーバに繋がるか

1. Claude Code を、再起動する(または、このプロジェクトで、開き直す)。
2. `.mcp.json` の `rag` サーバを、承認する(初回の求めに従う)。
3. `/mcp` と入力する。

Expected: `rag` が、接続済み(connected)で、三つのツール(`search_knowledge`・`get_document`・`list_sources`)が見える。

困ったとき: `rag` が失敗(failed)と出るなら、D が通るかを確かめる。D が通るのに繋がらぬなら、`.mcp.json` の書式(`"type": "http"`)が、Claude Code の仕様と違う恐れがある。`claude mcp add --help` で、正しい書式を確かめ、実装者に報告する。

### F. Claude Code が、ツールを呼び、結果を受け取るか

Claude Code に、次のように頼む。

> `search_knowledge` を使って、「設計の判断の理由を、どこに残すか」を探し、見つかった文書のパスを、教えて。

確かめること:

| 見る所 | 期待 |
|---|---|
| 会話に、ツールの呼び出しが表示されるか | `search_knowledge` が、`query` などの引数つきで、呼ばれた表示が出る |
| 結果に、出所が付いておるか | `プロジェクト:パス` と、見出しが、結果と、Claude Code の答えに出る |
| サーバ側に、記録が残るか | `docker compose -f rag/compose.yaml logs --tail 20 mcp` に、要求の記録が出る(出方は、実機で確かめる) |

### G. Claude Code が、結果を、適切に扱うか(質問集で測る)

「適切」とは、**出所を示し、資料が述べる範囲で答え、資料に無い事は、作らぬ**こと。質問集 `docs/rag/eval-questions.md` の、次の質問で確かめる。質問集が指す題材の文書が、DB に入っておる必要がある(入っておらぬ場合は、先に `make rag-ingest DOCS=<題材の docs の場所> PROJECT=eval-corpus`。題材の場所は、質問集の「題材」の節に書いてある)。

依頼の型(質問の部分を、質問集の質問に置き換える):

> `search_knowledge` で調べ、出所(パス)を示して、答えて。資料に書かれておらぬ事は、「資料に無い」と答えて。質問: 〈質問集の質問〉

| 質問集の # | 試すこと | 合格(○)の目安 |
|---|---|---|
| 1 | 基本。理由を、出所つきで答える | 期待する答えの要点を満たし、出典の文書を示す |
| 5 | 追記が、元の本文を覆す | **追記の結果(現行の仕様)**で答える。元の本文の古い記述を、現行として答えたら、×(「当初は…だが、追記で…に変わった」と述べれば、○) |
| 6 | 要確認の扱い | 「記録に明記なし。〜と読めるが推測(要確認)」と、**推測と述べる**。断定したら、×(作り話) |
| 11 | 答えが無い | 「資料に無い」と答える。もっともらしい答えを作ったら、×(作り話) |
| 12 | 要確認の扱い | 「記録なし(要確認)」と答える |

記録の表(利用者が、埋める):

| # | ツールを呼んだか | 出所を示したか | 答えの要点が合うか(○△×) | 気づいた点 |
|---|---|---|---|---|
| 1 | | | | |
| 5 | | | | |
| 6 | | | | |
| 11 | | | | |
| 12 | | | | |

目安: **5 問中、4 問以上が ○**で、**問 11 が ○**(作り話をせぬ)。満たさぬ場合は、結果を、実装者に報告する。ツールの説明文・手順・検索の分け方の、どこを直すかを、そこから決める。

### H. RAG の効果を、比べる(任意)

同じ質問を、**ツールを使わせずに**問い、G の結果と比べる。

> `search_knowledge` を使わずに、答えて。質問: 〈質問集の質問〉

出所を示せぬ、または、作り話が混じるかを見る。RAG が、**効いておる**かの、目で見る証拠になる。

### I. 片付け

- 止める(データは残る): `make rag-down`
- 止めて、データも消す: `make rag-destroy`(確認あり)
- G の確認で、題材を取り込んだ場合、その行だけ消す: `docker compose -f rag/compose.yaml exec -T db psql -U rag -d rag -c "DELETE FROM knowledge WHERE metadata->>'project' = 'eval-corpus'"`

---

## Self-Review

**1. 設計書のカバー**

| 設計書 | Task |
|---|---|
| ゴール 1(`make rag-up`) | Task 1 |
| ゴール 2(取り込みが終わる) | Task 3(Step 9) |
| ゴール 3(質問集の当たり) | Task 7(Step 6) |
| ゴール 4(繰り返しても件数が変わらぬ) | Task 3(Step 10、`test_ingest_twice_keeps_count`) |
| ゴール 5(出所と近さを返す) | Task 4 |
| ゴール 6(`GPU=1`) | Task 1(Step 6・12) |
| ゴール 7(MCP の手順が通る) | Task 6(Step 7・8・9) |
| ゴール 8(Claude Code から見える) | Task 6(Step 10・11。11 は利用者の確認) |
| Makefile の目標(`rag-up`・`rag-down`・`rag-destroy`・`rag-ingest`・`rag-search`・`rag-eval`・`rag-mcp-check`) | Task 1・3・4・6・7 |
| `rag-test`(設計書の目標の表に、追記済み) | Task 8 |
| 置き場(`compose.gpu.yaml`・`Dockerfile` を含む) | Task 1〜8 |
| 表の形・`metadata` | Task 1(`init.sql`)、Task 3(`ingest`) |
| 取り込み 1〜6・`doc_type` | Task 2・3 |
| 検索(SQL・`--json`・`--doc-type`) | Task 4 |
| MCP の三つのツール(`search_knowledge`・`get_document`・`list_sources`)・件数の丸め | Task 5(中身)、Task 6(包む殻) |
| `.mcp.json`・`Dockerfile`・`mcp` サービス | Task 6 |
| `make rag-status`(設計書の目標の表に、追記済み) | Task 3(Step 12) |
| 利用者が確かめる方法(DB・MCP・Claude Code・質問集) | 「利用者の確認の手順」(A〜I) |
| 設定の環境変数 | Task 2(`rag.py`)、Task 6(`MCP_HOST`・`MCP_PORT`)、Task 8(README) |
| 前提・外への通信 | 本書の冒頭の表、Task 8(README) |

**2. プレースホルダーの検査**: 手順に「後で決める」「適切に処理する」の類は無い。唯一の実行時の値は、Task 7 の Step 6 の `<題材の docs の場所>` で、質問集の「題材」の節から、読んで決める(ひな形に、特定のプロジェクトの名を残さぬため)。

**3. 型・名前の一貫性**: `rag.py` の関数名(`doc_type_of`・`split_markdown`・`iter_markdown`・`embed`・`vec_literal`・`connect`・`current_commit`・`replace_project`・`ingest`・`search`・`format_hits`)、`Chunk`・`Hit` のフィールド、Makefile の変数(`RAG_DIR`・`RAG_MODEL`・`RAG_COMPOSE`・`RAG_PY`・`RAG_PROJECT`・`RAG_ONLY`・`DOCS`・`K`・`QFILE`)を、全 Task で揃えた。

**4. Review Focus**: 5 件とも、担当の Task に、テストまたは確認手順を置いた。

**5. 設計書との差分**: なし。次の決定は、ユーザーの回答で決まり、設計書と本書に反映済み。
- ポートは、既定の 5432・11434 を使う
- `psycopg` は、`venv`(`rag/.venv`)に入れる。`make new` は、変えない。新しいプロジェクトでは、`make rag-venv`(他の `rag-*` 目標の前提)が、`venv` を作る(複製された `venv` は、印の場所が違うため、作り直す)
- 取り込みの既定の除外は、②の評価で決める
