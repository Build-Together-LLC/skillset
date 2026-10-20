# STAGE 1 — Pre-deploy Comparison Sheet: format & generator

A **short, reviewable** `.docx` for the testing team: *what moved* from the live branch to the
candidate, so they sign off — and mark each row **MOVE** or **HOLD** — before the deploy. That marked
sheet is the direct input to **Stage 2** (`references/curated-pr.md`). Built on `document-builder`
so it shares the house style and hyperlink support.

**Live side (what to compare against):** the branch the site actually runs, per the product config.
For a curated-release product that is the release branch, **not** the nominal `prod` — use `prod`
only if explicitly asked. Candidate = the config's candidate branch tip, or a shared promotion-PR
head. Multi-app products: per app, branch tip vs that app's last-deployed commit.

Repo bases come from the product config.

## Buckets (when comparing two snapshots / branch pairs)
- **Changed** — present on both sides, commit differs → full change table.
- **Unchanged** — identical commit → one line (with SHA) in the sign-off section.
- **Newly installed** — on the candidate but not prod → App | Repository | Branch | Commit (no deep diff).
- **Version drift / not this cycle** — third-party/framework bumps, or a diff merged weeks ago
  (prod merely lagging) → brief drift note, not a table.

Most products track one or two apps, so most runs are a single changed-repo section — keep it lean.

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
it as the MOVE/HOLD decision** ("Yes — <name>", "No / still in testing", "<TICKET> held"). Capture that
marked decision verbatim: it is the MOVE/HOLD input to Stage 2, so the held set (ticket + child
tickets) must be unambiguous.

## Generator template (docbuilder-based, with hyperlinks)

```python
import sys, pathlib
SKILL_DIR = pathlib.Path("~/.claude/skills/deploy-notes-comparison").expanduser()
sys.path.insert(0, str(SKILL_DIR.parent / "document-builder" / "scripts"))
sys.path.insert(0, str(SKILL_DIR / "scripts"))
from docbuilder import DocBuilder, Link, pr_url, commit_url, issue_url
from jira import jira_url, find_keys

REPO = "<owner>/<repo>"                             # from the product config

d = DocBuilder(
    title="17-10-2026 — <Product> Deploy Comparison (<candidate> vs <live>, held: PROJ-277/PROJ-348)",
    subtitle="<live> f57f091 → <candidate> c0b4d1e · for testing-team sign-off before deploy",
    meta={
        "Prepared": "17 October 2026",
        "Live (site)": Link("f57f091 (<live branch>)", commit_url(REPO, "f57f091")),
        "Candidate": Link("c0b4d1e (<candidate branch>)", commit_url(REPO, "c0b4d1e")),
        "Scope": "<app> <candidate> vs <live>",
    },
)

d.h1("Summary", page_break=False)
d.table(["Repository", "base → head", "Changes", "Features", "Bug Fixes", "Other"],
        [["<app>", "9d825ee → ec091b1", 6, 2, 3, 1]],
        caption="Changed repositories — candidate ahead of prod")

d.h1("<app>", page_break=False)
d.body([Link("github.com/" + REPO, "https://github.com/" + VIDIRA),
        "  —  prod 9d825ee → develop ec091b1"])
d.table(["Ref", "Type", "Change", "Summary", "Jira", "QA / Tested"],
        [
            [Link("#293", pr_url(REPO, 293)), "Feature",
             "Dispatch Slip issued even when Cash Discount is OFF",
             "A submitted non-return Sales Invoice issues its draft Dispatch Slip regardless of the CD flag.",
             Link("PROJ-346", jira_url("PROJ-346")), "☐"],
            [Link("#296", pr_url(REPO, 296)), "Bug Fix",
             "Customer primary address & contact section restored",
             "A Property Setter unhides the section ERPNext began hiding (WhatsApp no., Country, notif fields).",
             "—", "☐"],                                   # no ticket → em dash
            # no-PR direct commit → Ref is the commit; still link Jira if the message has a key
            [Link("5023fc1", commit_url(REPO, "5023fc1")), "Bug Fix",
             "party.set_price_list doctype-arg fix",
             "custom_set_price_list accepts the doctype arg ERPNext 16.36.1+ passes.",
             Link("PROJ-272", jira_url("PROJ-272")), "☐"],
        ],
        caption="<app> — develop → <live branch>.  Ref = PR/commit; tick QA / mark MOVE-HOLD.")

d.h1("Sign-off", page_break=False)
d.bullet("Unchanged apps: <list with SHAs>.")
d.bullet("Legend — Feature: new capability · Bug Fix: corrects behaviour · Other: refactor / perf / revert.")

d.save("<docs folder>/17-10-2026 — <Product> Deploy Comparison (<candidate> vs <live branch>, held PROJ-277-PROJ-348).docx")
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
