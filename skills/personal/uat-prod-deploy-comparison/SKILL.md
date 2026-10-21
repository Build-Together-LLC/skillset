---
name: uat-prod-deploy-comparison
description: >
  Build a Production-vs-UAT deployment comparison document (.docx) for the Walnut / Unity Frappe
  bench. Trigger this whenever the user provides two Frappe Cloud "Apps" snapshots (screenshots or
  text) — one Production site, one UAT site — and asks to compare the deployed commits, diff the
  sites, produce "deployment notes", a "release comparison", a "prod vs UAT" doc, or "what changed
  on UAT". Also trigger on follow-ups like "UAT is updated, refresh the doc", "add this app",
  "include PR-XXXX", or "recompare the sites". The skill discovers every changed repo, reconciles
  EVERY PR and commit in each prod→UAT range via the GitHub compare API (including reverts and
  no-PR direct commits), and emits a styled .docx with proper Google-Docs headings.
---

# UAT ↔ Production Deployment Comparison

You produce a **release sign-off document** comparing what is deployed on **Production**
(`erp.walnutedu.in`) against **UAT** (`uat.unityedu.tech`), for a Frappe bench with many apps.

The gold-standard output is `/home/aman/unity/walnut/docs/UAT vs Prod Comparison <YYYY-MM-DD>.docx`.
Match it exactly. A working generator lives at (session scratchpad) `gen_uat_prod.py`; the full
template is embedded at the end of this skill — reuse it.

Related memory: `deployment-notes-format.md` in the project memory dir. gh CLI is authenticated
(account `amankumarui`); local app clones are under `/home/aman/unity/walnut/apps/`.

---

## Step 0 — Intake the two snapshots

The user gives two Frappe Cloud **Apps** views (usually screenshots): the **Prod** site and the
**UAT** site. Each row is: `App | Plan | Repository (owner/name) | Branch | Commit (short SHA) |
Commit Message`.

1. Read BOTH snapshots and extract, per app: **repository, branch, short commit**.
2. Note the site + date each snapshot represents (put in the header line).
3. If a snapshot is scrolled/partial, say so and work with what is visible; never invent rows.

---

## Step 1 — Classify every app into four buckets

Compare the two snapshots app-by-app:

- **Changed** — app is on BOTH sites but the commit differs → gets a full change table.
- **Unchanged** — identical commit on both → one line in the "Unchanged" section (with SHA).
- **Newly installed on UAT** — app present on UAT but absent from the Prod snapshot → goes in the
  "Newly Installed on UAT" table (App | Repository | Branch | Commit); do NOT deep-diff it (no prod
  baseline). Note branch-only differences and version drift too.
- **Version drift / not this cycle** — third-party/framework apps that differ only by an upstream
  bump, or Walnut apps whose diff is old (merged weeks/months earlier = prod merely lagging). List
  these briefly in a drift note, not as detailed tables.

Respect the user's exclusions: they have previously asked to EXCLUDE certain peripheral apps from
the comparison (e.g. AWS Integration, Visitor Management, SMS Integration, Easebuzz, Excel View,
ChatNext, ChatNext ToDo Manager). Ask/confirm which apps are in scope if unsure.

---

## Step 2 — Deep reconciliation (the core of this skill)

For **each changed repo**, enumerate EVERY commit and PR between the two deployed commits. Do NOT
rely on the user's Discord/release-notes message — it routinely misses items. Use the compare API:

```bash
# every commit in the range (base = prod SHA, head = uat SHA)
gh api "repos/<owner>/<repo>/compare/<prodSHA>...<uatSHA>" --paginate \
  --jq '.commits[] | "\(.sha[0:7])  \(.commit.author.date[0:10])  \(.commit.message | split("\n")[0])"'

# every merged-PR number whose merge commit is in the range
gh api "repos/<owner>/<repo>/compare/<prodSHA>...<uatSHA>" --paginate --jq '.commits[].sha' \
  | while read s; do gh api "repos/<owner>/<repo>/commits/$s/pulls" --jq '.[].number'; done | sort -un
```

Then for every PR: `gh pr view <n> --repo <owner>/<repo> --json number,title,url,mergedAt,state,body`.

