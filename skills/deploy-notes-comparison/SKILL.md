---
name: deploy-notes-comparison
description: >
  Release tooling for a product deployed from git — most at home on Frappe/ERPNext, but nothing in it
  is Frappe-specific. It drives a THREE-STAGE release flow: (1) COMPARISON SHEET — a short,
  testing-team-facing .docx of what moved from the live branch to the candidate, every row ticket- and
  repo-hyperlinked, with a QA column the team marks MOVE or HOLD; (2) CURATED DEPLOYMENT PR —
  cherry-pick only the MOVE items onto the release branch, hold the rest, resolve conflicts, prove
  nothing held leaked, and open a PR with a provenance-linked description (opened, never merged by the
  skill); (3) NOTES + TRACKER — after merge, a client-shareable "Detailed Notes" .docx plus the
  "Feature x PR x Date Map" .xlsx, updated together. Products, branches, folders and tracker schemas
  come from a per-project config file, not from this skill. Trigger on "compare develop vs prod",
  "comparison sheet", "what moved for testing/sign-off" (Stage 1); "cherry-pick the move items",
  "create the deployment PR", "hold <TICKET>", "curated PR" (Stage 2); "create the Nth deployment
  doc/notes", "update the deployment sheet", "map PRs to a release" (Stage 3). Auto-detects product
  and stage; asks only for genuinely missing inputs. Uses document-builder for all .docx output.
---

# Deployment — Comparison → Curated PR → Notes & Tracker

This skill drives a **full three-stage release flow**. Detect the **product** (Step A) and the
**stage** (Step B), then follow that stage. The stages chain: a comparison feeds the decision, the
decision feeds the curated PR, the merged PR is written up as notes + tracker.

```
 ┌─ STAGE 1 ──────────┐   ┌─ STAGE 2 ─────────────────────┐   ┌─ STAGE 3 ────────────────┐
 │ COMPARISON SHEET   │   │ CURATED DEPLOYMENT PR         │   │ NOTES + TRACKER          │
 │ live vs candidate  │ → │ cherry-pick MOVE items onto   │ → │ client-shareable .docx + │
 │ .docx, per PR/fix, │   │ the release branch, HOLD rest,│   │ Feature×PR×Date .xlsx,   │
 │ ticket+repo links, │   │ resolve conflicts, verify no  │   │ updated together, after  │
 │ QA/decision col →  │   │ held leakage, open PR (DO NOT │   │ the PR is merged.        │
 │ team marks MOVE/   │   │ MERGE — user merges).         │   │                          │
 │ HOLD               │   │ Provenance-linked description.│   │                          │
 └────────────────────┘   └───────────────────────────────┘   └──────────────────────────┘
```

- **Stage 1 — Comparison sheet** (before a deploy): the sign-off aid. See `references/comparison-format.md`.
- **Stage 2 — Curated deployment PR** (the deploy itself): the cherry-pick onto the release branch.
  See `references/curated-pr.md`.
- **Stage 3 — Notes + tracker** (at/after the deploy): the durable record. Sections 3.x below.

All three read the **same underlying comparison** (live branch vs candidate). A run may be any one
stage, or the whole chain. A product that deploys a branch directly — no curated branch, no promotion
PR — uses Stages 1 and 3 only.

## The product config — read this first, every run

Nothing about any particular product lives in this skill. Branches, repos, folders, tracker schemas
and ticket bases are **config**, and they change. The skill reads them from the project, in this
order, and uses the first that exists:

```bash
ls .claude/deploy-products.md .claude/deploy-products.yml deploy-products.md 2>/dev/null | head -1
```

If none exists, say so and offer to create one from `references/products.example.md`, which is a
complete worked config for two real products — one with a promotion-PR flow and a curated release
branch, one deployed straight from a branch by a hosting provider. Do not guess a product's branches
or folders, and do not carry them from a previous session; read the file.

Each product block in that config supplies:

| Key | What it is |
|---|---|
| App / repo | `owner/repo` per tracked app, and the local clone path |
| Flow | promotion-PR (Develop → UAT → Prod) or direct-deploy (branch → host) |
| Live / candidate | which branch the site runs, and what it is compared against |
| Release branch | the curated branch Stage 2 targets, if the product has one |
| Release signal | the promotion PR, or the host's deploy job |
| Docs folder | where the .docx and tracker live |
| Doc filename / title | the naming convention for the series |
| Tracker | the glob for the single .xlsx, its column order, `status_col` and `ncols` |
| Required input | what to ask for when it is missing |
| Ticket base | the issue tracker URL and project keys |
| gh account | which account the repo needs, and any `gh` quirks |
| Baseline | the first-release window, for products whose series starts mid-history |

Shared libraries (all paths relative to this skill's own directory, `SKILL_DIR`):
- **Docs:** the `document-builder` skill's `scripts/docbuilder.py` — hyperlinks included. Never
  hand-roll python-docx.
- **Tracker styling/append helpers:** `scripts/xlsx_helpers.py`.
- **Per-product config:** the project file above; `references/products.example.md` is the template.
- **Comparison format + generator:** `references/comparison-format.md`.
- **Curated-PR recipe:** `references/curated-pr.md`.
- **Ticket linking + key detection:** `scripts/jira.py`, `references/jira.md`.

Run generators with a Python that has `python-docx` and `openpyxl` — the project venv if there is
one, otherwise `uv run --no-project --with python-docx --with openpyxl python <script>.py`. Write
generators to the session scratchpad first.

---

## Step A — Detect the PRODUCT

1. Read the config file. It defines the products; this skill does not.
2. Match on the words the user used — a product name, a site, a repo, an app — against the names and
   repos in that config.
3. Otherwise match the cwd against each product's local clone path.
4. One product defined → use it. Still ambiguous → ask, listing the configured names.

## Step B — Detect the STAGE

- "compare", "comparison sheet", "what moved", "for testing / QA / sign-off", "<live> vs <candidate>",
  "list the PRs & commits with one-liners" → **Stage 1** (comparison sheet).
- "cherry-pick the move items", "create the deployment/curated PR", "PR to <release branch>", "hold
  <TICKET> / the ones still in testing", "do not merge, I'll merge" → **Stage 2** (curated PR).
- "create deployment #N", "detailed notes", "deployment doc", "update the sheet/tracker", "map the PRs"
  → **Stage 3** (notes + tracker).
- "compare and give me the sheet + the deployment doc" usually means the **whole chain** — do Stage 1,
  surface the comparison for the decision, then (on the go-ahead) Stage 2, then Stage 3 after merge.
  Ask only if genuinely unclear.

---

## Rules & standards (all stages, every product)

1. **Never invent behaviour.** Every description comes from the **actual code diff** (`gh pr diff`,
   `gh api .../commits/<sha>`, `git show`). Can't confirm → mark unverified.
2. **Feature-level summary is the default (2–4 pages).** Group PRs/commits into features. Full
   PR×commit bifurcation only when the user explicitly asks for "all PRs and commits".
3. **Describe the NET live state.** Added-then-reverted in-window → describe what is *actually live*;
   explain the walk-back.
4. **Always surface guards, flags, roles and cron** — anything that is off by default, gated by a
   setting or a role, or driven by a scheduler. A reader needs to know what is live versus merely
   shipped. This is what makes the artifact trustworthy.
5. **Absolute dates only** (`18 October 2026`); convert a host's "X days ago" to a real date.
6. **State what the release does NOT change** when it is true and material.
7. **Multi-app products:** pull **every** tracked repo each run, carry the **`App`** column, and
   compute the window **per app**.
8. **Hyperlink everything you can** (see below) — PRs, commits, tickets/issues, the site.
9. Follow the project's own commit and PR conventions — attribution, comment style, author identity.
   They are the user's, not this skill's.
10. **gh account and quirks** come from the config. Some repos need a specific account, and some
    reject `gh pr edit` / `gh pr create` (Projects-classic) so PR bodies must go through `gh api`.
    Check the config before blaming the command.
11. **Verify before finishing** and report absolute paths + a short changelog.

### Hyperlinks (required wherever possible)

The `.docx` output (every stage) carries **live hyperlinks**, matching how the tracker links its PR
column. `docbuilder` renders a `Link(text, url)` anywhere text is accepted — in `body`, `bullet`, and
any `table` cell, alone or inside a list of parts:

```python
import sys, pathlib
SKILL_DIR = pathlib.Path("~/.claude/skills/deploy-notes-comparison").expanduser()
sys.path.insert(0, str(SKILL_DIR.parent / "document-builder" / "scripts"))
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from docbuilder import DocBuilder, Link, pr_url, commit_url, issue_url
# pr_url("owner/repo", 154) · commit_url("owner/repo", "ab60570") · issue_url("owner/repo", 42)
from jira import jira_url, find_keys          # linking + key detection (no token)

d.bullet(["Warehouse batch pricing removed via ", Link("#234", pr_url(REPO, 234)), "."])
d.table(["Change", "Ticket", "PR(s)"], [[
    "Announce scheme on threshold",
    Link("PROJ-271", jira_url("PROJ-271")),
    [Link("#227", pr_url(REPO, 227)), ", ", Link("#236", pr_url(REPO, 236))],
]])
```

Link, at minimum: **every PR** → `pr_url`; **every no-PR direct commit** → `commit_url`; **every
ticket** → `jira_url(key)`; **linked GitHub issues** → `issue_url`; the **build commit** in the meta
block → `commit_url`; the **site**, where the product has one → its URL. Detect keys in branch names /
PR titles+bodies / commit messages with `find_keys(text)`. Never fabricate a URL — link only
PRs/commits/issues confirmed via `gh`, and ticket keys actually seen. `find_keys` returns candidates,
not facts: `UTF-8` and `ISO-8601` match the shape, so validate with `get_issue(key)` or only link keys
that also appear in a branch name, PR title or commit trailer. Repo bases and the ticket base are in
the product config; ticket detail in `references/jira.md`.

**Ticket API token:** only needed to validate/enrich/list — read from env (`JIRA_BASE_URL`,
`JIRA_EMAIL`, `JIRA_API_TOKEN`); NEVER hardcode or commit it. `scripts/jira.env.example` has the
setup. If a token is ever pasted in chat, remind the user to rotate it and never write it to a file
or a commit.

---

# STAGE 1 — Comparison sheet (testing-team sign-off)

A **short, reviewable** `.docx`: *what moved* from the live branch to the candidate, so the team signs
off (and decides MOVE vs HOLD per row) **before** the deploy. Full format, reconciliation recipe, doc
structure and generator are in **`references/comparison-format.md`**. Essentials:

- **Sides.** Live = the branch the site actually runs, per the config — for a curated-release product
  that is the release branch, not the nominal `prod`. Candidate = the config's candidate branch tip,
  or a shared promotion-PR head. Multi-app products: one pair of sides **per app**, each app's live
  side being its last-deployed commit.
- **Reconcile EVERY PR and commit** in the range with the GitHub compare API (release-note lists miss
  items); assert `{refs in doc} == {PRs in range}` → "missing: []". No-PR commit → its own row (Ref =
  SHA). Reverts → own row + note.
- **One row per change**, columns `Ref | Type | Change | Summary | Jira | QA / Tested`. Ref hyperlinks
  to the PR/commit; **Jira is its own column** (hyperlinked); classify Feature / Bug Fix / Other.
- **The QA / Tested column is also the decision column.** The team marks each row tested, and which
  items MOVE this cycle vs HOLD (e.g. "No / still in testing", "<TICKET> held"). That marked sheet is the
  input to Stage 2 — capture the held set exactly (ticket + child tickets).
- Multi-app products: one section per app, in the config's order; carry links the same way throughout.
- Save to the product's docs folder as `<DD-MM-YYYY> — <Product> Deploy Comparison (<candidate> vs
  <live branch>[, held: …]).docx`. **Stage 1 does not touch the tracker or any branch.**

---

# STAGE 2 — Curated deployment PR (cherry-pick onto the release branch)

Only for a product whose config defines a **release branch**; a direct-deploy product skips this
stage. Take the Stage-1 decision and build the actual deployment: cherry-pick the **MOVE** items
onto the release branch, **hold** the rest, resolve conflicts, prove nothing held leaked, and open a
PR. **We DO NOT merge it — the user merges.** Full recipe (git/gh commands, conflict strategy,
verification, PR-body template) is in **`references/curated-pr.md`**. The shape:

1. **Inputs.** The MOVE set (PR numbers + any no-PR commit SHAs) and the HOLD set (tickets incl. child
   tickets — a parent ticket holds its children too). The release branch is the base; the site runs it.
2. **Switch gh account** to the one the config names for this repo; `git fetch upstream --prune`. Map each PR → its merge
   commit (`gh pr view <n> --json mergeCommit,...`). A squash/direct commit is picked as-is; a true
   merge commit is picked with `-m 1`.
3. **Branch off** the release branch in a **separate worktree** (never disturb the user's working
   tree): `git worktree add -b batch/<theme>-<DD-MM-YYYY> <scratch> upstream/<release branch>`.
   Set the commit author to whatever that branch's history already uses.
4. **Cherry-pick in chronological (merge/commit-date) order** to minimise conflicts. Resolve each
   conflict by keeping only the MOVE content and the branch's own context (rack hooks etc.); drop any
   hunk that belongs to a held ticket. A file that is wholly a held ticket is dropped entirely.
5. **Verify no leakage (the important part).** For every touched file, diff the result against
   `develop`: it should be byte-identical **except** the files a held ticket also edits (those keep the
   branch's non-held version). `grep` the net diff for held module/function names to prove they're
   absent. Compile changed `.py` (`py_compile`) and validate changed `.json`.
6. **Push and open the PR via `gh api`** (not `gh pr edit`/`create`):
   `gh api --method POST repos/<owner>/<repo>/pulls -f title=… -f head=… -f
   base=<release branch> -f body="$(cat body.md)"`. **Do not merge.** The description links each
   PR/commit (hyperlinks), says which commit did what, lists the HELD items and why, and states what
   the release does not change, plus any flags. Follow the project's PR conventions.
7. **Report** the PR number/URL, the commit stack, the verification result (held items absent), and
   that it is left **open for the user to merge**. Offer bench testing only if asked (it disturbs the
   working tree). Flag that the gh account was switched.

---

# STAGE 3 — Notes + Tracker (the durable, client-shareable record)

Produced **after** the curated PR is merged, or after a direct-deploy product's site is deployed. **Both** deliverables,
always kept consistent:
- `.docx` — `N. YYYY-MM-DD _ <Product> Deployment - Detailed Notes .docx` (client-shareable; short,
  2–4 pages, business-first, every PR/commit/Jira hyperlinked).
- `.xlsx` — the single tracker for that product, edited **in place** (created on the first run), then
  renamed to today's date if that is the product convention.

### 3.1 Establish the window (gather inputs; ASK if missing)

| Flow | Window | Missing → ask |
|---|---|---|
| **Promotion-PR flow** | last `Deployments` row → prev build; target = the merge commit of the curated release PR (Stage 2), or the current release-branch tip. `prevBuild..target`. | the curated PR number / merge commit, or whether to target the current release-branch tip |
| **Direct-deploy flow** | last `Deployments` row → prev build **per app**; target = the commit each branch was deployed to (read from the host's apps/build view), or the branch tip. Window computed **independently per app**. | per-app build commit at the target deploy + the deploy date; always pull every tracked repo |

```bash
git fetch upstream --prune
ls -t "<docs folder>/"*.xlsx | head -1          # find the tracker (never hardcode the filename)
gh pr list --repo <owner>/<repo> --state merged --base <branch> --limit 200 \
  --json number,title,mergedAt,mergeCommit,headRefName -q 'sort_by(.mergedAt)[] | "\(.number) \(.mergedAt[:10]) \(.mergeCommit.oid[:8]) | \(.title)"'
