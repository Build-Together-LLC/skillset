"""EXAMPLE: work/shots -> work/annot (numbered badges) -> work/final (the names the document uses).

Copy it and list your own shots. Badges come from boxes.json, written by the screenshot harness in image pixels, so annotate.py needs no coordinates.
Pictures that need two or three states are shot as pieces, cropped to a band around their target and stacked, so a slide stays on one page.
"""
import json, os, shutil, subprocess
from PIL import Image

B = os.path.dirname(os.path.abspath(__file__))
SH, AN, FI = (os.path.join(B, "work", d) for d in ("shots", "annot", "final"))
os.makedirs(AN, exist_ok=True); os.makedirs(FI, exist_ok=True)
boxes = json.load(open(SH + "/boxes.json"))
BADGED = ["01_form", "02_refused"]                       # shots that get numbered badges
PY = os.path.expanduser("~/.cache/demo-doc-builder/venv/bin/python")
SKILL = "<path to the demo-doc-builder skill>"

plan = {"scale": 2, "color": "#DC2626", "boxes": SH + "/boxes.json", "items": []}
for n in BADGED:
    plan["items"].append({"src": f"{SH}/{n}.png", "out": f"{AN}/{n}.png", "ops": [{"box": [n, int(k)]} for k in sorted(boxes[n], key=int)]})
json.dump(plan, open(B + "/work/annotate.plan.json", "w"), indent=1)
subprocess.run([PY, f"{SKILL}/scripts/annotate.py", B + "/work/annotate.plan.json"], check=True)


def pick(n):
    a = f"{AN}/{n}.png"
    return a if os.path.exists(a) else f"{SH}/{n}.png"


def crop_around(name, key, above, below):
    """Keep a band around the target box (css px, scale 2). Returns the name of the cropped piece."""
    im = Image.open(f"{SH}/{name}.png").convert("RGB")
    x1, y1, x2, y2 = boxes[name][key]
    top, bot = max(int((y1 - above) * 2), 0), min(int((y2 + below) * 2), im.height)
    im.crop((0, top, im.width, bot)).save(f"{AN}/{name}_crop.png")
    return name + "_crop"


def stack(parts, out, gap=28):
    ims = [Image.open(pick(p)).convert("RGB") for p in parts]
    w = max(i.width for i in ims)
    sheet = Image.new("RGB", (w, sum(i.height for i in ims) + gap * (len(ims) - 1)), (255, 255, 255))
    y = 0
    for i in ims:
        sheet.paste(i, (0, y)); y += i.height + gap
    sheet.save(out)


shutil.copy(pick("01_form"), f"{FI}/01_form.png")
stack(["02_refused", crop_around("03_list", "1", 70, 60)], f"{FI}/02_two_states.png")
print(len(os.listdir(FI)), "files in work/final")
