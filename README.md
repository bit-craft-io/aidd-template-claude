# 概要

- AI駆動開発の学習用リポジトリ

## 構成

- `CLAUDE.md` — Claude Code向けの規約(リポジトリ構成・.claude配下の役割等)
- `.claude/skills/` — 全プロジェクト共通のskill(`new-project`等)
- `docs/templates/` — 新規プロジェクト立ち上げ用の雛形
- `projects/<name>/` — 個々のプロジェクト(詳細は各自のREADME.md/CLAUDE.mdを参照)

## セットアップ

`claude-plugins-official` は既定で導入済み。以下のplugin marketplace・pluginは別途追加が必要:

```
/plugin marketplace add InterfaceX-co-jp/genshijin

/plugin install superpowers@claude-plugins-official
/plugin install skill-creator@claude-plugins-official
/plugin install genshijin
```

## 新規プロジェクトの始め方

1. `/new-project <name>` で雛形を生成
2. `projects/<name>/docs/brainstorming-intake.md` を埋める
3. `/superpowers:brainstorming` で設計を固める