Reconciliation rules (the user verifies these):
- **Include every PR.** After building the table, re-run the PR-number list above and assert the
  set in the doc == the set in the range. Report "missing: []".
- **A commit with no PR → reference the commit SHA** (link `/commit/<sha>`), not just prose.
  Find these: `gh api repos/<owner>/<repo>/commits/<sha>/pulls` returns empty.
- **Surface reverts explicitly.** A "Revert …" commit/PR is its own row (type = Other) AND the
  reverted item's row gets a note + a "Reverted #NNNN" QA marker. Watch for revert-of-revert
  (re-application) too.
- Numbers that appear as GitHub **issues** (not PRs) go in the Links column as `Issue #N`, never as
  a change row. Verify a number is a PR before treating it as one.
- **The Ref cell hyperlinks to the PR** (or to `/commit/<sha>` for a no-PR commit) — build it with
  `pr_url(base,n)` / `cm_url(base,h)`. Do NOT also put the PR in the Links column; the Ref *is* the PR.
- **The Links column holds the linked ISSUE(s) + any documentation / branch-strategy links** pulled
  from the PR body — never the PR itself. You MUST fetch each PR body and extract these; the linked
  issue is frequently in a DIFFERENT repo (e.g. a `cn-recruitment` PR whose ticket lives in
  `walnut_hrms`). Fetch with `gh pr view <n> --repo <owner>/<repo> --json body,closingIssuesReferences`
  and, because `closingIssuesReferences` misses cross-repo refs, ALSO regex the body for:
    - `(Closes|Fixes|Resolves|Ref|Refs)\s*:?\s*([\w.-]+/[\w.-]+)?#(\d+)` — captures both `#86` (same
      repo → `iss(base,86)`) and `WalnutAppSuite/walnut_hrms#86` (cross-repo → `xiss("WalnutAppSuite/walnut_hrms",86)`);
    - full issue URLs `https://github.com/<owner>/<repo>/issues/<n>`;
    - documentation links in the body/ticket — Google Docs (`docs.google.com/document`), kommodo.ai
      recordings, Discord message links, wiki pages — add each via `doclink("<label>", "<url>")`;
    - a one-line **branch-strategy** note if the body states a non-obvious base/branch (e.g. "Base is
      `walnut`, retargeted from `main`") — put it as a `doclink` to the PR's `/files` or just note it
      in the Summary.
  Example from PR `hybrowlabs/cn-recruitment#1243`: body says `Closes WalnutAppSuite/walnut_hrms#86.`
  → Ref = `#1243` → `pr_url(RC,1243)`; Links = `[xiss("WalnutAppSuite/walnut_hrms",86)]`.
- **Merge date → the Ref cell.** Ref shows `#3410` then `(DD-MM)` on a second line = the date the
  PR merged into develop (`mergedAt`). For no-PR commits use the commit author date.
- Optionally also run `compare/<uatSHA>...develop` to see merges newer than the UAT snapshot; the
  doc reflects the DEPLOYED state, so only include those if the user says "UAT is deploying X now".

---

## Step 3 — Classify each change

- **Feature** (blue `e8f1fb`) — new functionality.
- **Bug Fix** (red `fceaea`) — corrects existing behaviour.
- **Improvement / Other** (grey `eeeeee`) — refactor, perf, maintenance, CI, branch alignment,
  reverts.

Write a terse, accurate one-line Change label + a fuller Summary drawn from the PR title/body.
Every cell must have a value ("N/A" if nothing applies). Flag known-buggy / in-progress items in
the QA column (e.g. "In progress — <owner>").

---

## Step 4 — Generate the .docx (exact format)

Save to `/home/aman/unity/walnut/docs/UAT vs Prod Comparison <YYYY-MM-DD>.docx`. Remove the prior
day's file if this supersedes it. Structure, in order:

1. **Title** (Word `Title` style): `<DD-MM-YYYY> — UAT vs Production Change Comparison`.
2. Centered subtitle + a "Prepared … · Prod snapshot … · UAT snapshot …" line.
3. **Overview** (Heading 2) + 2 prose paragraphs.
4. **Table 0.1 summary** — `Repository | Prod → UAT | Changes | Features | Bug Fixes | Other`, one
   row per changed repo, then a totals line.
5. One **Heading 2 section per changed repo**: repo name (H2) → url/refs line → description →
   `Table X.1` caption → change table `Ref | Type | Change | Summary | Links | QA / Tested` → any
   notes. Each repo section starts on a new page.
6. **Newly Installed on UAT** (Heading 2) → `Table N.1` App | Repository | Branch | Commit.
7. **Unchanged Repositories & Sign-off** (Heading 2) → prose list of unchanged apps (with SHAs) →
   drift note → **Legend** (Heading 3) → Open-items note.

### CRITICAL — headings (do this every time)

The user requires a working Google-Docs outline. Use REAL Word heading styles, never manually
bolded paragraphs:

- Document title → **`Title`** style.
- Every repo section + Overview + Newly-Installed + Unchanged → **`Heading 2`**.
- Every **PR/commit Ref cell** (first paragraph of column 0 in each change table) → **`Heading 3`**,
  so each PR nests under its repo in the outline. Legend → `Heading 3`.
- Keep the visible run formatting (10pt bold dark-grey for refs) so it still looks like a table
  cell, but the paragraph STYLE must be the heading — that is what populates the outline.
- Do NOT style the summary-table or newly-installed-table first column as headings (those are repo
  names / app names, not PR refs).

### Styling rules (Times New Roman throughout)

- Page: US Letter, 0.75" margins. Body 12pt justified, line-spacing 1.15, black.
- Heading styles configured: H1 16pt navy `1F4E79`, H2 13pt `2E75B6`, H3 12pt `4A86C8` — all Times
  New Roman, left aligned. (Repos use H2 per above.)
- Table header row fill `1F4E79`, white 11pt bold text. Body cells 10–11pt `333333`, borders
  `AAAAAA`, alternate rows `f7fafd`.
- **Type cell colour-coding**: Feature `e8f1fb`, Bug Fix `fceaea`, Improvement/Other `eeeeee`.
- **The Ref cell is a real hyperlink to the PR** (or `/commit/<sha>`); the **Links column holds the
  linked issue(s) (cross-repo aware) + doc/branch links** extracted from the PR body — never the PR
  itself. Helpers: `pr_url`/`cm_url` (Ref), `iss`/`xiss`/`doclink` (Links); `add_hyperlink` below.
- Every table has a caption above it: `Table X.Y: …`.
- Every `add_run` sets `font.name='Times New Roman'` explicitly.

After saving, tell the user to sync via **File → Import → Replace** in their Google Doc (doc id
`1wE-zcBdS6tkSPuwFOixdSQFgAel-b0MZV95sS7y9sFw`), or import into a new tab to preserve comments.
You cannot write to the Google Doc directly (no Docs API scope); read their edits via
`https://docs.google.com/document/d/<id>/export?format=txt`.

---

## Step 5 — Self-verify before handing off

Programmatically re-open the saved docx and assert:
- [ ] For each changed repo, `{PR numbers in the doc} == {PR numbers in the compare range}` →
      print "missing: []".
- [ ] No-PR commits appear as commit-SHA refs.
- [ ] Reverts are represented (row + note).
- [ ] Outline: Title present; repos + Overview + section titles are `Heading 2`; every change-table
      Ref cell is `Heading 3`; newly-installed/summary first columns are NOT headings.
- [ ] Hyperlink count > 0; type cells colour-coded; merge dates in Ref.

---

## Discord update (optional companion)

The user often wants a Discord message covering only what landed on UAT since their last post, in
this style — grouped by app, numbered, description linked to the issue where one exists, `Ref
[PR-N](url)`; no-PR items link the commit:

```
UAT Updated with

<App>
1. <fix/feat: title> : Ref [PR-N](https://github.com/<owner>/<repo>/pull/N)
2. [<title linked to issue>](https://github.com/.../issues/M) : Ref [PR-N](.../pull/N)
```

Scope it to changes after the user's last Discord post; exclude anything not yet on the UAT site.

---

## Embedded generator template (python-docx)

Feed it a `DATA` dict; it emits the exact format above with the headings baked in. Extend the repo
list / rows as needed. `pr()/iss()/cm()` build (text,url) link tuples.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from docx import Document
from docx.shared import Pt, Emu, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml, OxmlElement

NAVY=RGBColor(0x1F,0x4E,0x79); GREY=RGBColor(0x59,0x59,0x59); BLACK=RGBColor(0,0,0); WHITE=RGBColor(0xFF,0xFF,0xFF)
FILL_FEATURE="e8f1fb"; FILL_BUG="fceaea"; FILL_OTHER="eeeeee"; FILL_PEND="fdf3e2"
HDR_FILL="1f4e79"; ALT_FILL="f7fafd"
TYPE_FILL={"Feature":FILL_FEATURE,"Bug Fix":FILL_BUG,"Improvement":FILL_OTHER,"Other":FILL_OTHER,"Pending":FILL_PEND,"Note":FILL_OTHER}

doc=Document()
s=doc.sections[0]; s.page_width=Emu(7772400); s.page_height=Emu(10058400)
for m in ('top_margin','bottom_margin','left_margin','right_margin'): setattr(s,m,Emu(685800))
st=doc.styles['Normal']; st.font.name='Times New Roman'; st.font.size=Pt(12); st.font.color.rgb=BLACK
st.paragraph_format.line_spacing=1.15; st.paragraph_format.space_after=Pt(6)

# Heading styles -> real Word styles so Google Docs builds an outline
for _l,_sz,_c,_b,_a in [(1,16,NAVY,16,4),(2,13,RGBColor(0x2E,0x75,0xB6),10,3),(3,12,RGBColor(0x4A,0x86,0xC8),8,3)]:
    hs=doc.styles[f'Heading {_l}']; hs.font.name='Times New Roman'; hs.font.size=Pt(_sz); hs.font.bold=True
    hs.font.color.rgb=_c; hs.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.LEFT
    hs.paragraph_format.space_before=Pt(_b); hs.paragraph_format.space_after=Pt(_a)
    rpr=hs.element.get_or_add_rPr(); rf=rpr.find(qn('w:rFonts'))
    if rf is None:
        rf=parse_xml(f'<w:rFonts {nsdecls("w")} w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Times New Roman" w:cs="Times New Roman"/>'); rpr.insert(0,rf)
    else:
        for a in ('w:ascii','w:hAnsi','w:eastAsia','w:cs'): rf.set(qn(a),'Times New Roman')

def set_run(r,name='Times New Roman',size=12,bold=False,italic=False,color=BLACK):
    r.font.name=name; r.font.size=Pt(size); r.font.bold=bold; r.font.italic=italic
    if color is not None: r.font.color.rgb=color
    rpr=r._element.get_or_add_rPr(); rf=rpr.find(qn('w:rFonts'))
    if rf is None:
        rf=parse_xml(f'<w:rFonts {nsdecls("w")} w:ascii="{name}" w:hAnsi="{name}" w:eastAsia="{name}" w:cs="{name}"/>'); rpr.insert(0,rf)
    else:
        for a in ('w:ascii','w:hAnsi','w:eastAsia','w:cs'): rf.set(qn(a),name)

def add_heading(text,level=2,page_break=False):
    h=doc.add_heading(text,level=level)
    if page_break: h.paragraph_format.page_break_before=True
    sz={1:16,2:13,3:12}[level]; col={1:NAVY,2:RGBColor(0x2E,0x75,0xB6),3:RGBColor(0x4A,0x86,0xC8)}[level]
    for r in h.runs: set_run(r,size=sz,bold=True,color=col)
    return h

def para(text='',size=12,bold=False,italic=False,color=BLACK,align=None,before=None,after=None,page_break=False):
    p=doc.add_paragraph()
    if page_break: p.paragraph_format.page_break_before=True
    if align is not None: p.alignment=align
    if before is not None: p.paragraph_format.space_before=Pt(before)
    if after is not None: p.paragraph_format.space_after=Pt(after)
    if text: set_run(p.add_run(text),size=size,bold=bold,italic=italic,color=color)
    return p

def title_para(text):
    try: p=doc.add_paragraph(style='Title')
    except KeyError: p=doc.add_paragraph()
    p.alignment=WD_ALIGN_PARAGRAPH.LEFT; p.paragraph_format.space_after=Pt(2)
    set_run(p.add_run(text),size=26,bold=True,color=NAVY); return p

def caption(t):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before=Pt(8); p.paragraph_format.space_after=Pt(3)
    set_run(p.add_run(t),size=11,bold=True,italic=True,color=RGBColor(0x33,0x33,0x33))

def repo_heading(name,prod_ref,uat_ref,url,desc):
    add_heading(name,level=2)   # <-- repos are Heading 2
    p2=doc.add_paragraph(); p2.paragraph_format.space_after=Pt(0)
    set_run(p2.add_run(f'{url}   —   prod {prod_ref}  →  UAT {uat_ref}'),size=10,color=GREY)
    p3=doc.add_paragraph(); p3.paragraph_format.space_after=Pt(4)
    set_run(p3.add_run(desc),size=11,italic=True,color=GREY)

def add_hyperlink(paragraph,url,text):
    r_id=paragraph.part.relate_to(url,"http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",is_external=True)
    hl=OxmlElement('w:hyperlink'); hl.set(qn('r:id'),r_id); run=OxmlElement('w:r'); rPr=OxmlElement('w:rPr')
    rPr.append(parse_xml(f'<w:rFonts {nsdecls("w")} w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'))
    for tag,val in (('w:sz','20'),('w:color','1F4E79')):
        e=OxmlElement(tag); e.set(qn('w:val'),val); rPr.append(e)
    u=OxmlElement('w:u'); u.set(qn('w:val'),'single'); rPr.append(u); run.append(rPr)
    t=OxmlElement('w:t'); t.text=text; run.append(t); hl.append(run); paragraph._p.append(hl); return hl

def cell_fill(cell,hexf): cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hexf}" w:val="clear"/>'))
def table_borders(t):
    t._tbl.tblPr.append(parse_xml(f'<w:tblBorders {nsdecls("w")}>'+''.join(
      f'<w:{e} w:val="single" w:sz="4" w:space="0" w:color="AAAAAA"/>' for e in
      ('top','left','bottom','right','insideH','insideV'))+'</w:tblBorders>'))

