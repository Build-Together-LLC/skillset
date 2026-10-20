"""demoslides: turn a demo into a presentation-style .docx (one slide per landscape page).

Built on demodoc. A presenter opens the .docx and pages through it like slides: big numbered screenshots,
a few lines of speaker text, no setup instructions.

    import demoslides as s
    s.init(theme="green", footer="Product: live demo", title="Product: live demo")
    s.cover("Product", "Live demo", rows=[["Time", "20 minutes"]], note="All data is fictional.")
    s.slide("1  Open the page")
    s.split("02_picker.png", [("1", "**Warehouse** is required."), ("2", "**Supplier** is optional.")], image_w=5.8)
    s.slide("2  Two views")
    s.pair("a.png", "b.png", "**User A** sees ...", "**User B** sees ...")
    s.alone("diagram.png", 9.4)                       # one centred picture
    s.quad(["1.png", "2.png", "3.png"], ["**1** ...", "**2** ...", "**3** ..."], width=2.3)   # steps or phone screens
    s.say("Introduce the safety net before the first click.")
    s.save("demo.docx")

Layout rules learned the hard way (see references/presentation-demo.md):
- every table column gets an explicit width, otherwise Word/LibreOffice split the row 50/50 and clip the picture
- keep a slide to one page: tall phone shots <= 2.4 in wide, full-page screenshots <= 5.9 in wide in a split
- pass crop=(x1, y1, x2, y2) in image pixels to show part of a tall screenshot on its own slide
"""

import os
import tempfile

import demodoc as d
from docx.enum.section import WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from PIL import Image

SLIDE_W = 10.5
_TMP = tempfile.mkdtemp(prefix="demoslides-")


def init(theme="green", footer="", author="", title="", margins=0.6, page="A4"):
    doc = d.init(theme=theme, page=page, footer=footer, author=author, title=title, margins=margins)
    section = doc.sections[0]
    width, height = section.page_width, section.page_height
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = max(width, height), min(width, height)
    d.S["width"] = SLIDE_W
    return doc


def slide(title):
    d.h1(title, page_break=True)


def say(text):
    d.p(f"*Say:* {text}", color="475569", size=11)


def note(text):
    d.p(f"*{text}*", size=11, color="475569")


def _no_borders(table):
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "nil")
        borders.append(element)
    table._tbl.tblPr.append(borders)


def _widths(table, widths):
    table.autofit = False
    for column, width in zip(table.columns, widths):
        column.width = Inches(width)
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            cell.width = Inches(width)


def _prepared(path, crop):
    if not crop:
        return path
    out = os.path.join(_TMP, f"{abs(hash((path, crop)))}.png")
    Image.open(path).crop(crop).save(out)
    return out


def _gap():
    d.S["doc"].add_paragraph().paragraph_format.space_after = 0


MAX_PICTURE_H = 5.25


def split(image, items, image_w=5.6, heading=None, crop=None):
    """Picture on the left, numbered speaker points on the right. items = [("1", "text"), ...].

    The width shrinks when the picture is tall, so the slide stays on one page.
    """
    image_w = d.fit(_prepared(image, crop), image_w, MAX_PICTURE_H)
    table = d.S["doc"].add_table(rows=1, cols=2)
    _no_borders(table)
    left_w, right_w = image_w + 0.15, SLIDE_W - image_w - 0.3
    _widths(table, [left_w, right_w])
    left, right = table.rows[0].cells
    left.paragraphs[0].add_run().add_picture(_prepared(image, crop), width=Inches(image_w))
    first = True
    if heading:
        d.rich(right.paragraphs[0], f"**{heading}**", size=13, color=d.THEMES[_theme_name()]["primary"])
        first = False
    for number, text in items:
        paragraph = right.paragraphs[0] if first else right.add_paragraph()
        first = False
        paragraph.paragraph_format.space_after = Pt(7)
        d.rich(paragraph, (f"**{number}**   " if number else "") + text, size=12)
    _gap()


def pair(left_image, right_image, left_caption, right_caption, width=5.05, right_width=None):
    """Two pictures side by side with a caption under each."""
    table = d.S["doc"].add_table(rows=2, cols=2)
    _no_borders(table)
    _widths(table, [SLIDE_W / 2, SLIDE_W / 2])
    for index, (image, caption) in enumerate(((left_image, left_caption), (right_image, right_caption))):
        use = right_width if (index == 1 and right_width) else width
        table.rows[0].cells[index].paragraphs[0].add_run().add_picture(image, width=Inches(use))
        d.rich(table.rows[1].cells[index].paragraphs[0], caption, size=12)
    _gap()


def alone(image, width):
    """One picture centred on the slide, for a diagram or a wide screenshot."""
    paragraph = d.S["doc"].add_paragraph()
    paragraph.alignment = 1
    paragraph.paragraph_format.space_after = Pt(2)
    paragraph.add_run().add_picture(image, width=Inches(width))


def quad(images, captions, width=2.4):
    """A row of pictures (phone screens, steps), each with its own caption underneath."""
    table = d.S["doc"].add_table(rows=2, cols=len(images))
    _no_borders(table)
    _widths(table, [SLIDE_W / len(images)] * len(images))
    for index, (image, caption) in enumerate(zip(images, captions)):
        top, bottom = table.rows[0].cells[index], table.rows[1].cells[index]
        top.paragraphs[0].alignment = bottom.paragraphs[0].alignment = 1
        top.paragraphs[0].add_run().add_picture(image, width=Inches(width))
        d.rich(bottom.paragraphs[0], caption, size=11)
    _gap()


def _theme_name():
    theme = d.S["theme"]
    for name, value in d.THEMES.items():
        if value is theme:
            return name
    return "green"


cover = d.cover
fit = d.fit
table = d.table
img = d.img
bullets = d.bullets
p = d.p
save = d.save
