# GitHub API — how `github` finds a day's work

`scripts/timesheet_suite.py github` is optional. It only runs when the user shares a GitHub username
and a token, and it only reads. The token comes from `GITHUB_TOKEN` (or `GH_TOKEN`) for that run and is
never saved.

## The day

Every query uses the user's calendar day, not UTC: `YYYY-MM-DDT00:00:00+05:30 .. T23:59:59+05:30` with
the profile's `utc_offset`. A commit at 00:10 IST on 9 Sep belongs to 9 Sep even though it is still
8 Sep in UTC.

## Calls, and why each is needed

| What | Call | Why this way |
|---|---|---|
| Commits (default branches) | `GET /search/commits?q=author:<user> author-date:<day>` | Fast, but **commit search only covers each repo's default branch** |
| Commits (any branch) | `GET /users/<user>/events` → `PushEvent`s that day → `GET /repos/<repo>/compare/<before>...<head>` | Push events see every branch. Their payload no longer lists commits, so the before/head range is compared to get them |
| PRs raised | `GET /search/issues?q=is:pr author:<user> created:<day>` | Includes the PR description and whether it was merged |
| PRs merged by the user | `GET /search/issues?q=is:pr is:merged org:<org> merged:<day>`, then `GET /repos/<repo>/pulls/<n>` | "Merged by" can't be searched; each merged PR is fetched and kept only if `merged_by` is the user. That's why orgs are needed |
| Reviews | `GET /search/issues?q=is:pr reviewed-by:<user> updated:>=<day start>`, then `GET /repos/<repo>/pulls/<n>/reviews` | Search can't filter by review date; reviews are kept only if submitted that day |

If `--orgs` isn't given (and the profile has no `github_orgs`), merged PRs are looked for in the orgs of
the repos that showed up in the day's commits, PRs and reviews. A day with only merges then finds
nothing — set the orgs.

## Two usernames

People often commit under one account and push or merge under another. Pass every username. Commits
with the same repo and first line are merged into one item with all their SHAs, so the same change
isn't counted twice.

## Limits and warnings

- **Search API:** 30 requests a minute; each search returns at most 300 results here. If more exist,
  a warning says how many were used.
- **Activity feed:** GitHub keeps only the latest 300 events (90 days at most). For older dates the
  script warns that branch-only commits before that point can't be seen; default-branch commits are
  still found by search.
- **Private repos:** the token must be able to read them, or they are silently missing from results.
- **Other people's accounts:** a token can't see another account's private activity feed. Search may
  also refuse that username ("The listed users cannot be searched") — that becomes a warning and the
  rest of the digest still runs.

## Cleaning descriptions

PR descriptions and commit bodies are reduced to plain text: HTML comments (PR templates), heading
marks, checkbox brackets and bot trailers (`Co-Authored-By`, `Generated with Claude Code`, session
links) are removed, and long text is cut at 600 characters. Summarise from this — don't paste it.
