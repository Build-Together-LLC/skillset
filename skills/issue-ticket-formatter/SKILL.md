---
name: issue-ticket-formatter
description: >-
  Convert a rough meeting transcript, brain-dump, bug note, error log, or draft PR
  description into a clean, professionally formatted GitHub issue OR Jira ticket in
  Markdown. Use this skill WHENEVER the user pastes messy/rough engineering notes and
  asks for a "github issue", "github ticket", "jira ticket", "jira", "PR description",
  or ".md file" of an issue/ticket — even if they only say a single word like "jira",
  "github", or "md". Also trigger when the user pastes a traceback or feature spec and
  wants it turned into a trackable ticket. The user specifies the target format
  (GitHub or Jira); if they don't, ask which one before writing. Default output is raw
  copy-pasteable Markdown in a fenced code block (no HTML), and a saved .md file.
---

# Issue / Ticket Formatter

Turn rough input (a recording transcript, rough issue, PR description, error log, or
feature brief) into a clean **GitHub issue** or **Jira ticket** as Markdown, in the exact
house style below.

## Step 0 — Which format?

There are two primary formats and two secondary ones. Pick decisively from the signals:

**GitHub issue** — the header is a light bold inline line, no field table (see Step 3). Signals:
- "github issue", "github ticket", "github", "gh", "issue"

**Jira ticket** — the header is a `| Field | Value |` table (see Step 4). Signals:
- "jira", "jira ticket", "ticket"
- the source already carries an issue key like `VE-###` / `PROJ-###` (strong Jira signal —
  keep that exact key in the title)

**Secondary formats:**
- "PR description" / "PR body" → **PR description** (see `references/pr-description.md`)
- "qa comment" / "test cases" / "qa checklist" → **QA checklist comment**
  (see `references/pr-description.md`)

Both primary formats carry the **same body content and section order** — only the **header**
and a few conventions differ (field table vs inline line; "Description" vs "Summary" as the
first heading). So the choice is really about the header style; keep everything else identical
between them.

If the user gives a one-word instruction ("jira", "github", "md"), treat it as the format and
proceed — don't ask. Only ask "GitHub issue or Jira ticket?" when there is genuinely no signal
at all (no keyword AND no issue key in the source). Do not guess silently in that case.

## Step 1 — How to deliver the output

The user copies this straight into GitHub/Jira, so the #1 rule is: **give them raw Markdown,
never rendered HTML.** People who copy from a rendered preview end up pasting `<h1>`, `<p>`,
`<li>` tags — which is wrong.

Always deliver BOTH:
1. **A fenced code block in the chat reply** containing the full raw Markdown (this is what
   they copy). If the ticket itself contains a ``` code block, wrap the whole thing in a
   longer fence (` ````markdown ` or ` `````markdown `) so it nests correctly.
2. **A saved `.md` file** in the outputs directory (via file tools) so they can download it.
   Name it from the issue key/slug, e.g. `VE-142-sub-brand.md` or
   `purchase-order-duplicate-warning.md`.

Then add 1–3 short lines noting what you changed or anything worth flagging (a real risk, an
unresolved open question, a naming collision). Keep it brief — no long preamble.

## Step 2 — Universal rules (apply to BOTH formats)

These are the transformations that make rough notes look professional:

- **Title** = `#` H1: the issue key (if any) + a short, specific title. Keep the source's key.
- **Acceptance criteria** → GitHub-style checkboxes `- [ ]` (trackable in both tools).
- **Preserve verbatim**: file paths, line numbers, function/method names, code snippets,
  commit hashes, config keys, and error lines. These are how a dev finds the code — never
  paraphrase or "clean up" a path or identifier.
- **Code blocks**: always fence with a language tag — ```python, ```bash, ```js, ```json.
- **Wiki-links → plain keys**: convert `[[VE-135]]` to `VE-135`. Jira and GitHub auto-link
  bare issue keys; the double-bracket syntax does not render.
- **Strip noise**:
  - Remove trailing `*Source: recording …*` footers that just restate the Problem section.
  - Remove decorative status emojis from headings (📝, 🎯, ✻, etc.). KEEP a real `⚠️`
    callout when it carries an actual warning (data risk, "do not touch", correctness trap).
  - Collapse duplicated paragraphs (rough notes often state the root cause twice).
  - Fix broken/stray Markdown tables (empty header rows, mismatched columns). A common one:
    a lone `| DocType | Fixture file |` header with no separator row sitting just above a real
    table — delete the orphan header.
