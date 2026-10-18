#!/usr/bin/env bash
# Convert a .docx to PDF and build contact sheets (8 pages each) so you can SEE the layout.
#   render_check.sh guide.docx          -> prints the sheet paths
# Look at every sheet before you hand the document over.
set -euo pipefail
DOCX="$(realpath "$1")"
HOME_DIR="${DEMO_DOC_HOME:-$HOME/.cache/demo-doc-builder}"
OUT="${DEMO_DOC_RENDER:-$HOME/demo-doc-render}"   # not hidden: a snap libreoffice cannot use dot-folders
rm -rf "$OUT" && mkdir -p "$OUT"
SOFFICE="$(command -v soffice || command -v libreoffice || ls /snap/bin/libreoffice 2>/dev/null | head -1 || true)"
[ -n "$SOFFICE" ] || { echo "libreoffice not installed, cannot render"; exit 2; }
# Convert a copy that lives in a non-hidden folder (snap libreoffice cannot touch ~/.claude or ~/.cache).
cp "$DOCX" "$OUT/input.docx"
timeout 240 "$SOFFICE" --headless --convert-to pdf --outdir "$OUT" "$OUT/input.docx" >/dev/null 2>&1
PDF="$OUT/input.pdf"
pdfinfo "$PDF" | grep Pages
pdftoppm -r 55 -png "$PDF" "$OUT/p"
"$HOME_DIR/venv/bin/python" - "$OUT" <<'PY'
import glob, sys
from PIL import Image
out = sys.argv[1]
files = sorted(glob.glob(f"{out}/p-*.png"))
for k in range(0, len(files), 8):
    ims = [Image.open(f) for f in files[k:k + 8]]
    w, h = ims[0].size
    sheet = Image.new("RGB", (w * 4, h * 2), "white")
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % 4) * w, (i // 4) * h))
    sheet.save(f"{out}/sheet{k // 8}.png")
    print(f"{out}/sheet{k // 8}.png")
PY
echo "pdf: $PDF"
