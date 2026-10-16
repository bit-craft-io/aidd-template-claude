"""RAG の MCP サーバ(待ち受け)。rag.py の関数を、読み取り専用のツールとして包む薄い殻。

設計書: docs/design/rag-minimal-pipeline.md
"""
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import rag

mcp = FastMCP(
    "rag",
    host=os.environ.get("MCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("MCP_PORT", "8000")),
    stateless_http=True,
    json_response=True,
    # コンテナ内では 0.0.0.0 で待ち受けるが、手元へは 127.0.0.1 のみに公開される。
    # DNS 再束縛の対策として、許す Host を、手元の名前に限る。
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
        allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
    ),
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
