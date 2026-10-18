# STAGE 1 — Pre-deploy Comparison Sheet: format & generator

A **short, reviewable** `.docx` for the testing team: *what moved* from the live branch to the
candidate, so they sign off — and mark each row **MOVE** or **HOLD** — before the deploy. That marked
sheet is the direct input to **Stage 2** (`references/curated-pr.md`). Adapted from the Walnut
`uat-prod-deploy-comparison` skill, retargeted to the BT products (Vidira / GUIN) and built on
`document-builder` so it shares the house style and hyperlink support.

**Live side (what to compare against):** VIDIRA defaults to `upstream/prod-autoreorder` — the curated
branch the prod site actually runs — not `prod`; use `prod` only if explicitly asked. Candidate =
`develop` tip (or a shared Prod PR head). GUIN: per app, branch tip vs last-deployed commit.

Repo bases: VIDIRA `Vidira-Innovations/vidira_group`; GUIN Taraknath `Vidira-Innovations/taraknath`,
POSNext `Build-Together-LLC/POSNext`.

## Buckets (when comparing two snapshots / branch pairs)
- **Changed** — present on both sides, commit differs → full change table.
- **Unchanged** — identical commit → one line (with SHA) in the sign-off section.
- **Newly installed** — on the candidate but not prod → App | Repository | Branch | Commit (no deep diff).
- **Version drift / not this cycle** — third-party/framework bumps, or a diff merged weeks ago
  (prod merely lagging) → brief drift note, not a table.

For VIDIRA/GUIN there is usually just the one (or two) tracked app(s) changing, so most runs are a
single changed-repo section — keep it lean.

## Reconciliation (don't miss anything)
```bash
gh api "repos/<owner>/<repo>/compare/<baseSHA>...<headSHA>" --paginate \
  --jq '.commits[] | "\(.sha[0:7])  \(.commit.author.date[0:10])  \(.commit.message | split("\n")[0])"'
gh api "repos/<owner>/<repo>/compare/<baseSHA>...<headSHA>" --paginate --jq '.commits[].sha' \
  | while read s; do gh api "repos/<owner>/<repo>/commits/$s/pulls" --jq '.[].number'; done | sort -un
gh pr view <n> --repo <owner>/<repo> --json number,title,url,mergedAt,state,body,closingIssuesReferences
```
- Every PR included; assert `{refs in doc} == {PRs in range}` → print "missing: []".
- No-PR commit → its own row, Ref = commit SHA.
- **Reverts** → own row (Type = Other) + a note on the reverted item; watch for revert-of-revert.
- A number that is a GitHub **issue** (not a PR) → Links column, never a change row.
- Ref = the PR/commit (hyperlinked). Links = the linked **issue(s)** (cross-repo aware) + any
  doc/spec links from the PR body. The PR is the Ref, not a Links entry.

## Doc structure (keep it to the point)
1. **Title** (docbuilder `title`): `<DD-MM-YYYY> — <Product> Deploy Comparison (prod vs <candidate>)`.
2. One-line subtitle: base → head per app, date, who prepared it.
3. **Summary table**: `Repository / App | base → head | Changes | Features | Bug Fixes | Other` + a totals line.
4. One **`h1` per changed repo/app** (page_break=False): a url/range line, then the change table
   `Ref | Type | Change | Summary | Jira | QA / Tested`. Ref hyperlinks to the PR/commit; **Jira is its
   own column**, hyperlinked via `jira_url(key)` (a row may map to one ticket, several, or none).
5. **Newly installed** (if any) + **Unchanged & sign-off** (SHAs) + a one-line **Legend**.

Classify each change: **Feature / Bug Fix / Improvement-Other**. Terse Change label + short Summary
from the PR title/body. `QA / Tested` starts as an empty checkbox `☐` — the tester ticks it **and uses
it as the MOVE/HOLD decision** ("Yes — Aman", "No / still in testing", "VE-277 held"). Capture that
marked decision verbatim: it is the MOVE/HOLD input to Stage 2, so the held set (ticket + child
tickets) must be unambiguous.

## Generator template (docbuilder-based, with hyperlinks)

