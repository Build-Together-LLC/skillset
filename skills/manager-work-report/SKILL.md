---
name: manager-work-report
description: >
  Produce a manager-ready work report (.docx with clickable PR, commit and Jira links) for any date
  range from the user's real activity: GitHub pull requests and commits from one or more accounts or
  tokens, the timesheet, Jira, the System Console log and the documents folders. Gives a summary
  (what went well, what is pending, what is blocked, asks), where the time went, a week-by-week
  table, and a day-by-day log with 3 to 4 lines per day (time split, what was worked on, what was
  delivered), plus appendices of every merged PR. Trigger on: "work report", "status report for my
  manager", "what did I do from <date> to <date>", "last week", "last month", "this week", "daily
  report", "day wise", "week wise", "standup summary", "what went well, pending, blocked", "share with
  manager", "pull my commits and PRs", or "report from timesheet and GitHub". Works for a single day,
  a week, a month or any custom range.
---

# Manager Work Report

Turn evidence into a report a manager can read in five minutes and verify in five clicks. Every
claim must trace to a PR, commit, Jira key, timesheet row, console run or document. Never invent
work, blockers or numbers.

A generic example narrative is in `references/example_narrative.json`.
`README.md` tells the user what to provide.

## Step 0 - Intake (do not stall)

1. **Date range.** Convert natural language to ISO dates (today comes from the system date):
   "last week" = previous Monday to Sunday; "this week" = this Monday to today; "last month" = the
   previous calendar month; "from Sept 15" = that date to today. Ask only if the range is missing.
2. **Detail level.** Default is the full report. If the user asks for day-wise or week-wise output,
   set `--sections` (see Step 4). If they say "3 to 4 lines per day", the Day by Day section already
   produces exactly that.
3. **Sources and credentials.** Use what the user already shared in the conversation or memory. Needed
   per source: GitHub token per account (or `gh auth token` if the gh CLI is logged in), timesheet
   URL and login, Jira site, email and API token, optional Console Log CSV, optional docs folders.
   Skip a source if it is missing and say so in the report. Use credentials read-only through
   environment variables; never write them to a file, the report or memory.
4. **Audience.** Default "Reporting manager". Keep wording factual and free of internal gossip.

## Step 1 - Collect

```bash
FROM=2026-09-15 TO=2026-10-20 OUT=$SCRATCH/report_data.json \
GH_ACCOUNTS='{"login1":"<token1>","login2":"<token2>"}' \
TS_HOST=https://<timesheet host> TS_USER=<user> TS_PWD='<password>' \
JIRA_HOST=https://<site>.atlassian.net JIRA_EMAIL=<email> JIRA_TOKEN='<token>' \
CONSOLE_CSV="<path>/Console Log.csv" DOCS_DIRS="<dir1>:<dir2>" \
python3 -I scripts/collect_activity.py
```

It gathers, for the range: PRs merged, PRs closed without merge, PRs opened, all PRs open now,
teammate PRs reviewed, commits (default branch of every repo the token can reach), timesheet rows,
Jira issues the user is assignee or reporter on that changed in the range, System Console runs per
day and per script (titles are masked), and documents modified in the range (private-looking file
names are skipped by the builder). All sources are optional.

If the timesheet is a Frappe site, login is `POST /api/method/login`; if two passwords are given,
try the second only after a 401. A denied or blocked call must not be retried in a disguised form;
report it and continue with the other sources.

## Step 2 - Read the data before writing

Print counts and the PR list by repo (Read tool, not sed). Check: merged versus closed-unmerged
(consolidated or reverted PRs are not failures), open PR ages, Jira statuses and sprint end dates,
hours per day and activity, console themes. Decide what the real themes are.

## Step 3 - Write the narrative JSON

Fields (see the example file): `title`, `subtitle`, `prepared_by`, `audience`, `status`, `sources`,
`extra_orgs`, `jira_prefixes`, `summary` (3 to 4 paragraphs), `went_well`, `pending`,
`blocked_summary`, `blocked` (list of item, why, need, owner), `themes` (title, text, refs),
`weekly_headlines` (key = Monday date), `time_notes`, `pending_detail`, `asks`, optional
`daily_overrides` (key = date, value = list of lines).

Rules:
- **Went well**: outcomes with evidence links (go-lives, promotions, fixes, closed Jira, documents).
- **Pending**: open PRs older than a few days, Jira not done, held features, sprint end.
- **Blocked**: only things the evidence supports (stale open PRs, items waiting on another party,
  items in Understanding or Testing for long, missing access, decisions without owner). State what
  is needed and who owns it. Mark anything you cannot confirm as "status to be confirmed" and ask
  the user to confirm before sharing.
- Use PR tokens like `Org/repo#123` and Jira keys like `VE-98`; the builder turns them into links.
- Do not name customers, bank or account numbers, employee or student identifiers, or secrets.
- Check numbers against the generated tables: the overview table is computed, so reuse its figures.

## Step 4 - Build

```bash
<python with python-docx> -I scripts/build_report.py \
  --data $SCRATCH/report_data.json --narrative <narrative.json> \
  --out ~/Downloads/docs/Work_Report_<FROM>_to_<TO>.docx \
  [--sections summary,time,weekly,daily,delivered,pending,blocked,docs]
```

Use a Python that has python-docx (a bench env works); it also needs the sibling `document-builder` skill, or set `DOCBUILDER_SCRIPTS`. Section presets:
- Full report: omit `--sections`.
- Day wise only: `--sections daily`.
- Week wise: `--sections summary,weekly,time,pending,blocked`.
- Quick manager summary: `--sections summary,pending,blocked`.
- Single day: set FROM and TO to the same date and use `--sections daily`.

Per-day lines are generated from data: **Time** (hours and activity split, combined activities split
equally), **Worked on** (first sentence of the largest timesheet entries, links stripped), **Delivered**
(PRs merged with links, commits per repo, Jira closed) and **Also** (console fixes, teammate reviews,
documents). Weekends without activity are omitted. Rewrite a day with `daily_overrides` when a
sentence is cut or unclear.

## Step 5 - Verify and report

- Open the .docx with python-docx: no blank table cells, headings are real styles, count hyperlinks,
  grep the text for every password and token you were given (must be zero) and for account numbers.
- Page count: `libreoffice --headless --convert-to pdf --outdir <folder under the user's home>`,
  then `pdfinfo`; delete the PDF unless asked.
- Reply with the path, page count, three headline numbers, what is blocked, and anything you could
  not collect. Tell the user to rotate credentials they pasted.

## Gotchas

- GitHub search covers 1,000 results per query and commits come from default branches only; quote
  commit counts as lower bounds. Fork and upstream copies of a PR can double count; the collector
  dedupes by repo and number.
- Timesheet rows may use combined activities ("Coding + Debugging"); the builder splits hours equally.
- A day with PRs but no timesheet row is shown with "no timesheet entry".
- The auto-mode classifier may block calls to production hosts; do not work around a denial.
- Console Log titles can contain account identifiers; the collector masks long digit runs and hides
  scripts that read integration settings.
