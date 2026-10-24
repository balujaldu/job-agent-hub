#!/usr/bin/env bash
# Stop hook: if product files changed since CLAUDE.md was last reviewed, ask Claude
# to bring CLAUDE.md up to date before finishing the turn.
set -euo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
STAMP="$ROOT/.claude/.claude-md-reviewed"
INPUT="$(cat)"

# Second stop after we already asked: let Claude finish (prevents loops).
if [ "$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false')" = "true" ]; then
  exit 0
fi

# Reference point: whichever is newer, CLAUDE.md or the last review stamp.
REF="$STAMP"
if [ ! -f "$STAMP" ] || [ "$ROOT/CLAUDE.md" -nt "$STAMP" ]; then
  REF="$ROOT/CLAUDE.md"
fi
[ -f "$REF" ] || exit 0

CHANGED="$(cd "$ROOT" && find api/app api/tests api/requirements.txt api/.env.example \
    web/app web/components web/lib web/package.json web/next.config.ts dev.sh \
    -type f -newer "$REF" \
    -not -path '*/__pycache__/*' -not -name '*.pyc' -not -name '.DS_Store' 2>/dev/null | sort | head -40)"

[ -z "$CHANGED" ] && exit 0

touch "$STAMP"  # only changes made after this review will trigger the next one

jq -n --arg files "$CHANGED" '{
  decision: "block",
  reason: ("Product files changed since CLAUDE.md was last reviewed:\n" + $files +
    "\n\nCheck whether these changes affect anything CLAUDE.md documents (commands, architecture, data flow, " +
    "safety invariants, conventions, gotchas). If they do, update CLAUDE.md concisely in its existing style; " +
    "do not add file-by-file changelogs. If nothing documented changed, leave it as is. Then mention in one line what you did.")
}'
