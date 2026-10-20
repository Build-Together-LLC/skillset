# skillset

Reusable Claude Code skills for [Build Together](https://github.com/Build-Together-LLC) — Frappe/ERPNext
engineering, design and research, and document/diagram tooling.

Everything here is **product-agnostic**. No skill in this repo assumes a particular client, site,
bench layout or internal service. Skills that are bound to one tenant's infrastructure stay in that
tenant's own repo.

## Install

Clone once, then symlink the skills you want into your Claude Code skills directory:

```bash
git clone git@github.com:Build-Together-LLC/skillset.git ~/skillset

# all of them
ln -s ~/skillset/skills/* ~/.claude/skills/

# or per project
mkdir -p .claude/skills && ln -s ~/skillset/skills/frappe-review .claude/skills/
```

Each skill is a directory containing `SKILL.md` plus any `scripts/`, `references/`, `templates/` and
`assets/` it needs. Claude Code loads a skill by its `SKILL.md` frontmatter `description`, so that
line is what decides when a skill fires — edit it, not the body, if a skill triggers too eagerly.

## Skills

| Skill | What it does |
|---|---|
| `accessibility-review` | Run a WCAG 2.1 AA accessibility audit on a design or page |
| `bench-commands` | Frappe Bench CLI command reference for site management, app management, development, and production operations |
| `client-scripts` | Frappe client-side JavaScript patterns for form events, field manipulation, dialogs, and UI customization |
| `cold-emailing` | Signal-based cold outreach: find where a prospect is actively engaging right now (podcasts, LinkedIn posts, communities, events, published... |
| `demo-doc-builder` | Build a complete, polished step-by-step demo / setup / how-to guide as a .docx from a short brief: real annotated screenshots taken from a... |
| `deploy-notes-comparison` | Release tooling for a product deployed from git — most at home on Frappe/ERPNext, but nothing in it is Frappe-specific. It drives a THREE-STAGE... |
| `design-critique` | Get structured design feedback on usability, hierarchy, and consistency |
| `design-handoff` | Generate developer handoff specs from a design |
| `design-system` | Audit, document, or extend your design system |
| `diagrams-as-code` | Generate professional architecture diagrams (AWS, GCP, Azure, Kubernetes, ERPNext, network, block diagrams) as PNG images using Python code |
| `doctype-patterns` | Frappe DocType creation patterns, field types, controller hooks, and data modeling best practices |
| `document-builder` | Produce any formal document as a styled .docx (or Markdown) using the house format: Times New Roman 12pt justified, real Word heading styles that... |
| `manager-work-report` | Build a manager-ready .docx work report for any date range from GitHub PRs and commits, timesheet, Jira and console logs: summary, week table, 3-4 lines per day, pending and blocked, with clickable links. |
| `feature-to-prd` | Architect agent that transforms a preliminary feature document, presentation, or brief into a fully structured Product Requirements Document (PRD)... |
| `frappe-api` | Frappe Python and JavaScript API reference including document operations, database queries, utilities, and REST API patterns |
| `frappe-architect` | Turns a BRD or feature brief into a technical architecture plan for Frappe/ERPNext |
| `frappe-debug` | Investigate a Frappe/ERPNext error or unexpected behavior |
| `frappe-developer` | Implements an approved architecture plan as working Frappe/ERPNext code — DocTypes, controllers, whitelisted APIs, client scripts, ERPNext... |
| `frappe-qa` | Tests Frappe/ERPNext code against a plan and emits a parseable PASS/FAIL verdict. Use to write and run FrappeTestCase tests, verify a feature... |
| `frappe-review` | Review Frappe/ERPNext code changes for framework idioms, security, permission correctness, and performance |
| `frappe-solutioning` | Use BEFORE designing or building any new Frappe/ERPNext feature, DocType, workflow or API. Searches the bench — upstream apps and custom apps... |
| `frappe-system-console` | Writes paste-ready Frappe System Console scripts (Setup → System Console) for data audits, fixes, deletions, syncs and one-off migrations on any... |
| `frappecli` | CLI for Frappe Framework / ERPNext instances |
| `issue-ticket-formatter` | - Convert a rough meeting transcript, brain-dump, bug note, error log, or draft PR description into a clean, professionally formatted GitHub issue... |
| `markitdown-convert` | Converts files to Markdown using the local `markitdown` CLI tool |
| `ontology` | Typed knowledge graph for structured agent memory and composable skills |
| `pr-reviewer` | Reviews GitHub Pull Requests for Frappe/ERPNext (v15), Vue, React, and React Native codebases. Performs comprehensive code review covering syntax,... |
| `print-format` | Frappe Print Format design — Jinja templates for receipts, certificates, invoices; PDF generation; page handling; multi-currency; wkhtmltopdf... |
| `production-performance-debugger` | Production-like performance debugging and load-testing workflow for web applications, APIs, Frappe/ERPNext, single hosted VMs, Kubernetes... |
| `proposal-builder` | Produce a Build Together client implementation proposal as a styled .docx — the ERPNext / Frappe (or any custom-software) sales proposal with... |
| `react-native-patterns` | React Native / Expo patterns for Frappe-backed mobile apps. Reference for Axios API calls, React Query v4, Redux Toolkit, React Navigation,... |
| `react-spa-patterns` | React SPA patterns for Frappe-backed applications. Reference for TanStack Query, Axios, Jotai, shadcn/ui, Tailwind, Refine v4, Mantine v5, React... |
| `research-synthesis` | Synthesize user research into themes, insights, and recommendations |
| `responsive-ui-walkthrough-media` | Create, fix, audit, or publish instructional walkthrough media for web/app UI, including animated GIFs, screenshots, short videos, highlighted UI... |
| `scheduler-and-jobs` | Production-grade Frappe background jobs and scheduler — queue selection, idempotency, retries, distributed locks, monitoring stuck jobs, debugging... |
| `self-improvement` | Captures learnings, errors, and corrections to enable continuous improvement. Use when: (1) A command or operation fails unexpectedly, (2) User... |
| `server-scripts` | Frappe server-side Python patterns for controllers, document events, whitelisted APIs, background jobs, and database operations |
| `testing-patterns` | How to write robust Frappe tests — FrappeTestCase, factories, mocking frappe.sendmail / external HTTP, permission tests, change_settings,... |
| `user-research` | Plan, conduct, and synthesize user research |
| `ux-copy` | Write or review UX copy — microcopy, error messages, empty states, CTAs |
| `workflow-patterns` | Frappe Workflow design — multi-state document lifecycles, role-based transitions, state-scoped field permissions, workflow handlers, and the... |

## Conventions

- **Frontmatter is the contract.** `name` and `description` only; the description says *what* and
  *when*, because that is all Claude sees before deciding to load the skill.
- **No hardcoded hosts, benches or paths.** Read them from arguments, environment variables or the
  user. A skill that needs a site takes one; it does not know one.
- **Examples are generic.** Use placeholder app and doctype names, not a real client's.
- **Scripts are self-contained.** If a script needs a package, say so at the top of the script and in
  the skill; do not assume a shared virtualenv.

## Vendored third-party skills

Two skills are installed from the [clawhub.ai](https://clawhub.ai) registry rather than written here:

| Skill | Registry slug | Version |
|---|---|---|
| `ontology` | `ontology` | 1.0.4 |
| `self-improvement` | `self-improving-agent` | 3.0.1 |

Their `.clawhub/origin.json` and `_meta.json` are kept so provenance stays traceable. Update them
from the registry; do not hand-edit them, or the next update will overwrite your changes. They are
also the only two skills here that reference the OpenClaw agent runtime — that is part of what they
ship, not a leftover.

## What is deliberately not here

Skills bound to one tenant's sites, repos or infrastructure stay with that tenant, per the rule
above. At the time of writing that means the dependency and symbol-graph skills, which read a
pre-computed index built by a cron on one particular bench rather than from the repo they ship in.

`deploy-notes-comparison` was in that category and was generalised instead: every product-specific
value — repos, branches, docs folders, tracker schemas, ticket bases, gh account — moved into a
per-project config file the skill reads, and the original two-product config is kept verbatim as
`references/products.example.md`. That is the pattern to follow for anything else bound to one
tenant: move the config out, keep the method.

## Contributing

One skill per pull request. Before opening it, check the skill against the conventions above by
grepping for anything tenant-specific — hostnames, `~/frappe-bench` paths, client or org names, real
doctype names from a live site.
