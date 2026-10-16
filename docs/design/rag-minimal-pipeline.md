# doc-spec: RAG の最小の通し(取り込み・検索・MCP サーバ)

## 追記の一覧

(なし)

## 機能概要

`docs/` の知識(設計書・ADR・計画書など)を、PostgreSQL(pgvector)に取り込み、問いに近い断片を、出所つきで返す仕組みを作る。
手元で、Docker のコンテナだけで動く(DB、埋め込みモデル `bge-m3` を動かす Ollama、**待ち受けの MCP サーバ**)。外部の API には、何も送らない。

`make rag-up` の一つで、三つのコンテナの起動と、モデルの用意までを行う。起動後は、MCP サーバが、`127.0.0.1` で待ち受け、Claude Code が、`.mcp.json` の指定に従って、ツールとして呼べる。

取り込みと検索は、短い Python で作り、評価用の質問集(`docs/rag/eval-questions.md`)で確かめる。Langflow の流れへの載せ替え、チーム共有(共有サーバ、CI、権限)は、扱わない。

## 実装背景

組織の設計の知識(判断・理由・規約)を、設計の場面(対話して詰める、依頼内容を判断する、Task を作る)で、人と AI(Claude Code)が、ツールとして引けるようにするため、引ける仕組みと、待ち受けの窓口を作る。

なぜ RAG を採るのか、狙う場面(プロジェクト・時間・人とセッションを跨ぐ、量が大きい)、他の案を退けた理由は、`docs/decisions/shared/rag-for-knowledge-retrieval.md` に書く(ここには、書かない)。

やり方(分け方・検索方式・埋め込みモデル)は、質問集で測って決めた(試験の結果は、会話に残る。ADR 化は、通しが動いてから)。

- 埋め込み: `bge-m3`(1024 次元)
- 文書の分け方: 見出し(`#`〜`###`)で区切り、長い節は、段落で 1500 字以内に切る
- 保存先・埋め込みの方針: `docs/decisions/shared/rag-vector-store-pgvector.md`、`docs/decisions/shared/rag-embedding-self-hosted.md`

Ollama と MCP サーバも、コンテナにする理由: Docker だけで完結し、複製先で、Ollama の導入が要らない。埋め込みを、自社の管理下のコンテナで動かす方針(上の ADR)と合い、将来、クラウドへ移すときも、同じコンテナの形で動かせる。

速さの目安(手元の実測。`bge-m3`、見出し分けの断片):

| 項目 | GPU | CPU のみ |
|---|---|---|
| 問い 1 件の埋め込み(検索の応答に効く) | 中央値 184 ms | 中央値 228 ms |
| 取り込み(全 816 件) | 92 秒(実測) | 約 12 分(先頭 100 件の比からの推計) |

検索の応答は、GPU の有無で、ほぼ変わらない。遅くなるのは、取り込み(初回と、文書の更新のとき)。

## 影響・対象範囲

- 新規に、`rag/` ディレクトリを足す(コンテナの定義、取り込み、検索、MCP サーバ、評価)
- 既存の `Makefile` に、`rag-` で始まる目標を足す(既存の `new` は、変えない)
- 既存の `.mcp.json`(現在は、サーバの定義が空)に、`rag` サーバの接続先を足す
- `make new` は、ひな形を丸ごと複製するため、`rag/`・目標・`.mcp.json` の定義も、複製先に入る(標準機能として、意図したもの)
- 取り込みの対象は、実行時に指定する `docs/` 配下の Markdown
- `rag/.venv` は、大きいため追跡しない(`.gitignore` の既存の `.venv` で足りる)。新しいプロジェクトでは、その場所で `venv` を作る。ひな形の `rag/.venv` は、ひな形での動作確認のためにあり、`make new` で複製先へ入っても、印(`rag/.venv/.ready`)に記した場所が違うため、複製先で作り直す(`make new` は、変えない)

## ゴール

次を、全て満たすこと。

1. `make rag-up` で、DB(表あり)・Ollama・MCP サーバが起動し、`bge-m3` が用意される(初回は、イメージの取得・作成と、モデルの取得で、外への通信が起きる)
2. 取り込みが、全文書を、エラー無く終える(断片の数と所要時間が、表示される)
3. 質問集を、DB に対して回した結果が、試験(メモリ上の計算)と同等である(見出し分けで、上位 5 件の当たりが、11 問中 10 問以上。試験では 11 問)
4. 取り込みを、繰り返しても、件数が変わらない(置き換えで動く)
5. 検索が、出所(プロジェクト・パス・見出し)と、近さを返す
6. `make rag-up GPU=1` で、Ollama のコンテナが GPU を使う(NVIDIA の GPU がある機のみ)
7. MCP サーバが、`127.0.0.1:8000` で待ち受け、MCP の手順(初期化 → ツールの一覧 → 検索の呼び出し)が、`make rag-mcp-check` で通る
8. `.mcp.json` の定義で、Claude Code から、`rag` のツールが見え、呼べる(利用者が、Claude Code を再起動して確かめる)

