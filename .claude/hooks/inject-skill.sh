#!/bin/bash
# 使い方: inject-skill.sh <skill名> ["有効化メッセージ"]
set -euo pipefail

SKILL_NAME="$1"
MESSAGE="${2:-セッション開始時から ${SKILL_NAME} モードを有効化し、以降毎ターン維持せよ。以下がそのルール定義:}"
SKILL_PATH="$CLAUDE_PROJECT_DIR/.claude/skills/${SKILL_NAME}/SKILL.md"

if [ ! -f "$SKILL_PATH" ]; then
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":\"[警告] Skill '${SKILL_NAME}' が見つかりません: ${SKILL_PATH}\"}}"
  exit 0
fi

BODY=$(awk '{gsub(/\r$/,"")} /^---$/{c++;next} c>=2' "$SKILL_PATH")

jq -Rs --arg msg "$MESSAGE" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:($msg + "\n\n" + .)}}' <<< "$BODY"
