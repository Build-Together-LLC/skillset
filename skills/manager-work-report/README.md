# Manager Work Report: what to give the skill

Say: "Make my work report for 15 Sept to today" (or "last week", "last month", "day wise for this
week") and share the items below. The skill pulls everything, writes the narrative and builds a
.docx with clickable links in `~/Downloads/docs`.

## Always give
1. **Date range**: dates, or words like last week, last month, this week, since 15 Sept.
2. **GitHub access**: a personal access token for each account (scopes: repo, read:org), or confirm
   the `gh` CLI is logged in on this machine. Name every account you commit from.

## Give what you have (each source makes the report stronger)
| Source | What to share | What it adds |
|---|---|---|
| Timesheet | URL, login, password | Hours, activity split, what you worked on each day |
| Jira | Site URL, email, API token | Closed, in-progress and blocked issues, sprint end |
| Console Log | CSV export of the Frappe Console Log list | Production data fixes by day |
| Documents | Folders where you save docs | Documents produced in the period |
| Context | Anything blocked or waiting on someone | Accurate blocked and ask sections |
| Audience | Manager name and what they care about | Tone and emphasis |

## Limit to an organisation or repo
Say "only UnityAppSuite" (or "only Org/repo") and the skill fetches PRs, reviews and commits from
that organisation or repo alone; other organisations are not pulled or shown. Several can be listed.
The timesheet, Jira, console log and documents are not tied to an organisation; skip them when you
want a commits-only report.

## Output choices
- **Full report** (default): summary, time split, week table, day by day, delivered work, pending,
  blocked, documents, asks.
- **Day wise**: 3 to 4 lines per day (time, work, delivered, extras), grouped by week.
- **Week wise**: weekly table with headlines plus the summary.
- **Quick summary**: what went well, pending and blocked on two pages.

## Safety
Credentials are used only for read-only calls and are never written into the report, memory or a
file. Rotate any token or password you paste into a chat. Customer names, bank and account numbers
and personal identifiers are masked or left out.
