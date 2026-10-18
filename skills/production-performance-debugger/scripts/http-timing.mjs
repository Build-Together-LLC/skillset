#!/usr/bin/env node
/**
 * Repeat one HTTP request and print curl-like timing percentiles.
 * Useful before writing a full lifecycle scenario.
 *
 * Usage:
 *   node http-timing.mjs --url https://example.com/api/method/ping --n 10
 *   node http-timing.mjs --url https://example.com/api --method POST --json '{"x":1}' --header 'authorization: token ...'
 */

import { performance } from 'node:perf_hooks';

function parseArgs(argv) {
  const args = { header: [] };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) continue;
    const key = a.slice(2);
    const next = argv[i + 1];
    if (key === 'header') args.header.push(next), i++;
    else if (!next || next.startsWith('--')) args[key] = true;
    else args[key] = next, i++;
  }
  return args;
}

function percentile(values, p) {
  const s = [...values].sort((a, b) => a - b);
  if (!s.length) return null;
  return Number(s[Math.min(s.length - 1, Math.ceil((p / 100) * s.length) - 1)].toFixed(3));
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.url) {
    console.error('Usage: node http-timing.mjs --url URL [--n 10] [--method POST] [--json JSON] [--header "k: v"]');
    process.exit(2);
  }
  const headers = {};
  for (const h of args.header || []) {
    const idx = h.indexOf(':');
    if (idx > 0) headers[h.slice(0, idx).trim()] = h.slice(idx + 1).trim();
  }
  let body;
  if (args.json) {
    body = args.json;
    headers['content-type'] ||= 'application/json';
  } else if (args.body) body = args.body;

  const n = Number(args.n || 1);
  const rows = [];
  for (let i = 0; i < n; i++) {
    const started = performance.now();
    let status = 0, bytes = 0, error = null;
    try {
      const res = await fetch(args.url, { method: args.method || (body ? 'POST' : 'GET'), headers, body });
      status = res.status;
      const text = await res.text();
      bytes = text.length;
    } catch (e) {
      error = e.message || String(e);
    }
    const elapsedMs = Number((performance.now() - started).toFixed(3));
    rows.push({ run: i + 1, status, elapsedMs, bytes, error });
    console.log(JSON.stringify(rows.at(-1)));
  }
  const times = rows.map(r => r.elapsedMs);
  const errors = rows.filter(r => r.error || r.status >= 400 || r.status === 0).length;
  console.error(JSON.stringify({
    count: rows.length,
    errors,
    errorRate: Number((errors / rows.length).toFixed(4)),
    min: Number(Math.min(...times).toFixed(3)),
    p50: percentile(times, 50),
    p95: percentile(times, 95),
    p99: percentile(times, 99),
    max: Number(Math.max(...times).toFixed(3)),
  }, null, 2));
}

main().catch(e => { console.error(e); process.exit(1); });
