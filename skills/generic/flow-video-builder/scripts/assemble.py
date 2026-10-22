"""Join the recorded scenes into one video: title card, recording, narration, subtitles.

    $FLOWVIDEO_HOME/venv/bin/python assemble.py --project DIR

Writes DIR/out/video.mp4 (subtitle track included), video.srt and transcript.md.
"""
import argparse
import json
import os
import re
import subprocess

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("--project", default=".")
args = ap.parse_args()
PROJ = os.path.abspath(args.project)
OUT = os.path.join(PROJ, "out") + "/"
os.makedirs(OUT, exist_ok=True)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
flow = json.load(open(os.path.join(PROJ, "flow.json")))
cfg = flow.get("config", {})
timing = json.load(open(os.path.join(PROJ, "audio", "timing.json")))
W, H = (cfg.get("viewport") or {}).get("width", 1440), (cfg.get("viewport") or {}).get("height", 900)
CARD_S = cfg.get("card_seconds", 2.4)
NAVY = tuple(cfg.get("card_color", [27, 42, 74]))
VF = f"scale={W}:{H}:flags=lanczos,fps=30,format=yuv420p"


def font(bold, size):
    names = ["NotoSans-Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"] if bold else ["NotoSans-Regular.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"]
    for root in ("/usr/share/fonts/truetype/noto", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation", "/System/Library/Fonts/Supplemental", "/Library/Fonts"):
        for n in names:
            p = os.path.join(root, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def run(*a):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *a], check=True)


def card(n, title):
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    d.text((W // 2, H // 2 - 30), title, font=font(True, 54), fill="white", anchor="mm")
    d.text((W // 2, H // 2 + 50), f"Scene {n:02d}", font=font(False, 24), fill=(170, 185, 215), anchor="mm")
    png = OUT + f"card{n:02d}.png"
    im.save(png)
    seg = OUT + f"card{n:02d}.mp4"
    run("-loop", "1", "-framerate", "30", "-i", png, "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono", "-t", str(CARD_S),
        "-vf", f"fade=t=in:st=0:d=0.5,fade=t=out:st={CARD_S - 0.5}:d=0.5," + VF, "-c:v", "libx264", "-crf", "22", "-c:a", "aac", "-b:a", "128k", "-shortest", seg)
    return seg


def srt_time(t):
    return "%02d:%02d:%02d,%03d" % (t // 3600, t % 3600 // 60, t % 60, int((t % 1) * 1000))


def duration(path):
    err = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


segs, srt, t0, n = [], [], 0.0, 0
done = []
for sc in flow["scenes"]:
    meta_p = os.path.join(PROJ, "rec", sc["id"], "meta.json")
    if not os.path.exists(meta_p):
        print("skipped (not recorded):", sc["id"])
        continue
    n += 1
    done.append(sc)
    if cfg.get("cards", True):
        segs.append(card(n, sc["title"]))
        t0 += CARD_S
    m, tm = json.load(open(meta_p)), timing[sc["id"]]
    dur = m["lead"] + tm["total"] + 1.2
    seg = OUT + sc["id"] + ".mp4"
    lead_ms = int(m["lead"] * 1000)
    run("-ss", f"{m['offset']:.3f}", "-t", f"{dur:.3f}", "-i", m["file"], "-i", os.path.join(PROJ, "audio", sc["id"] + ".wav"),
        "-filter_complex", f"[0:v]{VF}[v];[1:a]adelay={lead_ms}|{lead_ms},apad[a]", "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-crf", "22", "-preset", "medium", "-c:a", "aac", "-b:a", "160k", seg)
    ends = tm["starts"][1:] + [tm["total"]]
    for s, a, b in zip(sc["narr"], tm["starts"], ends):
        srt.append((t0 + m["lead"] + a, t0 + m["lead"] + b - 0.3, s))
    t0 += duration(seg)
    segs.append(seg)

open(OUT + "list.txt", "w").write("".join(f"file '{s}'\n" for s in segs))
with open(OUT + "video.srt", "w") as f:
    for i, (a, b, s) in enumerate(srt, 1):
        f.write(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{s}\n\n")
loud = cfg.get("loudnorm", "I=-21:TP=-2:LRA=9")  # soft voice: quieter than the usual -16
run("-f", "concat", "-safe", "0", "-i", OUT + "list.txt", "-i", OUT + "video.srt", "-map", "0:v", "-map", "0:a", "-map", "1",
    "-c:v", "copy", "-af", f"lowpass=f=9000,loudnorm={loud},aresample=44100", "-c:a", "aac", "-b:a", "160k",
    "-c:s", "mov_text", "-metadata:s:s:0", "language=eng", OUT + "video.mp4")
open(OUT + "transcript.md", "w").write("# Transcript\n\n" + "\n".join(f"## Scene {i}: {s['title']}\n\n" + " ".join(s["narr"]) + "\n" for i, s in enumerate(done, 1)))
print("scenes", n, "| seconds", round(t0, 1), "|", OUT + "video.mp4")
