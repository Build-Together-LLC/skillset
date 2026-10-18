"""demodoc: build a polished step-by-step demo / setup guide as .docx.

House rules (same as the document-builder skill): Times New Roman, 12 pt body, justified, real Word
heading styles. Everything that looks like a URL becomes a clickable hyperlink, in body text,
tables and code blocks. Colours come from a theme.

    import demodoc as d
    d.init(theme="green", footer="My Product setup guide")
    d.cover("My Product", "Setup guide", rows=[["Version", "1.0"]])
    d.h1("1  Overview")
    d.p("See https://example.com or [[the docs|https://docs.example.com]].")
    d.img("shot.png", "The settings page", label="settings")
    d.p("As shown in Figure {fig:settings}.")
    d.save("guide.docx")
"""

import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

# ---------------------------------------------------------------- themes
# primary: title, H1, table header   secondary: H2   tertiary: H3, captions
THEMES = {
    "navy": dict(primary="1A3C5E", secondary="2E75B6", tertiary="4A86C8", header_fill="BDD7EE", header_text="1A3C5E", stripe="F2F7FB", border="AAAAAA", link="1D4ED8"),
    "green": dict(primary="0F764A", secondary="1F272E", tertiary="475569", header_fill="0F764A", header_text="FFFFFF", stripe="F1F8F4", border="CBD5E1", link="1D4ED8"),
    "blue": dict(primary="1D4ED8", secondary="1E3A8A", tertiary="475569", header_fill="1D4ED8", header_text="FFFFFF", stripe="EFF6FF", border="CBD5E1", link="0B5FD6"),
    "purple": dict(primary="6D28D9", secondary="4C1D95", tertiary="52525B", header_fill="6D28D9", header_text="FFFFFF", stripe="F5F3FF", border="D4D4D8", link="5B21B6"),
    "orange": dict(primary="C2410C", secondary="7C2D12", tertiary="57534E", header_fill="C2410C", header_text="FFFFFF", stripe="FFF7ED", border="D6D3D1", link="1D4ED8"),
    "teal": dict(primary="0F766E", secondary="134E4A", tertiary="475569", header_fill="0F766E", header_text="FFFFFF", stripe="F0FDFA", border="CBD5E1", link="1D4ED8"),
    "slate": dict(primary="334155", secondary="0F172A", tertiary="64748B", header_fill="334155", header_text="FFFFFF", stripe="F8FAFC", border="CBD5E1", link="1D4ED8"),
}
CALLOUTS = {  # kind: (fill, edge)
    "NOTE": ("EFF6FF", "2563EB"),
    "TIP": ("ECFDF5", "16A34A"),
    "WARNING": ("FEF2F2", "DC2626"),
    "EXAMPLE": ("FFFBEB", "D97706"),
    "SECURITY": ("F5F3FF", "7C3AED"),
}
CODE_BG, CODE_FG, CODE_COMMENT, CODE_TITLE, CODE_LINK = "0F172A", "E2E8F0", "86EFAC", "94A3B8", "93C5FD"
URL = re.compile(r"https?://[^\s<>\"'`)\]|]+")
TOKEN = re.compile(r"(\[\[[^\]]+\]\]|\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*|https?://[^\s<>\"'`)\]|]+)")

S = {}  # module state, filled by init()


def _t():
    return S["theme"]


def _hex(value):
    return RGBColor.from_string(value)


def _fonts(run, name):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(attr), name)


def _shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def _borders(table, color, sz=4):
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), str(sz))
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), color)
        b.append(e)
    table._tbl.tblPr.append(b)


def _margins(table, top=70, bottom=70, left=110, right=110):
    m = OxmlElement("w:tblCellMar")
    for k, v in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        e = OxmlElement(f"w:{k}")
        e.set(qn("w:w"), str(v))
        e.set(qn("w:type"), "dxa")
        m.append(e)
    table._tbl.tblPr.append(m)


def _rows(table, header=True):
    for i, row in enumerate(table.rows):
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        if header and i == 0:
            trPr.append(OxmlElement("w:tblHeader"))


def _hyperlink(par, text, url, font, size, color, bold=False, italic=False):
    r_id = par.part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    h = OxmlElement("w:hyperlink")
    h.set(qn("r:id"), r_id)
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rf = OxmlElement("w:rFonts")
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(attr), font)
    rpr.append(rf)
    if bold:
        rpr.append(OxmlElement("w:b"))
    if italic:
        rpr.append(OxmlElement("w:i"))
    c = OxmlElement("w:color")
    c.set(qn("w:val"), color)
    rpr.append(c)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(size * 2)))
    rpr.append(sz)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rpr.append(u)
    r.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    r.append(t)
    h.append(r)
    par._p.append(h)


