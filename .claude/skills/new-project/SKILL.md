---
name: new-project
description: >
  Scaffold a new project under projects/<name>/: creates the directory, copies
  the whole .claude/ (skills, agents, rules, hooks, settings.json) and the base
  docs templates into it, and records the source commit in
  .claude/TEMPLATE_VERSION. Does NOT git-init — that happens later, once real
  implementation starts. Use when the user asks to start/create a new project,
  or says "/new-project <name>".
---

新しいプロジェクトを `projects/<name>/` 配下に立ち上げる。この skill は、本家(root)の
`.claude/` 一式と基底のテンプレートを**コピーして**雛形を用意するのみで、**git
リポジトリの初期化は行わない**。root の `CLAUDE.md` に定める通り、各プロジェクトは
最終的に独立した git リポジトリとして管理するが、それは brainstorming を経て実装が
始まる段階で改めて行う(空の雛形だけの状態で履歴を持たせても意味が無い為)。

コピーしたものは、以後そのプロジェクトの持ち物である。本家の更新は、分家へ自動では
届かない。どの時点の本家からコピーしたかは `.claude/TEMPLATE_VERSION` に残す。

## 手順

1. プロジェクト名を確認する。`/new-project <name>` の形で渡されていればそれを使う。
   渡されていなければユーザーに尋ねる。

   名前は `^[a-z0-9]+(-[a-z0-9]+)*$`(小文字英数字とハイフンのみ、
   kebab-case)に従うこと。日本語・大文字・アンダースコア・空白等を
   含む名前が渡された場合は、**エラーとしてそこで止める**(先に進めな
   い)。命名規則を伝え、英語の kebab-case な名前を渡し直すよう求め
   る。ユーザーの代わりに名前を作って進めてはならない。

   `projects/<name>/` が既に存在する場合は上書きせず、ユーザーに確認する。

2. `.claude/` 一式をコピーする。個人設定の `settings.local.json` は渡さない:

   ```bash
   mkdir -p projects/<name>
   cp -r .claude projects/<name>/.claude
   rm -f projects/<name>/.claude/settings.local.json
   ```

   `.claude/rules/base-rules.md` も、ここでコピーされる。**base-rules.md には追記しない**。
   このプロジェクト独自のルールは、`projects/<name>/.claude/rules/` に別ファイルを
   追加して書く。

3. docs の雛形をコピーする:

   ```bash
   mkdir -p projects/<name>/docs/images
   mkdir -p projects/<name>/docs/tables
   mkdir -p projects/<name>/docs/templates
   mkdir -p projects/<name>/docs/decisions
   cp docs/templates/*.md projects/<name>/docs/templates/
   cp docs/decisions/adr-template.md projects/<name>/docs/decisions/adr-template.md
   cp docs/templates/brainstorming-intake.md projects/<name>/docs/brainstorming-intake.md
   ```

   `docs/decisions/` へ渡すのは `adr-template.md` のみ。本家の ADR(`adr-0001-...` 等)は、
   本家の意思決定の記録なので渡さない。

4. コピー元の記録 `projects/<name>/.claude/TEMPLATE_VERSION` を書く:

   ```
   source: bc.ai-develop-claude
   commit: <git rev-parse --short HEAD>
   date: <YYYY-MM-DD(コピーした日)>
   dirty: <yes|no>
   ```

   `dirty` は、本家に未コミットの変更がある(`git status --porcelain` が空でない)と `yes`。
   `yes` のときは、コピー元の commit だけでは内容を再現できないので、ユーザーに警告する。

5. プロジェクト用の `CLAUDE.md` 雛形を置く(中身は brainstorming を経て後から埋める):

   ```markdown
   # CLAUDE.md

   このファイルは、このプロジェクト固有の文脈を記す。

   ## ルール

   - 本家から引き継いだ絶対ルール: `.claude/rules/base-rules.md`(追記しない)
   - このプロジェクト独自のルール: `.claude/rules/` に別ファイルを追加して書く

   ## プロジェクト概要

   (brainstorming で固めた後に記載)

   ## ビルド・テスト・起動

   (実装後に記載)

   ## アーキテクチャ

   (brainstorming で決めた構成を記載)
   ```

6. 最小限の `.gitignore` を置く(技術スタックが決まっていない段階なので汎用的な項目のみ):

   ```
   .env
   .env.local
   *.db
   node_modules/
   __pycache__/
   venv/
   .venv/
   ```

7. ユーザーに報告する: `projects/<name>/docs/brainstorming-intake.md` を埋めた上で
   `/superpowers:brainstorming` を実行するよう促す。この skill 自身は設計や実装には
   踏み込まない — 雛形の用意のみが役目。

   併せて、次を伝える:
   - コピー元は、本家の commit `<hash>`(`dirty` なら、その旨も)。以後は分家の持ち物で、
     本家の更新は自動では届かない
   - **git init はまだ行っていない**。brainstorming を経て実装に入る段階になったら、
     `projects/<name>/` の中で個別に `git init` すること(root repo のコミット履歴とは別系統。
     root repo の git ユーザー設定を読み取り、同じ値を明示的に設定するのを忘れないこと
     — sibling repo からは継承されない)
