# base-rules.md

全プロジェクト共通の絶対ルール。本ファイルには追記しない。プロジェクト独自のルールは、
`.claude/rules/` に別ファイルを追加して書く(本ファイルは、ひな形の更新時にのみ差し替える)。

## Jira

チケット操作は `/jira` スキルを使う。対象は次のとおり。

- サイト: `bit-craft.atlassian.net`
- 課題タイプ: `タスク` / `エピック`
- `AIDDS`(名前 aidd-scrum): 計画(`docs/superpowers/plans/` の実装計画)のタスクの登録先。バックログに追加する。「現在のスプリント」もこちら
- `AIDDK`(名前 aidd-kanban): カンバンのタスクの登録先。バックログに追加する

振り分けの基準(「タスクにして」とだけ言われた場合):

- 実装中(スプリント中)に見つけたもので、現在のスプリントの内容と依存関係があるもの → `AIDDS`
- 依存関係がなく、後からでも対応できるもの → `AIDDK`
- どちらか判断できない場合は、作成前に確認する

## ドキュメント運用の流れ(brainstorming-intake / CLAUDE.md / doc-spec)

各プロジェクトにおける企画〜実装のドキュメントは、以下の役割分担・時系列で運用する。

1. **`docs/brainstorming-intake.md`**: 大きな機能・企画の"種"となる生の材料(目標・動機、ラフな画面イメージ等)を、brainstorming**に持ち込む前**に書く。brainstorming後に内容を書き直すものではない
2. **brainstorming**: 対話を通じて、その企画を具体的な機能単位(例: 機能A、機能B)へ分割し、方針を決める
3. **`CLAUDE.md`(プロジェクト概要・アーキテクチャ節)**: brainstormingで決まった全体像・機能への分割を記す「見取り図」。実装が進むにつれ随時更新し、各doc-specへのリンクを追記してゆく
4. **`docs/design/<機能名>.md`(doc-spec)**: 機能A・機能Bそれぞれの実装着手前スペック。全部を先に洗い出すのではなく、機能が具体化する都度、1つずつ追加してゆく

つまり、複数のdoc-spec(機能A・機能B…)が積み上がることで、より大きな機能が形作られる。その束ね役はCLAUDE.mdのプロジェクト概要・アーキテクチャ節であり、`brainstorming-intake.md`は入力記録として基本的に更新しない

### 画面モックアップ画像の扱い

`brainstorming-intake.md` がモックアップ画像を参照している場合(参照が無い機能には本ルール適用外。例: backend APIのみで完結する機能):

1. **[brainstorming/doc-spec作成時]** 該当画像をReadツールで実際に読み込み、doc-specに「画面デザイン」節を設け、配色・レイアウト・CSSトークン名等を具体的に書き出す
2. **[brainstorming/spec self-review時]** intakeに画像参照があるのにdoc-specへ「画面デザイン」節が無い場合、これをplaceholder・欠落として扱い、ユーザーによる review gateに進める前に追記する
3. **[writing-plans/spec self-review時]** doc-specに「画面デザイン」節が存在する場合、その内容を実装するスタイリング専用task(CSS定義・エントリポイントへのimport・見た目確認込み)をタスク分解に必ず1つ含める。節が存在するのに対応taskが無ければ、spec coverageのギャップとして扱い追加する

## ブランチ運用

- 作業は、その日の日付の `feature/YYYYMMDD` で行う。既にあればそれを使い、無ければ `develop` から作る。`develop` が無いときは、作らずに確認する
- `main` に直接コミットしない
