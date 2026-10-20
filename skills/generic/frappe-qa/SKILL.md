---
name: frappe-qa
description: Tests Frappe/ERPNext code against a plan and emits a parseable PASS/FAIL verdict. Use to write and run FrappeTestCase tests, verify a feature meets its plan, check permissions/edge cases, or when the feature-pipeline conductor calls the QA stage. Trigger on "QA this feature", "test the code", "does this meet the plan", "write tests for", or "run the tests and give a verdict".
---

# Frappe QA

Verify that implemented code actually satisfies the plan, then deliver a clear verdict. You test and judge; you do not fix code (that is frappe-developer's job).

## How to run

1. **Read the plan** (`pipeline/plan.md` when driven by the pipeline, otherwise the spec) and the implemented code. Derive the acceptance criteria from the plan, not from the code's current behavior.
2. **Write and run tests through the reference skill and command** — do not improvise test scaffolding:
   - Load the **testing-patterns** skill for FrappeTestCase structure, factories, mocking (`frappe.sendmail`/HTTP), permission tests, `change_settings`, and anti-patterns to avoid.
   - Use the **/frappe-test** command (or `bench run-tests`) to execute the suite; see the **bench-commands** skill for invocation.
3. **Cover** the plan's happy path, edge cases, permission/role rules, and any workflow-state transitions. Note anything in the plan that is untestable or unimplemented.

## Handoff contract (when driven by feature-pipeline)

- Write findings to `pipeline/qa_report.md`: what was tested, what passed, and each failure with a concrete repro and the plan requirement it violates.
- **End the report with a single parseable line**: exactly `VERDICT: PASS` or `VERDICT: FAIL`. The conductor reads this line to decide whether to loop.
- PASS only when the plan's acceptance criteria are met and tests are green. Any unmet requirement or failing test means `VERDICT: FAIL`.

## What good looks like

- Acceptance criteria trace back to the plan, not to the code as written.
- Failures are reproducible and each cites the requirement it breaks.
- The report always ends with a clean `VERDICT: PASS` / `VERDICT: FAIL` line.
- No fixing code here; findings go back to frappe-developer.

> Bridge skill: delegates to the `frappe-claude` plugin's `testing-patterns` skill and `/frappe-test` command. If the team publishes a canonical `frappe-qa`, replace this file with it.
