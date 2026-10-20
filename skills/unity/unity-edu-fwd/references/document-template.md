# Functional Workflow Document — Section Specifications

This reference defines the exact content and format expected in each section of a Unity Edu FWD.

---

## Section 1: Cover / Header Block

A 2-column table at the very top of the document. Left column = field label (shaded `BDD7EE`), right column = value.

Fields:
- Document Title: `[Module Name] — Functional Workflow Document`
- Client / School: `[School Name]`
- Version: `v[X.X]` (default `v1.0`)
- Date: `[DD Month YYYY]`
- Prepared By: `[Implementer Name]`
- Reviewed By: _(blank — for client to fill)_
- Approved By: _(blank — for client to fill/sign)_

Follow with a horizontal rule (paragraph border bottom) before Section 2.

---

## Section 2: Module Overview

**Heading 1:** `1. Module Overview`

Content blocks (each as a labelled paragraph or small 2-col table):

- **Module Name**: Full name as it appears in Unity Edu
- **Module Category**: e.g. Academic, Finance, Operations, HR
- **Purpose**: 2–3 sentences describing what the module does and the business problem it solves
- **Key Benefits**: 3–5 bullet points (use docx numbering config, LevelFormat.BULLET)
- **Scope Summary**: One sentence on what is covered in this document

---

## Section 3: Key Roles & Permissions

**Heading 1:** `2. Key Roles & Permissions`

Brief intro line: _"The following roles interact with the [Module Name] module. Access levels are configured in ERPNext role permissions."_

Then a table:

| Role | Description | Key Permissions |
|------|-------------|-----------------|
| System Manager | Full system access | Create, Read, Write, Delete, Submit, Cancel |
| [Role Name] | [What this person does] | [Relevant permissions] |

Include only roles that actually interact with this module.
Standard Unity Edu roles to consider: System Manager, Principal, Academic Admin, Class Teacher, Fee Accountant, Librarian, HR Manager, Kitchen Manager, Parent (portal).

---

## Section 4: Core Workflows

**Heading 1:** `3. Core Workflows`

For each workflow:

**Heading 2:** `3.[N] [Workflow Name]` (e.g. `3.1 Fee Category Setup`)

Brief one-line description of the workflow's purpose.

**A) Step-by-Step Narrative**
Numbered paragraphs. Each step format: `[Step N]: [Actor] [action verb] [object]. [Optional: system response or condition].`

**B) Workflow Summary Table**
Immediately after the narrative. Columns: Step | Actor | Action | System Response

**C) Flow Diagram (complex only)**
Only if 3+ decision branches. Use preformatted text block showing ASCII flow.

Number workflows from 3.1, 3.2, 3.3, etc.

---

## Section 5: DocTypes & Data Fields

**Heading 1:** `4. DocTypes & Data Fields`

Intro line: _"The following DocTypes are used in the [Module Name] module. Only key fields are listed."_

For each DocType:

**Heading 2:** `4.[N] [DocType Name]`

One-line description of this DocType's purpose.

Field table:

| Field Label | Field Type | Mandatory | Notes |
|-------------|------------|-----------|-------|
| [Label] | [Link/Data/Currency/Date/Select/etc.] | Yes/No | [Brief note] |

Limit to 6–8 fields. Do not list internal system fields (name, creation, modified, owner, etc.) unless relevant.

---

## Section 6: Integration Points

**Heading 1:** `5. Integration Points`

Intro line: _"The [Module Name] module connects with the following modules and external systems."_

Table:

| Integrated With | Type | Description |
|----------------|------|-------------|
| [Module / System] | Internal / External | [What data flows and when] |

If no integrations: _"No integration points specified for this implementation. Update if applicable."_

Common Unity Edu integrations to consider per module:
- Fee Management ↔ Accounts (GL entries), Student, Academic Year
- Attendance ↔ HR (Leave), Student, Timetable
- Admission ↔ Student, Fee Management, Google Workspace
- Kitchen ↔ Accounts, Student (meal counts)
- Library ↔ Student, HR (staff borrowing)

---

## Section 7: Configuration Assumptions

**Heading 1:** `6. Configuration Assumptions`

Intro line: _"The following configurations were set up as part of this implementation. Changes to these settings may affect module behaviour."_

Bullet list of assumptions. Examples:
- Academic Year and Academic Term have been created before module go-live
- School-specific fee heads have been configured per the fee structure document provided by [School Name]
- User roles and permissions have been assigned as per the Role Permission Matrix
- ERPNext system settings: timezone, currency (INR), date format (DD-MM-YYYY)

Always include at least 4–5 assumptions relevant to the module.

---

## Section 8: Out of Scope / Exclusions

**Heading 1:** `7. Out of Scope / Exclusions`

Intro line: _"The following items are explicitly outside the scope of this implementation and are not covered by this document."_

Bullet list. Format each as: `[Feature/Process] — [brief reason or note]`

Examples (tailor to module):
- Integration with third-party payment gateways — not part of current phase
- Custom mobile app for parents — out of scope; standard ERPNext portal applies
- Bulk SMS / WhatsApp notifications — to be handled in a separate integration module
- Historical data migration beyond [agreed date range] — not in scope
- Multi-branch / multi-school setup — single school implementation only

Always include at least 3–5 items. Even if none are specified, infer sensible exclusions.

---

## Section 9: UAT Checklist

**Heading 1:** `8. UAT Checklist`

Intro paragraph:
_"Use this checklist during User Acceptance Testing (UAT). Each item corresponds to a workflow or feature described in this document. Mark each item once tested and verified in the UAT environment."_

Then a grouped checklist by workflow:

**Heading 2:** `8.[N] [Workflow Name]`

List of tick-box items using `☐` (U+2610):
```
☐  [Testable action — what the tester should be able to do]
☐  [Testable action]
☐  [Testable action]
```

Each item should be written as a concrete, verifiable action — not vague ("system works") but specific ("Fee Invoice is generated with correct amount and due date").

---

## Closing Block

After the UAT Checklist, add a final section:

**Heading 1:** `Document Sign-Off`

_"By signing below, the authorised representative of [School Name] confirms that the workflows, configurations, and scope described in this document have been reviewed and accepted."_

A 3-row sign-off table:

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Prepared By | [Name] | | |
| Reviewed By | | | |
| Approved By (Client) | | | |

Leave Signature and Date columns blank for handwritten completion.
