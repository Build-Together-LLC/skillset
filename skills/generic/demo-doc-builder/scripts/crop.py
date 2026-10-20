#!/usr/bin/env python3
"""Crop screenshots by CSS pixels, so the numbers in a plan match what you saw in the browser.

    crop.py plan.json
    { "scale": 2, "items": [ {"src": "shots/a.png", "out": "final/a.png", "box": [x1, y1, x2, y2]},
                              {"src": "shots/b.png", "out": "final/b.png", "box": [0, 120, null, 900]} ] }

box is [left, top, right, bottom] in CSS pixels; null means the edge of the image. The scale (device pixel ratio the
screenshot was taken at) is applied for you. Crop the app's sidebar off, and cut tall pages into the part you talk about.
"""
import json
import os
import sys

from PIL import Image


def main(plan_path):
    plan = json.load(open(plan_path))
    base = os.path.dirname(os.path.abspath(plan_path))
    for item in plan["items"]:
        scale = item.get("scale", plan.get("scale", 1))
        src, out = (p if os.path.isabs(p) else os.path.join(base, p) for p in (item["src"], item["out"]))
        im = Image.open(src).convert("RGB")
        left, top, right, bottom = item["box"]
        box = (left * scale, top * scale, min((right * scale) if right is not None else im.width, im.width),
               min((bottom * scale) if bottom is not None else im.height, im.height))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        im.crop(tuple(int(v) for v in box)).save(out)
        print("cropped", out)


if __name__ == "__main__":
    main(sys.argv[1])
