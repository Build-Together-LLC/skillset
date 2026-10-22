#!/usr/bin/env bash
# One-time setup for flow-video-builder. Everything goes into its own folder, never into a project environment.
#   bash setup.sh                 # default voice en_US-amy-medium
#   bash setup.sh en_GB-jenny_dioco-medium
# Needs: python3 with venv, node 18+, npm, a Chrome or Chromium browser.
set -euo pipefail

HOME_DIR="${FLOWVIDEO_HOME:-$HOME/.cache/flow-video-builder}"
VOICE="${1:-en_US-amy-medium}"
mkdir -p "$HOME_DIR/voices"
cd "$HOME_DIR"

if [ ! -x venv/bin/python ]; then
  python3 -m venv venv
fi
# piper-tts: offline neural voice (CPU). imageio-ffmpeg: bundled ffmpeg. pillow: title cards. rapidocr: privacy scan of the finished video.
venv/bin/python -m pip install -q --upgrade pip
venv/bin/python -m pip install -q piper-tts imageio-ffmpeg pillow numpy rapidocr_onnxruntime

if [ ! -d node_modules/playwright-core ]; then
  [ -f package.json ] || echo '{"name":"flow-video-builder-tools","private":true}' > package.json
  npm install --silent playwright-core
fi
# Playwright needs its own small ffmpeg build to record video.
node node_modules/playwright-core/cli.js install ffmpeg

if [ ! -f "voices/$VOICE.onnx" ]; then
  venv/bin/python -m piper.download_voices "$VOICE" --data-dir voices
fi

for c in "${CHROME_PATH:-}" /usr/bin/google-chrome /usr/bin/google-chrome-stable /usr/bin/chromium /usr/bin/chromium-browser; do
  [ -n "$c" ] && [ -x "$c" ] && { echo "browser: $c"; break; }
done || true
echo "ready: $HOME_DIR (voice $VOICE)"
echo "If the browser line is missing, install Chrome or Chromium, or set CHROME_PATH."
