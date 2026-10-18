---
name: bt-prod-deploy-notes-comparison
description: >
  Build-Together deployment tooling for two ERPNext products — VIDIRA (Vidira-Innovations/vidira_group;
  the prod SITE vidira.m.frappe.cloud runs the curated `prod-autoreorder` branch, fed from `develop`)
  and GUIN (guinerp.m.frappe.cloud running Vidira-Innovations/taraknath @ develop + Build-Together-LLC/POSNext
  @ BT). It drives the THREE-STAGE release process we actually follow: (1) COMPARISON SHEET — a short,
  testing-team-facing .docx of what moved from the live branch to the candidate (develop / a branch / a
  shared Prod PR), every row Jira- and repo-hyperlinked, with a QA/decision column; the team marks each
  row MOVE or HOLD. (2) CURATED DEPLOYMENT PR — cherry-pick only the MOVE items onto `prod-autoreorder`,
  hold the rest (e.g. VE-277 + children still in testing), resolve conflicts, verify nothing held leaked,
  and open a PR with a provenance-linked description — we DO NOT merge it; the user merges. (3) NOTES +
  TRACKER — after merge, the client-shareable "Detailed Notes" .docx plus the "Feature x PR x Date Map"
  .xlsx, updated together. Trigger on: "compare develop vs prod/prod-autoreorder", "comparison sheet",
  "what moved for testing/sign-off" (→ Stage 1); "cherry-pick the move items", "create the deployment PR
  to prod-autoreorder", "hold VE-xxx", "curated PR" (→ Stage 2); "create the Nth deployment doc/notes",
  "update the deployment sheet", "map PRs to a release" (→ Stage 3). GUIN + VIDIRA. Auto-detects product
  and stage; asks only for genuinely missing inputs. Uses document-builder for all .docx output.
---

# BT Prod Deployment — Comparison → Curated PR → Notes & Tracker (Vidira + GUIN)

This one skill drives the **full three-stage release flow we follow**, for two products. Detect the
**product** (Step A) and the **stage** (Step B), then follow that stage. The stages chain: a comparison
feeds the decision, the decision feeds the curated PR, the merged PR is written up as notes + tracker.

```
 ┌─ STAGE 1 ──────────┐   ┌─ STAGE 2 ─────────────────────┐   ┌─ STAGE 3 ────────────────┐
 │ COMPARISON SHEET   │   │ CURATED DEPLOYMENT PR         │   │ NOTES + TRACKER          │
 │ live vs candidate  │ → │ cherry-pick MOVE items onto   │ → │ client-shareable .docx + │
 │ .docx, per PR/fix, │   │ prod-autoreorder, HOLD rest,  │   │ Feature×PR×Date .xlsx,   │
 │ Jira+repo links,   │   │ resolve conflicts, verify no  │   │ updated together, after  │
 │ QA/decision col →  │   │ held leakage, open PR (DO NOT │   │ the PR is merged.        │
 │ team marks MOVE/   │   │ MERGE — user merges).         │   │                          │
 │ HOLD               │   │ Provenance-linked description.│   │                          │
 └────────────────────┘   └───────────────────────────────┘   └──────────────────────────┘
```

- **Stage 1 — Comparison sheet** (before a deploy): the sign-off aid. See `references/comparison-format.md`.
- **Stage 2 — Curated deployment PR** (the deploy itself): the cherry-pick onto `prod-autoreorder`.
  See `references/curated-pr.md`.
- **Stage 3 — Notes + tracker** (at/after the deploy): the durable record. Sections 3.x below.

All three read the **same underlying comparison** (live branch vs candidate). A run may be any one
stage, or the whole chain. VIDIRA almost always; GUIN uses Stages 1 & 3 (no curated branch — it
deploys `develop`/`BT` directly via Frappe Cloud).

Shared libraries:
- **Docs:** `document-builder` → `~/.claude/skills/document-builder/scripts/docbuilder.py`
  (supports hyperlinks — see "Hyperlinks"). Never hand-roll python-docx.