def summary_table(rows):
    heads=["Repository","Prod → UAT","Changes","Features","Bug Fixes","Other"]
    t=doc.add_table(rows=1+len(rows),cols=len(heads)); t.alignment=WD_TABLE_ALIGNMENT.LEFT
    for i,h in enumerate(heads):
        c=t.rows[0].cells[i]; c.text=''; set_run(c.paragraphs[0].add_run(h),size=11,bold=True,color=WHITE); cell_fill(c,HDR_FILL)
    for ri,row in enumerate(rows):
        for ci,v in enumerate(row):
            c=t.rows[ri+1].cells[ci]; c.text=''; set_run(c.paragraphs[0].add_run(str(v)),size=11,color=RGBColor(0x33,0x33,0x33),bold=(ci==0))
            if ri%2: cell_fill(c,ALT_FILL)
    table_borders(t)

def simple_table(heads,rows,linkcol=None):
    t=doc.add_table(rows=1+len(rows),cols=len(heads)); t.alignment=WD_TABLE_ALIGNMENT.LEFT
    for i,h in enumerate(heads):
        c=t.rows[0].cells[i]; c.text=''; set_run(c.paragraphs[0].add_run(h),size=11,bold=True,color=WHITE); cell_fill(c,HDR_FILL)
    for ri,row in enumerate(rows):
        for ci,v in enumerate(row):
            c=t.rows[ri+1].cells[ci]; c.text=''
            if linkcol==ci and isinstance(v,tuple): add_hyperlink(c.paragraphs[0],v[1],v[0])
            else: set_run(c.paragraphs[0].add_run(str(v)),size=10,color=RGBColor(0x33,0x33,0x33),bold=(ci==0))
            if ri%2: cell_fill(c,ALT_FILL)
    table_borders(t)

