#!/usr/bin/env bash
# Builds a 20 second sample video from examples/demo.html, to check the whole pipeline on a new machine.
#   bash run-example.sh [workdir]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
TOOLS="${FLOWVIDEO_HOME:-$HOME/.cache/flow-video-builder}"
WORK="${1:-$(mktemp -d)}"
mkdir -p "$WORK"
sed "s#{{EXAMPLES_ROOT}}#$HERE#g" "$HERE/flow.example.json" > "$WORK/flow.json"

"$TOOLS/venv/bin/python" "$HERE/../scripts/tts.py" --project "$WORK"
node "$HERE/../scripts/record.js" --project "$WORK"
"$TOOLS/venv/bin/python" "$HERE/../scripts/assemble.py" --project "$WORK"

# The page shows a real-looking host name; the scrub rule in flow.example.json must have replaced it, so the scan finds nothing.
printf '# words that must never appear in the video\nRealperson\n' > "$WORK/terms.txt"
"$TOOLS/venv/bin/python" "$HERE/../scripts/ocr_scan.py" --video "$WORK/out/video.mp4" --terms "$WORK/terms.txt" --every 2
echo "OK: $WORK/out/video.mp4"
