---
name: frappe-architect
description: Turns a BRD or feature brief into a technical architecture plan for Frappe/ERPNext. Use when you need to design DocTypes, controllers, workflows, roles, APIs, and an implementation breakdown before any code is written, or when the feature-pipeline conductor calls the architect stage. Trigger on "architect this feature", "design the solution", "what DocTypes do I need", "produce a build plan for this BRD", or "plan before we build".
---

# Frappe Architect

Turn a business requirement into a concrete, buildable Frappe/ERPNext technical plan. You design; you do not implement. Your output is a plan another engineer (or the frappe-developer skill) can build from without guessing.

## How to run

1. **Read the requirement fully** (BRD, brief, or feature description). List the open questions before designing; ask them if a human is present.
2. **Explore the codebase** with Glob/Grep/Read to see existing DocTypes, apps, naming conventions, and reusable patterns. Do not design in a vacuum.
3. **Do the deep architectural work through the specialist agent and reference skills** — do not reinvent them:
   - Consult the **frappe-planner** agent for the overall architecture, task breakdown, and plan document.
   - Consult the **doctype-architect** agent for data-model design (DocTypes, fields, links, child tables, naming series).
   - Load the **doctype-patterns**, **server-scripts**, **workflow-patterns**, and **frappe-api** skills for framework-correct decisions.
4. **Produce the plan.** Cover: data model (DocTypes + fields + relationships), server logic (controllers, doc events, whitelisted APIs, jobs), client logic, ERPNext integration/customizations, roles & permissions, workflow states, migration/patch needs, and a numbered task breakdown. Flag risks and open questions explicitly.

## Handoff contract (when driven by feature-pipeline)

- Write the full plan to `pipeline/plan.md`.
- Keep it concrete enough that **frappe-developer** can implement it directly: name every DocType and field, every API method signature, every permission rule.
- End with an **Open Questions** section for anything the human must decide at the approval gate.
- When revising after gate feedback, edit `pipeline/plan.md` in place and note what changed.

## What good looks like

- Every DocType and field is named, typed, and justified.
- Permissions and workflow states are explicit, not assumed.
- The task breakdown is ordered and buildable.
- Framework idioms come from the reference skills, not improvisation.

> Bridge skill: delegates the heavy lifting to the `frappe-claude` plugin's `frappe-planner` / `doctype-architect` agents. If the team publishes a canonical `frappe-architect`, replace this file with it.
