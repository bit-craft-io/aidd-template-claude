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
