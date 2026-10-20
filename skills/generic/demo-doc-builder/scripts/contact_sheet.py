#!/usr/bin/env python3
"""Put many images on one sheet, labelled, so you can look at all of them in a single view.

    contact_sheet.py out.png a.png b.png c.png ... [--cols 3] [--w 800] [--h 560] [--top]

Use it before a screenshot goes into a document: one look at the sheet shows a blank page, a stray popup, a cropped title,
a real name or an empty list. --top keeps only the top of tall pages. The sheet is for you, not for the document.
"""
import argparse

from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--w", type=int, default=800)
    ap.add_argument("--h", type=int, default=560)
    ap.add_argument("--top", action="store_true", help="show only the top part of tall images")
    a = ap.parse_args()
    rows = (len(a.images) + a.cols - 1) // a.cols
    sheet = Image.new("RGB", (a.cols * a.w, rows * (a.h + 22)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(a.images):
        im = Image.open(path).convert("RGB")
        if a.top:
            im = im.crop((0, 0, im.width, min(im.height, int(im.width * a.h / a.w))))
        im.thumbnail((a.w, a.h))
        x, y = (i % a.cols) * a.w, (i // a.cols) * (a.h + 22)
        sheet.paste(im, (x, y + 22))
        draw.text((x + 4, y + 5), path.split("/")[-1], fill="red")
    sheet.save(a.out)
    print("sheet", a.out, sheet.size)


if __name__ == "__main__":
    main()
