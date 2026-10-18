#!/usr/bin/env python3
"""Build a .docx from a JSON spec using demodoc.

    build_from_spec.py spec.json out.docx [--theme green|navy|blue|purple|orange|teal|slate]

Spec keys: theme, page (A4|Letter), footer, title, author, cover{title,subtitle,rows,note},
contents[[part, what]], blocks[...]. Block types (all text supports **bold**, *italic*, `code`,
[[label|url]] and bare URLs, which become hyperlinks):
  h1 h2 h3        {"type":"h1","text":"...","page_break":false}
  p               {"type":"p","text":"..."}
  bullets steps   {"type":"steps","items":["...", "..."]}
  code            {"type":"code","title":"Terminal","text":"line1\\nline2"}
  callout         {"type":"callout","kind":"NOTE|TIP|WARNING|EXAMPLE|SECURITY","text":"..."}
  table           {"type":"table","rows":[[hdr...],[...]],"widths":[2,4],"caption":"...","label":"x"}
  img             {"type":"img","path":"a.png","caption":"...","width":6.3,"label":"a"}
  expect          {"type":"expect","text":"..."}
  pagebreak spacer
Use {fig:label} / {tbl:label} in text to refer to a figure or table number.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demodoc as d  # noqa: E402


def build(spec, out, base, theme=None):
    d.init(theme=theme or spec.get("theme", "green"), page=spec.get("page", "A4"), footer=spec.get("footer", ""),
           author=spec.get("author", ""), title=spec.get("title", ""))
    if spec.get("cover"):
        c = spec["cover"]
        d.cover(c["title"], c.get("subtitle"), c.get("rows"), c.get("note"))
    if spec.get("contents"):
        d.h1("What is inside")
        d.contents(spec["contents"])
    for b in spec["blocks"]:
        t = b["type"]
        if t in ("h1", "h2", "h3"):
            getattr(d, t)(b["text"], *([b.get("page_break", False)] if t == "h1" else []))
        elif t == "p":
            d.p(b["text"])
        elif t in ("bullets", "steps"):
            getattr(d, t)(b["items"])
        elif t == "code":
            d.code(b["text"], b.get("title"))
        elif t == "callout":
            d.callout(b["kind"], b["text"])
        elif t == "table":
            d.table(b["rows"], b.get("widths"), b.get("header", True), b.get("font"), b.get("caption"), b.get("label"))
        elif t == "img":
            path = b["path"] if os.path.isabs(b["path"]) else os.path.join(base, b["path"])
            d.img(path, b.get("caption"), b.get("width", 6.3), b.get("label"))
        elif t == "expect":
            d.expect(b["text"])
        elif t == "pagebreak":
            d.pagebreak()
        elif t == "spacer":
            d.spacer()
        else:
            raise SystemExit(f"unknown block type: {t}")
    return d.save(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--theme")
    a = ap.parse_args()
    print("saved", build(json.load(open(a.spec)), a.out, os.path.dirname(os.path.abspath(a.spec)), a.theme))
