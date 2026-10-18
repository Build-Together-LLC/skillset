import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import demoslides as s

IMG = os.path.join(HERE, "work", "img")
sample = next((os.path.join(IMG, f) for f in sorted(os.listdir(IMG)) if f.endswith(".png")), None) if os.path.isdir(IMG) else None

s.init(theme="green", footer="Acme: live demo", title="Acme: live demo")
s.cover("Acme", "Live demo", rows=[["Time", "10 minutes"], ["Data", "Fictional"]], note="Every value is an example.")
s.slide("1  The idea")
s.table([["Today", "With Acme"], ["Typed by hand", "Read and checked"]], widths=[5.2, 5.3], caption="Before and after")
s.say("One sentence on why this exists.")
if sample:
    s.slide("2  A screen")
    s.split(sample, [("1", "**First** thing to say."), ("2", "**Second** thing to say.")], image_w=5.6)
s.save(os.path.join(HERE, "Slides-Example.docx"))
print("built", os.path.join(HERE, "Slides-Example.docx"))
