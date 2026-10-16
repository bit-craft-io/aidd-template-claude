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
