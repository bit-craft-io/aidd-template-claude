---
name: new-project
description: >
  Scaffold a new project under projects/<name>/: creates the directory and
  copies docs/templates/ and an empty .claude/ (skills/rules) into it.
  Does NOT git-init — that happens later, once real implementation starts.
  Use when the user asks to start/create a new project, or says
  "/new-project <name>".
---

新しいプロジェクトを `projects/<name>/` 配下に立ち上げる。この skill
は雛形一式(ディレクトリ・空のテンプレート)を用意するのみで、**git
リポジトリの初期化は行わない**。root の `CLAUDE.md` に定める通り、各
プロジェクトは最終的に独立した git リポジトリとして管理するが、それは
brainstorming を経て実装が始まる段階で改めて行う(空の雛形だけの状態
で履歴を持たせても意味が無い為)。

## 手順

1. プロジェクト名を確認する。`/new-project <name>` の形で渡されていれ
   ばそれを使う。渡されていなければユーザーに尋ねる。

   名前は `^[a-z0-9]+(-[a-z0-9]+)*$`(小文字英数字とハイフンのみ、
   kebab-case)に従うこと。日本語・大文字・アンダースコア・空白等を
   含む名前が渡された場合は、**エラーとしてそこで止める**(先に進めな
   い)。命名規則を伝え、英語の kebab-case な名前を渡し直すよう求め
   る。ユーザーの代わりに名前を作って進めてはならない。

   `projects/<name>/` が既に存在する場合は上書きせず、ユーザーに確認する。

2. ディレクトリ一式を作成する:

   ```bash
   mkdir -p projects/<name>/docs/images
   mkdir -p projects/<name>/docs/tables
   cp docs/templates/brainstorming-intake.md projects/<name>/docs/brainstorming-intake.md

   mkdir -p projects/<name>/.claude/skills
   mkdir -p projects/<name>/.claude/rules
   touch projects/<name>/.claude/skills/.gitkeep
   touch projects/<name>/.claude/rules/.gitkeep
   ```

   `.claude/skills/` `.claude/rules/` は空のまま用意する。このプロジェ
   クト固有の技・規約が必要になった時点で、その都度ここへ追加する
   (中身を先回りして作らない)。

3. プロジェクト用の `CLAUDE.md` 雛形を置く(空の見出しのみ。中身は
   brainstorming を経て後から埋める):

   ```markdown
   # CLAUDE.md

   このファイルは、このプロジェクト固有の文脈を記す(root の CLAUDE.md
   は全プロジェクト共通の規約のみを記すため、ここには書かない)。

   ## プロジェクト概要

   (brainstorming で固めた後に記載)

   ## ビルド・テスト・起動

   (実装後に記載)

   ## アーキテクチャ

   (brainstorming で決めた構成を記載)
   ```

4. 最小限の `.gitignore` を置く(技術スタックが決まっていない段階な
   ので汎用的な項目のみ):

   ```
   .env
   .env.local
   *.db
   node_modules/
   __pycache__/
   venv/
   .venv/
   ```

5. ユーザーに報告する: `projects/<name>/docs/brainstorming-intake.md`
   を埋めた上で `/superpowers:brainstorming` を実行するよう促す。この
   skill 自身は設計や実装には踏み込まない — 雛形の用意のみが役目。

   併せて、**git init はまだ行っていない**旨を伝える。brainstorming
   を経て実装に入る段階になったら、`projects/<name>/` の中で個別に
   `git init` すること(root repo のコミット履歴とは別系統。root
   repo の git ユーザー設定を読み取り、同じ値を明示的に設定するのを
   忘れないこと — sibling repo からは継承されない)。
