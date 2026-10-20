#!/usr/bin/env bash
# Runs the whole pipeline on the bundled example so you can see what the skill produces.
#   bash run-example.sh [theme]     -> examples/work/Example-Guide-<theme>.docx
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$HERE/../scripts"
HOME_DIR="${DEMO_DOC_HOME:-$HOME/.cache/demo-doc-builder}"
THEME="${1:-green}"
bash "$S/setup.sh" >/dev/null
cd "$HERE"
node "$S/screenshots.js" shots.plan.json
"$HOME_DIR/venv/bin/python" "$S/annotate.py" annotate.plan.json
node "$S/diagram.js" diagrams.plan.json
"$HOME_DIR/venv/bin/python" "$S/build_from_spec.py" spec.json "work/Example-Guide-$THEME.docx" --theme "$THEME"
