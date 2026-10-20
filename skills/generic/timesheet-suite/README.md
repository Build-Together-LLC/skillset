# Timesheet Suite

Write your day in any way you like. Get back a clean timesheet and a ready-to-paste update for every chat app you use.

## What it does

You tell Claude what you worked on — a few bullets, a pasted chat, a long message, with or without hours. The
skill turns it into:

1. **A timesheet** (`timesheet_<date>.json`) in the exact format your Frappe site (ERPNext, HRMS, …) expects.
2. **One message per chat app you chose** — Discord, Slack, Microsoft Teams, Gmail, WhatsApp — each inside that
   app's length limit, with links kept while they fit.

When you ask, it can also:

- **Read your AI-coding chats** (Claude Code, OMP) for the day with `sessions`, so Claude can draft your update from
  what you actually worked on instead of from memory. Only your prompts and Claude's longer answers are read, secrets
  are redacted, and nothing leaves your computer.
- **Use GitHub** and **Jira** to add real PR titles, ticket names and links to your lines.
- **Save the timesheet on your site** as a draft, **submit** it (only when you say so), and later **update,
  cancel or amend** it.
- **Post the finished update** to a Discord or Slack channel through your own webhook (`post`), after you say yes.

It works with any Frappe site. Worked examples for two organisations are in `references/examples/`.

## What you need

- Claude Code with this skill installed (keep this whole folder together).
- Python 3. Nothing else to install.

## First time

Claude asks you once, in one message:

1. Your **Frappe site** — a name or URL, like `https://erp.mycompany.com`
2. Your **employee ID**, like `HR-EMP-00186`
3. Your **name**, as on your Employee record
4. Your **company**
5. Your **default project**
6. The **time your day starts**, like `09:30`
7. Which **chat apps** to write for — one, several, or none

Shortcut: share an API key and secret for the site and Claude looks up your Employee record and shows it to you to
confirm, instead of you typing items 2–4. Jira and GitHub are never part of setup; they come up only when you want them.

Everything is saved on your computer, so you are never asked again. To change something later just say so — "my
default project is IIMBX now", "also post to Slack", "drop WhatsApp". If you used an older version of this skill,
Claude only asks the two new things: the site and the chat apps.

## Every day

Just tell Claude about your day:

```
timesheet for today
- fixed the PDF bug on UAT, 2h
- reviewed Shruti's PRs
- call with Vasudha about Bhartiyam payroll (1h)
```

```
get me the update for 8 Sep — here's the chat from yesterday: …
```

- **Hours are optional.** Left out, Claude estimates them and tells you. "Make it 9 hours" splits the missing hours to reach 9. Hours that are only
  estimates are marked `"estimated": true` and are rescaled to the day's total in quarter hours; hours you stated
  (a 30-minute meeting) are never touched.
- **Projects:** everything goes to your default project unless you say otherwise.
- **Several days at once** ("27 and 28") gives one timesheet and one set of messages per day.

At the end Claude lists anything it guessed so you can fix it before posting.

## What you get

| File | What it is |
|---|---|
| `timesheet_<date>.json` | One line per task, times back to back from your start time, valid activity types and projects |
| `discord_<date>.md` | Discord update, under 2000 characters |
| `chat_slack_<date>.txt` | Slack message (4000 characters) |
| `chat_teams_<date>.md` / `.json` | Teams message to paste / card for a webhook |
| `chat_gmail_<date>.html` / `.txt` | Email: open the `.html`, select all, paste into a new Gmail message; the `.txt` starts with the subject |
| `chat_whatsapp_<date>.txt` | WhatsApp message |
| `github_<date>.json`, `jira_<date>.json` | Only if you used GitHub / Jira |

Saved in `~/Downloads/timesheets/` unless you pick another folder. After a build Claude shows each message and, for
every app, how much of its limit is used. If a message cannot fit, you are told which apps and by how much, and
Claude shortens the summaries — lines, links and hours are never dropped.

## Chat apps

Limits are listed in `references/chat_targets.md`. Notes: Slack's `<url|label>` links only work when sent through
your own webhook — pasted into the Slack box they show literally. The Teams `.json` is a card for a Workflows
webhook; the `.md` is for pasting. `build` itself never posts anything. Discord and Slack can be posted with
`post` (see below); Teams, Gmail and WhatsApp stay copy-and-paste.

## Optional: post to Discord or Slack

`post --date D --target discord|slack` sends the message `build` already wrote. Put your channel's webhook URL in
`DISCORD_WEBHOOK_URL` or `SLACK_WEBHOOK_URL` for that one run — it is never a flag, never saved and never printed.
The default is a dry run showing the destination host, the size and the first lines. Sending needs
`--confirm-post <target>/<date>`, asked of you each time. A day already posted is refused unless you add `--repost`,
and a failed send is never retried automatically, so you can't get two copies by accident.

## Optional: Jira

Say "include ticket ABC-123" or "pull my Jira tickets". Claude asks for your Jira site (`yourco.atlassian.net`),
your Atlassian **email** and an **API token**. The token is only given through the `JIRA_API_TOKEN` environment
variable and is never saved; the site and email can be saved if you wish. Tickets become links with their title
and status in your timesheet lines and in every chat message. Credentials only ever go to the Jira site you
confirmed — a ticket link someone pastes is never trusted as a destination. It never adds lines or hours by itself.

