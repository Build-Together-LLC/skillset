# Project Charter — Document Template Reference

Detailed section specifications for the Project Charter `.docx` file.
Read this file when generating the document to ensure all sections follow the correct format.

---

## Section 1: Cover / Header Block

A 2-column table at the very top of the document. No heading above it — this IS the cover.

- Left column: field labels, bold, `BDD7EE` fill, width 3000 DXA
- Right column: values, regular weight, white fill, width 6026 DXA
- Total width: 9026 DXA (A4 content area)
- The Document Title row should have the title in 16pt bold, Deep Navy (`1F3864`)
- Add a paragraph spacer with a bottom border (2pt, `2E75B6`) below the cover block as a visual divider

Fields in order:
1. Document Title
2. Client / Institution
3. Project Code
4. Version
5. Date
6. Confidentiality
7. Prepared By
8. Reviewed By (blank)
9. Approved By (blank)

---

## Section 2: Table of Contents

Use the docx-js `TableOfContents` element. Include heading levels 1 and 2.

```javascript
new TableOfContents("Table of Contents", {
  hyperlink: true,
  headingStyleRange: "1-2",
})
```

Add a note below: _"Note: Right-click the TOC and select 'Update Field' after opening in Word to populate page numbers."_

Add a page break after this section.

---

## Section 3: Project Overview

**Heading 1**: "1. Project Overview"

Three subsections:

**3a. Project Description** (Heading 2: "1.1 Project Description")
- 2–4 paragraphs describing the project in plain language
- What is being built, for whom, and the high-level approach

**3b. Background & Context** (Heading 2: "1.2 Background & Context")
- Why this project was initiated
- Any preceding events (RFP, discovery phase, prior engagement)
- Business problem being addressed

**3c. Project Summary Table**
A compact reference table:

| Field | Value |
|-------|-------|
| Project Name | [value] |
| Project Code | [value] |
| Start Date | [value] |
| Target End Date | [value] |
| Project Manager | [value] |
| Client POC | [value] |
| Platform | Frappe / ERPNext (Unity Edu) |

---

## Section 4: Client Details

**Heading 1**: "2. Client Details"

A single table:

| Field | Details |
|-------|---------|
| Institution Name | [value] |
| Institution Type | [School / University / EdTech / etc.] |
| Location | [City, State, Country] |
| Primary Contact | [Name, Designation, Email, Phone] |
| Secondary Contact | [Name, Designation, Email, Phone] or "Not specified" |
| Industry Vertical | Education — [sub-vertical] |

---

## Section 5: Objectives & Success Criteria

**Heading 1**: "3. Objectives & Success Criteria"

Two parts:

**5a. Project Objectives** (Heading 2: "3.1 Project Objectives")
- Numbered list of 3–6 clear objectives
- Each should be specific and action-oriented
- Example: "Digitize the complete student admission lifecycle from enquiry to enrolment"

**5b. Success Criteria** (Heading 2: "3.2 Success Criteria")
- Table format with measurable criteria:

| # | Success Criterion | Measurement Method | Target |
|---|-------------------|-------------------|--------|
| 1 | All in-scope modules configured and live | Go-Live checklist | 100% modules live |
| 2 | UAT signed off by client stakeholders | UAT sign-off document | All test cases passed |
| 3 | End-user training completed | Training attendance records | 90% staff trained |

---

## Section 6: Scope of Work

**Heading 1**: "4. Scope of Work"

Three subsections:

**6a. In Scope** (Heading 2: "4.1 In Scope — Modules & Features")
- Table listing each module and key features:

| # | Module | Key Features / Capabilities |
|---|--------|-----------------------------|
| 1 | Student Admission | Enquiry management, application processing, fee collection |
| 2 | Fee Management | Fee structure, invoicing, payment collection, receipts |

**6b. Key Deliverables** (Heading 2: "4.2 Key Deliverables")
- Numbered list of concrete deliverables:
  1. Configured Unity ERP instance with all in-scope modules
  2. Data migration from legacy system
  3. User training sessions (admin + end-user)
  4. Functional Workflow Documents for each module
  5. Post-go-live support for [X] weeks

**6c. Out of Scope** (Heading 2: "4.3 Out of Scope")
- Bulleted list of explicit exclusions
- Always include at least 3 items, even if inferred
- Common exclusions for Unity Edu projects:
  - Custom mobile application development
  - Hardware procurement or network infrastructure
  - Integration with systems not listed in scope
  - Historical data migration beyond [X] years
  - Ongoing maintenance beyond hypercare period

---

## Section 7: Project Team

**Heading 1**: "5. Project Team (Unity Edu)"

Table format:

| Role | Name | Responsibilities | Contact |
|------|------|-----------------|---------|
| Project Manager | [Name] | Overall delivery, client coordination, status reporting | [email] |
| Technical Lead | [Name] | Architecture, development, code review | [email] |
| Implementation Consultant | [Name] | Configuration, testing, training | [email] |
| Executive Sponsor | [Name] | Strategic oversight, escalation resolution | [email] |

---

## Section 8: Stakeholders & Decision Makers

**Heading 1**: "6. Stakeholders"

**8a. Stakeholder Register** (Heading 2: "6.1 Stakeholder Register")

| Name | Organization | Role / Designation | Stake in Project | Influence Level |
|------|-------------|-------------------|-----------------|----------------|
| [Name] | [Client] | Principal / Director | Decision maker for scope and budget | High |
| [Name] | [Client] | IT Head | Technical sign-off, infrastructure | High |
| [Name] | Unity Edu | Project Manager | Delivery accountability | High |

Influence Level options: High / Medium / Low