- **Tracker styling/append helpers:** `scripts/xlsx_helpers.py` next to this skill.
- **Per-product config** (repos, branches, folders, tracker schemas, GUIN baseline): `references/products.md`.
- **Comparison format + generator:** `references/comparison-format.md`.
- **Curated-PR recipe** (cherry-pick, hold, conflict resolution, verification, PR body): `references/curated-pr.md`.
- **Jira linking + key detection:** `scripts/jira.py`, `references/jira.md`.

Run generators with the venv (deps installed there):
```bash
/home/aman/personal/buildtogether/env/bin/python <script>.py
```
(Fallback: `uv run --no-project --with python-docx --with openpyxl python <script>.py`.) Write
generators to the session scratchpad first.

---

## Step A — Detect the PRODUCT

1. Explicit words: "GUIN"/"guinerp"/"taraknath"/"pos_next"/"POSNext" → **GUIN**;
   "vidira"/"vidira_group"/"prod"/"prod-autoreorder"/"UAT" → **VIDIRA**.
2. The repo(s) named, or the cwd (`apps/taraknath` or `apps/pos_next` → GUIN; `apps/vidira_group` → VIDIRA).
3. Still ambiguous → ask.

## Step B — Detect the STAGE

- "compare", "comparison sheet", "what moved", "for testing / QA / sign-off", "prod/prod-autoreorder
  vs develop", "list the PRs & commits with one-liners" → **Stage 1** (comparison sheet).
- "cherry-pick the move items", "create the deployment/curated PR", "PR to prod-autoreorder", "hold
  VE-xxx / Shruti's PRs / the ones still in testing", "do not merge, I'll merge" → **Stage 2** (curated PR).
- "create deployment #N", "detailed notes", "deployment doc", "update the sheet/tracker", "map the PRs"
  → **Stage 3** (notes + tracker).
- "compare and give me the sheet + the deployment doc" usually means the **whole chain** — do Stage 1,
  surface the comparison for the decision, then (on the go-ahead) Stage 2, then Stage 3 after merge.
  Ask only if genuinely unclear.

---

## Rules & standards (all stages, both products)

1. **Never invent behaviour.** Every description comes from the **actual code diff** (`gh pr diff`,
   `gh api .../commits/<sha>`, `git show`). Can't confirm → mark unverified.
2. **Feature-level summary is the default (2–4 pages).** Group PRs/commits into features. Full
   PR×commit bifurcation only when the user explicitly asks for "all PRs and commits".
3. **Describe the NET live state.** Added-then-reverted in-window → describe what is *actually live*;
   explain the walk-back.
4. **Always surface guards, flags, roles, cron** — CD `CD Applicable` OFF by default, Auto Reorder
   module flag-gated OFF, role gates, per-profile settings, negative-stock blocks, scheduler on/off.
   This is what makes the artifact trustworthy.
5. **Absolute dates only** (`18 October 2026`); convert Frappe-Cloud "X days ago" to a real date.
6. **State what the release does NOT change** (GST / core pricing) when true.
7. **GUIN:** pull **both** repos every time; carry the **`App`** column; compute the window **per app**.
8. **Hyperlink everything you can** (see below) — PRs, commits, Jira/issues, the site.
9. **No Claude attribution** on any commit or PR we create (user memory). **Minimal comments** in any
   code/generator — no docstrings, no explanatory comments; explain in chat.
10. **gh account:** the Vidira repo needs the **`maskeddefender`** account (`gh auth switch --user
    maskeddefender`); `amankumarui` 404s. `gh pr edit`/`gh pr create` are **broken** here
    (Projects-classic) → use `gh api` (see Stage 2 and below).
11. **Verify before finishing** and report absolute paths + a short changelog.

### Hyperlinks (required wherever possible)

