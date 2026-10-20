#!/usr/bin/env bash
# One-time (and idempotent) setup for demo-doc-builder.
# Creates ~/.cache/demo-doc-builder with a Python venv (python-docx, Pillow) and playwright-core.
set -euo pipefail
HOME_DIR="${DEMO_DOC_HOME:-$HOME/.cache/demo-doc-builder}"
mkdir -p "$HOME_DIR"

if [ ! -x "$HOME_DIR/venv/bin/python" ]; then
  python3 -m venv "$HOME_DIR/venv"
fi
"$HOME_DIR/venv/bin/pip" install -q --upgrade python-docx pillow

if [ ! -d "$HOME_DIR/node_modules/playwright-core" ]; then
  (cd "$HOME_DIR" && { [ -f package.json ] || npm init -y >/dev/null; } && npm install --silent playwright-core)
fi

find_browser() {
  for b in "${CHROME:-}" /usr/bin/google-chrome /usr/bin/google-chrome-stable /usr/bin/chromium /usr/bin/chromium-browser; do
    [ -n "$b" ] && [ -x "$b" ] && { echo "$b"; return; }
  done
  ls "$HOME"/.cache/ms-playwright/chromium-*/chrome-linux*/chrome 2>/dev/null | head -1
}
BROWSER="$(find_browser || true)"
SOFFICE="$(command -v soffice || command -v libreoffice || ls /snap/bin/libreoffice 2>/dev/null || true)"

echo "demo-doc-builder home : $HOME_DIR"
echo "python (docx, PIL)    : $HOME_DIR/venv/bin/python"
echo "playwright-core       : $HOME_DIR/node_modules/playwright-core"
echo "browser               : ${BROWSER:-NOT FOUND (install Chrome or set CHROME=/path)}"
echo "libreoffice (preview) : ${SOFFICE:-not found (render check will be skipped)}"
echo "pdftoppm (preview)    : $(command -v pdftoppm || echo not found)"