**8b. RACI Matrix** (Heading 2: "6.2 RACI Matrix")
- Optional but recommended for complex projects
- R = Responsible, A = Accountable, C = Consulted, I = Informed

| Activity | Client POC | Client IT | Unity PM | Unity Tech Lead |
|----------|-----------|----------|---------|----------------|
| Scope Sign-off | A | C | R | I |
| UAT Testing | R | R | A | C |
| Go-Live Decision | A | C | R | C |

---

## Section 9: Project Timelines & Milestones

**Heading 1**: "7. Project Timelines"

**9a. Phase Overview** (Heading 2: "7.1 Phase Overview")
- Table with phases, durations, and dates:

| Phase | Description | Start Date | End Date | Duration |
|-------|-------------|-----------|---------|----------|
| Phase 1 — Discovery | Requirements gathering, gap analysis | [date] | [date] | 2 weeks |
| Phase 2 — Configuration | Module setup, customization | [date] | [date] | 4 weeks |
| Phase 3 — Data Migration | Legacy data import and validation | [date] | [date] | 2 weeks |
| Phase 4 — UAT | User acceptance testing | [date] | [date] | 2 weeks |
| Phase 5 — Training | Admin and end-user training | [date] | [date] | 1 week |
| Phase 6 — Go-Live | Production deployment | [date] | [date] | 1 week |
| Phase 7 — Hypercare | Post-go-live support | [date] | [date] | 2-4 weeks |

**9b. Key Milestones** (Heading 2: "7.2 Key Milestones")

| # | Milestone | Target Date | Owner | Status |
|---|-----------|------------|-------|--------|
| M1 | Project Kickoff | [date] | PM | Planned |
| M2 | Requirements Sign-off | [date] | Client POC | Planned |
| M3 | UAT Completion | [date] | PM + Client | Planned |
| M4 | Go-Live | [date] | PM | Planned |

Status options: Planned / In Progress / Completed / Delayed

---

## Section 10: Assumptions & Constraints

**Heading 1**: "8. Assumptions & Constraints"

**10a. Assumptions** (Heading 2: "8.1 Assumptions")
- Numbered list of assumptions
- Common defaults for Unity Edu projects:
  1. Client will provide dedicated POC(s) available for weekly status calls and UAT sessions.
  2. Client will provide access to existing systems and data within the first week of project kickoff.
  3. Server / hosting infrastructure (Frappe Cloud or client-managed) will be provisioned before configuration begins.
  4. Client will complete UAT within the agreed timeframe and provide timely sign-off.
  5. Any third-party integrations will have API documentation available.

**10b. Constraints** (Heading 2: "8.2 Constraints")
- Numbered list of constraints
- Examples:
  1. Project must go live before [academic session / date].
  2. Implementation team is limited to [X] members.
  3. Client IT infrastructure must support Frappe's minimum system requirements.

---

## Section 11: Risk Register

**Heading 1**: "9. Risk Register"

Table with color-coded risk levels:

| # | Risk Description | Likelihood | Impact | Severity | Mitigation Strategy | Owner |
|---|-----------------|-----------|--------|----------|--------------------|----|
| R1 | [description] | High | High | Critical | [mitigation] | [name] |
| R2 | [description] | Medium | High | High | [mitigation] | [name] |

Severity derivation:
- Critical = High likelihood + High impact (Red `FF0000`)
- High = High+Medium or Medium+High (Red `FF0000`)
- Medium = Medium+Medium, Low+High, or High+Low (Amber `FFC000`)
- Low = Low+Low or Low+Medium (Green `70AD47`)

Apply the severity color as text color or cell shading on the Severity column.

---

## Section 12: Dependencies

**Heading 1**: "10. Dependencies"

Table format:

| # | Dependency | Type | Dependent On | Impact if Delayed | Status |
|---|-----------|------|-------------|-------------------|--------|
| D1 | Frappe Cloud server provisioning | Infrastructure | Frappe Cloud team | Configuration phase delayed | Pending |
| D2 | BillDesk API credentials | Integration | Client / BillDesk | Payment module cannot be configured | Pending |

Type options: Infrastructure / Integration / Data / Resource / Regulatory

If no dependencies provided, include at least:
- Server/hosting provisioning
- Client data availability
- Any third-party integration mentioned in scope

---

## Section 13: Governance & Escalation Matrix

**Heading 1**: "11. Governance & Escalation"

Use the default governance table from SKILL.md if not provided by the user.
Add a brief narrative above the table explaining the escalation philosophy:
"Issues are resolved at the lowest possible level. Escalation is triggered when resolution
exceeds the response time at the current level or when the issue exceeds the authority of the current level."

---

## Section 14: Communication Plan

**Heading 1**: "12. Communication Plan"

Use the default communication table from SKILL.md if not provided.
Add a note about primary communication channels:
"All formal communication will be via email. Informal coordination via [Slack/WhatsApp/Teams].
Project documents will be stored in [Google Drive / shared folder]."

---

## Section 15: Change Request Process

**Heading 1**: "13. Change Request Process"

Use the default 5-step process from SKILL.md.
Present as a numbered narrative with each step as a Heading 3 sub-section.
Include a note: "All approved changes will be reflected in an updated version of this Project Charter."

---

## Section 16: Approval & Sign-off

**Heading 1**: "14. Approval & Sign-off"

Narrative paragraph:
"By signing below, the undersigned acknowledge that they have reviewed this Project Charter and
agree to the project scope, timelines, governance structure, and responsibilities outlined herein."

Then the sign-off table (from SKILL.md spec).

Leave a generous amount of white space (2–3 empty paragraphs) between each sign-off row for
physical signatures when printed.