def change_table(rows):
    # row = (ref, ref_url, date, type, change, summary, links, qa)
    #   ref      : "#3410" (a PR) or a commit sha
    #   ref_url  : the PR URL (or /commit/<sha> for a no-PR commit) — the Ref cell HYPERLINKS to it
    #   links    : [(text,url), ...] -> the LINKED ISSUE(s) (cross-repo aware) + any documentation /
    #              branch-strategy links pulled from the PR body.  NOT the PR itself (that is the Ref).
    heads=["Ref","Type","Change","Summary","Links","QA / Tested"]
    t=doc.add_table(rows=1+len(rows),cols=len(heads)); t.alignment=WD_TABLE_ALIGNMENT.LEFT; t.autofit=False
    for i,h in enumerate(heads):
        c=t.rows[0].cells[i]; c.text=''; set_run(c.paragraphs[0].add_run(h),size=11,bold=True,color=WHITE); cell_fill(c,HDR_FILL)
    for ri,(ref,ref_url,date,typ,change,summary,links,qa) in enumerate(rows):
        cells=t.rows[ri+1].cells
        cells[0].text=''; rp=cells[0].paragraphs[0]
        rp.style=doc.styles['Heading 3']            # <-- Ref = Heading 3 (nests under repo in the outline)
        rp.paragraph_format.space_before=Pt(0); rp.paragraph_format.space_after=Pt(0)
        if ref_url:
            add_hyperlink(rp, ref_url, ref)         # <-- Ref itself links to the PR (or commit)
        else:
            set_run(rp.add_run(ref),size=10,bold=True,color=RGBColor(0x33,0x33,0x33))
        if date:
            dp=cells[0].add_paragraph(); dp.paragraph_format.space_before=Pt(1); dp.paragraph_format.space_after=Pt(0)
            set_run(dp.add_run(f'({date})'),size=9,bold=True,color=GREY)
        cells[1].text=''; set_run(cells[1].paragraphs[0].add_run(typ),size=10,bold=True,color=RGBColor(0x33,0x33,0x33)); cell_fill(cells[1],TYPE_FILL.get(typ,FILL_OTHER))
        cells[2].text=''; set_run(cells[2].paragraphs[0].add_run(change),size=10,color=RGBColor(0x33,0x33,0x33))
        cells[3].text=''; set_run(cells[3].paragraphs[0].add_run(summary),size=10,color=RGBColor(0x33,0x33,0x33))
        cells[4].text=''; lp=cells[4].paragraphs[0]
        for j,(lt,lu) in enumerate(links):
            if j: set_run(lp.add_run('\n'),size=10)
            add_hyperlink(lp,lu,lt) if lu else set_run(lp.add_run(lt),size=10,color=RGBColor(0x33,0x33,0x33))
        cells[5].text=''; set_run(cells[5].paragraphs[0].add_run(qa),size=10,color=RGBColor(0x33,0x33,0x33))
        if ri%2:
            for ci in (0,2,3,4,5): cell_fill(cells[ci],ALT_FILL)
    table_borders(t)

