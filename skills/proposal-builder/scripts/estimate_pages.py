#!/usr/bin/env python3
"""Estimate the rendered page count of a docbuilder .docx, and show where the pages go.

LibreOffice fails silently headless on this machine (exits 0, writes no PDF), so a real
conversion is not available. This simulates the house layout instead: US Letter, 0.75"
margins, Times New Roman 12pt body at 1.15 spacing (~41 lines/page), 11pt table text,
and an H1 page break before every section.

Calibration: a proposal this model scored 63 rendered as 62 actual pages -> factor 0.98,
i.e. the model is close to 1:1 once the H1 page breaks are simulated. Treat the output as
+/-10%, and always report it to the user as an estimate rather than a rendered count.

Usage:
    python estimate_pages.py FILE.docx [FILE2.docx ...]
    python estimate_pages.py --breakdown FILE.docx
"""
import math
import sys

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

CHARS_PER_BODY_LINE = 92     # TNR 12pt across a 6.5" text column
CHARS_PER_TBL_INCH = 13.0    # TNR 11pt inside a table cell
LINES_PER_PAGE = 41.0
TBL_LINE = 0.85              # a table line is tighter than a body line
TBL_ROW_CHROME = 0.25        # cell padding and borders, per row
CALIBRATION = 0.98           # model -> observed (63 modelled == 62 rendered)


def _row_lines(row, per_col_inches):
    """Tallest cell in the row, in lines."""
    return max(
        max(1, math.ceil(len(c.text) / max(6.0, per_col_inches * CHARS_PER_TBL_INCH)))
        for c in row.cells
    )


def walk(path):
    """Yield (section_title, element_kind, line_cost) for every body element."""
    doc = Document(path)
    section = "COVER"
    for block in doc.element.body.iterchildren():
        tag = block.tag.split("}")[1]
        if tag == "p":
            p = Paragraph(block, doc)
            text = p.text.strip()
            if p.style.name == "Heading 1":
                section = p.text[:44]
                yield section, "h1", 2.2
                continue
            if not text:
                yield section, "blank", 0.35
                continue
            lines = max(1, math.ceil(len(text) / CHARS_PER_BODY_LINE))
            extra = 0.9 if p.style.name.startswith("Heading") else 0.35
            yield section, "p", lines + extra
        elif tag == "tbl":
            table = Table(block, doc)
            rows = table.rows
            if not rows:
                continue
            ncol = len(rows[0].cells)
            per = 6.5 / max(1, ncol)
            for row in rows:
                yield section, "tr", _row_lines(row, per) * TBL_LINE + TBL_ROW_CHROME
            yield section, "blank", 0.5


def estimate(path):
    """Simulate pagination, honouring the page break before each H1."""
    pages, lines = 1, 0.0
    for _, kind, cost in walk(path):
        if kind == "h1":
            if pages > 1 or lines > 0:
                pages += 1
                lines = 0.0
        lines += cost
        while lines > LINES_PER_PAGE:
            lines -= LINES_PER_PAGE
            pages += 1
    return pages


def breakdown(path):
    per_section = {}
    order = []
    for section, _, cost in walk(path):
        if section not in per_section:
            per_section[section] = 0.0
            order.append(section)
        per_section[section] += cost
    return order, per_section


def main(argv):
    show = "--breakdown" in argv
    files = [a for a in argv if not a.startswith("-")]
    if not files:
        print(__doc__)
        return 1
    for f in files:
        raw = estimate(f)
        print(f"\n{f.split('/')[-1]}")
        print(f"  model pages       : {raw}")
        print(f"  estimated real    : ~{round(raw * CALIBRATION)} pages  (+/-10%, not a rendered count)")
        if show:
            order, per = breakdown(f)
            print("  where the pages go:")
            for s in sorted(order, key=lambda x: -per[x]):
                print(f"    {per[s] / LINES_PER_PAGE:5.2f}  {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
