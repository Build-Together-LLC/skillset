---
name: project-charter
description: >
  Generates professional Project Charter Documents (.docx) for Unity Edu implementations on Frappe/ERPNext.
  Use this skill whenever the user wants to create a project charter, project kickoff document, or project
  initiation document for a Unity Edu or Frappe ERP engagement. Trigger on phrases like: "create a project
  charter", "draft a charter document", "project kickoff doc", "project initiation document", "PID",
  "charter for [client]", "new project setup document". Also trigger proactively when the user describes
  a new client engagement, mentions starting a new implementation, or talks about formalizing project scope
  with a client — even without explicitly saying "charter". The output is a polished .docx file suitable
  for both client sign-off and internal project reference.
---

# Unity Edu — Project Charter Document Generator

Generates structured, professional Project Charter Documents for Unity Edu school/institution ERP
implementations. These documents serve a dual purpose: **client-facing alignment** (scope agreement,
stakeholder clarity, sign-off) and **internal reference** (team onboarding, governance, risk tracking).

The charter is the single source of truth at project kickoff. It answers: What are we building? For whom?
By when? Who's responsible? What could go wrong? And how do we communicate?

---

## Step 1 — Extract Project Information

Parse the user's input and identify which of the required fields are present. The charter needs
information across several categories. Check what's already provided and only ask for what's missing.

### Category A: Project Identity

| Field | Description | Required? |
|-------|-------------|-----------|
| Project Name | A short name for the engagement (e.g. "IIMB Student Lifecycle System") | Yes |
| Project Code | Internal reference code (e.g. "UE-IIMB-2026") | No — generate if not provided |
| Project Description | 2–3 sentence summary of what is being built and why | Yes |
| Background / Context | Why this project exists — what problem is being solved | Yes |

### Category B: Client Details

| Field | Description | Required? |
|-------|-------------|-----------|
| Client / Institution Name | Full legal or commonly used name | Yes |
| Client Type | School / School Chain / University / EdTech / Other | Yes |
| Client Location | City, State, Country | Yes |
| Primary Contact | Name, designation, email, phone of main client POC | Yes |
| Secondary Contact | Backup contact on client side | No |

### Category C: Unity Edu Team

| Field | Description | Required? |
|-------|-------------|-----------|
| Project Manager | Name and contact of the PM from Unity Edu | Yes |
| Technical Lead | Developer or technical owner | No |
| Implementation Team | List of team members and their roles | No |
| Executive Sponsor | Senior leader accountable (e.g. Nikhil / Sankar) | No |

### Category D: Scope of Work

| Field | Description | Required? |
|-------|-------------|-----------|
| Modules In Scope | List of ERPNext/Unity Edu modules being implemented | Yes |
| Key Deliverables | What will be delivered (e.g. configured system, training, data migration) | Yes |
| Out of Scope | What is explicitly NOT included | Yes — infer if not provided |

### Category E: Stakeholders

| Field | Description | Required? |
|-------|-------------|-----------|
| Stakeholder List | Names, roles, and their relationship to the project | Yes |
| Decision Makers | Who has final approval authority | Yes |

### Category F: Timelines

| Field | Description | Required? |
|-------|-------------|-----------|
| Project Start Date | Planned or actual start | Yes |
| Estimated End Date | Target completion | Yes |
| Key Milestones | Phase-wise milestones with target dates | Yes |

### Category G: Additional Sections

| Field | Description | Required? |
|-------|-------------|-----------|
| Objectives & Success Criteria | Measurable outcomes that define project success | Yes — infer if not provided |
| Assumptions | Things assumed to be true for planning purposes | Yes — infer if not provided |
| Constraints | Known limitations (time, budget, resources, technology) | No |
| Risks | Top risks with likelihood, impact, and mitigation | Yes — infer 3–5 if not provided |
| Dependencies | External dependencies that could affect the project | No |
| Governance & Escalation | Decision-making authority levels and escalation paths | Yes — use defaults if not provided |
| Communication Plan | Meeting cadence, reporting, channels | Yes — use defaults if not provided |
| Change Request Process | How scope changes will be handled | Yes — use standard process |

After extracting, **ask only for fields that are genuinely missing or unclear**. Group all missing
fields into a single prompt. Do not ask multiple rounds of questions.

For fields marked "infer if not provided", use your knowledge of the client (from conversation context
or memory) and standard ERPNext/Unity Edu implementation patterns to generate sensible defaults. Always
flag inferred content with a note like: _"Inferred based on standard Unity Edu implementation patterns.
Please review and confirm."_

---

## Step 2 — Confirm Metadata

Ask for these if not already known (provide sensible defaults):

- **Document Version**: default `v1.0`
- **Date**: default today's date
- **Prepared By**: default from context or ask
- **Confidentiality Level**: Internal / Confidential / Public (default: Confidential)

---

## Step 3 — Generate the Document

Once all fields are collected, generate the `.docx` file using `docx-js` (the `docx` npm package).
If it is not installed, run `npm install docx` in a scratch folder first. Write the generator as a
small Node script, run it, and check the file opens before handing it over.

### Document Structure

Generate the document in this exact section order:

```
1.  Cover / Header Block
2.  Table of Contents
3.  Project Overview
4.  Client Details
5.  Objectives & Success Criteria
6.  Scope of Work (In Scope, Out of Scope, Deliverables)
7.  Project Team (Unity Edu Side)
8.  Stakeholders & Decision Makers
9.  Project Timelines & Milestones
10. Assumptions & Constraints
11. Risk Register
12. Dependencies
13. Governance & Escalation Matrix
14. Communication Plan
15. Change Request Process
16. Approval & Sign-off
```

See `references/document-template.md` (next to this file) for full section specs.