# --- Ref-cell URLs (the Ref hyperlinks to these) ---
def pr_url(base,n): return f"{base}/pull/{n}"            # PR  -> Ref
def cm_url(base,h): return f"{base}/commit/{h}"          # no-PR commit -> Ref
# --- Links-cell entries (issues + docs; cross-repo aware) ---
def iss(base,n):        return (f"Issue #{n}", f"{base}/issues/{n}")                                   # same-repo issue
def xiss(owner_repo,n): return (f"{owner_repo.split('/')[-1]}#{n}", f"https://github.com/{owner_repo}/issues/{n}")  # cross-repo issue, e.g. xiss("WalnutAppSuite/walnut_hrms",86)
def doclink(text,url):  return (text, url)               # Google Doc / kommodo recording / Discord / wiki, etc.

# ---- Build the document from your reconciled DATA (fill in per run) ----
title_para("18-07-2026 — UAT vs Production Change Comparison")
para("prod  →  UAT  ·  Feature & Bug Summary for Release Sign-off",size=13,italic=True,color=GREY,align=WD_ALIGN_PARAGRAPH.CENTER,after=2)
para("Prepared: <date>  ·  Prod snapshot: erp.walnutedu.in (<d>)  ·  UAT snapshot: uat.unityedu.tech (<d>)  ·  Core repositories compared: <n>",
     size=11,color=GREY,align=WD_ALIGN_PARAGRAPH.CENTER,after=10)

