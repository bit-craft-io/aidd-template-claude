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
