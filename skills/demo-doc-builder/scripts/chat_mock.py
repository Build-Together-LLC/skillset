#!/usr/bin/env python3
"""Draw WhatsApp-style phone screens from a transcript, as sharp PNGs for a guide or a demo deck.

    chat_mock.py transcript.json

{ "title": "School admissions", "subtitle": "business account (demo)", "height": 620, "outDir": "chat",
  "replace": ["http://localhost:8000", "https://school.example"],
  "screens": [ { "name": "c1_confirm",
                 "messages": [ {"day": "Today"}, {"out": "book", "time": "17:06"},
                               {"in": "You already have a meeting booked ...", "time": "17:06"},
                               {"buttons": ["Yes, cancel it", "Keep it"]}, {"choose": true} ],
                 "sheet": {"title": "Pick a day", "rows": ["1. Wed 21 Oct", "2. Thu 22 Oct"], "picked": 1} } ] }

Build the transcript from the REAL strings the product sends (print them from its code), never from memory: the picture then
cannot disagree with the product. "in" is the business, "out" is the parent. "buttons" are quick replies, "choose" is the list
button, "sheet" is the list that opens over the chat. "replace" swaps a real address for an example one. Needs the same setup as
screenshots.js (run setup.sh once). A height of 600 to 650 keeps the empty space at the top small.
"""
import html
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CSS = """
*{box-sizing:border-box;overflow-wrap:anywhere} body{margin:0;background:#cfd8dc;font-family:Roboto,Segoe UI,Helvetica,Arial,sans-serif}
.phone{width:390px;background:#efeae2;position:relative;overflow:hidden;display:flex;flex-direction:column}
.hdr{background:#075e54;color:#fff;padding:12px 14px;display:flex;align-items:center;gap:10px;flex:none}
.av{width:36px;height:36px;border-radius:50%;background:#128c7e;display:flex;align-items:center;justify-content:center;font-weight:700}
.hdr b{display:block;font-size:15px}.hdr small{opacity:.8;font-size:11px}
.chat{flex:1;padding:12px 10px;display:flex;flex-direction:column;gap:6px;overflow:hidden;justify-content:flex-end}
.chip{align-self:center;background:#e1f3fb;color:#54656f;font-size:11px;padding:4px 10px;border-radius:8px;margin:4px 0}
.b{max-width:84%;padding:7px 9px 5px;border-radius:8px;font-size:14px;line-height:1.35;color:#111b21;box-shadow:0 1px .5px rgba(0,0,0,.13);white-space:pre-wrap}
.in{align-self:flex-start;background:#fff;border-top-left-radius:0}.out{align-self:flex-end;background:#d9fdd3;border-top-right-radius:0}
.t{display:block;text-align:right;font-size:10px;color:#667781;margin-top:2px}
.qr{align-self:flex-start;width:84%;display:flex;flex-direction:column;gap:4px;margin-top:-2px}
.qr div,.lbtn{background:#fff;color:#027eb5;text-align:center;padding:9px;border-radius:8px;font-size:14px;font-weight:500;box-shadow:0 1px .5px rgba(0,0,0,.13)}
.lbtn{align-self:flex-start;width:84%;margin-top:-2px}
.sheet{position:absolute;left:0;right:0;bottom:0;background:#fff;border-radius:16px 16px 0 0;box-shadow:0 -4px 14px rgba(0,0,0,.25);padding:10px 0 6px}
.sheet h4{margin:2px 16px 8px;font-size:15px;color:#111b21}.row{display:flex;align-items:center;justify-content:space-between;padding:11px 16px;font-size:14px;border-top:1px solid #f0f2f5;color:#111b21}
.dot{width:16px;height:16px;border:2px solid #8696a0;border-radius:50%}.dot.on{border-color:#00a884;background:radial-gradient(#00a884 40%,#fff 45%)}
.shade{position:absolute;inset:0;background:rgba(0,0,0,.35)}
.bar{flex:none;background:#f0f2f5;padding:8px 10px;display:flex;gap:8px;align-items:center}.bar i{flex:1;background:#fff;border-radius:20px;height:34px;display:block;color:#8696a0;font-style:normal;font-size:13px;padding:8px 14px}
"""


def screen_html(spec, plan):
    old, new = plan.get("replace", ["", ""])
    esc = lambda t: html.escape(t.replace(old, new) if old else t)
    parts = []
    for m in spec["messages"]:
        if "day" in m:
            parts.append(f'<div class="chip">{esc(m["day"])}</div>')
        elif "in" in m or "out" in m:
            kind = "in" if "in" in m else "out"
            tick = " ✓✓" if kind == "out" else ""
            parts.append(f'<div class="b {kind}">{esc(m[kind])}<span class="t">{m.get("time", "10:30")}{tick}</span></div>')
        elif "buttons" in m:
            parts.append('<div class="qr">' + "".join(f"<div>{esc(b)}</div>" for b in m["buttons"]) + "</div>")
        elif m.get("choose"):
            parts.append('<div class="lbtn">☰ Choose</div>')
    sheet = ""
    if spec.get("sheet"):
        s = spec["sheet"]
        rows = "".join(f'<div class="row"><span>{esc(r)}</span><span class="dot{" on" if k == s.get("picked", -1) else ""}"></span></div>' for k, r in enumerate(s["rows"]))
        sheet = f'<div class="shade"></div><div class="sheet"><h4>{esc(s["title"])}</h4>{rows}</div>'
    return (f'<!doctype html><meta charset=utf-8><style>{CSS}.phone{{height:{plan.get("height", 620)}px}}</style><div class="phone">'
            f'<div class="hdr"><div class="av">{esc(plan.get("title", "W")[:1])}</div><div><b>{esc(plan.get("title", ""))}</b>'
            f'<small>{esc(plan.get("subtitle", ""))}</small></div></div><div class="chat">{"".join(parts)}</div>'
            f'<div class="bar"><i>Message</i></div>{sheet}</div>')


def main(path):
    plan = json.load(open(path))
    base = os.path.dirname(os.path.abspath(path))
    out = os.path.join(base, plan.get("outDir", "chat"))
    os.makedirs(os.path.join(out, "html"), exist_ok=True)
    for spec in plan["screens"]:
        open(os.path.join(out, "html", spec["name"] + ".html"), "w").write(screen_html(spec, plan))
    shots = {"base": "file://" + out, "outDir": "png", "scale": 2, "viewport": {"width": 390, "height": plan.get("height", 620)},
             "shots": [{"name": s["name"], "url": f"/html/{s['name']}.html", "wait": 400} for s in plan["screens"]]}
    json.dump(shots, open(os.path.join(out, "plan.json"), "w"), indent=1)
    subprocess.run(["node", os.path.join(HERE, "screenshots.js"), os.path.join(out, "plan.json")], check=True)
    print("phone screens in", os.path.join(out, "png"))


if __name__ == "__main__":
    main(sys.argv[1])