def _clean_url(text, start, end):
    url = text[start:end].rstrip(".,;:!?")
    after = text[start + len(url):start + len(url) + 1]
    if after == "<" or url.endswith("//"):
        return None
    return url


def rich(par, text, size=None, color=None, link_color=None, base_font=None, bold=False):
    """Inline markup: **bold**, *italic*, `code`, [[label|url]]; bare URLs become links."""
    size = size or S["size"]
    font = base_font or S["font"]
    link_color = link_color or _t()["link"]

    def plain(chunk, **kw):
        if not chunk:
            return
        r = par.add_run(chunk)
        _fonts(r, kw.get("font", font))
        r.font.size = Pt(kw.get("size", size))
        r.bold = kw.get("bold", bold) or None
        r.italic = kw.get("italic") or None
        col = kw.get("color", color)
        if col:
            r.font.color.rgb = _hex(col)

    def with_links(chunk, **kw):
        pos = 0
        for m in URL.finditer(chunk):
            url = _clean_url(chunk, m.start(), m.end())
            if not url:
                continue
            plain(chunk[pos:m.start()], **kw)
            _hyperlink(par, url, url, kw.get("font", font), kw.get("size", size), link_color, bold=kw.get("bold", bold), italic=kw.get("italic"))
            pos = m.start() + len(url)
        plain(chunk[pos:], **kw)

    for tok in TOKEN.split(text):
        if not tok:
            continue
        if tok.startswith("[["):
            label, url = tok[2:-2].split("|", 1)
            _hyperlink(par, label, url, font, size, link_color, bold=bold)
        elif tok.startswith("**"):
            with_links(tok[2:-2], bold=True)
        elif tok.startswith("`"):
            with_links(tok[1:-1], font=S["code_font"], size=max(size - 1.5, 9), color="B42318")
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            with_links(tok[1:-1], italic=True)
        elif URL.fullmatch(tok):
            with_links(tok)
        else:
            plain(tok)


def link(label, url):
    return f"[[{label}|{url}]]"


# ---------------------------------------------------------------- setup
def init(theme="green", page="A4", font="Times New Roman", size=12, code_font="Courier New", footer="", justify=True, margins=0.8, table_size=11, author="", title=""):
    """Start a new document. Returns the python-docx Document."""
    if isinstance(theme, str):
        theme = THEMES[theme]
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = (Inches(8.27), Inches(11.69)) if page.upper() == "A4" else (Inches(8.5), Inches(11))
    sec.left_margin = sec.right_margin = Inches(margins)
    sec.top_margin = sec.bottom_margin = Inches(margins)
    S.clear()
    S.update(doc=doc, theme=theme, font=font, size=size, code_font=code_font, justify=justify, table_size=table_size,
             width=(sec.page_width - sec.left_margin - sec.right_margin) / 914400, figs={}, tbls={}, fig_n=0, tbl_n=0, author=author, title=title)

    normal = doc.styles["Normal"]
    normal.font.name = font
    normal.font.size = Pt(size)
    normal.font.color.rgb = _hex("000000")
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), font)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15
    for name, pt, key in (("Title", 28, "primary"), ("Heading 1", 18, "primary"), ("Heading 2", 14, "secondary"), ("Heading 3", 13, "tertiary")):
        st = doc.styles[name]
        st.font.name = font
        st.font.size = Pt(pt)
        st.font.bold = True
        st.font.italic = False
        st.font.color.rgb = _hex(theme[key])
        rpr = st.element.get_or_add_rPr()
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts")
            rpr.append(rf)
        for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rf.set(qn(attr), font)
        for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            rf.attrib.pop(qn(attr), None)
        ppr = st.element.get_or_add_pPr()
        for border in ppr.findall(qn("w:pBdr")):
            ppr.remove(border)
        st.paragraph_format.keep_with_next = True
        st.paragraph_format.space_before = Pt(16 if name == "Heading 1" else 12)
        st.paragraph_format.space_after = Pt(6)

    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for text, field in ((f"{footer}  |  page " if footer else "page ", None), (None, "PAGE")):
        if text:
            r = fp.add_run(text)
            _fonts(r, font)
            r.font.size = Pt(10)
            r.font.color.rgb = _hex(theme["tertiary"])
        else:
            for kind in ("begin", "instr", "end"):
                run = fp.add_run()
                _fonts(run, font)
                run.font.size = Pt(10)
                run.font.color.rgb = _hex(theme["tertiary"])
                if kind == "instr":
                    it = OxmlElement("w:instrText")
                    it.set(qn("xml:space"), "preserve")
                    it.text = field
                    run._r.append(it)
                else:
                    fc = OxmlElement("w:fldChar")
                    fc.set(qn("w:fldCharType"), kind)
                    run._r.append(fc)
    return doc


