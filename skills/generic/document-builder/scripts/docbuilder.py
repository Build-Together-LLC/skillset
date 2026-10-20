"""
docbuilder.py — standard .docx builder.import os


One import gives you the house style used by every document from this skill:
Times New Roman throughout, 12pt justified body, real Word Heading styles
(so Google Docs picks up the outline on upload), navy/blue palette, captioned
and bordered tables.

Usage
-----
    import sys; sys.path.insert(0, "<skill>/scripts")
    from docbuilder import DocBuilder

    d = DocBuilder(title="Payroll Revamp", subtitle="Requirements Document",
                   meta={"Prepared by": "Aman", "Status": "Draft v1"})

    d.h1("Document Overview")                       # page 1-2: the table
    d.table(["Item", "Detail"], rows, caption="Document control sheet")

    d.h1("Consolidated Summary")                    # then: the summary
    d.body("...")

    d.h1("Detailed Flow")                           # then: the flow
    d.h2("Step 1 — Intake")
    d.body("...")

    d.save("/path/Payroll_Revamp_20260724.docx")

Every helper forces the font on the run itself — python-docx loses style
inheritance on headings and table cells, so never rely on the style alone.
"""

import os

from docx import Document
from docx.shared import Pt, Emu, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml, OxmlElement

FONT = "Times New Roman"
MONO = "Courier New"          # code / mermaid blocks only — the one exception

PALETTE = {
    "navy":       "1A3C5E",   # H1, primary banner
    "blue":       "2E75B6",   # H2
    "lightblue":  "4A86C8",   # H3
    "subbanner":  "2E6DA4",   # banner subtitle background
    "tablehead":  "BDD7EE",   # table header fill
    "altrow":     "F2F7FB",   # alternating row fill
    "bodygrey":   "333333",   # table body text, captions
    "border":     "AAAAAA",   # table borders
}

# US Letter, 0.75" margins, in EMU
PAGE_W, PAGE_H, MARGIN = 7772400, 10058400, 685800

_HEADINGS = {           # level: (pt, hex colour, space_before, space_after)
    1: (15, "navy",      22, 6),
    2: (14, "blue",      14, 4),
    3: (13, "lightblue", 10, 4),
}


def _rgb(key_or_hex):
    return RGBColor.from_string(PALETTE.get(key_or_hex, key_or_hex))


def _shade(element, hex_fill):
    """Apply a solid background fill to a paragraph or table cell."""
    element.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_fill}" w:val="clear"/>'))


def _set_run(run, size=12, bold=False, italic=False, color="000000", font=FONT):
    """Force every font attribute on the run, including complex-script slots."""
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = _rgb(color)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for slot in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(slot), font)
    return run


class Link:
    """A (text, url) hyperlink token. Pass anywhere body/bullet/table text is accepted,
    on its own or inside a list of parts, e.g.
        d.body(["Shipped via ", Link("#154", pr_url("my-org/my-repo", 154)), "."])
        d.table(headers, [[change, Link("#154", url), ...]])
    """

    __slots__ = ("text", "url")

    def __init__(self, text, url):
        self.text = str(text)
        self.url = str(url)


def link(text, url):
    return Link(text, url)


# Convenience URL builders for the deployment skills (repo = "owner/name").
def pr_url(repo, n):
    return f"https://github.com/{repo}/pull/{n}"


def commit_url(repo, sha):
    return f"https://github.com/{repo}/commit/{sha}"


def issue_url(repo, n):
    return f"https://github.com/{repo}/issues/{n}"


def jira_url(key, base=None):
    """Browse URL for a Jira issue key like 'PROJ-271' (works for any project key).

    Pass base=, or set JIRA_BASE_URL. There is no default: a hardcoded Jira site would
    silently produce dead links in someone else's document.
    """
    site = (base or os.environ.get("JIRA_BASE_URL", "")).rstrip("/")
    if not site:
        raise RuntimeError("jira_url needs base= or JIRA_BASE_URL (e.g. https://your-site.atlassian.net)")
    return f"{site}/browse/{key}"


def _add_hyperlink(paragraph, url, text, size=12, color="2E75B6", bold=False, italic=False):
    """Append a real external hyperlink run (underlined, coloured) to a paragraph."""
    r_id = paragraph.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hl = OxmlElement("w:hyperlink")
    hl.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    rPr.append(parse_xml(
        f'<w:rFonts {nsdecls("w")} w:ascii="{FONT}" w:hAnsi="{FONT}" w:eastAsia="{FONT}" w:cs="{FONT}"/>'
    ))
    sz = OxmlElement("w:sz"); sz.set(qn("w:val"), str(int(size * 2))); rPr.append(sz)
    col = OxmlElement("w:color"); col.set(qn("w:val"), PALETTE.get(color, color)); rPr.append(col)
    if bold:
        rPr.append(OxmlElement("w:b"))
    if italic:
        rPr.append(OxmlElement("w:i"))
    u = OxmlElement("w:u"); u.set(qn("w:val"), "single"); rPr.append(u)
    run.append(rPr)
    t = OxmlElement("w:t"); t.set(qn("xml:space"), "preserve"); t.text = text
    run.append(t)
    hl.append(run)
    paragraph._p.append(hl)
    return hl