## 対象外

- Langflow の流れへの載せ替え(要否も含め、後で判断する)
- チーム共有(共有サーバ、CI での取り込み、認証・権限)。MCP サーバは、`127.0.0.1` のみで待ち受け、認証は付けない
- 書き込みのツール(取り込みの呼び出しなど)。MCP のツールは、読み取り専用
- 評価(`rag-eval`)の MCP での公開(評価は、開発者が測る道具)
- ツールを、いつ呼ばせるかの指示(`CLAUDE.md`・各スキルの手順への書き込み)。別の作業で行う
- 語句検索との併用、順位の入れ替え(リランク)、回答の生成
- 画像の取り込み
- 「答えが無い問い」の判定(検索のみでは、判定できぬ。生成側の課題)

## 前提(設計書の外で、要るもの)

- Docker(Compose)と、Python 3(`venv` を使える)が、手元に在ること。Ollama の導入は、不要
- `make rag-up` の初回は、外への通信を行う。ベースのイメージと依存の取得・MCP サーバのイメージの作成、モデルの取得(約 1.2GB)。その旨を、画面に出す
- 手元の 5432(PostgreSQL)・11434(Ollama)・8000(MCP サーバ)のポートが、空いていること。別の物が動いているときは、先に止める
- `GPU=1` を使うには、NVIDIA のドライバと、Docker の NVIDIA 用の実行環境が要る

手順の詳細は、`rag/README.md` に書く(同じ内容を、二か所に書かぬため、ここには書かない)。

## 解決策・技術アーキテクチャ

### 全体構成

```
docs/*.md ──▶ ingest.py ──(見出しで分ける)──▶ Ollama(bge-m3)で埋め込み ──▶ PostgreSQL(pgvector)

Claude Code ──(.mcp.json)──▶ MCP サーバ(待ち受け) ─┐
make rag-search / rag-eval ──────────────────────────┴─▶ rag.py の検索 ─▶ Ollama で問いを埋め込み ─▶ 近い断片 + 出所
```

- 取り込みと検索は、同じ埋め込みモデルを使う(モデルが違うと、当たらぬ)
- DB・Ollama・MCP サーバは、`compose.yaml` の三つのサービス。Python のコマンド(取り込み・検索・評価)は、手元(`venv`)で動かし、公開したポートで繋ぐ。MCP サーバは、コンテナ内で動き、コンテナ同士の名前(`db`・`ollama`)で繋ぐ

### 置き場

```
rag/
  compose.yaml            db・ollama・mcp の三つのサービス
  compose.gpu.yaml        ollama に GPU を足す定義(GPU=1 のとき重ねる)
  Dockerfile              MCP サーバのイメージ
  sql/init.sql            表と索引
  rag.py                  分割・埋め込み・DB 操作・検索・文書の取得・一覧の共通部品
  mcp_server.py           MCP サーバ(rag.py の関数を、ツールとして包む薄い殻)
  mcp_check.py            MCP サーバの手順の確認(標準ライブラリのみ)
  ingest.py               取り込み
  search.py               検索(コマンド)
  eval.py                 質問集の評価
  requirements.txt        手元の Python の依存(psycopg)
  requirements-mcp.txt    MCP サーバの依存(MCP の SDK)。イメージにのみ入れる
  README.md               使い方
```

### Makefile の目標

| 目標 | 働き |
|---|---|
| `make rag-up [GPU=1]` | コンテナを(MCP サーバのイメージを作りつつ)起動し(健康確認を待つ)、`bge-m3` を取得する(既にあれば、取得しない) |
| `make rag-down` | コンテナを止める。データ(DB・モデル)は残す |
| `make rag-destroy` | コンテナを止め、データ(ボリューム)も消す(確認を取る) |
| `make rag-ingest [PROJECT=<名前>] [DOCS=<場所>]` | 取り込み。先に `rag-venv` が、`venv` を用意する |
| `make rag-venv` | `rag/.venv` を作り、依存を入れる(`rag-ingest`・`rag-search`・`rag-eval`・`rag-test` の前提。内部の目標) |
| `make rag-status` | DB に入っている物(プロジェクト・種類ごとの、文書数・断片数・コミット・モデル)を見る |
| `make rag-search Q="問い" [K=5]` | 検索 |
| `make rag-eval [QFILE=<質問集>]` | 質問集の評価 |
| `make rag-test` | `rag/` の単体テスト(DB を使う分は、DB が止まっていれば、飛ばす) |
| `make rag-mcp-check` | MCP サーバの手順(初期化 → ツールの一覧 → 検索の呼び出し)を確かめる |

