# PR description & QA comment formats

Read this when the user asks for a **PR description / PR body** or a **QA test-cases comment**
instead of an issue/ticket.

## PR description

Same universal rules as issues (Step 2 of SKILL.md). Structure:

```markdown
# <type: short title>   ← e.g. "feat: KG Marks Entry Tool — …" (keep conventional-commit prefix if present)

## Summary
<what this PR does, end to end, in 1–3 sentences>

## Issues fixed
1. **<short label>** — <one-line cause/fix>.
2. …

## Changes
<a Markdown table: | Area | Change | — convert any ASCII-art box tables to real Markdown tables>

## Files changed
- `path/to/file` *(new)* / *(perms)* / etc.

## Testing
- **Automated:** <tests + counts>
- **Manual:** see the QA test cases (posted as a PR comment).

## Deployment notes
- <migrate / rebuild / cache-clear / preconditions>

## Out of scope
<what this PR deliberately does not touch>
```

Conventions:
- Convert any ASCII-art tables (`┌──┬──┐`) into proper Markdown tables.
- Tag code fences with a language.
- If the source had the QA cases inline ("see below"), move them to a separate QA comment
  file and change the Testing line to point at the comment.

## QA test-cases comment

Testers want **clickable checkboxes**. GitHub task-list checkboxes (`- [ ]`) only work as
list items — NOT inside table cells. So do NOT put the cases in a table with `☐` glyphs;
use a task list grouped under short headings.

```markdown
## QA Test Cases — <feature>

**Pre-requisites:** <bullets folded into one line with · separators>

Check each box as it passes.

### <Group name, e.g. Access & setup>
- [ ] **1 · <Area>** — <Steps> → *<Expected result>.*
- [ ] **2 · <Area>** — <Steps> → *<Expected result>.*

### <Next group>
- [ ] **3 · <Area>** — <Steps> → *<Expected>.*
```

Per line: `- [ ] **<#> · <Area>** — <Steps> → *<Expected>.*` — number, area, steps, then the
expected result in italics after an arrow. Group the numbered cases under thematic headings
(Access, Scoring, Validation, Submit, UI, Regression, …) so a long list stays scannable.

Deliver as a fenced code block (raw Markdown to paste as a comment) plus a saved `.md` file,
same as issues/tickets.