The `.docx` output (every stage) carries **live hyperlinks**, matching how the tracker links its PR
column. `docbuilder` renders a `Link(text, url)` anywhere text is accepted — in `body`, `bullet`, and
any `table` cell, alone or inside a list of parts:

```python
from docbuilder import DocBuilder, Link, pr_url, commit_url, issue_url
# pr_url("owner/repo", 154) · commit_url("owner/repo", "ab60570") · issue_url("owner/repo", 42)
import sys; sys.path.insert(0, "<skill>/scripts")
from jira import jira_url, find_keys          # linking + key detection (no token)

d.bullet(["Warehouse batch pricing removed via ", Link("#234", pr_url(REPO, 234)), "."])
d.table(["Change", "Jira", "PR(s)"], [[
    "Announce scheme on threshold",
    Link("VE-271", jira_url("VE-271")),
    [Link("#227", pr_url(REPO, 227)), ", ", Link("#236", pr_url(REPO, 236))],
]])
```

Link, at minimum: **every PR** → `pr_url`; **every no-PR direct commit** → `commit_url`; **every Jira
ticket** → `jira_url(key)` (`https://buildtogether.atlassian.net/browse/<KEY>`, no credentials, any
project key); **linked GitHub issues** → `issue_url`; the **build commit** in the meta block →
`commit_url`; the **site** (GUIN) → its URL. Detect keys in branch names / PR titles+bodies / commit
messages with `find_keys(text)`. Never fabricate a URL — link only PRs/commits/issues confirmed via
`gh`, and Jira keys actually seen (optionally validate with `get_issue(key)`; `None` → wrong key, keep
it plain). Repo bases are in `references/products.md`; Jira detail in `references/jira.md`.

**Jira token:** only needed to validate/enrich/list — read from env (`JIRA_EMAIL`, `JIRA_API_TOKEN`,
`JIRA_BASE_URL`); NEVER hardcode or commit it. `scripts/jira.env.example` has the setup. If a token is
ever pasted in chat, remind the user to rotate it and never write it to a file/commit.

---

# STAGE 1 — Comparison sheet (testing-team sign-off)

A **short, reviewable** `.docx`: *what moved* from the live branch to the candidate, so the team signs
off (and decides MOVE vs HOLD per row) **before** the deploy. Full format, reconciliation recipe, doc
structure and generator are in **`references/comparison-format.md`**. Essentials:

- **Sides.** VIDIRA: live = current `upstream/prod-autoreorder` (what the prod site runs; use `prod`
  only if explicitly asked); candidate = `develop` tip, or a shared Prod PR head. GUIN: per app —
  taraknath `develop` vs last-deployed commit, pos_next `BT` vs last-deployed commit.
- **Reconcile EVERY PR and commit** in the range with the GitHub compare API (release-note lists miss
  items); assert `{refs in doc} == {PRs in range}` → "missing: []". No-PR commit → its own row (Ref =
  SHA). Reverts → own row + note.
- **One row per change**, columns `Ref | Type | Change | Summary | Jira | QA / Tested`. Ref hyperlinks
  to the PR/commit; **Jira is its own column** (hyperlinked); classify Feature / Bug Fix / Other.
- **The QA / Tested column is also the decision column.** The team marks each row tested, and which
  items MOVE this cycle vs HOLD (e.g. "No / still in testing", "VE-277 held"). That marked sheet is the
  input to Stage 2 — capture the held set exactly (ticket + child tickets).
