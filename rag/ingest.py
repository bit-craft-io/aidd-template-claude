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