- **Keep internal cross-references consistent**: rough notes often get re-scoped, so a
  sentence may point at "the field from (A)" when the field is now defined in (B), or a
  prerequisite may cite the wrong section. When you renumber, reorder, or drop a scope
  section, fix every reference to it (backfill prerequisites, "see (X)", "per step N") so the
  ticket doesn't contradict itself.
- **Tracebacks / logs**: don't paste the giant variable dump. Keep the meaningful **call
  path** (the frames that matter) plus the **actual error line**, in a fenced block. Add one
  line noting anything the trace proves (e.g. "the value was in scope but never assigned").
- **Tone**: simple, clear, professional English. Concise. Prose where it reads naturally;
  structure where it aids scanning. Don't pad. Don't add sections the source can't fill —
  omit empty ones rather than inventing content.
- **Language of judgement**: keep the author's verified findings and recommendations; mark
  genuinely open items as open questions rather than resolving them yourself.

## Step 3 — GitHub issue structure

Header is a **light bold inline line** under the title (NOT a field table):

```markdown
# <short title>

**Type:** feature · **App:** `app_name` · **Area:** <area>

## Summary
<1–3 sentences: what and why>

## Current state (verified)
<what exists today, with file paths / line numbers>

## Scope   (or: ## What we want / ## Tasks)
<numbered or sub-headed parts; keep it concrete>

## Implementation notes
<how to build it; code snippets fenced with a language>

## Acceptance criteria
- [ ] <testable outcome>
- [ ] <testable outcome>

## Affected areas
<files / modules touched>

## Open questions
<unresolved decisions to confirm before build>

## Rollout
<migrate / deploy / test steps>
```

**Bug variant** (use when the source is a defect + traceback):

```markdown
# <short title of the bug>

## Summary
<symptom + one-line cause>

## Root cause
<the real reason, with the offending field/line>

## Proof / trace  (or: ## Confirmed production traceback)
<trimmed call path + the actual error, fenced>

## The fix
<the change; often a fenced code diff/snippet>

## Steps to reproduce
1. …

## Acceptance criteria
- [ ] …

## Rollout
<deploy + verify>
```

Use only the sections the source supports. Order them as above.

## Step 4 — Jira ticket structure

Jira leads with a **field table**, then `---`, then the body. Pull any related issue keys
into the table's **Related** row.

```markdown
# <KEY> — <short title>

| Field | Value |
|---|---|
| **Type** | <Bug / Enhancement / Port / Feature …> |
| **App** | `app_name` |
| **Priority** | <High / Medium-High / …> — <one-line why> |
| **Assignee** | _TBD_ |
| **Branch** | `<KEY>` _(confirm key in Jira)_ |
| **Related** | <KEY-2> (<one-line relation>) |   ← include only if there is one

---

## Description
<summary — Jira's first field is "Description">

## Background / Context
<optional>

## The problem
<...>

## Scope
<In scope / Out of scope, sub-parts A/B/C>

## Acceptance Criteria
- [ ] <...>

## Open Questions
<...>

## Code References
<file paths / functions / line numbers>
```

Notes:
- Use **Description** as the first content heading when it fits Jira's convention; otherwise
  **Summary** is fine.
- Fields not present in the source get sensible placeholders (`_TBD_`, `_(confirm key in Jira)_`).
- Everything else follows the universal rules in Step 2 (checkboxes, verbatim code refs,
  fenced+tagged code, wiki-link cleanup, noise stripping).

## Compatibility with GitHub-flavoured Markdown → Jira

The output is GitHub-flavoured Markdown, which Jira's modern editor auto-converts on paste.
If the user says their Jira uses the **old wiki markup** (`h2.` headings, `{code}` blocks,
`{panel}`), offer to convert the syntax to that instead — see
`references/jira-wiki-markup.md`.

## Quick worked example (GitHub, one line)

Input: "products created by anyone stay disabled; enable only via a maker-approver workflow
limited to Stock Manager + Purchase Manager; replace the current System-Managers-only client
guard."

Output title: `# Product (Item): default to *Disabled*, enable only via a maker-approver Workflow`
— then Summary / Current state / Requirements / Implementation notes / Acceptance criteria
(`- [ ]`) / Open questions, with the `item.js:269` reference preserved verbatim.