- GUIN per app (Taraknath section, then POSNext); carry links the same way Vidira does.
- Save to the product's docs folder as `<DD-MM-YYYY> — <Product> Deploy Comparison (<candidate> vs
  prod-autoreorder[, held: …]).docx`. **Stage 1 does not touch the tracker or any branch.**

---

# STAGE 2 — Curated deployment PR (cherry-pick onto prod-autoreorder)

VIDIRA only. Take the Stage-1 decision and build the actual deployment: cherry-pick the **MOVE** items
onto `prod-autoreorder`, **hold** the rest, resolve conflicts, prove nothing held leaked, and open a
PR. **We DO NOT merge it — the user merges.** Full recipe (git/gh commands, conflict strategy,
verification, PR-body template) is in **`references/curated-pr.md`**. The shape:

1. **Inputs.** The MOVE set (PR numbers + any no-PR commit SHAs) and the HOLD set (tickets incl. child
   tickets, e.g. VE-277 and its children, VE-348). `prod-autoreorder` is the base; the prod site runs it.
2. **Switch gh account** to `maskeddefender`; `git fetch upstream --prune`. Map each PR → its merge
   commit (`gh pr view <n> --json mergeCommit,...`). A squash/direct commit is picked as-is; a true
   merge commit is picked with `-m 1`.
3. **Branch off** `upstream/prod-autoreorder` in a **separate worktree** (never disturb the user's
   working tree): `git worktree add -b batch/<theme>-<DD-MM-YYYY> <scratch> upstream/prod-autoreorder`.
   Set the commit author to the branch's convention (`Aman Kumar <amanupadhayay2906@gmail.com>`).
4. **Cherry-pick in chronological (merge/commit-date) order** to minimise conflicts. Resolve each
   conflict by keeping only the MOVE content and the branch's own context (rack hooks etc.); drop any
   hunk that belongs to a held ticket. A file that is wholly a held ticket is dropped entirely.
5. **Verify no leakage (the important part).** For every touched file, diff the result against
   `develop`: it should be byte-identical **except** the files a held ticket also edits (those keep the
   branch's non-held version). `grep` the net diff for held module/function names to prove they're
   absent. Compile changed `.py` (`py_compile`) and validate changed `.json`.
6. **Push and open the PR via `gh api`** (not `gh pr edit`/`create`):
   `gh api --method POST repos/Vidira-Innovations/vidira_group/pulls -f title=… -f head=… -f
   base=prod-autoreorder -f body="$(cat body.md)"`. Base = `prod-autoreorder`. **Do not merge.** The
   description links each PR/commit (hyperlinks), says which commit did what, lists the HELD items and
   why, and states no-GST/pricing-change + flags. **No Claude attribution.**
7. **Report** the PR number/URL, the commit stack, the verification result (held items absent), and
   that it is left **open for the user to merge**. Offer bench testing only if asked (it disturbs the
   working tree). Flag that the gh account was switched.

---

# STAGE 3 — Notes + Tracker (the durable, client-shareable record)

Produced **after** the curated PR is merged (or the GUIN site is deployed). **Both** deliverables,
always kept consistent:
- `.docx` — `N. YYYY-MM-DD _ <Product> Deployment - Detailed Notes .docx` (client-shareable; short,
  2–4 pages, business-first, every PR/commit/Jira hyperlinked).
- `.xlsx` — the single tracker for that product, edited **in place** (created on first GUIN run), then
  renamed to today's date if that is the product convention.

### 3.1 Establish the window (gather inputs; ASK if missing)

| Product | Window | Missing → ask |
|---|---|---|
| **VIDIRA** | last `Deployments` row → prev build; target = the merge commit of the curated **prod-autoreorder** PR (Stage 2), or the current `upstream/prod-autoreorder` tip. `prevBuild..target`. | the curated PR number / merge commit, or whether to target the current `prod-autoreorder` tip |
| **GUIN** | last `Deployments` row → prev build **per app**; target = the commit each branch was deployed to (Frappe-Cloud **Apps** tab), or the branch tip. Window computed **independently per app**. | per-app build commit at the target deploy + the deploy date; always pull **both** repos |

```bash
git fetch upstream --prune
ls -t "<docs folder>/"*.xlsx | head -1          # find the tracker (never hardcode the filename)
gh pr list --repo <owner>/<repo> --state merged --base <branch> --limit 200 \
  --json number,title,mergedAt,mergeCommit,headRefName -q 'sort_by(.mergedAt)[] | "\(.number) \(.mergedAt[:10]) \(.mergeCommit.oid[:8]) | \(.title)"'