add_heading("Overview",level=2)
para("This document compares each application deployed on Production against the tip running on UAT. "
     "Changes are grouped at Pull-Request level and linked to their GitHub issue / PR; identical repos are listed as unchanged.",
     align=WD_ALIGN_PARAGRAPH.JUSTIFY)
caption("Table 0.1: Changed Repositories — UAT ahead of Production")
summary_table([ ["<Repo>","<prodSHA> → <uatSHA>", 0,0,0,0], ])
para("Totals — … . Every merged PR in each prod→UAT range was reconciled via the GitHub compare API (incl. reverts).",
     size=11,italic=True,color=GREY,after=4)

# One block per changed repo:
EQ="https://github.com/WalnutAppSuite/edu_quality"
para("",page_break=True)
repo_heading("Edu Quality","<prodSHA>","<uatSHA>",EQ,"Core school-management platform …")
caption("Table 1.1: Edu Quality — prod (<prodSHA>) → UAT develop (<uatSHA>).  Ref date = date PR merged into develop.")
RC="https://github.com/hybrowlabs/cn-recruitment"
change_table([
 # ref,   ref_url (Ref links to the PR),  date,   type,       change,           summary,             links = ISSUE(s)+docs,                       qa
 ("#3410", pr_url(EQ,3410),               "06-07","Bug Fix",  "<one-line change>","<fuller summary>",  [iss(EQ,3409)],                              "☐"),
 # cross-repo issue: cn-recruitment PR whose ticket lives in walnut_hrms, plus a doc link from the PR body
 ("#1243", pr_url(RC,1243),               "31-08","Feature", "Buddy on Job Offer","<summary>",         [xiss("WalnutAppSuite/walnut_hrms",86),
                                                                                                        doclink("Spec doc","https://docs.google.com/document/d/…")], "☐"),
 # no-PR direct commit: Ref links to the commit, Links may be empty
 ("<sha>", cm_url(EQ,"<sha>"),            "13-07","Other",   "<no-PR commit>",   "Direct commit …",   [],                                          "N/A"),
])

