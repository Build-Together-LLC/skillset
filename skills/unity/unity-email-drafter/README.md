# Unity Email Drafter

Describe the email you need. Get back a draft in Unity Edu's house style — saved in Gmail if it's
connected.

## What it does

Every email from the team should read the same way: direct, warm, and clear about what we need. The
skill:

1. Checks it knows **who** it's to, **what** it should achieve, **which type** of email it is, and
   any urgency. Anything missing, it asks.
2. **Searches Gmail** for earlier threads with that person, so a reply stays in the same thread and
   uses the context.
3. Writes the email as **Hook → Context → Ask → one clear call to action**.
4. Saves it as a **Gmail draft** — never sends it.

It knows nine types of email, each with its own tone:

| Type | Use it for |
|---|---|
| Blocker / escalation | Something is stuck and the reader has to act |
| Status update | Progress for a client — wins first, then what's in progress |
| Follow-up / reminder | A request nobody has acted on — each follow-up adds a little more urgency |
| Technical setup | Asking a client to set up SES, DNS, a payment gateway — steps, links and costs |
| Payment / invoice | Chasing payment, always linked to the work delivered |
| Meeting / scheduling | Short: date, time, agenda |
| Signoff request | UAT or phase signoff, linked to the next phase |
| Internal / HR | PEP notices, intern feedback, announcements — asks for acknowledgement |
| Vendor | Frappe Cloud, Billdesk and others — ticket numbers and business impact |

## What you need

- Claude Code with this skill installed (keep this whole folder together).
- **Optional: a Gmail connector.** Without it, Claude says so, asks you to paste the thread, and gives
  you the finished email as text to paste yourself.

## How to use it

```
follow up with the Bhartiyam team — we still don't have the homework
formats, it's been 10 days and it's blocking the homework fix
```

```
draft a signoff request for IIMBx phase 1, UAT has been up since Aug 20
```

It also starts on its own when you describe a situation that needs an email, like "billing is
pending with TGAA".

## House rules it follows

- **No signature block.** Your own Gmail signature is added when you send.
- **No filler** — no "hope this finds you well", "circle back", "per my last email".
- **Emoji section markers** (📌 ✅ 🛠️ ⚠️ 💳) for longer emails; **never tables** — they break in
  many email clients.
- **Costs in USD and INR** where they matter.
- **CC:** Nikhil on all IIMBx/DBE client emails; for escalations, the person one level above the
  blocker; on replies, the existing CC list is kept.

Follow-ups get firmer in steps: a clear ask → mention the date and the dependency → call it a blocker
and state the impact (after a week) → bring in stakeholders with a firm deadline (after two weeks).
Never passive-aggressive.

## Common problems

| You see | What it means |
|---|---|
| "No Gmail connector is connected" | Connect Gmail to get drafts saved and threads checked — or paste the thread and copy the email yourself |
| Claude asks for an email address | It doesn't have that contact — see the note below |
| Reply started a new thread | No earlier thread matched — give the subject line or paste the last message |

## Note: two reference files are not included yet

`SKILL.md` refers to `references/client-directory.md` (client contacts and CC rules) and
`references/email-templates.md` (full templates for each type). **Neither was in the source bundle.**
Until they're added, the skill uses the type descriptions in `SKILL.md` and **asks you for contact
details instead of guessing them**. Adding the two files will make drafts faster and more consistent.

For cold outreach to new prospects, use `cold-emailing` instead.

## For developers

- `SKILL.md` — the instructions Claude follows: email types, tone, structure, the Gmail steps, and
  the quality checklist.
- `references/` — not in the repo yet; see the note above.
