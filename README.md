# 概要

- AI駆動開発の学習用リポジトリ

## 構成

- `CLAUDE.md` — Claude Code向けの文脈(プロジェクト概要・.claude配下の役割等)
- `.claude/skills/` — 全プロジェクト共通のskill(`jira`・`doc-spec`等)
- `.claude/rules/base-rules.md` — 全プロジェクト共通の絶対ルール(追記しない)
- `.claude/rules/jira.md`・`git.md`・`design-addenda.md` — 話題ごとの運用の規則(Jira、git、決定の記録)
- `docs/templates/` — brainstorming-intake・doc-spec・ADRの雛形
- `docs/decisions/` — 意思決定の記録。直下はプロジェクト固有のADR(採用後は書き換えない)、`shared/` はひな形から引き継ぐ共通の決定(書き換え可)

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

1. ひな形のディレクトリで、`make new` を実行する(`make` だけで、使い方が出る):
   ```
   make new NAME=<name>            # ひな形の隣(../<name>)に作る
   make new NAME=<name> DEST=<dir> # <dir>/<name> に作る
   ```
   作る場所を示して、確認(Y/n。Enter で進む)を取る。`YES=1` を付けると、確認を飛ばす。
   `make new` がするのは、複製のみ。ひな形の `.git` と `.claude/settings.local.json` は、複製に含めない。
   `.claude/TEMPLATE_VERSION` の `commit` と `date` は、コピー元の値で書かれる。
   `docs/templates/brainstorming-intake.md` は、`docs/brainstorming-intake.md` に写される。
2. 新しいプロジェクトで、git を整える(`make new` は、git に触れない):
   ```
   cd <name>
   git init -b main
   git config user.name  "<名前>"
   git config user.email "<メール>"
   git add -A && git commit -m "chore: init from aidd-template-claude"
   git branch develop
   ```
   最初のコミットのみ、`main` に置く(`develop` を作るには、コミットが要るため)。以後は、`develop` から切った `feature/YYYYMMDD` で作業する(`.claude/rules/git.md`)。
   `origin` を足す場合は、続けて `git remote add origin <url>` を行う。
3. `docs/brainstorming-intake.md` を埋める
4. `/superpowers:brainstorming` で設計を固める<br />
Ex: /superpowers:brainstorming docs/brainstorming-intake.md
5. `CLAUDE.md` の「プロジェクト概要」以降を、brainstorming の結果で埋める
