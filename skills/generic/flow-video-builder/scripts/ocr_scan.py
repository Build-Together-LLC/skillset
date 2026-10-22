"""Read the text in the finished video and fail if a forbidden word shows up (real names, work email addresses, keys).

    $FLOWVIDEO_HOME/venv/bin/python ocr_scan.py --video out/video.mp4 --terms terms.txt [--every 2] [--from 0 --to 120]

terms.txt: one term per line, matched case-insensitively. A line starting with re: is a regular expression.
Exit code 1 when anything is found, with the time of each hit so the scene can be fixed and recorded again.
Text recognition can miss small or blurred text, so use it as a net under the masking rules, not instead of them.
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile

import imageio_ffmpeg
from rapidocr_onnxruntime import RapidOCR

ap = argparse.ArgumentParser()
ap.add_argument("--video", required=True)
ap.add_argument("--terms", required=True)
ap.add_argument("--every", type=float, default=2.0, help="seconds between frames")
ap.add_argument("--from", dest="start", type=float, default=0.0)
ap.add_argument("--to", dest="end", type=float, default=0.0, help="0 means the whole video")
args = ap.parse_args()

parts = []
for line in open(args.terms):
    line = line.strip()
    if line and not line.startswith("#"):
        parts.append(line[3:] if line.startswith("re:") else re.escape(line.lower()))
rx = re.compile("|".join(parts), re.I)

tmp = tempfile.mkdtemp(prefix="ocrscan_")
cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-ss", str(args.start)]
if args.end:
    cmd += ["-t", str(args.end - args.start)]
cmd += ["-i", args.video, "-vf", f"fps=1/{args.every}", os.path.join(tmp, "f_%05d.png")]
subprocess.run(cmd, check=True)
frames = sorted(glob.glob(os.path.join(tmp, "f_*.png")))
ocr = RapidOCR()
hits = 0
for i, f in enumerate(frames):
    res, _ = ocr(f)
    found = sorted(set(rx.findall(" ".join(r[1] for r in (res or [])))))
    if found:
        hits += 1
        print("HIT t=%ds" % (args.start + i * args.every), found, flush=True)
    os.remove(f)
print("scanned %d frames, %d with hits" % (len(frames), hits))
sys.exit(1 if hits else 0)