```python
import os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/document-builder/scripts"))
from docbuilder import DocBuilder, Link, pr_url, commit_url, issue_url
sys.path.insert(0, os.path.expanduser("~/.claude/skills/bt-prod-deploy-notes-comparison/scripts"))
from jira import jira_url, find_keys

VIDIRA = "Vidira-Innovations/vidira_group"          # or taraknath / POSNext for GUIN

d = DocBuilder(
    title="17-10-2026 — Vidira Deploy Comparison (develop vs prod-autoreorder, held: VE-277/VE-348)",
    subtitle="prod-autoreorder f57f091 → develop c0b4d1e · for testing-team sign-off before deploy",
    meta={
        "Prepared": "17 October 2026",
        "Live (prod site)": Link("f57f091 (prod-autoreorder)", commit_url(VIDIRA, "f57f091")),
        "Candidate": Link("c0b4d1e (develop)", commit_url(VIDIRA, "c0b4d1e")),
        "Scope": "vidira_group develop vs prod-autoreorder",
    },
)

d.h1("Summary", page_break=False)
d.table(["Repository", "base → head", "Changes", "Features", "Bug Fixes", "Other"],
        [["vidira_group", "9d825ee → ec091b1", 6, 2, 3, 1]],
        caption="Changed repositories — candidate ahead of prod")

d.h1("vidira_group", page_break=False)
d.body([Link("github.com/" + VIDIRA, "https://github.com/" + VIDIRA),
        "  —  prod 9d825ee → develop ec091b1"])
d.table(["Ref", "Type", "Change", "Summary", "Jira", "QA / Tested"],
        [
            [Link("#293", pr_url(VIDIRA, 293)), "Feature",
             "Dispatch Slip issued even when Cash Discount is OFF",
             "A submitted non-return Sales Invoice issues its draft Dispatch Slip regardless of the CD flag.",
             Link("VE-346", jira_url("VE-346")), "☐"],
            [Link("#296", pr_url(VIDIRA, 296)), "Bug Fix",
             "Customer primary address & contact section restored",
             "A Property Setter unhides the section ERPNext began hiding (WhatsApp no., Country, notif fields).",
             "—", "☐"],                                   # no ticket → em dash
            # no-PR direct commit → Ref is the commit; still link Jira if the message has a key
            [Link("5023fc1", commit_url(VIDIRA, "5023fc1")), "Bug Fix",
             "party.set_price_list doctype-arg fix",
             "custom_set_price_list accepts the doctype arg ERPNext 16.36.1+ passes.",
             Link("VE-272", jira_url("VE-272")), "☐"],
        ],
        caption="vidira_group — develop → prod-autoreorder.  Ref = PR/commit; tick QA / mark MOVE-HOLD.")

d.h1("Sign-off", page_break=False)
d.bullet("Unchanged apps: <list with SHAs>.")
d.bullet("Legend — Feature: new capability · Bug Fix: corrects behaviour · Other: refactor / perf / revert.")

d.save("<docs folder>/17-10-2026 — Vidira Deploy Comparison (develop vs prod-autoreorder, held VE-277-VE-348).docx")
```

Notes:
- For a **no-PR commit** put `Link(sha, commit_url(repo, sha))` as the Ref.
- **Jira column:** `Link(key, jira_url(key))` — `jira_url` needs no credentials and works for any
  project key. A row with no ticket → `"—"`. Several tickets → a list of `Link`s joined by `", "`.
  Detect keys from the branch name / PR title+body / commit message with `find_keys(text)`.
- docbuilder tables use the house header band + alternating rows; per-type row colour-coding is not
  applied by default. If the user wants Feature/Bug/Other colour bands, post-process the returned
  table object (`t = d.table(...)`) and shade the Type cell per row — otherwise leave it plain to
  keep the reviewer doc simple.

## Self-verify
```python
import docx
from docx.oxml.ns import qn
doc = docx.Document(PATH)
print("hyperlinks:", len(doc.element.body.findall('.//'+qn('w:hyperlink'))))   # > 0
for p in doc.paragraphs:
    if p.style.name.startswith(("Title", "Heading")) and p.text.strip():
        print(p.style.name, p.text)
# assert {refs in each change table} == {PR numbers in the gh compare range} -> "missing: []"
```