# Newly installed on UAT:
para("",page_break=True)
add_heading("Newly Installed on UAT (not on Production)",level=2)
para("Present on UAT but not installed on Production; net-new installs, listed with branch + commit.",align=WD_ALIGN_PARAGRAPH.JUSTIFY,after=6)
caption("Table N.1: Apps newly installed on UAT (not on Production)")
simple_table(["App","Repository","Branch","Commit"],
 [["Transporter",("WalnutAppSuite/Transporter","https://github.com/WalnutAppSuite/Transporter"),"main","260ed2a"]],linkcol=1)

# Unchanged + legend:
para("",page_break=True)
add_heading("Unchanged Repositories & Sign-off",level=2)
para("The following apps run the same commit on Production and UAT: … (list with SHAs).",align=WD_ALIGN_PARAGRAPH.JUSTIFY,after=6)
add_heading("Legend",level=3)
para("Feature (blue) — new functionality.  Bug Fix (red) — corrects behaviour.  Improvement/Other (grey) — refactor/maintenance/revert.",size=11,color=RGBColor(0x33,0x33,0x33))

doc.save("/home/aman/unity/walnut/docs/UAT vs Prod Comparison <YYYY-MM-DD>.docx")
```

---

## Self-verification snippet

```python
import docx
d=docx.Document(PATH)
# outline
for p in d.paragraphs:
    if p.style.name.startswith(('Title','Heading')) and p.text.strip(): print(p.style.name, p.text)
# per-repo PR completeness: compare {refs in table} to {PRs in gh compare range} -> assert equal
# ref cells are Heading 3:
assert d.tables[1].rows[1].cells[0].paragraphs[0].style.name=='Heading 3'
```
