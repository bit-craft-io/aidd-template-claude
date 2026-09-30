# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## リポジトリ構成

このリポジトリは複数プロジェクトを収める入れ物であり、各プロジェクトは `projects/<name>/` の下に独立して置かれる。

```
root/
├── CLAUDE.md          # このファイル。全プロジェクト共通の規約・方針のみを記す
├── .claude/            # 全プロジェクトで共有する汎用スキル・エージェント・コマンド
│   └── skills/          # プロジェクトに依存しない汎用的な技のみ
└── projects/
    └── <name>/
        ├── CLAUDE.md        # そのプロジェクト固有の文脈(概要・技術スタック・コマンド等)
        ├── .claude/skills/  # そのプロジェクト固有の技があれば、ここに置く
        └── ...               # 実装コード一式
```

- 特定プロジェクトの説明・技術スタック・ビルド手順は、このファイルではなく各 `projects/<name>/CLAUDE.md` に書く
- 汎用的でない(特定プロジェクトの都合に依る)スキルは `root/.claude/skills/` ではなく `projects/<name>/.claude/skills/` に置く。Claude Codeはネストした `.claude/skills/` も自動的に見つける
- 現時点で確立された全プロジェクト共通の規約は特に無い。今後、複数プロジェクトに跨って繰り返し適用したい方針が固まった際に、ここへ追記する

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

## .claude配下の役割

| ディレクトリ/ファイル | 役割 |
|---|---|
| `.claude/skills/` | 再利用可能な技(SKILL.md)。個人・プロジェクト固有の作業手順 |
| `.claude/rules/` | Markdown形式の規約。ファイルパスに応じ条件付きで読み込み可 |
| `.claude/agents/` | 独立した文脈窓を持つ専用subagentの定義 |
| `.claude/agent-memory/` | `memory: project`指定のsubagentが持つ永続記憶 |
| `.claude/output-styles/` | Claudeの応答スタイル(人格)を切り替える定義 |
| `.claude/workflows/` | 複数subagentを組み合わせて動かす、JavaScript製の動的ワークフロー |
| `.claude/hooks/` | Hook用スクリプトの置き場(`settings.json`から参照。フォルダ自体は公式仕様ではなく慣例) |
| `.claude/settings.json` | チーム共有設定(git管理対象) |
| `.claude/settings.local.json` | 個人設定(gitignore対象、自動生成) |

## Git管理

`projects/` は root repo の追跡対象から外れて居る(`.gitignore`参照)。**各 `projects/<name>/` は、それぞれ独立した git リポジトリ**として個別に管理する(`projects/<name>/`直下に其々の`.git`を持つ)。root repo のコミット・ブランチ操作は、`projects/`配下のプロジェクトには一切影響せぬ。新規プロジェクトを追加する際は、`projects/<name>/`を作った上で其の中で個別に`git init`すること。
