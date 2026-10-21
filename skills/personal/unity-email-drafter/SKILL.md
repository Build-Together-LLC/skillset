---
name: unity-email-drafter
description: "Professional email drafting skill for Unity Edu team. Use this skill whenever anyone on the team needs to draft, compose, send, or reply to a client email, vendor email, internal communication, follow-up, escalation, invoice/payment request, status update, meeting request, or signoff request. Trigger on phrases like: 'draft an email', 'write an email', 'send an email', 'follow up with', 'reply to', 'email [person name]', 'update [client] on', 'request payment', 'escalate to', or any mention of composing professional correspondence. Also trigger proactively when the user describes a situation that clearly needs an email (e.g., 'we're blocked by X', 'need signoff from Y', 'billing is pending'). This skill enforces Unity Edu's communication standards across all team members."
---

# Unity Edu — Professional Email Drafting Skill

## Overview

This skill enables any Unity Edu team member to draft consistent, professional, and context-aware emails. It enforces the company's communication standards while adapting to different email types, recipients, and urgency levels.

## Before Drafting — Mandatory Steps

### Step 1: Gather Context

Before writing a single word, confirm you have:

1. **Recipient(s)** — name and email address
2. **Goal** — what the email should accomplish
3. **Mode** — which email type (see Email Types below)
4. **Constraints** — urgency, tone, thread context

If any of the above is missing, ask the user before proceeding.

### Step 2: Search Gmail for Context

**Always search Gmail before drafting** when a Gmail connector is available.

- Search for existing threads with the recipient using the connector's search tool
- Read the latest messages in the thread to understand context
- If replying, keep the thread ID so the draft stays in the same conversation

Tool names differ between claude.ai and Claude Code (e.g. `search_threads`, `get_thread`,
`create_draft`) — use whichever Gmail tools are connected. **If no Gmail connector is connected,
say so once, ask the user to paste the relevant thread, and continue.** Don't stop.

### Step 3: Identify Client Context

Read `references/client-directory.md` (next to this file) for client-specific details (contacts, project names, key stakeholders, CC conventions).

**If that file doesn't exist**, don't guess contact details. Use the CC Conventions below, and ask
the user for any recipient or CC email address you don't already have.

---

## Core Email Principles

### Voice & Tone

- **Professional yet accessible** — write like a seasoned engineer who values time and relationships
- **Direct language** — never use: "synergy", "circle back", "as per my last email", "just checking in", "hope this finds you well" (exception: senior/formal contacts where cultural norms expect it)
- **Warm escalation** — firm on the ask, respectful in delivery. Never passive-aggressive.
- **Confidence without arrogance** — state facts, show work done, be clear about what's needed

### Structure — Hook → Context → Value/Ask → CTA

Every email must follow this flow:

1. **Hook** (1 sentence) — Why you're writing. Lead with the most important thing.
2. **Context** (1-3 sentences) — Background the reader needs. Reference previous calls/emails.
3. **Value/Ask** — The main content. Use structured formatting (see below).
4. **CTA** (1 sentence) — One clear, specific ask. Not vague ("let me know") but actionable ("please confirm by Friday").

### Formatting Rules

- Use **emoji section markers** for structured emails with 2+ sections: 📌 ✅ 🛠️ 📅 ⚠️ 💳 🔗 👤 🚧
- Use **numbered lists** for action items, sequential steps, or prioritized items
- Use **bullet points** (•) for non-sequential details within a section
- Use **bold** sparingly — only for section headers or critical terms
- **Never** use tables in email body (they break in most email clients)
- Keep paragraphs to 2-3 sentences max

### Signature Rule

**NEVER include an email signature block.** No "Warm Regards", no name, no title, no contact info. The sender adds their own signature. End the email at the last line of content.

### CC Conventions

- **Nikhil (nikhil@unityedu.ai)** — CC on all IIMBx/DBE client communications
- When replying in a thread, preserve the existing CC list unless there's a reason to change it
- For escalations, CC the person one level above the blocker

---

## Email Types & Templates

Read `references/email-templates.md` (next to this file) for detailed templates for each type below.
If that file doesn't exist, the type descriptions below are enough to draft from.

### Type 1: Blocker / Escalation Email
**When:** Something is blocked and you need the recipient to act
**Tone:** Firm, factual, urgent but not aggressive
**Key elements:** State what's blocked, how long, impact, specific ask
**Emoji:** ⚠️ for blocker callout

