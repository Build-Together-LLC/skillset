"""Create a new video project folder with a starter flow.json and terms.txt.

    python new_project.py DIR --base http://localhost:8000 [--login]
"""
import argparse
import json
import os

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("--base", default="http://localhost:8000")
ap.add_argument("--login", action="store_true", help="add a login block that reads DEMO_USER and DEMO_PASSWORD from the environment")
a = ap.parse_args()
os.makedirs(a.dir, exist_ok=True)
cfg = {"base": a.base, "viewport": {"width": 1440, "height": 900}, "voice": "en_US-amy-medium", "speed": 1.14, "scrub": []}
if a.login:
    cfg["login"] = {"url": "/login", "fill": {"#login_email": "${DEMO_USER}", "#login_password": "${DEMO_PASSWORD}"}, "submit": "#login_password", "wait": 7000}
flow = {"config": cfg, "scenes": [
    {"id": "s01", "title": "The first screen", "url": "/", "ready": 3500,
     "narr": ["Say what this screen is.", "Then say why it matters."],
     "steps": [{"s": 1, "do": "hl", "sel": "h1"}]}]}
path = os.path.join(a.dir, "flow.json")
if os.path.exists(path):
    raise SystemExit(path + " already exists")
json.dump(flow, open(path, "w"), indent=1)
open(os.path.join(a.dir, "terms.txt"), "w").write("# Words that must never appear in the video: real names, email domains. A re: line is a regular expression.\n")
open(os.path.join(a.dir, ".gitignore"), "w").write("audio/\nrec/\nout/\n")
print("created", path)
