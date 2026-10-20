# Activity Types — Hybrowlabs defaults (example snapshot)

**This is the bundled snapshot of one site's list — `operate.hybrowlabs.com`.** It is the validator
and the guide ONLY when the profile's site is `operate.hybrowlabs.com` and no refreshed cache exists.
On any other Frappe site the bundled list does not apply: run `catalogue refresh` to read that site's
own enabled Activity Types, then search them with `catalogue list --type activity --match <text>`
(see `references/catalogue.md`). Without a cache on another site, builds skip Activity Type validation
and warn once — the site itself rejects unknown values on sync.

**Hybrowlabs source:** `references/activity_types.csv` (exported from the Frappe `Activity Type`
doctype; the rows below are that export — the CSV is authoritative if they ever differ).
`activity_type` on `Timesheet Detail` is a **Link field**, so the value you write must match one of the
site's entries **byte-for-byte** — same words, same capitalisation, same spacing around `+`. Frappe
rejects anything else. The matching rules below hold for any site; the quirks and the list are
Hybrowlabs-specific.

---

## Matching rules (apply in order; quirks cited are the Hybrowlabs list)

1. **Exact match first.** Take the text before the first colon in the user's line and look for it
   verbatim in the list below. Most lines — including combined ones — are already present.

2. **Combined activities usually exist verbatim — do not decompose them.** Present in the list:
   `Coding + Meeting`, `Debugging + Meeting`, `Meeting + Debugging`, `Coding + Debugging`,
   `Testing + Debugging`, `Coding + Testing`, `Coding + Research`, `Coding + Learning`,
   `Learning + Research`, `Meeting + Working`, `Meeting + testing`, `Setup + Debugging`,
   `Coding + Setup`, and more. Both `Debugging + Meeting` and `Meeting + Debugging` now exist,
   so keep whichever order the user wrote.

3. **Respect the stored capitalisation, even when it looks wrong.** `DEBUGGING` is all-caps;
   `working`, `followups`, `others`, `wiki`, `funnel`, `support`, `integration`, `blocker`,
   `git conflict`, `laptop issue`, `bug fix` are lower-case. If the user writes `Debugging`
   alone, output `DEBUGGING`. If they write `Working`, output `working`.

4. **Respect the stored spacing.** Irregular-spacing variants exist as separate records — copy the
   one you matched exactly: `Coding +Testing` (no space after `+`) vs `Coding + Testing`;
   `Setup+Coding` vs `Coding + Setup`; `setup+meeting`, `coding+debugging`, `Coding+Learning`,
   `Meeting+Learning`, `Coding + Meeting +Debugging`, `Coding+Meeting+Learning`.

5. **Do not "fix" typos that exist in the system** — reproduce them as-is:
   `Content Desiging & Copywriting`, `Learnning Frappe`, `Learning Frapee from Youtube`,
   `RPNext Dev Environment Setup and Debugging`, `Meating Regarding project`,
   `reading freappe LMS doc`, `Requirement Understanding Vedio`, `Setuping the system`,
   `Setuping + Learning`, `Create sharefable Demo`, `Sales Traning`,
   `frappe app (LMS)  installation` (two spaces before `installation`).

6. **The recurring special case: `Coordination`.** The user writes `Coordination:` constantly, but
   there is **no `Coordination` activity type** in the master list. Map every `Coordination` line to
   **`Communication`** (the closest real type) and note the substitution once in the ⚠️ section.
   The same goes for `X + Coordination` combos that don't exist (`Meeting + Coordination`,
   `Debugging + Coordination`, `Planning + Coordination`): map to the non-coordination half's
   real type — `Meeting`, `Debugging + Meeting`, `Planning` respectively — and flag once.
   (If `Coordination` is ever added to Frappe, add it to `activity_types.csv` and this rule goes away.)

7. **Other combos that are NOT in the list** — map to the primary (first) token's real type and flag:
   `Coding + Deployment` → `Deployment` for deploy-led work or `Coding` for code-led;
   `Documentation + Coding` / `Coding + Documentation` → `Documentation` if the deliverable is a doc,
   else `Coding`; `Meeting + Planning` → `Planning`; `Meeting + Coding` → `Coding + Meeting`
   (canonical order). Never invent a new combined type.

