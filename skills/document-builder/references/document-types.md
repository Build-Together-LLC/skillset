# Document type templates

Every type below still follows the mandatory skeleton:
**cover → overview table (pages 1–2) → consolidated summary → detailed flow → open questions.**
Only the *columns* and the *flow sections* change. Pick the closest match; blend if needed.

---

## SOP / Runbook

Opening table — `Step | Action | Owner | System | Expected Result`
Second table — `Pre-requisite | Detail` (access, roles, environment)

Flow sections:
1. Purpose & scope
2. Pre-requisites (access, roles, tools)
3. Procedure — one `h2` per step, with the exact command/click path and expected result
4. Verification — how to confirm it worked
5. Rollback / what to do if it fails
6. Escalation contacts

Use `d.banner("Warning", ...)` before any destructive or irreversible step.

---

## RCA / Incident post-mortem

Opening table — `Item | Detail`: incident ID, date/time, duration, severity, systems affected,
users affected, root cause (one line), status.
Second table — timeline: `Time | Event | Actor`.

Flow sections:
1. What happened (plain language, no blame)
2. Impact — who and what, quantified
3. Timeline (detailed)
4. Root cause — the actual mechanism, with code/config references
5. Contributing factors
6. Resolution — what was changed
7. Preventive actions — `Action | Owner | Due date | Status`

Name systems and code paths, never individuals, as causes.

---

## Requirements / Spec

Opening table — `Component | Type | Purpose | Owner`
Second table — `Requirement ID | Requirement | Priority | Status`

Flow sections:
1. Background & problem statement
2. Goals / non-goals
3. Functional requirements
4. Data model — DocTypes / fields tables
5. Business logic & events
6. UI / screens
7. Roles & permissions matrix
8. Workflow diagram (`d.code()` with mermaid)
9. Risks & dependencies

For a **Frappe feature PRD specifically**, prefer the `feature-to-prd` skill's six-section
structure instead — it is more detailed for that case.

---

## Release / Deployment notes

Opening table — `App | Change | PR | Risk | Status`
Second table — environment matrix: `Environment | Version / Commit | Date`

Flow sections:
1. Release summary
2. Changes by app — one `h2` per app, table of PRs/commits
3. Database / migration impact
4. Configuration changes required
5. Rollback plan
6. Post-deploy verification checklist

For the prod-vs-UAT bench comparison specifically, use the `uat-prod-deploy-comparison` skill.

---

## Audit / Review report

Opening table — `Area | Finding | Severity | Recommended Action | Owner`
Second table — severity counts: `Severity | Count`

Flow sections:
1. Scope & method — what was and was not examined
2. Findings — one `h2` per finding: observation, evidence, risk, recommendation
3. Positive observations
4. Remediation plan with dates

Severity vocabulary: Critical / High / Medium / Low / Informational — define them in the doc.

---

## Training / Handover

Opening table — `Topic | Audience | Duration | Pre-requisite`
Second table — system access needed: `System | Role | Requested from`

Flow sections:
1. Who this is for
2. System overview
3. Day-to-day tasks — one `h2` each, with screenshots or click paths
4. Common problems and fixes
5. Who to contact for what
6. Glossary

Write for someone with zero prior context. Expand every acronym on first use.

---

## Status / Progress report

Opening table — `Workstream | Status | % Complete | Owner | Target Date`
Use a consistent status vocabulary: On Track / At Risk / Blocked / Done.

Flow sections:
1. Headline — one paragraph
2. Progress since last report
3. Blockers and asks — be explicit about what you need and from whom
4. Next period plan
5. Risks

---

## Policy / Process note

Opening table — `Clause | Policy | Applies To | Effective Date`

Flow sections:
1. Purpose
2. Scope — who it binds
3. Policy statements (numbered)
4. Roles & responsibilities
5. Exceptions & approval route
6. Review cycle

---

## Meeting minutes

Opening table — `Field | Value`: date, attendees, absent, chair.
Second table — decisions: `# | Decision | Owner`.
Third table — actions: `# | Action | Owner | Due`.

Flow sections: discussion notes per agenda item (`h2` each), then next meeting.

Minutes record **decisions and actions**, not transcripts.
