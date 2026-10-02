# 概要

- AI駆動開発の学習用リポジトリ

## 構成

- `CLAUDE.md` — Claude Code向けの文脈(プロジェクト概要・.claude配下の役割等)
- `.claude/skills/` — 全プロジェクト共通のskill(`jira`・`doc-spec`等)
- `.claude/rules/base-rules.md` — 全プロジェクト共通の絶対ルール(追記しない)
- `docs/templates/` — brainstorming-intake・doc-specの雛形
- `docs/decisions/` — ADRのテンプレートと、意思決定の記録

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

このリポジトリ(aidd-template-claude)をコピーして作る。コピー後は、そのプロジェクトの持ち物で、
ひな形の更新は自動では届かない。

1. コピーして、`.git` を作り直す。コピー元の記録も残す:
   ```
   cp -r aidd-template-claude <name>
   cd <name> && rm -rf .git .claude/settings.local.json
   printf 'source: aidd-template-claude\ncommit: <コピー元の git rev-parse --short HEAD>\ndate: <YYYY-MM-DD>\n' > .claude/TEMPLATE_VERSION
   git init
   ```
   `git init` のあと、コピー元と同じ `user.name` / `user.email` を、明示的に設定する(引き継がれない)。
2. `docs/templates/brainstorming-intake.md` を `docs/brainstorming-intake.md` にコピーして、埋める
3. `/superpowers:brainstorming` で設計を固める<br />
Ex: /superpowers:brainstorming docs/brainstorming-intake.md
4. `CLAUDE.md` の「プロジェクト概要」以降を、brainstorming の結果で埋める
