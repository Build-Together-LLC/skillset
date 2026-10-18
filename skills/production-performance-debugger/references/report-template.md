# Performance Bottleneck Understanding Report Template

Use this template after reproducing and profiling, before proposing or implementing a fix.

```markdown
# Performance Investigation: <API / Screen / Workflow>

## Executive Summary

- Environment: <production/UAT/staging, VM/Kubernetes/Frappe Cloud, site/app>
- User-visible symptom: <what the human sees>
- Lifecycle tested: <login/session/API sequence or endpoint-only>
- Main bottleneck: <one sentence>
- Confidence: High / Medium / Low

## Scope and Safety

- Read-only or mutating: <read-only/mutating/skipped mutating calls>
- Load level used: <single request / smoke / concurrency ramp>
- Secrets handling: cookies/tokens redacted
- Caveats: <stale browser session, ephemeral pod patch, limited user, test data constraints>

## Runtime Path

- Entry: <domain / LB / ingress / nginx / service>
- App runtime: <pod/container/VM process>
- Worker: <gunicorn/node/uwsgi/etc.>
- Database/cache: <MariaDB/Postgres/Redis/etc.>
- Relevant app path: <file/function/handler if known>

## Reproduction

```bash
# redacted command or script path
<command>
```

## Timing Results

| Test | p50 / run time | p95 if load-tested | Error rate | Notes |
|---|---:|---:|---:|---|
| External curl | | | | |
| Internal service/pod curl | | | | |
| Direct handler/backend probe | | | | |
| Controlled variant | | | | |

## Profiling Findings

### Time Breakdown

| Phase | Time | Evidence |
|---|---:|---|
| Routing/LB/TLS | | |
| App handler | | |
| SQL | | |
| Cache/Redis | | |
| Serialization/document loading | | |
| External calls/files | | |

### Repeated Work / Amplification

- Query count:
- Slow query examples:
- Repeated hooks/metadata/cache calls:
- Documents/child tables loaded:
- Rows scanned vs rows returned:

## Root Cause Explanation

Explain why the bottleneck happens in plain English. Include whether it is:

- endpoint-specific business logic;
- global framework hook;
- login/session/boot hot path;
- N+1 query/document loading;
- missing index/query shape;
- worker/concurrency starvation;
- external dependency wait;
- infrastructure/routing issue.

## Causality Proof

| Comparison | Result | Interpretation |
|---|---|---|
| Normal vs controlled variant | | |
| Single endpoint vs lifecycle | | |
| One user/data shape vs another | | |
| External vs internal call | | |

## Impacted Areas

- Confirmed impacted APIs/screens:
- Likely impacted similar paths:
- Not impacted / ruled out:

## Recommended Fixes

### Short-term mitigation

- <safe temporary mitigation>

### Source fix

- <code/data/index/config fix>

### Correctness checks

- Permissions/security:
- Data correctness:
- Cache invalidation:
- Regression tests:

## Deployment Notes

- Branch/commit/PR:
- If live-patched: which pods/VM files and why ephemeral:
- Rollback plan:
- Monitoring after deploy:

## Artifacts

- Profiling script:
- Load test script:
- Logs/report paths:
- Issue/PR links:
```