### Type 2: Status Update / Progress Report
**When:** Sharing project progress with client
**Tone:** Confident, organized
**Key elements:** Split into ✅ Completed and 🛠️ In Progress sections
**Rule:** Lead with wins, then mention what's in progress

### Type 3: Follow-up / Reminder
**When:** Following up on a previous request that hasn't been actioned
**Tone:** Polite but clear that you're waiting
**Key elements:** Reference previous email/call, restate the ask, add timeline pressure
**Rule:** Each follow-up should escalate slightly — add a business impact statement

### Type 4: Technical Setup / Instructions
**When:** Asking client to set up a service (SES, DNS, payment gateway, etc.)
**Tone:** Helpful, instructional
**Key elements:** Step-by-step numbered instructions, URLs, cost estimates, "what we need from you" checklist
**Rule:** Always include cost estimates and reference links

### Type 5: Payment / Invoice Follow-up
**When:** Requesting payment, sharing invoices, or following up on pending payments
**Tone:** Professional, factual, tie payment to work delivered
**Key elements:** Reference work completed, invoice details, agreed terms
**Rule:** Always justify the payment ask with a summary of delivered work

### Type 6: Meeting / Scheduling
**When:** Confirming, requesting, or following up on meetings
**Tone:** Brief, friendly
**Key elements:** Date, time, agenda, attendee expectations
**Rule:** Keep it short — this doesn't need to be a long email

### Type 7: Signoff Request
**When:** Requesting UAT signoff or project phase closure
**Tone:** Confident, summarize what was delivered
**Key elements:** What's been completed, how long it's been on UAT, clear signoff ask
**Rule:** Tie signoff to next phase or payment to create momentum

### Type 8: Internal / HR Communication
**When:** PEP notices, intern feedback, team announcements
**Tone:** Firm but supportive for performance issues; clear and direct for announcements
**Key elements:** Specific expectations, measurable criteria, timelines, consequences
**Rule:** Always include an acknowledgment request for formal communications

### Type 9: Vendor Communication
**When:** Writing to Frappe Cloud, Billdesk, or other vendors
**Tone:** Peer-to-peer professional
**Key elements:** Specific technical details, reference ticket numbers, name the blocker
**Rule:** Always include business impact — vendors prioritize when they understand urgency

---

## Gmail Draft Workflow

After composing the email, **create a Gmail draft** with the connected Gmail tools. If no Gmail
connector is connected, give the user the finished email as text — To, CC, Subject, then the body —
ready to paste.

1. **Search for existing thread** — search with recipient + topic keywords
2. **Read context** — read the most recent message in the thread
3. **Create draft** — create the draft with:
   - `to`: recipient email(s)
   - `cc`: relevant stakeholders (check client directory)
   - thread ID: if replying in an existing thread
   - `subject`: only needed for new threads
   - `body`: the email content (no signature)

4. **Confirm to user** — share:
   - To/CC/Subject summary
   - Thread info (new or reply)
   - Link to Gmail drafts
   - Brief note on what the draft covers

---

## Escalation Ladder

When framing urgency, use this progression:

1. **First request:** Clear ask with reasoning → "Could you please share X so we can proceed with Y"
2. **First follow-up (3-5 days):** Reference original request + add timeline → "Following up on our request from [date]. This is currently a dependency for us."
3. **Second follow-up (1 week+):** Blocker framing + impact → "⚠️ This has been pending for over a week and is blocking [specific deliverable]."
4. **Escalation (2+ weeks):** Loop in stakeholders + firm deadline → "We're unable to proceed further without this. Requesting this be prioritized at the earliest."

**Never:** Threaten, be passive-aggressive, or use phrases like "as previously mentioned" or "per my last email."

---

## Quality Checklist

Before finalizing any email, verify:

- [ ] Follows Hook → Context → Value/Ask → CTA structure
- [ ] No signature block included
- [ ] No corporate jargon (synergy, circle back, etc.)
- [ ] Specific CTA — not just "let me know"
- [ ] Correct recipient emails and CC list
- [ ] Thread context checked — replying in right thread
- [ ] Typos in names, project names, and technical terms checked
- [ ] Cost figures include both USD and INR where relevant
- [ ] URLs are complete and correct
- [ ] Blocker items are explicitly called out if applicable
