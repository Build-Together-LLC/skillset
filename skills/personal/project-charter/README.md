# Project Charter

Tell Claude about a new client engagement. Get back a Project Charter as a Word document, ready for
client sign-off.

## What it does

A project charter is the one document everyone agrees on at kickoff: what we are building, for whom,
by when, who is responsible, what could go wrong, and how we will talk to each other.

You give Claude what you know — a client name and module list is enough to start. The skill:

1. Works out which details are missing and asks for them **in one message**, not one at a time.
2. Fills in sensible defaults for the standard parts (risks, governance, communication plan, change
   process) and **marks every guessed part** so you can check it.
3. Builds a styled `.docx` with 16 sections, from the cover block to the sign-off table.

## What you need

- Claude Code with this skill installed (keep this whole folder together).
- Node.js. Claude installs the `docx` npm package itself if it is missing.

## How to use it

Any of these work:

```
create a project charter for Bhartiyam International School —
modules: Admissions, Fees, Attendance. Start 1 Oct, go-live 15 Dec.
```

```
charter for IIMBx phase 2 — here's the proposal PDF
```

- **Short input is fine.** Only a client name and modules? Claude infers the rest and flags it.
- **Stakeholders can't be guessed.** If you don't list them, Claude will ask.
- **Share an earlier proposal** (Google Doc, PDF) and Claude reads it before asking anything.
- **Several phases?** Scope and timelines are split by phase.

## What you get

A file named `<ProjectCode>_Project_Charter_<version>.docx`, saved in your current folder unless you
ask for another one.

| Section | What's in it |
|---|---|
| Cover block | Title, client, project code, version, date, confidentiality, prepared/reviewed/approved by |
| Overview → Scope | Description, background, objectives, in scope, out of scope, deliverables |
| Team → Stakeholders | Unity Edu team, client stakeholders, decision makers |
| Timelines | Start, end, and milestones (default: Discovery → Configuration → Data Migration → UAT → Training → Go-Live → Hypercare) |
| Risks & governance | Risk register with likelihood and impact, escalation matrix (L1–L3), dependencies |
| Ways of working | Communication plan, change request process |
| Sign-off | Blank signature and date columns for the kickoff meeting |

Styling is fixed: Arial, A4, deep navy (`1F3864`) and Unity blue (`2E75B6`), with red/amber/green
for risk levels.

## Common problems

| You see | What it means |
|---|---|
| Sections marked _"Inferred based on standard Unity Edu implementation patterns"_ | Claude filled these in — read and confirm before sending to the client |
| Claude asks about stakeholders | That section can't be inferred; list names and roles |
| `Cannot find module 'docx'` | Node couldn't find the package — ask Claude to install it and run again |

## Note on document styles

This repo also has `document-builder`, which uses the Walnut house format (Times New Roman,
justified). **Project charters deliberately use their own Arial/navy style.** Ask for a "project
charter" to get this skill; ask for an SOP, RCA or spec to get `document-builder`.

## For developers

- `SKILL.md` — the instructions Claude follows: fields to collect, section order, styling, defaults.
- `references/document-template.md` — the exact layout of each of the 16 sections, with `docx-js`
  snippets.