```

### 3.2 Enumerate every PR + direct commit (per app for GUIN)
Reconcile the PR list against the raw commit delta — **direct pushes (no PR) must still be documented**.
On prod-autoreorder the provenance PRs are the *curated* ones (e.g. #301), but the feature content
traces to the original `develop` PRs — cite both when useful, and the true `git diff --stat
prev..target` for what actually changed.

### 3.3 Read the real diffs
`gh pr diff <PR>` / `gh api repos/<o>/<r>/commits/<sha>`. Write feature-level business lines. Surface
flags/guards/roles/cron and any in-window revert (net live state). For VIDIRA, state the **held** set
(what is deliberately NOT live on prod-autoreorder) — it is part of the trustworthy record.

### 3.4 Write the .docx (docbuilder, with hyperlinks)
`page_break=False` on every `h1` to stay compact. Standard section order (the established series):
`In plain terms (business view)` → `1. Features / changes` → `2. Bug fixes` → `3. Important
operational notes` → `Provenance vs legacy v15 app` → `Open questions`. For **GUIN**, split the
feature/bug tables **per app** (Taraknath, then POSNext) or add an `App` column. Meta block links the
build commit; feature/bug tables link every PR/commit/Jira. Titles, filenames and the exact meta
fields per product are in `references/products.md`.

### 3.5 Update the tracker .xlsx (in place)
Load with openpyxl; clone existing-row styles via `scripts/xlsx_helpers.py` (`header_style()` paints
the dark-blue `FF1F4E78` band). Exact column orders and `status_col`/`ncols` per product are in
`references/products.md`. Per release:
1. **`Deployment Map`** — insert one row per feature/fix before the trailing blank + `Legend:` row
   (`insert_map_rows`); GUIN sets the **`App`** cell; set `Current Status` fill by outcome; flip any
   earlier row whose state changed.
2. **`All PRs (task list)`** — append the window's PRs (`append_row`; GUIN: with `App`); Link column = PR URL.
3. **`Deployments`** — append row `N` (GUIN: per-app build commits + per-app scope ranges).
4. **New dated sheet `YYYY-MM-DD`** — `add_dated_sheet` (copies the previous dated sheet, wipes rows 2+,
   writes this release's rows + footer).

Status fills: green `FFC6EFCE` (deployed & working), red `FFFFC7CE` (reverted / not live), yellow
`FFEA9999` (paused / in progress). After updating, **rename the tracker to today's date** if that is
the product convention (Vidira: `… - DD-MM-YYYY.xlsx`).

If documenting a curated PR that is **not yet merged**, say so and record the branch tip as the build
with a `(PR #n)` note; once merged, swap in the real merge commit.

### 3.6 Verify & report
Re-open both: docx headings + table dims + hyperlink count > 0; xlsx new rows, legend still last, new
dated sheet present, status fills + App column correct. Report absolute paths + a short changelog, and
send the files to the user.

---

## Conventions carried across the series
- Dates absolute; convert Frappe-Cloud "X days ago" to a date.
- Generated Python uses `#` comments only, no docstrings (house preference).
- State what a release does **not** change (GST / core pricing) when true.
- Restate flag-gated behaviour every release it is touched (CD OFF; Auto Reorder module flag-gated OFF).
- VIDIRA prod site runs **`prod-autoreorder`**, a curated branch fed from `develop` — the held set is
  real and must be stated; the curated PR is opened but **merged by the user**.
- GUIN: always pull BOTH repos, carry the `App` column, describe NET live state after any revert.
- No Claude attribution on commits/PRs; set PR bodies via `gh api --method PATCH
  repos/<o>/<r>/pulls/<n> -f body=@file` (and POST to create) — `gh pr edit`/`create` fail here.
