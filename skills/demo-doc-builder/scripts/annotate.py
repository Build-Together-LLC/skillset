#!/usr/bin/env python3
"""Annotate screenshots: boxes, numbered badges, arrows, labels, and pixelate/blur for secrets.

    annotate.py plan.json

plan.json ("scale": 2 for screenshots taken with a device pixel ratio of 2: coordinates stay in CSS pixels,
boxes, badges and fonts are scaled up so the marks look the same size):
{ "color": "#DC2626", "scale": 1,
  "items": [ { "src": "shots/a.png", "out": "img/a.png",
               "ops": [ {"rect": [x1,y1,x2,y2]},
                        {"badge": [1, x, y]},
                        {"arrow": [x1,y1,x2,y2]},
                        {"text":  [x, y, "label"]},
                        {"pixelate": [x1,y1,x2,y2, "QR hidden"]},
                        {"blur": [x1,y1,x2,y2]} ] } ] }

Always pixelate QR codes, tokens, e-mail addresses and anything personal before a screenshot is used.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def font(size):
    for f in FONTS:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def pixelate(im, box, label=None, color=(220, 38, 38), block=18, scale=1):
    x1, y1, x2, y2 = box
    block = block * scale
    small = im.crop(box).resize((max((x2 - x1) // block, 1), max((y2 - y1) // block, 1)), Image.NEAREST)
    im.paste(small.filter(ImageFilter.GaussianBlur(0.5)).resize((x2 - x1, y2 - y1), Image.NEAREST), box)
    if label:
        d = ImageDraw.Draw(im)
        f = font(18 * scale)
        w = d.textlength(label, font=f)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        d.rounded_rectangle((cx - w / 2 - 12 * scale, cy - 18 * scale, cx + w / 2 + 12 * scale, cy + 18 * scale), 8 * scale, fill=(255, 255, 255), outline=color, width=2 * scale)
        d.text((cx - w / 2, cy - 11 * scale), label, font=f, fill=color)


def blur(im, box, radius=14):
    im.paste(im.crop(box).filter(ImageFilter.GaussianBlur(radius)), box)


def annotate(src, out, ops, color="#DC2626", scale=1):
    col = rgb(color)
    im = Image.open(src).convert("RGB")
    for op in ops:                      # redactions first, so marks are drawn on top
        if "pixelate" in op:
            args = op["pixelate"]
            box = tuple(v * scale for v in args[:4])
            pixelate(im, box, args[4] if len(args) > 4 else None, col, scale=scale)
        elif "blur" in op:
            blur(im, tuple(v * scale for v in op["blur"][:4]), 14 * scale)
    d = ImageDraw.Draw(im)
    fb, ft = font(15 * scale), font(16 * scale)
    for op in ops:
        if "rect" in op:
            d.rectangle(tuple(v * scale for v in op["rect"]), outline=col, width=3 * scale)
        elif "badge" in op:
            n, x, y = op["badge"]
            x, y, r = x * scale, y * scale, 13 * scale
            d.ellipse((x - r, y - r, x + r, y + r), fill=col, outline=(255, 255, 255), width=2 * scale)
            w = d.textlength(str(n), font=fb)
            d.text((x - w / 2, y - 9 * scale), str(n), font=fb, fill=(255, 255, 255))
        elif "arrow" in op:
            x1, y1, x2, y2 = [v * scale for v in op["arrow"]]
            d.line((x1, y1, x2, y2), fill=col, width=4 * scale)
            import math
            a = math.atan2(y2 - y1, x2 - x1)
            for s in (-0.5, 0.5):
                d.line((x2, y2, x2 - 16 * scale * math.cos(a + s), y2 - 16 * scale * math.sin(a + s)), fill=col, width=4 * scale)
        elif "text" in op:
            x, y, label = op["text"]
            x, y = x * scale, y * scale
            w = d.textlength(label, font=ft)
            d.rounded_rectangle((x - 6 * scale, y - 4 * scale, x + w + 6 * scale, y + 24 * scale), 6 * scale, fill=(255, 255, 255), outline=col, width=2 * scale)
            d.text((x, y), label, font=ft, fill=col)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    im.save(out)
    return out


def main(plan_path):
    plan = json.load(open(plan_path))
    base = os.path.dirname(os.path.abspath(plan_path))
    for item in plan["items"]:
        src = item["src"] if os.path.isabs(item["src"]) else os.path.join(base, item["src"])
        out = item["out"] if os.path.isabs(item["out"]) else os.path.join(base, item["out"])
        print("annotated", annotate(src, out, item.get("ops", []), plan.get("color", "#DC2626"), item.get("scale", plan.get("scale", 1))))


if __name__ == "__main__":
    main(sys.argv[1])
