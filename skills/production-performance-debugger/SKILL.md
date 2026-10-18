---
name: production-performance-debugger
description: Production-like performance debugging and load-testing workflow for web applications, APIs, Frappe/ERPNext, single hosted VMs, Kubernetes pods/containers, and Frappe Cloud benches over SSH. Use this whenever the user reports a slow API, slow login, load-test result, latency spike, worker timeout, database bottleneck, N+1 query, Kubernetes/Frappe Cloud performance issue, or asks to benchmark/profile an endpoint or full user lifecycle. This skill guides the agent to enter the real runtime, reproduce the full lifecycle, profile at the correct layer, and produce an evidence-backed bottleneck document before proposing fixes.
compatibility: Requires shell/SSH access to the target runtime or equivalent logs/metrics; optional tools include curl, Python, bench, kubectl, docker, database CLI, k6/JMeter/Locust, and application credentials supplied by the user.
---

# Production Performance Debugger

Use this skill to investigate real application slowness without prematurely guessing the root cause. It is designed for:

- a normal single hosted VM over SSH;
- Docker/containerized apps;
- Kubernetes pods/services/ingress;
- Frappe Cloud benches reachable through SSH/bench access;
- Frappe/ERPNext APIs, login/session slowness, Desk/webapp boot, background workers, and database-heavy flows.

The core principle: **the copied slow API is a lead, not the whole investigation.** Reproduce the realistic runtime lifecycle, measure where time is spent, prove causality, then document and fix.

## Safety and access rules

- Do not use or expose raw cookies, tokens, passwords, or customer-private data in final reports. Redact secrets in saved artifacts.
- Do not run destructive commands, migrations, restarts, pod deletions, cache flushes, DB kills, or load tests against production without explicit approval.
- Prefer read-only profiling first. For write/mutating APIs, use a staging/UAT environment or ask before replaying.
- If live-patching a pod/container for proof-of-concept profiling, state that it is ephemeral and will be lost on restart/rollout unless merged/deployed.
- If the environment is customer-facing, start with low concurrency and ramp gradually.

## Entry criteria

Trigger when the user provides any of:

- a slow curl/API/browser request;
- a slow login or boot complaint;
- load-test results or a request to run load testing;
- Kubernetes/VM/Frappe Cloud access context;
- a human observation like “this screen takes too long” or “this API is stuck”.

Before asking questions, inspect what is available: repo, deployment files, logs, SSH/kubectl context, credentials already configured, and prior artifacts.

Ask only for missing essentials:

- target environment and whether load testing is permitted;
- safe test user/session or credentials;
- whether API is read-only or mutating;
- expected user lifecycle, concurrency, and acceptable test window.

## Workflow

### 1) Establish the runtime map

Identify where the request actually runs.

For a VM:

```bash
hostname
ps aux | egrep 'gunicorn|uwsgi|node|python|nginx|supervisor|bench' | head
systemctl status nginx 2>/dev/null || true
```

For Docker:

```bash
docker ps
docker logs --tail=200 <container>
docker exec -it <container> bash
```

For Kubernetes:

```bash
kubectl config current-context
kubectl get ns
kubectl get pods -A | grep -i '<app-or-site>'
kubectl get svc,ingress -n <namespace>
kubectl logs -n <namespace> <pod> --tail=200
kubectl exec -n <namespace> -it <pod> -- bash
```

For Frappe/Frappe Cloud bench over SSH:

```bash
pwd
bench version
bench --site <site> list-apps
bench --site <site> doctor
```

Goal: separate routing/ingress issues from app worker, DB, Redis/cache, queue, or business logic issues.

### 2) Reconstruct the real lifecycle

Do not only replay one copied curl if the user says the UI or workflow is slow. Model the user path:

1. open/login;
2. session cookie and CSRF acquisition;
3. boot/session/user info calls;
4. list/dashboard/load APIs;
5. target business API;
6. follow-up calls triggered by the screen.

For load tests, script the sequence in k6/JMeter/Locust/Python instead of hammering a single endpoint unless the user explicitly wants endpoint-only testing.

### 3) Baseline external and internal timings

Measure from outside and inside the runtime.

External HTTP timing:

```bash
curl -sS -o /tmp/resp.json -w 'dns=%{time_namelookup} connect=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} total=%{time_total} code=%{http_code}\n' '<url>'
```

Internal service timing from app pod/VM:

```bash
time curl -sS -o /tmp/resp.json 'http://127.0.0.1:<port>/<path>'
# or service DNS in Kubernetes
```

If external is slow but internal is fast, inspect ingress/LB/TLS/network. If both are slow, inspect app/DB/cache.

### 4) Profile the handler path

Add the smallest useful instrumentation. Prefer a temporary profiling script or request-local timing wrapper over broad code changes.

