---
name: unity-edu-fwd
description: >
  Generates professional Functional Workflow Documents (FWDs) for Unity Edu modules built on Frappe ERPNext.
  Use this skill whenever the user wants to document a Unity Edu / ERPNext module for school clients — including
  modules like Fee Management, Student Admission, Attendance, Kitchen Management, Library, HR, Timetable, etc.
  Trigger on phrases like: "create a workflow document", "functional workflow for [module]", "generate FWD",
  "document the [module] module", "UAT document for [module]", "write up the [module] workflow".
  Also trigger proactively whenever the user describes a module in rough terms and the context suggests
  a school ERP implementation — even without explicitly asking for a document.
  Output: a single polished .docx file per module, structured for client sign-off and UAT approval.
---

# Unity Edu — Functional Workflow Document Generator

Generates structured, professional Functional Workflow Documents (FWDs) for Unity Edu school ERP modules.
Documents are designed for **non-technical school stakeholders** (admin, department heads, end users) and
serve as **UAT sign-off references**.

---

## Step 1 — Extract Module Information

Parse the user's freeform input and identify which of the 6 required fields are present:

| # | Field | Description |
|---|-------|-------------|
| 1 | **Module Name & Purpose** | What the module is called and what business problem it solves |
| 2 | **Workflows / Processes** | The key processes or user journeys the module handles |
| 3 | **User Roles** | Who uses the module (e.g. Admin, Class Teacher, Fee Accountant) |
| 4 | **DocTypes / Forms** | Key Frappe DocTypes or forms involved |
| 5 | **Integration Points** | Other modules or external systems this connects to |
| 6 | **Customisations & Special Rules** | Any school-specific configurations, custom fields, or business rules |

After extracting, **ask only for fields that are genuinely missing or unclear** — do not re-ask for anything already provided. Group all missing fields into a single prompt, not multiple back-and-forth questions.

---

## Step 2 — Confirm & Collect Metadata

Ask for the following if not already known:
- **School / Client Name**
- **Prepared By** (your name / team)
- **Version** (default: `v1.0`)
- **Date** (default: today's date)

---

## Step 3 — Generate the Document

Once all fields are collected, generate the `.docx` file using `docx-js`.
Follow the docx skill at `/mnt/skills/public/docx/SKILL.md` for all formatting rules.

### Document Structure

Generate the document in this exact section order:

```
1. Cover / Header Block
2. Module Overview
3. Key Roles & Permissions
4. Core Workflows
5. DocTypes & Data Fields
6. Integration Points
7. Configuration Assumptions
8. Out of Scope / Exclusions
9. UAT Checklist
```

See `/tmp/unity-edu-fwd/references/document-template.md` for full section specs and formatting rules.

### Styling Rules

- **Font**: Arial throughout
- **Page size**: A4 (11906 × 16838 DXA), 1-inch margins (1440 DXA each side)
- **Heading 1**: 18pt, bold, color `1F3864` (deep navy)
- **Heading 2**: 13pt, bold, color `2E75B6` (Unity blue)
- **Body text**: 11pt, color `000000`
- **Table header shading**: `BDD7EE` (light blue), ShadingType.CLEAR
- **Table border**: `CCCCCC`, BorderStyle.SINGLE, size 1
- **Content width**: 9026 DXA (A4 with 1" margins)
- **Section spacing**: Add a `new Paragraph({})` spacer between each major section

### Color Palette

| Element | Hex | Use |
|---------|-----|-----|
| `1F3864` | Deep Navy | H1 headings, cover title |
| `2E75B6` | Unity Blue | H2 headings, table headers |
| `BDD7EE` | Light Blue | Table header fill |
| `F2F2F2` | Light Grey | Alternate table rows (optional) |
| `70AD47` | Green | UAT checklist ticks / status |
| `FF0000` | Red | Out of Scope label |

---

## Step 4 — Output

1. Save the `.docx` to `/mnt/user-data/outputs/[ModuleName]_Functional_Workflow_Document_v[version].docx`
2. Call `present_files` to share the download link with the user
3. Briefly confirm what was generated — do not over-explain the content

---

## Workflow Formatting Rules

### For Each Workflow

**Always produce both:**

**A) Narrative Steps** — numbered, plain English, actor clearly stated:
```
1. The Fee Accountant creates a Fee Category (e.g. Tuition, Transport) in ERPNext.
2. The system saves the category and makes it available for use in Fee Structures.
3. The Admin assigns Fee Categories to a Fee Structure for the academic year.
...
```

**B) Summary Table** — immediately after the narrative:

| Step | Actor | Action | System Response |
|------|-------|--------|-----------------|
| 1 | Fee Accountant | Creates Fee Category | Category saved and listed |
| 2 | Admin | Assigns to Fee Structure | Structure updated for academic year |

**For complex workflows (3 or more decision branches):**
Add a plain-text ASCII flow diagram OR a Mermaid-style description as a comment block above the narrative. Do NOT attempt to embed actual images — describe the flow in text.

Example:
```
[Start] → Fee Due Date Reached
         ├─ Paid? → Yes → Mark as Paid → [End]
         └─ No → Send Reminder → Waited 7 days?
                                 ├─ Paid? → Yes → Mark as Paid
                                 └─ No → Escalate to Admin → [End]
```

---

## DocTypes Section Rules

For each DocType, show:
- **DocType Name** (bold)
- A one-line description of its purpose
- A small table of key fields only (mandatory or business-critical):

| Field Label | Field Type | Mandatory | Notes |
|-------------|------------|-----------|-------|
| Fee Category | Link | Yes | Links to Fee Category DocType |
| Amount | Currency | Yes | Fee amount in INR |
| Due Date | Date | No | Auto-set if schedule used |

Limit to **max 6–8 fields per DocType**. Do not list every field.

---

## UAT Checklist Rules

Simple tick-box list — one line per workflow, grouped by section:

```
☐  Fee Category can be created and saved
☐  Fee Structure can be created and linked to academic year
☐  Fee Schedule generates correct due dates
☐  Fee Invoice is generated for a student
☐  Payment entry is recorded against an invoice
☐  Outstanding fees report shows correct balances
```

Use `☐` (Unicode U+2610) for unchecked boxes — never use `[ ]` or `-`.

---

## Cover / Header Block Format

Generate a professional header table at the top of the document (before any section headings):

| Field | Value |
|-------|-------|
| Document Title | [Module Name] — Functional Workflow Document |
| Client / School | [School Name] |
| Version | v[X.X] |
| Date | [DD Month YYYY] |
| Prepared By | [Name] |
| Reviewed By | _(leave blank)_ |
| Approved By | _(leave blank)_ |

Style this as a 2-column table with the left column in `BDD7EE` header shading.

---

## Edge Cases

- If the user provides a module name but no workflows, **infer common workflows** from your ERPNext knowledge for that module and explicitly state: _"I've inferred the following workflows based on standard ERPNext [module] functionality. Please review and confirm."_
- If DocTypes are not provided, **infer standard DocTypes** for the module with the same caveat.
- If integrations are not mentioned, state _"No integration points specified. Update if applicable."_ in that section.
- If customisations are not mentioned, state _"No customisations noted. Standard ERPNext configuration assumed."_
- Always populate Out of Scope with at least 3 sensible exclusions relevant to the module, even if none are specified.