`GPU` は、`1`・`true`・`yes` のとき有効とし、`0`・`false`・空は無効とする(`0` を有効と取らぬため)。

### コンテナ(`compose.yaml`)

| サービス | イメージ | 公開 | 保存 | 備考 |
|---|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` | `127.0.0.1:5432` | ボリューム `rag-db-data` | 起動時に `sql/init.sql` で表を作る。健康確認あり |
| `ollama` | `ollama/ollama`(版を固定) | `127.0.0.1:11434` | ボリューム `rag-ollama-models` | `OLLAMA_KEEP_ALIVE` を長めにし、休止後の最初の問いの遅れを避ける |
| `mcp` | `rag/Dockerfile` で作る | `127.0.0.1:8000` | なし | `db`・`ollama` が健康になってから起動する。接続先は、コンテナ同士の名前(`db`・`ollama`) |

`compose.gpu.yaml` は、`ollama` に、NVIDIA の GPU の予約(`driver: nvidia`)を足す。

コンテナは、開発用で、`127.0.0.1` のみに公開する。既定の資格情報は、開発専用(本番では、別に設定する)。

### 表の形

`knowledge` 表を作る(索引は、HNSW のコサイン)。

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE knowledge (
    id        SERIAL PRIMARY KEY,
    content   TEXT,
    metadata  JSONB,
    embedding VECTOR(1024)
);
CREATE INDEX knowledge_embedding_idx
    ON knowledge USING hnsw (embedding vector_cosine_ops);
```

`metadata` の項目:

| 項目 | 内容 | 使い道 |
|---|---|---|
| `project` | プロジェクト名 | 絞り込み・権限・共有 |
| `path` | 文書のパス(`docs/` からの相対) | 出所の提示、全文の取得 |
| `heading` | 見出し(節の題) | 出所の提示 |
| `doc_type` | `adr` / `design` / `plan` / `shared` / `other` | 絞り込み |
| `commit` | 取り込み時のコミット(短縮形) | 古さの判定 |
| `model` | `bge-m3` | モデルを変えたときの取り直し |

### 取り込み(`ingest.py`)

入力: `--docs <docs の場所>`(既定 `docs`)、`--project <名前>`(既定は、リポジトリのディレクトリ名)、`--exclude <パターン>`(任意、複数可)。

1. `--docs` 配下の `*.md` を、全て読む(`--exclude` に合うものは除く)
2. 見出し(`#`〜`###`)で区切る。コードのかこみの中の `#` は、見出しにしない。1500 字を超える節は、段落(空行)で切る
3. 各断片の先頭に、`[パス]` を付ける(出所を、本文にも持たせる)
4. Ollama の `/api/embed` で、`bge-m3` の埋め込みを得る(16 件ずつ)
5. **一つのトランザクションで**、同じ `project` の行を全て削除し、新しい行を入れる(置き換え。繰り返しても、件数が変わらぬ)
6. 件数・所要時間・`doc_type` ごとの件数を表示する

`doc_type` は、パスから決める。

| パス | `doc_type` |
|---|---|
| `decisions/shared/` 配下 | `shared` |
| `decisions/` 直下の `adr-*.md` | `adr` |
| `design/` 配下 | `design` |
| `superpowers/plans/` 配下 | `plan` |
| 上記以外 | `other` |

### 検索(`rag.py` の `search`、`search.py`)

入力: 問い、`project`(任意)、`doc_type`(任意)、`k`(既定 5)。

1. 問いを、同じモデルで埋め込む(`bge-m3` は、接頭辞なし)
2. 次の問い合わせで、近い順に `k` 件を取る(`<=>` は、コサイン距離)

```sql
SELECT content, metadata, 1 - (embedding <=> %s) AS score
FROM knowledge
WHERE (%s IS NULL OR metadata->>'project' = %s)
  AND (%s IS NULL OR metadata->>'doc_type' = %s)
ORDER BY embedding <=> %s
LIMIT %s;
```

3. 近さ(`score`)、出所(`project`・`path`・`heading`)、本文を返す

### MCP サーバ(`mcp_server.py`)

`rag.py` の関数を、MCP のツールとして包む、薄い殻。待ち受けの形は、MCP の「ストリーミング HTTP」(状態を持たぬ形、応答は JSON)。コンテナ内で `0.0.0.0:8000` に待ち受け、`compose.yaml` が、手元の `127.0.0.1:8000` のみへ公開する。接続先 URL は、`http://127.0.0.1:8000/mcp`。

出すツールは、三本。いずれも、読み取り専用。