```

### 3.2 Enumerate every PR + direct commit (per app, for multi-app products)
Reconcile the PR list against the raw commit delta — **direct pushes (no PR) must still be documented**.
On a curated release branch the provenance PRs are the *curated* ones, but the feature content traces
back to the original candidate-branch PRs — cite both when useful, and the true `git diff --stat
prev..target` for what actually changed.

### 3.3 Read the real diffs
`gh pr diff <PR>` / `gh api repos/<o>/<r>/commits/<sha>`. Write feature-level business lines. Surface
flags/guards/roles/cron and any in-window revert (net live state). For a curated-release product,
state the **held** set — what is deliberately NOT live — as part of the trustworthy record.

### 3.4 Write the .docx (docbuilder, with hyperlinks)
`page_break=False` on every `h1` to stay compact. Standard section order (the established series):
`In plain terms (business view)` → `1. Features / changes` → `2. Bug fixes` → `3. Important
operational notes` → `Provenance` → `Open questions`. For a multi-app product, split the feature/bug
tables **per app** or add an `App` column. Meta block links the build commit; feature/bug tables link
every PR/commit/ticket. Titles, filenames and the exact meta fields per product are in the config.

### 3.5 Update the tracker .xlsx (in place)
Load with openpyxl; clone existing-row styles via `scripts/xlsx_helpers.py` (`header_style()` paints
the dark-blue `FF1F4E78` band). Exact column orders and `status_col`/`ncols` per product are in
`references/products.md`. Per release:
1. **`Deployment Map`** — insert one row per feature/fix before the trailing blank + `Legend:` row
   (`insert_map_rows`); multi-app products set the **`App`** cell; set `Current Status` fill by outcome; flip any
   earlier row whose state changed.
2. **`All PRs (task list)`** — append the window's PRs (`append_row`; with `App` when multi-app); Link column = PR URL.
3. **`Deployments`** — append row `N` (multi-app: per-app build commits + per-app scope ranges).
4. **New dated sheet `YYYY-MM-DD`** — `add_dated_sheet` (copies the previous dated sheet, wipes rows 2+,
   writes this release's rows + footer).

Status fills: green `FFC6EFCE` (deployed & working), red `FFFFC7CE` (reverted / not live), yellow
`FFEA9999` (paused / in progress). After updating, **rename the tracker to today's date** if that is
the product convention (e.g. `… - DD-MM-YYYY.xlsx`).

If documenting a curated PR that is **not yet merged**, say so and record the branch tip as the build
with a `(PR #n)` note; once merged, swap in the real merge commit.

### 3.6 Verify & report
Re-open both: docx headings + table dims + hyperlink count > 0; xlsx new rows, legend still last, new
dated sheet present, status fills + App column correct. Report absolute paths + a short changelog, and
send the files to the user.

---

## Conventions carried across the series
- Dates absolute; convert a host's "X days ago" to a real date.
- Match the project's code-comment convention in anything generated.
- State what a release does **not** change when it is true and material.
- Restate flag-gated behaviour every release it is touched, naming the default.
- A curated-release product's site runs the release branch, not `prod` — the held set is real and
  must be stated; the curated PR is opened but **merged by the user**.
- Multi-app products: always pull every repo, carry the `App` column, describe NET live state after
  any revert.
- Follow the project's commit and PR conventions. Where the config flags it, set PR bodies via
  `gh api --method PATCH repos/<o>/<r>/pulls/<n> -f body=@file` (and POST to create), because
  `gh pr edit`/`create` fail on Projects-classic repos.