## Optional: GitHub

Share your **GitHub username(s)** and a **token** with read access. Claude looks up that day's commits, PRs you
opened, PRs you merged (including teammates') and reviews, and uses them to write better descriptions on the lines you
already mentioned. If GitHub shows work you didn't mention, Claude asks whether to add it and for how long. Usernames
can be saved; the token never is.

## Optional: save it on your site

Share your site's **API key and secret** (best) or email and password. Nothing is ever written until you say yes
for that specific action, and every command shows a dry run first.

| You want to | What happens | You will be asked |
|---|---|---|
| Save the day | A new draft is created, or the existing draft is replaced | yes, each time |
| Look at what's there | The remote timesheet is read back so you can change a line | nothing (read-only) |
| Change a draft | Only the lines that differ are updated; Claude shows the difference first | yes, each time |
| Change a submitted timesheet (**amend**) | It is cancelled and a new draft is made — it needs approval again | yes, each time |
| Cancel a submitted timesheet | It is cancelled | yes, each time |
| Delete a draft | It is removed permanently | yes, each time |
| **Submit** | The draft is submitted — or sent into your site's approval workflow | yes, **every time**, separately from saving |

It only submits when you say so, one timesheet at a time. Saving never submits, and "I'm done" does not count as a
request to submit. Each approval covers one action on one timesheet; if someone edits the timesheet in the
meantime, it stops and asks again. If your site uses an approval workflow, "waiting for approval" is a normal
result, not an error.

**The removed `sync --apply`:** older versions wrote with `sync --apply` and `--confirm-cancel`. Both are gone.
Writing now needs the flag that matches the action (`--confirm-create`, `--confirm-update`, `--confirm-cancel`,
`--confirm-delete`, `--confirm-submit`) plus `--expect-modified`; `sync` only creates or replaces a draft and tells
you to use `amend` for a submitted one.

**"attendance is not marked Present":** HRMS refuses a timesheet for a day without Present attendance —
in practice a Sunday or holiday. `build` warns about a Sunday up front. Retrying cannot help: get attendance marked
(or an Attendance Request approved) and re-run the same confirm command, or move the hours to another day.

## Keeping it safe

- Passwords, API keys and tokens are used for one run only and are never saved to a file.
- If you paste a secret into the chat, change it afterwards.
- Credentials are only sent to the site saved in your profile; changing that site needs your explicit confirmation.
  A server that tries to redirect elsewhere is refused.
- Before writing, the tool checks that the login really is the employee on the timesheet.
- The approval gate is honest about its limits: the program can't tell who typed a confirm flag. The protection is
  Claude asking you in the conversation, plus an optional Claude Code permission rule that makes every confirm command
  ask you again — merge `assets/claude_settings_snippet.json` into your Claude Code `settings.json`. Every applied
  change is also logged to `~/.config/timesheet-suite/audit.log` (no secrets).

## Common problems

| You see | What it means |
|---|---|
| `missing: site` (or other fields) | First run or an older profile — answer only what is missing |
| `ask which chat apps` (exit 2) | You haven't chosen chat apps yet; your timesheet JSON was still written |
| `is not a valid Activity Type — did you mean …` | That activity doesn't exist on your site; Claude picks the closest real one |
| `not validated for this site` | No Activity Type / Project list for your site yet — run `catalogue refresh` (needs API credentials) |
| `assuming INR` | Currency unknown until `catalogue refresh` reads it from your site |
| `Slack update is … characters` (any app) | Too long for that app; Claude shortens the summaries |
| `overlapping with TS-…` | Another timesheet already covers those hours |
| `confirmation_required` / `conflict` | A confirm flag didn't match, or the timesheet changed since you saw it — nothing was written |
| `redirected to a different host` | The site redirected your login elsewhere; it was refused. Check the site in your profile |
| `Jira rejected the credentials` | Wrong email, or not a classic API token |
| `activity feed … only reaches back to …` | For older dates GitHub can't show commits on side branches |
| `No GitHub token` / `No Frappe credentials` | The optional step needs the token or login first |
| `attendance is not marked Present` | The site won't take a timesheet for a day with no Present attendance (often a Sunday) — see above |
| `Entries add up to Xh but the target is Yh` | Hours you stated don't match the day's total; mark guessed hours `"estimated": true` so the total can rescale them |

## For developers

- `SKILL.md` — the instructions Claude follows.
- `scripts/timesheet_suite.py` — composition root: `build`, `github`, command dispatch. The rest lives in
  `ts_common` (shared helpers), `ts_profile`, `ts_catalogue`, `ts_chat`, `ts_jira`, `ts_frappe` (HTTP client),
  `ts_lifecycle` (sync / update / amend / cancel / submit / pull), `ts_sessions` (chat-history digest) and `ts_post`
  (Discord / Slack webhook). Python standard library only.
- Tests: `python3 -m unittest discover -s scripts` (fakes: `ts_fakes.py`, `ts_http_fake.py`, `ts_testkit.py`).
- `references/` — catalogue, chat limits, Jira, GitHub and Frappe API notes, plus `examples/` for two organisations.
- `assets/` — sample specs, the timesheet and every chat message built from them, a Jira digest, and the
  Claude Code settings snippet.