| ツール | 引数 | 返す物 |
|---|---|---|
| `search_knowledge` | `query`(問い)、`doc_type`(任意)、`project`(任意)、`k`(1〜20、既定 5。範囲外は丸める) | 近い順の断片(近さ・出所・本文)。参考であり、決定は、人が承認する |
| `get_document` | `path`(`docs` からの相対)、`project`(任意) | 文書の全文(断片を、順につないだ物)。複数のプロジェクトに同じ `path` が在り、`project` が無いときは、エラー(候補を示す)。無ければ、その旨 |
| `list_sources` | `doc_type`(任意) | 取り込み済みの、プロジェクト・種類ごとの、文書数・断片数・コミット・モデル |

ツールの説明文には、使う場面(設計の対話で詰めるとき、依頼内容を判断するとき、Task を作るとき)と、使わぬ場面(コードの細部の確認、git の最新の状態の確認)を書く。AI は、この説明文を読んで、呼ぶかを判断する。

`.mcp.json` に、次を足す(書式は、Claude Code の仕様に従う。実装のときに確かめる)。

```json
{
  "mcpServers": {
    "rag": { "type": "http", "url": "http://127.0.0.1:8000/mcp" }
  }
}
```

### 評価(`eval.py`)

`docs/rag/eval-questions.md` の表を読み、各質問を検索にかけ、出典の文書が上位 `k` 件に入るかを数える(試験と同じ判定。札ごとの集計も出す)。質問集の場所は、引数で指定できる(質問集は、②が済んだらひな形から外すため)。

### 設定

環境変数で、差し替える(接続先を、将来の管理サービスへ変えやすくするため)。

| 変数 | 既定 | 内容 |
|---|---|---|
| `RAG_DATABASE_URL` | `postgresql://rag:rag@127.0.0.1:5432/rag` | DB の接続先(`mcp` コンテナでは、`compose.yaml` が `db` 宛てに上書きする) |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | 埋め込みの問い合わせ先(`mcp` コンテナでは、`ollama` 宛てに上書きする) |
| `RAG_EMBED_MODEL` | `bge-m3` | 埋め込みモデル |
| `MCP_HOST` / `MCP_PORT` | `0.0.0.0` / `8000` | MCP サーバの待ち受け(コンテナ内) |

### 要確認(決めていない・確かめていない点)

決めた点(2026-10-15):

- Python の依存: `psycopg`(v3)を、`venv`(`rag/.venv`)に入れる。`rag/requirements.txt` に書き、`make rag-ingest` が自動で用意する
- ポート: 既定を使う(DB は 5432、Ollama は 11434)。MCP サーバは、SDK の既定の 8000 を使う
- 取り込みの既定の除外: 既定では、全ての `*.md` を入れる。雛形・`brainstorming-intake.md` などを除く既定が要るかは、②の評価で決める
- 待ち受けの MCP サーバを、このひな形の範囲に含める。形は、compose のサービス(コンテナ)

確かめていない点:

- MCP の Python の SDK(パッケージ名 `mcp`)の、版と使い方(`FastMCP` の引数、ストリーミング HTTP の起動の書き方)。記憶による。実装の最初に、実物で確かめる
- Claude Code の `.mcp.json` の書式(`"type": "http"`)。記憶による
- 待ち受けの Host の検査(DNS 再束縛の対策)が、`127.0.0.1:8000` 宛ての要求を、通すか
- Ollama のイメージの版: 手元の Ollama は 0.31.1。同じ版のイメージが在るかは、未確認
- コンテナでの GPU 動作: この機の Docker には、`nvidia` の実行環境が登録されているが、`bge-m3` のコンテナで、実際に GPU を使えるかは、未確認
- 試験で、`bge-m3` と見出し分けを選んだ判断の ADR 化は、通しが動いてから行う

### テスト方針

- 分割・`doc_type` の判定・質問集の読み取り・件数の丸めは、DB を使わず、単体で確かめる
- DB を使う取り込み・検索・文書の取得・一覧は、DB が動いていれば、単体のテストで確かめる(止まっていれば、飛ばす)
- MCP サーバは、`make rag-mcp-check`(標準ライブラリのみの確認)で、手順を通しで確かめる
- 上の「ゴール」の 1〜8 を、実機で確かめる(6 は、GPU のある機のみ。8 は、利用者が、Claude Code を再起動して確かめる)
- 利用者が自分で確かめる手順(DB の件数、MCP の手順、Claude Code からの接続と呼び出し、質問集での、答えの扱いの確認)は、計画書の「利用者の確認の手順」に書く(同じ内容を、二か所に書かぬため、ここには書かない)。なお、Claude Code が、結果を適切に扱うか(出所を示す、追記を踏まえる、資料に無い事を作らぬ)の確認は、ゴール 8 の範囲(見えて、呼べる)を超え、質問集を、Claude Code 経由で回して測る別の確認である