Measure:

- total handler time;
- phase timings;
- SQL query count and total SQL time;
- slow/repeated SQL;
- cache/Redis calls;
- document/object instantiation counts;
- serialization cost;
- background job waits;
- upstream API calls;
- file/storage calls.

For Frappe/ERPNext, pay special attention to:

- `frappe.get_doc()` loops and child table loading;
- `doc.as_dict()` / serialization;
- `Document.onload`, hooks, monkey patches;
- permission logic and custom row-level permission layers;
- custom virtual-field/value hydration;
- login/session/boot paths;
- `information_schema` or table-count cache queries;
- Redis/cache get/unpickle loops;
- MariaDB processlist states like `Opening tables`, locks, temp tables, filesort.

Useful Frappe commands:

```bash
bench --site <site> console
bench --site <site> mariadb
bench --site <site> execute '<dotted.path>' --kwargs '{}'
```

Inside a Frappe console/probe, compare direct handler execution with the HTTP path when browser session headers are stale or noisy.

### 5) Prove causality with controlled comparisons

Do not stop at “this looks slow”. Prove it.

Examples:

- normal path vs direct SQL prefiltered path;
- normal path vs disabled nonessential hook in a throwaway probe;
- normal path vs request-local cache;
- one user vs another user/role;
- one document with many child rows vs a small document;
- same API from outside LB vs inside pod;
- single request vs low-concurrency lifecycle load.

The aim is to identify an amplification mechanism: N+1 queries, repeated metadata/cache reads, slow login cache rebuild, full-doc loads before filtering, missing index, worker starvation, or external dependency wait.

### 6) Run load testing responsibly

If load testing is requested:

1. Confirm environment and safe concurrency.
2. Start with smoke: 1 user, 1 iteration.
3. Ramp gradually: e.g. 5 → 10 → 25 users, with think time.
4. Track p50/p95/p99, error rate, throughput, worker timeouts, DB CPU/locks, queue depth, pod CPU/memory, and connection count.
5. Use a lifecycle script when the UI flow matters.
6. Stop immediately on high error rates or customer-impact risk.

If tools are missing, use the bundled dependency-free Node scripts:

```bash
# quick repeated timing for one endpoint
node scripts/http-timing.mjs --url 'https://site/api/method/ping' --n 10

# realistic multi-step lifecycle smoke/load test
cp scripts/sample-frappe-lifecycle-scenario.json /tmp/scenario.json
# edit baseUrl, credentials, and target steps; do not commit secrets
node scripts/lifecycle-load-test.mjs --config /tmp/scenario.json --concurrency 5 --iterations 10 --out /tmp/load-results.json
```

A Python `requests.Session()` script is also fine when Node is unavailable. See `references/report-template.md` for what to record.

### 7) Produce the bottleneck understanding document

Before fixing, write a short but evidence-backed report. Include:

- environment and runtime path;
- lifecycle/API tested;
- reproduction steps with secrets redacted;
- timing table;
- profile findings;
- root-cause hypothesis and confidence;
- proof/counterfactual tests;
- impacted APIs/screens;
- recommended fixes;
- risks and correctness checks;
- deployment notes.

Use the template in `references/report-template.md`.

### 8) Fix only after the bottleneck is understood

When implementing:

- make the smallest source-of-truth change;
- preserve permission/security semantics;
- add request-local caches only when invalidation boundaries are clear;
- push filters into SQL before full document loads;
- batch-fetch instead of N+1;
- add indexes only after confirming query shape;
- test correctness and performance separately;
- create issue/PR with benchmark evidence.

## Output expectations

For an investigation, final response should be concise:

```markdown
Investigated.

Environment: <VM/K8s/Frappe Cloud/site>
Lifecycle tested: <login/session/API sequence or endpoint-only>
Main bottleneck: <one sentence>
Evidence:
- <timing/profile fact>
- <query/cache/hook fact>
Recommended next action: <fix or deeper profiling>
Artifacts:
- <report path>
- <script path>
Caveats: <if any>
```

Never paste secrets or full cookies back to the user.

## Bundled scripts and references

Scripts:

- `scripts/http-timing.mjs` — dependency-free Node script to repeat one HTTP request and print latency percentiles.
- `scripts/lifecycle-load-test.mjs` — dependency-free Node lifecycle smoke/load tester with cookie jar, variable extraction, templating, concurrency, and JSON results.
- `scripts/sample-frappe-lifecycle-scenario.json` — editable Frappe login/session/API scenario template. Copy it outside the skill folder before adding credentials.

References:

- `references/report-template.md` — bottleneck report template.
- `references/frappe-hot-paths.md` — Frappe/ERPNext performance hotspots checklist.