### Styling Rules

- **Font**: Arial throughout
- **Page size**: A4 (11906 × 16838 DXA), 1-inch margins (1440 DXA each side)
- **Heading 1**: 18pt, bold, color `1F3864` (deep navy)
- **Heading 2**: 14pt, bold, color `2E75B6` (Unity blue)
- **Heading 3**: 12pt, bold, color `2E75B6`
- **Body text**: 11pt, color `333333`
- **Table header shading**: `1F3864` (deep navy) with white text
- **Table alternate rows**: `F2F7FB` (very light blue)
- **Table border**: `CCCCCC`, BorderStyle.SINGLE, size 1
- **Content width**: 9026 DXA (A4 with 1" margins)
- **Section spacing**: Add a `new Paragraph({})` spacer between each major section

### Color Palette

| Element | Hex | Use |
|---------|-----|-----|
| `1F3864` | Deep Navy | H1 headings, cover title, table headers |
| `2E75B6` | Unity Blue | H2/H3 headings, accent borders |
| `F2F7FB` | Ice Blue | Alternate table row fill |
| `BDD7EE` | Light Blue | Cover block header fill |
| `333333` | Dark Grey | Body text |
| `70AD47` | Green | Success / Low risk |
| `FFC000` | Amber | Medium risk |
| `FF0000` | Red | High risk / Critical |

---

## Step 4 — Output

1. Save the `.docx` as `[ProjectCode]_Project_Charter_[version].docx` in the current working
   directory, or in the folder the user asked for
2. If the environment has a tool for sharing files with the user, use it; otherwise give the full
   path
3. Briefly confirm what was generated — do not over-explain the content

---

## Default Content for Inferred Sections

### Default Governance & Escalation Matrix

When not provided by the user, use this structure:

| Level | Issue Type | Escalated By | Escalated To | Response Time |
|-------|-----------|-------------|-------------|---------------|
| L1 — Operational | Day-to-day issues, bugs, questions | Implementation Team | Project Manager | 24 hours |
| L2 — Project | Timeline delays, resource gaps, scope clarifications | Project Manager | Executive Sponsor + Client POC | 48 hours |
| L3 — Strategic | Contract disputes, major scope changes, go/no-go decisions | Executive Sponsor | Client Decision Maker + Unity Edu Leadership | 1 week |

### Default Communication Plan

| Activity | Frequency | Participants | Channel | Owner |
|----------|-----------|-------------|---------|-------|
| Daily Standup | Daily (during active sprints) | Implementation Team | Google Meet / Slack | Tech Lead |
| Weekly Status Update | Weekly | PM + Client POC | Email report + Call | Project Manager |
| Steering Committee | Bi-weekly / Monthly | Sponsors + Decision Makers | Video call | Executive Sponsor |
| UAT Review | Per milestone | All stakeholders | On-site / Video | Project Manager |
| Risk Review | Monthly | PM + Tech Lead | Internal | Project Manager |

### Default Change Request Process

Use this standard 5-step process:

1. **Raise**: Requestor (client or internal) submits a Change Request describing the change, reason, and urgency.
2. **Assess**: Project Manager evaluates impact on scope, timeline, cost, and resources within 3 business days.
3. **Approve / Reject**: Decision Maker (based on escalation level) approves, rejects, or requests modification.
4. **Implement**: If approved, the change is incorporated into the project plan with updated timelines.
5. **Document**: The charter and project plan are updated to reflect the approved change. A CR log is maintained.

### Default Risk Inference (for Frappe/ERPNext projects)

When the user doesn't provide risks, infer from the module list and client type. Common risks include:

- **Data Migration Complexity**: Legacy data may be incomplete, inconsistent, or in incompatible formats.
- **Client Resource Availability**: Key client stakeholders may not be available for UAT or decision-making on time.
- **Scope Creep**: Additional requirements emerging during implementation that were not part of the original scope.
- **Third-Party Integration Delays**: Dependencies on external systems (payment gateways, government portals, existing ERPs) may introduce delays.
- **Change Management Resistance**: End users may resist adopting the new system, requiring additional training cycles.

Assign likelihood (Low/Medium/High) and impact (Low/Medium/High) based on the project context.

---

## Cover / Header Block Format

Generate a professional header block at the top of the document (before TOC):

| Field | Value |
|-------|-------|
| Document Title | [Project Name] — Project Charter |
| Client / Institution | [Client Name] |
| Project Code | [Code] |
| Version | v[X.X] |
| Date | [DD Month YYYY] |
| Confidentiality | [Level] |
| Prepared By | [Name] |
| Reviewed By | _(leave blank)_ |
| Approved By | _(leave blank)_ |

Style the left column with `BDD7EE` shading and bold text. Right column in regular weight.

---

## Approval & Sign-off Block

At the end of the document, include a sign-off table:

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Project Manager (Unity Edu) | [PM Name] | | |
| Executive Sponsor (Unity Edu) | [Sponsor Name] | | |
| Primary Contact (Client) | [Client POC] | | |
| Decision Maker (Client) | [Decision Maker] | | |

Leave Signature and Date columns blank — these are filled during the sign-off meeting.

---

## Edge Cases

- If the user provides only a client name and module list, infer everything else from context and standard patterns. Flag all inferred content clearly.
- If no milestones are given, generate standard ERP implementation milestones: Discovery → Configuration → Data Migration → UAT → Training → Go-Live → Hypercare.
- If stakeholders aren't listed, ask — this section cannot be meaningfully inferred.
- If the project spans multiple phases, structure timelines and scope by phase (Phase 1, Phase 2, etc.).
- If the user provides a Google Doc, PDF, or earlier proposal for reference, read it first and extract relevant details before asking questions.
