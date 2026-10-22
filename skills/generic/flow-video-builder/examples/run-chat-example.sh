#!/usr/bin/env bash
# Builds a chat-replay video from templates/chat.html. Needs only a browser: no app, no login.
#   bash run-chat-example.sh [workdir]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
TOOLS="${FLOWVIDEO_HOME:-$HOME/.cache/flow-video-builder}"
WORK="${1:-$(mktemp -d)}"
mkdir -p "$WORK"
sed "s#{{SKILL_ROOT}}#$ROOT#g" "$HERE/chat-flow.example.json" > "$WORK/flow.json"
"$TOOLS/venv/bin/python" "$ROOT/scripts/tts.py" --project "$WORK"
node "$ROOT/scripts/record.js" --project "$WORK"
"$TOOLS/venv/bin/python" "$ROOT/scripts/assemble.py" --project "$WORK"
echo "OK: $WORK/out/video.mp4"