# ---------------------------------------------------------------- text blocks
def p(text, align=None, after=None, italic=False, color=None, size=None):
    par = S["doc"].add_paragraph()
    rich(par, text, size=size, color=color)
    if italic:
        for r in par.runs:
            r.italic = True
    align = align or ("justify" if S["justify"] else "left")
    par.alignment = {"justify": WD_ALIGN_PARAGRAPH.JUSTIFY, "left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER}[align]
    if after is not None:
        par.paragraph_format.space_after = Pt(after)
    return par


def _heading(level, text, page_break=False):
    h = S["doc"].add_heading(text, level)
    if page_break:
        h.paragraph_format.page_break_before = True
    return h


def h1(text, page_break=False):
    return _heading(1, text, page_break)


def h2(text):
    return _heading(2, text)


def h3(text):
    return _heading(3, text)


def bullets(items):
    for it in items:
        par = S["doc"].add_paragraph(style="List Bullet")
        par.paragraph_format.space_after = Pt(3)
        rich(par, it)


def steps(items):
    """Numbered list that restarts at 1 for every call."""
    for n, it in enumerate(items, 1):
        par = S["doc"].add_paragraph()
        par.paragraph_format.left_indent = Inches(0.34)
        par.paragraph_format.first_line_indent = Inches(-0.28)
        par.paragraph_format.space_after = Pt(3)
        lead = par.add_run(f"{n}.  ")
        _fonts(lead, S["font"])
        lead.font.size = Pt(S["size"])
        lead.bold = True
        lead.font.color.rgb = _hex(_t()["primary"])
        rich(par, it)


def expect(text):
    par = S["doc"].add_paragraph()
    par.paragraph_format.left_indent = Inches(0.15)
    rich(par, "**What you should see:** " + text)
    return par


def _gap():
    S["doc"].add_paragraph().paragraph_format.space_after = Pt(2)


def code(text, title=None):
    """Dark command block. Lines starting with # are comments. URLs are clickable."""
    t = S["doc"].add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _borders(t, "94A3B8")
    _margins(t, 90, 90, 140, 140)
    c = t.rows[0].cells[0]
    _shade(c, CODE_BG)
    first = True
    if title:
        par = c.paragraphs[0]
        r = par.add_run(title)
        _fonts(r, S["font"])
        r.font.size = Pt(10)
        r.bold = True
        r.font.color.rgb = _hex(CODE_TITLE)
        par.paragraph_format.space_after = Pt(3)
        first = False
    size = 9.5
    for line in text.strip("\n").split("\n"):
        par = c.paragraphs[0] if first else c.add_paragraph()
        first = False
        par.paragraph_format.space_after = Pt(0)
        par.paragraph_format.line_spacing = 1.05
        par.alignment = WD_ALIGN_PARAGRAPH.LEFT
        color = CODE_COMMENT if line.lstrip().startswith("#") else CODE_FG
        pos = 0
        for m in URL.finditer(line):
            url = _clean_url(line, m.start(), m.end())
            if not url:
                continue
            seg = line[pos:m.start()]
            if seg:
                r = par.add_run(seg)
                _fonts(r, S["code_font"])
                r.font.size = Pt(size)
                r.font.color.rgb = _hex(color)
            _hyperlink(par, url, url, S["code_font"], size, CODE_LINK)
            pos = m.start() + len(url)
        tail = line[pos:] or (" " if pos == 0 else "")
        if tail:
            r = par.add_run(tail)
            _fonts(r, S["code_font"])
            r.font.size = Pt(size)
            r.font.color.rgb = _hex(color)
    _rows(t, header=False)
    _gap()


def callout(kind, text):
    fill, edge = CALLOUTS[kind]
    t = S["doc"].add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _margins(t, 90, 90, 160, 140)
    c = t.rows[0].cells[0]
    _shade(c, fill)
    tcPr = c._tc.get_or_add_tcPr()
    tb = OxmlElement("w:tcBorders")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "24")
    left.set(qn("w:color"), edge)
    tb.append(left)
    tcPr.append(tb)
    par = c.paragraphs[0]
    par.paragraph_format.space_after = Pt(0)
    r = par.add_run(kind + "  ")
    _fonts(r, S["font"])
    r.bold = True
    r.font.size = Pt(10)
    r.font.color.rgb = _hex(edge)
    rich(par, text)
    _rows(t, header=False)
    _gap()


