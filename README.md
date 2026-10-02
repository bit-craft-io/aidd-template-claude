# 概要

- AI駆動開発の学習用リポジトリ

## 構成

- `CLAUDE.md` — Claude Code向けの規約(リポジトリ構成・.claude配下の役割等)
- `.claude/skills/` — 全プロジェクト共通のskill(`new-project`等)
- `docs/templates/` — 新規プロジェクト立ち上げ用の雛形
- `projects/<name>/` — 個々のプロジェクト(詳細は各自のREADME.md/CLAUDE.mdを参照)

## セットアップ

`claude-plugins-official` は既定で導入済み。<br />そこに存在するplugin(`superpowers`・
`skill-creator`)は通常通り、そこから直接導入する:

```
claude plugin install   superpowers@claude-plugins-official --scope user
claude plugin install skill-creator@claude-plugins-official --scope user
```

一方`adr`・`genshijin`は`claude-plugins-official`に存在せぬため、`.claude-plugin/`配下に
リポジトリを個別cloneし、それを束ねるローカルmarketplace(`project-plugins`、
`.claude-plugin/marketplace.json`)として登録・管理する。初回セットアップ:

```
mkdir .claude-plugin
git clone https://github.com/zircote/adr.git                .claude-plugin/adr
git clone https://github.com/InterfaceX-co-jp/genshijin.git .claude-plugin/genshijin

claude plugin marketplace add ./
claude plugin install       adr@project-plugins --scope user
claude plugin install genshijin@project-plugins --scope user
```

- `/plugin list` で有効化状態を確認できる。
- `.claude-plugin/*`は、git cloneするので、gitの追跡対象外(`.gitignore`)。
- `.claude-plugin/marketplace.json`のみgit管理する。

## 新規プロジェクトの始め方

1. `/new-project <name>` で雛形を生成
2. `docs/brainstorming-intake.md` を埋める
3. `/superpowers:brainstorming` で設計を固める<br />
Ex: /superpowers:brainstorming docs/brainstorming-intake.md