def _render_parts(paragraph, value, size=12, bold=False, italic=False, color="000000"):
    """Render str | Link | list[str|Link] into `paragraph`, hyperlinking any Link parts.
    Plain strings keep the given run styling; Links render as underlined hyperlinks."""
    parts = value if isinstance(value, (list, tuple)) else [value]
    for part in parts:
        if isinstance(part, Link):
            _add_hyperlink(paragraph, part.url, part.text, size=size, bold=bold, italic=italic)
        else:
            _set_run(paragraph.add_run("" if part is None else str(part)),
                     size=size, bold=bold, italic=italic, color=color)
    return paragraph


class DocBuilder:
    """Styled .docx builder. Tables auto-number as `Table <section>.<n>`."""

    def __init__(self, title=None, subtitle=None, meta=None, toc=False):
        self.doc = Document()
        self._section_no = 0      # bumped by each h1
        self._table_no = 0        # reset by each h1
        self._first_h1 = True     # first h1 must not force a blank leading page

        self._setup_page()
        self._setup_normal()
        self._setup_headings()

        if title:
            self.cover(title, subtitle, meta)
        if toc:
            self.toc()

    # ---------------------------------------------------------------- setup

    def _setup_page(self):
        s = self.doc.sections[0]
        s.page_width, s.page_height = Emu(PAGE_W), Emu(PAGE_H)
        s.top_margin = s.bottom_margin = Emu(MARGIN)
        s.left_margin = s.right_margin = Emu(MARGIN)

    def _setup_normal(self):
        st = self.doc.styles["Normal"]
        st.font.name = FONT
        st.font.size = Pt(12)
        st.font.color.rgb = _rgb("000000")
        pf = st.paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.line_spacing = 1.15
        pf.space_after = Pt(6)
        rpr = st.element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.insert(0, rfonts)
        for slot in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rfonts.set(qn(slot), FONT)

    def _setup_headings(self):
        """Configure the BUILT-IN Word heading styles. This is what makes
        Google Docs recognise the outline on upload — never fake a heading
        with a bold paragraph."""
        for lvl, (size, color, before, after) in _HEADINGS.items():
            st = self.doc.styles[f"Heading {lvl}"]
            st.font.name = FONT
            st.font.size = Pt(size)
            st.font.bold = True
            st.font.color.rgb = _rgb(color)
            pf = st.paragraph_format
            pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pf.space_before = Pt(before)
            pf.space_after = Pt(after)
            pf.keep_with_next = True
            rpr = st.element.get_or_add_rPr()
            rfonts = rpr.find(qn("w:rFonts"))
            if rfonts is None:
                rfonts = OxmlElement("w:rFonts")
                rpr.insert(0, rfonts)
            for slot in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
                rfonts.set(qn(slot), FONT)

    # ---------------------------------------------------------------- cover

    def cover(self, title, subtitle=None, meta=None):
        """Title block. Uses the built-in `Title` style so Google Docs maps it."""
        h = self.doc.add_heading(title, level=0)
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in h.runs:
            _set_run(r, size=24, bold=True, color="navy")

        if subtitle:
            p = self.doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _set_run(p.add_run(subtitle), size=14, italic=True, color="bodygrey")

        if meta:
            self.spacer()
            self.table(["Field", "Value"], [[k, v] for k, v in meta.items()],
                       caption=None, widths=[2.0, 4.5])
        self.spacer()

    def toc(self):
        """Insert a TOC field. Word fills it on F9; Google Docs regenerates it."""
        p = self.doc.add_paragraph()
        fld = parse_xml(
            f'<w:fldSimple {nsdecls("w")} w:instr=" TOC \\o &quot;1-3&quot; \\h \\z \\u ">'
            f'<w:r><w:t>Right-click &gt; Update Field to build the table of contents.</w:t></w:r>'
            f"</w:fldSimple>"
        )
        p._p.append(fld)
        return p

    # ------------------------------------------------------------- headings

    def h1(self, text, page_break=True):
        """Section heading. Starts a new page (except the first) and resets
        the table counter so captions read Table 1.1, 1.2, then 2.1, ..."""
        if page_break and not self._first_h1:
            self.doc.add_page_break()
        self._first_h1 = False
        self._section_no += 1
        self._table_no = 0
        h = self.doc.add_heading(text, level=1)
        for r in h.runs:
            _set_run(r, size=_HEADINGS[1][0], bold=True, color=_HEADINGS[1][1])
        return h

    def h2(self, text):
        h = self.doc.add_heading(text, level=2)
        for r in h.runs:
            _set_run(r, size=_HEADINGS[2][0], bold=True, color=_HEADINGS[2][1])
        return h

    def h3(self, text):
        h = self.doc.add_heading(text, level=3)
        for r in h.runs:
            _set_run(r, size=_HEADINGS[3][0], bold=True, color=_HEADINGS[3][1])
        return h

    # ----------------------------------------------------------------- body

    def body(self, text, bold=False, italic=False, align="justify", size=12,
             color="000000"):
        p = self.doc.add_paragraph()
        p.alignment = {
            "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
            "left": WD_ALIGN_PARAGRAPH.LEFT,
            "center": WD_ALIGN_PARAGRAPH.CENTER,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
        }[align]
        p.paragraph_format.line_spacing = 1.15
        _render_parts(p, text, size=size, bold=bold, italic=italic, color=color)
        return p

    def bullet(self, text, level=0, bold=False):
        p = self.doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.line_spacing = 1.15
        _render_parts(p, text, size=12, bold=bold)
        return p

    def numbered(self, text, level=0):
        p = self.doc.add_paragraph(style="List Number" if level == 0 else "List Number 2")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.line_spacing = 1.15
        _set_run(p.add_run(text), size=12)
        return p

    def assumption(self, text):
        """Clearly-flagged gap note — use instead of leaving a section blank."""
        return self.body(f"ASSUMPTION: {text}", italic=True, color="bodygrey")

    def code(self, text, mono=True):
        """Pseudocode / mermaid block. Monospace is the one font exception."""
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.left_indent = Pt(18)
        _shade(p._element.get_or_add_pPr(), "F5F5F5")
        for i, line in enumerate(text.strip("\n").split("\n")):
            run = p.add_run(line)
            _set_run(run, size=10, color="bodygrey", font=MONO if mono else FONT)
            if i < len(text.strip("\n").split("\n")) - 1:
                run.add_break()
        return p

    # --------------------------------------------------------------- tables

    def caption(self, description):
        """`Table <section>.<n>: description`, auto-numbered."""
        self._table_no += 1
        sec = self._section_no if self._section_no else 1
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        _set_run(p.add_run(f"Table {sec}.{self._table_no}: {description}"),
                 size=11, bold=True, italic=True, color="bodygrey")
        return p

    def table(self, headers, rows, caption=None, widths=None, alt_rows=True):
        """Bordered, header-shaded table. `caption` is added above and
        auto-numbered. `widths` is a list of inches, one per column."""
        if caption:
            self.caption(caption)

        t = self.doc.add_table(rows=1 + len(rows), cols=len(headers))
        t.alignment = WD_TABLE_ALIGNMENT.LEFT
        t.autofit = widths is None

        for i, head in enumerate(headers):
            cell = t.rows[0].cells[i]
            cell.text = ""
            _set_run(cell.paragraphs[0].add_run(str(head)), size=11, bold=True)
            _shade(cell._element.get_or_add_tcPr(), PALETTE["tablehead"])

        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                cell = t.rows[r + 1].cells[c]
                cell.text = ""
                _render_parts(cell.paragraphs[0], val, size=11, color="bodygrey")
                if alt_rows and r % 2 == 1:
                    _shade(cell._element.get_or_add_tcPr(), PALETTE["altrow"])

        self._borders(t)
        self._repeat_header(t)
        if widths:
            self._widths(t, widths)
        self.spacer()
        return t

    def _borders(self, table):
        tblPr = table._tbl.tblPr
        edges = "".join(
            f'<w:{e} w:val="single" w:sz="4" w:space="0" w:color="{PALETTE["border"]}"/>'
            for e in ("top", "left", "bottom", "right", "insideH", "insideV")
        )
        tblPr.append(parse_xml(f'<w:tblBorders {nsdecls("w")}>{edges}</w:tblBorders>'))

    def _repeat_header(self, table):
        """Repeat the header row when a table spans pages — matters because
        the opening overview table often runs 1-2 pages."""
        trPr = table.rows[0]._tr.get_or_add_trPr()
        el = OxmlElement("w:tblHeader")
        el.set(qn("w:val"), "true")
        trPr.append(el)

    def _widths(self, table, widths):
        from docx.shared import Inches
        for row in table.rows:
            for cell, w in zip(row.cells, widths):
                cell.width = Inches(w)

    # -------------------------------------------------------------- banners

    def banner(self, title, subtitle=None):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(22)
        p.paragraph_format.space_after = Pt(0)
        _shade(p._element.get_or_add_pPr(), PALETTE["navy"])
        _set_run(p.add_run(f"  {title}"), size=14, bold=True, color="FFFFFF")
        if subtitle:
            p2 = self.doc.add_paragraph()
            p2.paragraph_format.space_before = Pt(0)
            p2.paragraph_format.space_after = Pt(9)
            _shade(p2._element.get_or_add_pPr(), PALETTE["subbanner"])
            _set_run(p2.add_run(f"  {subtitle}"), size=9, italic=True, color="FFFFFF")
        return p

    # ---------------------------------------------------------------- misc

    def spacer(self, size=8):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        _set_run(p.add_run(""), size=size)
        return p

    def page_break(self):
        self.doc.add_page_break()

    def save(self, path):
        self.doc.save(path)
        return path
