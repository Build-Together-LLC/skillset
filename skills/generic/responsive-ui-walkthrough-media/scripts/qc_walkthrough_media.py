#!/usr/bin/env python3
"""Create QC artifacts for responsive UI walkthrough media.

Outputs:
- desktop.png and mobile.png rendered screenshots for a URL (Chrome required)
- *_contact.jpg contact sheets for GIFs (ffmpeg required)
- summary.json
"""

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def run(cmd):
    return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def chrome_bin():
    for name in ["google-chrome", "chromium", "chromium-browser"]:
        p = shutil.which(name)
        if p:
            return p
    raise SystemExit("No Chrome/Chromium binary found")


def screenshot(url, out, viewport):
    w, h = viewport
    cmd = [
        chrome_bin(),
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        f"--window-size={w},{h}",
        f"--screenshot={out}",
        url,
    ]
    proc = run(cmd)
    return {"file": str(out), "viewport": f"{w}x{h}", "stderr_tail": proc.stderr[-500:]}


def gif_contact_sheet(gif, out_dir, scale_width=720):
    gif = Path(gif)
    out = out_dir / f"{gif.stem}_contact.jpg"
    # Pick first frame of each likely teaching step for 9-frame GIFs: 0, 3, 6.
    # If the GIF has fewer frames, ffmpeg still emits what it can.
    vf = f"select='eq(n,0)+eq(n,3)+eq(n,6)',scale={scale_width}:-1,tile=3x1"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(gif), "-vf", vf, "-frames:v", "1", str(out)]
    run(cmd)
    return str(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="Rendered page URL to capture")
    ap.add_argument("--out", required=True, help="Output QC directory")
    ap.add_argument("--gif", action="append", default=[], help="GIF path to create contact sheet for; repeatable")
    ap.add_argument("--desktop", default="1440x900", help="Desktop viewport, e.g. 1440x900")
    ap.add_argument("--mobile", default="390x844", help="Mobile viewport, e.g. 390x844")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {"screenshots": [], "contact_sheets": []}

    if args.url:
        dw, dh = map(int, args.desktop.lower().split("x"))
        mw, mh = map(int, args.mobile.lower().split("x"))
        summary["screenshots"].append(screenshot(args.url, out_dir / "desktop.png", (dw, dh)))
        summary["screenshots"].append(screenshot(args.url, out_dir / "mobile.png", (mw, mh)))

    for gif in args.gif:
        summary["contact_sheets"].append(gif_contact_sheet(gif, out_dir))

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
