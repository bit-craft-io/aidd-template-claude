# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

このリポジトリは、AI駆動開発のひな形(aidd-template-claude)である。コピーして新しいプロジェクトを作り、
以後は、そのプロジェクトの持ち物として育てる。ひな形の更新は、コピーしたプロジェクトへ自動では届かない。

## ルール

- ひな形から引き継いだ絶対ルール(ドキュメント運用・ブランチ運用): `.claude/rules/base-rules.md`(追記しない)
- ひな形から引き継いだ、話題ごとの運用の規則: `.claude/rules/jira.md`(Jira)、`.claude/rules/git.md`(git)、`.claude/rules/adr.md`(判断の記録)、`.claude/rules/design-addenda.md`(設計書の追記)
- このプロジェクト独自のルール: `.claude/rules/` に別ファイルを追加して書く
- どの時点のひな形からコピーしたかは、`.claude/TEMPLATE_VERSION` に記す(コピー時に書く。README 参照)

## 前提のプラグイン

このプロジェクトは、Claude Code のプラグイン `superpowers`(brainstorming・writing-plans・subagent-driven-development など)と
`skill-creator` を前提にする。未導入だと、`/superpowers:brainstorming` や、`superpowers:*` を使う手順
(`.claude/skills/jira-exec` など)が動かない。未導入のときは、次を実行する:

```
claude plugin install   superpowers@claude-plugins-official --scope user
claude plugin install skill-creator@claude-plugins-official --scope user
```

`adr`・`genshijin` の導入は、README の「セットアップ」を参照。導入状況は、`/plugin list` で確認できる。

## プロジェクト概要

(brainstorming で固めた後に記載)

## ビルド・テスト・起動

(実装後に記載)

## アーキテクチャ

(brainstorming で決めた構成を記載)

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

このひな形をコピーして作ったプロジェクトは、それぞれ独立した git リポジトリとして管理する。
コピー後は、コピー元の `.git` を引き継がず、`git init` し直す。
