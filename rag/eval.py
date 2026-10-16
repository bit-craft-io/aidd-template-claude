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
                # 狙いから種別を決めて引く運用に合わせ、出典の種別で絞る(出典の無い問いは、省く=既定の範囲)
                dt = rag.doc_type_of(q["sources"][0]) if q["sources"] else None
                hits = rag.search(conn, q["q"], a.project, dt, a.k)
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