def table(rows, widths=None, header=True, font=None, caption=None, label=None):
    """rows[0] is the header row. caption adds an auto-numbered 'Table n.' line above."""
    th = _t()
    if caption:
        S["tbl_n"] += 1
        if label:
            S["tbls"][label] = S["tbl_n"]
        cap = S["doc"].add_paragraph()
        cap.paragraph_format.keep_with_next = True
        cap.paragraph_format.space_after = Pt(3)
        rich(cap, f"**Table {S['tbl_n']}.** {caption}", size=11, color=th["tertiary"])
    size = font or S["table_size"]
    t = S["doc"].add_table(rows=len(rows), cols=len(rows[0]))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _borders(t, th["border"])
    _margins(t)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.rows[i].cells[j]
            par = c.paragraphs[0]
            par.paragraph_format.space_after = Pt(0)
            par.alignment = WD_ALIGN_PARAGRAPH.LEFT
            is_head = header and i == 0
            rich(par, str(val), size=size, color=th["header_text"] if is_head else None,
                 link_color="FFFFFF" if is_head and th["header_text"] == "FFFFFF" else None, bold=is_head)
            if is_head:
                _shade(c, th["header_fill"])
            elif i % 2 == 0:
                _shade(c, th["stripe"])
    if widths:
        for row in t.rows:
            for j, w in enumerate(widths):
                row.cells[j].width = Inches(w)
    _rows(t, header=header)
    _gap()
    return t


def img(path, caption=None, width=6.3, label=None):
    """Picture with an auto-numbered 'Figure n.' caption. Use {fig:label} in text to refer to it."""
    width = min(width, S["width"])
    par = S["doc"].add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.keep_with_next = bool(caption)
    par.paragraph_format.space_after = Pt(2)
    par.add_run().add_picture(path, width=Inches(width))
    if caption:
        S["fig_n"] += 1
        if label:
            S["figs"][label] = S["fig_n"]
        cap = S["doc"].add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_after = Pt(10)
        rich(cap, f"*Figure {S['fig_n']}. {caption}*", size=10.5, color=_t()["tertiary"])


def pagebreak():
    S["doc"].add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def spacer(pt=8):
    S["doc"].add_paragraph().paragraph_format.space_after = Pt(pt)


def cover(title, subtitle=None, rows=None, note=None, top_space=5):
    for _ in range(top_space):
        S["doc"].add_paragraph()
    t = S["doc"].add_paragraph(style="Title")
    t.alignment = WD_ALIGN_PARAGRAPH.LEFT
    t.add_run(title)
    if subtitle:
        par = S["doc"].add_paragraph()
        r = par.add_run(subtitle)
        _fonts(r, S["font"])
        r.font.size = Pt(16)
        r.font.color.rgb = _hex(_t()["tertiary"])
    spacer()
    if rows:
        table([[a, b] for a, b in rows], widths=[1.4, S["width"] - 1.4], header=False)
    if note:
        callout("WARNING", note)
    pagebreak()


def contents(entries, headers=("Part", "What you will do")):
    table([list(headers)] + [list(e) for e in entries], widths=[2.3, S["width"] - 2.3])


# ---------------------------------------------------------------- save
def _resolve_tokens():
    pat = re.compile(r"\{(fig|tbl):([A-Za-z0-9_-]+)\}")

    def sub(m):
        table_ = S["figs"] if m.group(1) == "fig" else S["tbls"]
        return str(table_.get(m.group(2), "?"))

    for node in S["doc"].element.body.iter(qn("w:t")):
        if node.text and "{" in node.text:
            node.text = pat.sub(sub, node.text)


def save(path):
    _resolve_tokens()
    doc = S["doc"]
    doc.core_properties.author = S["author"] or doc.core_properties.author
    doc.core_properties.title = S["title"] or doc.core_properties.title
    doc.save(path)
    return path
