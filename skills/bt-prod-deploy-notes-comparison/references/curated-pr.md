# STAGE 2 — Curated deployment PR onto `prod-autoreorder` (VIDIRA)

The prod SITE `vidira.m.frappe.cloud` runs the curated **`prod-autoreorder`** branch, not `prod`.
Each deploy = cherry-pick the Stage-1 **MOVE** items from `develop` onto `prod-autoreorder`, **hold**
the rest (tickets still in testing + their child tickets), resolve conflicts, prove nothing held
leaked, and open a PR. **We open it; the user merges it.** Never merge it yourself unless told to.

Repo: `Vidira-Innovations/vidira_group`. Base: `prod-autoreorder`.

## 0. Inputs (ask if missing)
- **MOVE set** — PR numbers, plus any no-PR direct-commit SHAs (e.g. a `party.py` signature fix pushed
  straight to develop).
- **HOLD set** — tickets NOT moving this cycle, *including child tickets* (e.g. `VE-277` and its
  children, `VE-348`, `VE-271` if held). Get this exactly from the marked Stage-1 comparison.
- Confirm the base is `prod-autoreorder` (default) and that we are **not** to merge.

## 1. Account + fetch
```bash
gh auth switch --user maskeddefender          # the Vidira repo 404s on amankumarui
gh api repos/Vidira-Innovations/vidira_group --jq .full_name   # sanity: should print the repo
git fetch upstream --prune
```

## 2. Map each MOVE item → the commit to pick
```bash
for n in <PRs>; do
  gh pr view $n --repo Vidira-Innovations/vidira_group \
    --json number,title,mergedAt,mergeCommit,headRefName \
    --jq '"#\(.number) merge=\(.mergeCommit.oid[:8]) mergedAt=\(.mergedAt[:10]) \(.title)"'
done
# parent count: 2 = true merge (pick with -m 1); 1 = squash/direct (pick as-is)
git rev-list --parents -n1 <sha> | wc -w        # 3 tokens ⇒ 2 parents ⇒ merge
```
A PR's `-m 1` diff (`git diff <merge>^1 <merge>`) is exactly the net change that PR added to develop.

## 3. Branch in a separate worktree (don't disturb the user's tree)
```bash
WT=<scratchpad>/wt-autoreorder
git worktree add -b batch/<theme>-<DD-MM-YYYY> "$WT" upstream/prod-autoreorder
cd "$WT"
git config user.name  "Aman Kumar"
git config user.email "amanupadhayay2906@gmail.com"     # match the branch's commit convention
```

## 4. Cherry-pick in chronological order
Order the picks by merge/commit date (oldest first) so later work lands on its real predecessors —
fewest conflicts.
```bash
git -c core.editor=true cherry-pick -m 1 <merge-sha>    # true merge
git -c core.editor=true cherry-pick      <sha>          # squash / direct commit
```

### Conflict resolution strategy
Conflicts arise where `prod-autoreorder` differs from `develop` in a touched file — usually because a
**held** ticket (or an already-applied curated pick like the rack hooks) also edits it.
- Keep **only** the MOVE content plus the branch's own existing context (e.g. the rack
  `before_validate` hook already on prod-autoreorder). Add the new line into the existing list.
- **Drop any hunk that belongs to a held ticket** — do not pull its surrounding lines in just to make
  the patch apply.
