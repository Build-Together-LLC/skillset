# Project Update

Tell Claude what happened on a project this week, however roughly. Get back a finished update you can
paste straight into the Project Update form.

## What it does

You write rough notes — bullets, a paragraph, even one line like "deployed fees, waiting on client
for withdrawal rules". The skill sorts every item into:

1. **Completed** — and where it is now (production, UAT, demoed)
2. **In progress** — with an expected date
3. **Roadblocks** — what's stuck, who has to act, since when, and what it puts at risk
4. **Action required from client** — pulled out on its own so the client can't miss it
5. **Scope changes** — only when scope actually changed
6. **Next steps**

It then writes the update as HTML for the `custom_project_update` field on the **Project Update**
DocType, which uses Frappe's rich-text (Quill) editor.

## What you need

- Claude Code with this skill installed (keep this whole folder together).
- Nothing else to install.

## How to use it

```
project update for MK Pawar — finished round-robin lead assignment and the
multi-level admissions approval, both on prod. Meta lead ads still waiting
on their API access. They want WhatsApp alerts added.
```

- **Something important missing?** Claude asks everything it needs **in one message**: health
  status, UAT or production, dates for in-progress work, details on blockers.
- **Detailed notes?** No questions — the update comes straight back.
- **Several projects in one message** gives you one update per project.

## What you get

One HTML code block — use the copy button and paste it into the field — then a one-line count:

```
Update ready — 14 completed · 3 in progress · 2 client actions.
```

The update opens with a status line the client can take in at a glance:

| Status | Means |
|---|---|
| 🟢 On Track | No blockers, or only minor ones that don't affect the timeline |
| 🟡 At Risk | Blockers that **will** move the timeline if not fixed in 1–2 weeks |
| 🔴 Blocked | Work has stopped until someone outside the team acts |

Then a 2–3 sentence executive summary, so a busy stakeholder can read just that.

**On purpose, the output has no follow-up questions and no intro text** — only what you paste. If
you want changes, just ask.

## Common problems

| You see | What it means |
|---|---|
| Formatting is lost after pasting | Paste into the rich-text field itself, not a plain text box. The wrapper `<div class="ql-editor read-mode">` must stay |
| "No roadblocks this week." | Nothing was blocked — this is left in on purpose, to reassure the client |
| No Scope Update section | Scope didn't change, so the section is left out |

## For developers

- `SKILL.md` — the instructions Claude follows: how items are sorted, the rules for each section,
  and edge cases.
- `references/html-template.md` — the exact HTML structure Quill expects, how to group 8+ completed
  items, fallback text for empty sections, and two full worked examples.
