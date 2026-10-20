---
name: project-update
description: "Generates professional weekly project update content for Unity Edu's Project Update DocType (custom_project_update field). Use this skill whenever anyone on the team needs to write, draft, or prepare a project update, weekly update, status report, sprint update, or client progress report. Trigger on phrases like: 'write project update', 'draft weekly update', 'prepare status report', 'update for [client]', 'what should I put in the project update', 'help me write the update', 'project update for this week', 'generate update for [project]'. Also trigger proactively when the user describes recent work completed, blockers, or progress on a client project — even without explicitly saying 'project update'. If the user shares rough notes, bullet points, task lists, or a stream-of-consciousness summary of what happened this week, this skill kicks in to structure it into a polished update. Even short inputs like 'we finished X and Y, waiting on Z from client' should trigger this skill."
---

# Project Update Generator — Unity Edu

## Purpose

Generate clear, professional, client-facing project updates for Unity Edu's "Project Update" DocType. The output is HTML content for the `custom_project_update` rich text field (Frappe Quill editor).

**Core principle:** The output must be directly copy-pasteable. No trailing questions, no "Does this look right?", no "Want me to adjust?" — just the finished update ready to paste.

## Workflow

### Step 1: Parse the Raw Input

Accept whatever the user gives — rough bullets, a paragraph dump, a task list, or even a single sentence. Immediately classify each piece of information into:

1. **Completed** — things done this period
2. **In Progress** — actively being worked on
3. **Blocked / Roadblocks** — stuck, waiting on client or external input
4. **New Scope** — newly accepted or proposed requirements
5. **Next Steps** — planned work for the coming period

### Step 2: Identify Gaps and Clarify

After parsing, check for these common gaps. If gaps exist, ask **all** clarifying questions in a **single message** using a mix of tappable options (for structured questions) and text questions (for open-ended ones). Never drip-feed questions one at a time.

**Mandatory checks — always verify these:**

| Gap | What to ask |
|-----|-------------|
| **Health status missing** | 🟢 On Track / 🟡 At Risk / 🔴 Blocked — provide context to help user choose |
| **Deployment target unclear** | Were completed items deployed to UAT or Production? |
| **No ETAs on in-progress items** | When is each in-progress item expected to be ready? |
| **Vague blockers** | Who needs to act? How long has it been pending? What's the impact? |
| **Empty Next Steps** | What's planned for the coming week? |
| **New requirements without status** | Accepted into scope? Under evaluation? Deferred? |

**Skip clarification if** the input is already detailed enough to fill every section. Go straight to generation.

### Step 3: Generate the Final Update — Directly

Once you have enough information, **generate the final HTML immediately**. Do NOT show an outline first. Do NOT ask for confirmation. The user wants to copy and paste — give them the finished product.

Read `references/html-template.md` for the exact HTML structure and formatting rules.

**Output format:** Present the HTML inside a single code block (```html) so the user can use the copy button on Claude and paste directly into the Frappe field.

After the code block, add **one short line** like: "Update ready — 14 completed · 3 in progress · 2 client actions." That's it. No questions. No "let me know if you want changes."

If the user wants revisions, they'll ask.

## Section Rules

### Health Status Line (first line of the update)
Format: `[emoji + status] · [X] completed · [Y] in progress · [Z] awaiting client input`

- **🟢 On Track** — No blockers, or blockers are minor and don't affect the timeline
- **🟡 At Risk** — Blockers exist that WILL affect the timeline if not resolved within 1-2 weeks
- **🔴 Blocked** — Critical path is stopped; cannot proceed without external input

### Executive Summary
2-3 sentences max. Structure: [biggest win or milestone] + [current focus] + [client attention needed if any].

A busy client stakeholder should be able to read ONLY the executive summary and know the state of the project.

**Good:** "MK Pawar Admissions & CRM module saw significant progress this week with 14 core features completed and deployed to production, including Round-Robin Lead Assignment and Multi-Level Admissions Approval Workflow. Three integrations remain in progress pending client-side API access. Three new requirements have been accepted into scope and will be phased into the upcoming sprint."

**Bad:** "This week we worked on various tasks and made good progress on the project."

### ✅ Completed
Each item answers: What was done + where is it now (deployed to production / ready for UAT / demonstrated to client).

Group related items logically rather than listing them in random order. If there are many items (8+), group them under sub-themes using bold labels.

**Good:** "**Academic Year Filter on Lead Creation** — Implemented and deployed to production."
**Bad:** "Academic Year Filter done."

### ▶️ In Progress
Each item MUST include an expected completion date or a conditional ETA ("~1 week after receiving X from client").

**Good:** "**Meta Lead Ads Integration** — Development underway. Expected completion dependent on client-side API access and approvals."
**Bad:** "Working on Meta Lead Ads."

### ⚠️ Roadblocks & Dependencies
Each item MUST include: what's blocked, who needs to act, how long it's been pending (if known), and what's at risk.

**Good:** "**Homework Format Specifications:** To resolve the homework sending issue, we need the supported formats — MCQ, PDF/Word, or others. Pending since **Apr 25, 2026**. Without this, the homework module fix cannot proceed."
**Bad:** "Need homework format info from client."

### 🔔 Action Required from Client
Separated out clearly — this section exists so the client cannot miss what they need to do. Each item: specific ask + deadline/urgency + what it enables.

If no client actions needed: "No action required from your side this week."

### 📋 Scope Update (optional)
Include ONLY when new requirements have been added, deferred, or descoped. Skip entirely if scope hasn't changed — don't include an empty section.

### ➡️ Next Steps
What the team will work on in the coming period. Include owners where known. Include UAT/production deployment plans if applicable.

## Edge Cases

- **No blockers:** Include the Roadblocks section with "No roadblocks this week." — this reassures the client.
- **Nothing completed:** Don't skip — say "No features were completed this week. Focus was on [ongoing work]."
- **Multiple projects in one message:** Generate separate HTML blocks for each project.
- **Very short input** (e.g., "TGAA — deployed fees module, waiting on Purvi for withdrawal rules"): Ask only the critical missing pieces (health, ETA, deployment target), then generate.
- **User provides a structured input** with all sections filled: Skip clarification entirely, generate immediately.

## Tone & Style

- Professional but direct. No corporate fluff.
- Write for a busy client stakeholder — scannable, no filler.
- Bold for emphasis on feature names, dates, and key terms.
- Blockers are factual and firm, never passive-aggressive.
- Frame client dependencies as "we need X to deliver Y" — tie every ask to a deliverable.

## What NOT to Include in Output

- No trailing questions ("Does this look right?", "Want me to adjust?", "Anything to add?")
- No preamble ("Here's the update I've generated for you:")
- No explanations of the format
- Just the HTML code block + one-line summary after it