- A file that is **wholly** a held ticket → drop it entirely (`git rm` / don't stage it). Example: in
  an earlier deploy `overrides/party.py` was 100% VE-272 and was dropped; when VE-272 later moved, the
  file came back via its own pick.
- A later hardening of a MOVE file that lives inside a **held** commit stays out — keep the MOVE
  version even if it means the file is not byte-identical to `develop` (that's expected, see §5).

Resolve, then `git add <file>` and `git -c core.editor=true cherry-pick --continue`.

## 5. Verify no held leakage (the important part)
```bash
# every touched file vs develop: MATCHES unless a held ticket also edits it
for f in $(git diff --name-only upstream/prod-autoreorder..HEAD); do
  git diff --quiet HEAD upstream/develop -- "$f" && echo "MATCHES  $f" || echo "DIFFERS  $f"
done
```
Expect **MATCHES develop** for every MOVE file, and **DIFFERS** only for files a held ticket also
touches (hooks.py carrying only the moved hooks; a file whose newer version is inside a held commit).
For each DIFFERS file, read the net diff and confirm the gap is *only* held content:
```bash
git diff HEAD upstream/develop -- <file> | grep -E '^\+' | grep -v '^\+\+\+'   # what develop still has that we don't
git diff upstream/prod-autoreorder..HEAD -- <file>                            # what we added (should be MOVE-only)
```
`grep` the added diff for held module/function names (e.g. `selling_price.sync_free_items`,
`scheme_alerts.bundle.js`, a held override) to prove they are absent. Also confirm no held selling/
scheme files (`selling_price.py`, `sales_order.py`, `pick_list*`, the scheme bundle) appear in the
touched-file list at all unless intended.

New top-level functions a MOVE adds should reference **no** `vidira_group` held module — grep the
added lines: `git diff ... | grep -oE 'vidira_group\.[a-z_.]+' | sort -u`.

Finally, sanity-build:
```bash
git diff --name-only upstream/prod-autoreorder..HEAD -- '*.py'  | xargs -I{} <venv>/python -m py_compile {}
for j in $(git diff --name-only upstream/prod-autoreorder..HEAD -- '*.json'); do <venv>/python -c "import json;json.load(open('$j'))" && echo "OK $j"; done
```

## 6. Push + open the PR (via `gh api`, NOT `gh pr create/edit`)
```bash
git push upstream batch/<theme>-<DD-MM-YYYY>
gh api --method POST repos/Vidira-Innovations/vidira_group/pulls \
  -f title='<theme> → prod-autoreorder (holding <HELD tickets>)' \
  -f head='batch/<theme>-<DD-MM-YYYY>' \
  -f base='prod-autoreorder' \
  -f body="$(cat <scratchpad>/pr_body.md)" \
  --jq '"PR #\(.number)  \(.html_url)  [\(.state)]"'
# verify body landed (this repo sometimes needs a follow-up PATCH):
gh pr view <n> --repo Vidira-Innovations/vidira_group --json baseRefName,headRefName,body \
  --jq '"base=\(.baseRefName) head=\(.headRefName) body_chars=\(.body|length)"'
# if body empty: gh api --method PATCH repos/.../pulls/<n> -f body="$(cat body.md)"
```
**Do not merge.** Leave it open for the user.

### PR body template (hyperlinked, no Claude attribution)
```markdown
Curated deployment onto **`prod-autoreorder`** (the branch `vidira.m.frappe.cloud` runs) of the items
signed off in the <DD-MM-YYYY> Deploy Comparison. Cherry-picked from `develop`; **<HELD tickets> are
deliberately held** and are not in this PR.

Base: `prod-autoreorder` · <N> commits · <F> files · no functional change beyond the items below.

## What moves
| Ref | Type | Change | Jira |
|---|---|---|---|
| [#NNN](…/pull/NNN) + [`sha`](…/commit/sha) | Bug/Feature | one line: what it does + the key technical detail | [VE-xxx](…/browse/VE-xxx) |

## Held — NOT in this PR
- **VE-xxx** — one line why (and the PR/commit it lives in, linked).

## Provenance & safety
- Cherry-picked chronologically; conflicts resolved to MOVE-only. Every touched file is byte-identical
  to `develop` except <file> (reason) and <file> (reason).
- No change to GST or core pricing. CD OFF by default; Auto Reorder module flag-gated OFF.
- Migrate installs: <custom fields / patches the picks add>.
```
End the body with nothing Claude-related. (The repo's general attribution footer does **not** apply —
user memory forbids Claude attribution on our commits/PRs.)

## 7. Report
Give the PR number/URL, the commit stack (`git log upstream/prod-autoreorder..HEAD`), the §5 result
(held items confirmed absent, compiles/JSON valid), and that it is **left open for the user to merge**.
Mention the gh account was switched to `maskeddefender`. Offer bench testing only if asked — it needs
the branch checked out in the live bench and would disturb the user's working tree.

## Gotchas seen in this series
- `prod-autoreorder` moves while you work — a prior PR may merge mid-task. Re-check its tip; a new PR
  then branches off the new tip (a merged PR can't be added to).
- `upstream/develop` can be stale → force-fetch `+refs/heads/develop:refs/remotes/upstream/develop`;
  use the `gh api .../compare` range as authoritative for provenance.
- Some bench test failures are environmental (no FiscalYear linked to the test company; pagination over
  a large restored local catalog), not code defects — confirm against develop before blaming the pick.
- A PR number and a Jira number can coincide (GitHub PR #277 ≠ Jira VE-277) — don't conflate them.