8. **Ignore the one-off sentence-shaped entries** unless the user's text matches them almost
   verbatim (e.g. `Facilitated and Resolved Bundling Error for Chatnext Team on GMeet`,
   `Learning Because work not Assigned`). Prefer a generic type.

9. **No match at all?** Fall back to the **dominant real activity** of the line first (what did the
   person mostly do — code, debug, meet, deploy, document, test?), and only if nothing fits use
   `Other` / `Work` / `Task`. Always flag a fallback in the ⚠️ section, quoting what the user wrote
   and what you chose. **Never invent an activity type.**

---

## Quick reference — most common

| User writes | Use |
|---|---|
| coding / development | `Coding` |
| debugging / bug fixing | `DEBUGGING` |
| debugging + meeting (either order) | `Debugging + Meeting` or `Meeting + Debugging` |
| coding + meeting | `Coding + Meeting` |
| coding + debugging | `Coding + Debugging` |
| coding + testing | `Coding + Testing` |
| testing / QA | `Testing` |
| research | `Research` |
| research + review | `Research and Review` |
| meeting / standup / scrum | `Meeting` |
| internal meeting | `Internal Meeting` |
| client meeting | `Client Meeting` |
| discussion | `Discussion` |
| **coordination / coordinated with X** | **`Communication`** (no `Coordination` type exists) |
| learning / studying | `Learning` |
| code review / PR review | `Code review` (lower-case r — `Code Review` doesn't exist) |
| deployment / release / UAT deploy | `Deployment` |
| documentation / writing docs | `Documentation` |
| planning | `Planning` |
| setup / environment setup | `Setup` |
| print format work | `Print format` |
| data import / migration | `Data import` |
| requirement gathering | `Requirement Analysis` |
| PRD / spec writing | `Creating PRD` |
| resolve merge conflicts | `Resolve Merge Conflicts` |
| lunch break | `Lunch` |
| anything else | dominant real type, else `Other` |

---

## Hybrowlabs master list (bundled snapshot, alphabetical)

Copy the string exactly as printed. For another site use `catalogue list --type activity` instead.

- `Analyze`
- `Android Studio setup for ChatNext`
- `Assignment (Courses)`
- `Automation (Blog Agentic Prompt tuning)`
- `Automation Script Creation`
- `Automation Script Video + README file Creation`
- `Automation Testing`
- `Bench Set up`
- `blocker`
- `bug fix`
- `Built Tech News Automation Bot (n8n + Telegram)`
- `Call`
- `Calling`
- `Change Request`
- `Checking`
- `Client + Internal Team Meetings`
- `Client Demo`
- `Client Meeting`
- `Client Office Visit`
- `Code familiarization / onboarding`
- `Code review`
- `Coding`
- `Coding + Branch issues`
- `Coding + Debugging`
- `Coding + Debugging + Learning`
- `Coding + Learning`
- `Coding + Meeting`
- `Coding + Meeting + Debugging + Learning`
- `Coding + Meeting +Debugging`
- `Coding + Research`
- `Coding + Setup`
- `Coding + Setup + Learning`
- `Coding + Testing`
- `Coding +Testing`
- `coding+debugging`
- `Coding+Learning`
- `Coding+Meeting+Learning`
- `Communication`
- `Completed Day 0 & Started Day 1 of Frappe Framework Training`
- `Content Desiging & Copywriting`
- `Content Design & copywriting`
- `content research and schedule`
- `Continued Day 1 of Frappe training and completed the core tasks (excluding bonus).`
- `create funnel`
- `Create sharefable Demo`
- `Create the demo`
- `Created Graphics for social media`
- `Created memes`
- `Creating PRD`
- `creative design`
- `CRM`
- `CRM Project Debugging & Meeting with Reporting Manager Grawish`
- `CRM Repo Setup and Debugging – Initial Setup`
- `CRM SPANCO Widget Corrections & Improvements`
- `Dashboard`
- `Data`
- `Data Entry`
- `Data file prepared`
- `Data import`
- `Data import & export`
- `Data Mapping & Importing`
- `Database restore and local instance setup`
- `Day 2 – Frappe REST API Resources & DocType Exploration`
- `DEBUGGING`
- `Debugging + Meeting`
- `Debugging + Testing`
- `Demo + Coding`
- `Demonstration + Screen Recording`
- `Deployment`
- `Design & Editing`
- `Design Carousel`
- `Designing the Architecture + Coding`
- `Discussion`
- `Documentation`
- `Drafting Solution Doc`
- `Email Template`
- `Emails`
- `Enhancements and Bug Fixes in Todo Editing and Due Date Management`
- `ERPNext Dev Environment Setup`
- `ERPNext Dev Environment Setup and Debugging`
- `Event`
- `Exam Configuration`
- `Execution`
- `Explaining Code structure + KT`
- `Facilitated and Resolved Bundling Error for Chatnext Team on GMeet`
- `Factory Visit`
- `feeling not Well`
- `Finding Accommodation`
- `Flowchart`
- `Follow up`
- `followups`
- `frappe app (LMS)  installation`
- `frappe setup`
- `Functional Query`
- `funnel`
- `General Work`
- `git conflict`
- `Helpdesk Tickets`
- `Implementation`
- `Induction`
- `Install and testing the APK`
- `Installation`
- `integration`
- `Internal Meeting`
- `Interview`
- `Issue`
- `Joining`
- `Joining Procedure`
- `laptop issue`
- `Lead Generation`
- `Learning`
- `Learning + Coding`
- `learning + exploration`
- `Learning + Research`
- `Learning Because work not Assigned`
- `Learning Frapee from Youtube`
- `Learning Frappe`
- `Learning React Native`
- `Learning ReactJS`
- `Learnning Frappe`
- `LMS`
- `Local setup`
- `Lunch`
- `Meating Regarding project`
- `Meeting`
- `Meeting + Debugging`
- `meeting + learning`
- `Meeting + testing`
- `Meeting + Working`
- `Meeting+Learning`
- `Meme content design`
- `Meme creation`
- `On-Boarding`
- `Onboarding`
- `Other`
- `others`
- `Outbound calls`
- `Overtime Work`
- `PAPL_HRMS |`
- `Planning`
- `POC`
- `Post on Radaar`
- `Power Bi`
- `PPT Presentation`
- `Print format`
- `Project`
- `Project charter`
- `Project Configuration`
- `Project flow testing`
- `Project Management + QA`
- `Project Setup – App Installation for Development Environment`
- `Project weekly Review meeting`
- `Project work`
- `Prompt Engineering + Setup`
- `Proposal Writing`
- `Prototype Creation`
- `Prototype Demo`
- `Quotation creation`
- `reading freappe LMS doc`
- `Refactor API and Bug Discussion Meeting`
- `Reports`
- `Requirement Analysis`
- `Requirement Understanding`
- `Requirement Understanding Vedio`
- `Research`
- `research and development`
- `Research and Review`
- `Resolve Merge Conflicts`
- `Review`
- `Reviewing the codebase`
- `Revision`
- `RPNext Dev Environment Setup and Debugging`
- `Salary Slip Configuration`
- `Sales & Marketing`
- `Sales exhibition visit`
- `Sales Learning Module`
- `Sales Training`
- `Sales Traning`
- `Scheduling`
- `Security Configuration`
- `Self-Initiated Project Learning (ReactJS)`
- `Server Setup`
- `Setup`
- `Setup & UI Bug Testing for cn_todo_manager App`
- `Setup + Debugging`
- `Setup+Coding`
- `setup+meeting`
- `Setuping + Learning`
- `Setuping the system`
- `Shoot + Research`
- `Site creation`
- `Solved CRM Frontend & Redis Error Debugging`
- `SPANCO Widget Corrections & Improvements`
- `Studied Assigned Task`
- `Study Video creation`
- `support`
- `Support portal`
- `System Design + Coding`
- `Task`
- `Task Assignment`
- `test execution`
- `Testing`
- `Testing + Debugging`
- `Testing CRM`
- `Timesheet`
- `Topic Research & Review`
- `Training Sessions`
- `Traveling`
- `Troubleshooting ERPNext Setup`
- `Unit Testing`
- `VeratasHRMS`
- `Verification`
- `Video creation`
- `Video Inspiration`
- `video review`
- `Visit`
- `Web Page`
- `Web View Implementation for Custom Routes and Dynamic Color`
- `Weekend`
- `wiki`
- `Wireframe`
- `Work`
- `work + testing`
- `Work not assigned`
- `working`
- `Writing & shooting`

---

If two entries look identical, check `references/activity_types.csv` — it preserves the exact
export including trailing/double spaces that markdown may collapse.
