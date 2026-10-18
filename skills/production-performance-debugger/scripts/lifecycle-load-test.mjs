#!/usr/bin/env node
/**
 * Generic lifecycle load/smoke tester for API/webapp performance debugging.
 *
 * No npm dependencies; requires Node 18+ for built-in fetch.
 *
 * Usage:
 *   node lifecycle-load-test.mjs --config scenario.json --out results.json
 *   node lifecycle-load-test.mjs --config scenario.json --concurrency 5 --iterations 20
 *
 * See scripts/sample-frappe-lifecycle-scenario.json for the config shape.
 */

import fs from 'node:fs/promises';
import { performance } from 'node:perf_hooks';

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (!next || next.startsWith('--')) args[key] = true;
      else args[key] = next, i++;
    }
  }
  return args;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function percentile(values, p) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1);
  return Number(sorted[idx].toFixed(3));
}

function render(value, vars) {
  if (value == null) return value;
  if (typeof value === 'string') {
    return value.replace(/\{\{\s*([\w.-]+)\s*\}\}/g, (_, k) => {
      const parts = k.split('.');
      let cur = vars;
      for (const p of parts) cur = cur?.[p];
      return cur == null ? '' : String(cur);
    });
  }
  if (Array.isArray(value)) return value.map(v => render(v, vars));
  if (typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, render(v, vars)]));
  }
  return value;
}

function getPath(obj, path) {
  if (!path) return obj;
  return path.split('.').reduce((cur, part) => cur?.[part], obj);
}

class CookieJar {
  constructor() { this.cookies = new Map(); }
  addFromResponse(headers, baseUrl) {
    const raw = headers.getSetCookie ? headers.getSetCookie() : [];
    // Node fetch before getSetCookie support may combine set-cookie; keep best effort.
    const values = raw.length ? raw : (headers.get('set-cookie') ? [headers.get('set-cookie')] : []);
    for (const value of values) {
      const first = value.split(';')[0];
      const eq = first.indexOf('=');
      if (eq > 0) this.cookies.set(first.slice(0, eq).trim(), first.slice(eq + 1).trim());
    }
  }
  header() {
    return [...this.cookies.entries()].map(([k, v]) => `${k}=${v}`).join('; ');
  }
  get(name) { return this.cookies.get(name); }
}

async function doStep(config, step, vuState) {
  const vars = vuState.vars;
  const baseUrl = config.baseUrl || '';
  const url = render(step.url || `${baseUrl}${step.path || ''}`, vars);
  const method = step.method || 'GET';
  const headers = {
    ...(config.headers || {}),
    ...(step.headers || {}),
  };

  const cookieHeader = vuState.jar.header();
  if (cookieHeader) headers.cookie = cookieHeader;

  let body;
  if (step.json !== undefined) {
    body = JSON.stringify(render(step.json, vars));
    headers['content-type'] ||= 'application/json';
  } else if (step.form !== undefined) {
    body = new URLSearchParams(render(step.form, vars)).toString();
    headers['content-type'] ||= 'application/x-www-form-urlencoded';
  } else if (step.body !== undefined) {
    body = render(step.body, vars);
  }

  const started = performance.now();
  let response, text = '', json = undefined, error = null;
  try {
    response = await fetch(url, { method, headers, body, redirect: step.redirect || 'manual' });
    vuState.jar.addFromResponse(response.headers, baseUrl);
    text = await response.text();
    const ctype = response.headers.get('content-type') || '';
    if (ctype.includes('application/json') || text.trim().startsWith('{') || text.trim().startsWith('[')) {
      try { json = JSON.parse(text); } catch { /* not JSON */ }
    }
  } catch (e) {
    error = e.message || String(e);
  }
  const elapsedMs = performance.now() - started;

  const expected = step.expectStatus ?? config.expectStatus ?? [200, 201];
  const allowed = Array.isArray(expected) ? expected : [expected];
  const status = response?.status || 0;
  const ok = !error && allowed.includes(status);

  if (step.extract && response) {
    for (const [name, rule] of Object.entries(step.extract)) {
      let val;
      if (rule.from === 'json') val = getPath(json, rule.path);
      else if (rule.from === 'header') val = response.headers.get(rule.name || rule.header);
      else if (rule.from === 'cookie') val = vuState.jar.get(rule.name);
      else if (rule.from === 'body_regex') {
        const m = text.match(new RegExp(rule.regex, rule.flags || ''));
        val = m?.[rule.group || 1];
      }
      if (val != null) vars[name] = val;
    }
  }

  return {
    name: step.name || `${method} ${step.path || step.url}`,
    method,
    url: step.redactUrl ? '<redacted>' : url,
    status,
    ok,
    elapsedMs: Number(elapsedMs.toFixed(3)),
    bytes: text.length,
    error,
  };
}

async function runVu(config, vuId, iterations, results) {
  const state = { vuId, jar: new CookieJar(), vars: { ...(config.vars || {}), vuId } };
  for (let iter = 0; iter < iterations; iter++) {
    const iterationStarted = performance.now();
    const stepResults = [];
    for (const step of config.steps || []) {
      const res = await doStep(config, step, state);
      stepResults.push(res);
      results.steps.push({ vuId, iteration: iter, ...res });
      if (!res.ok && (step.abortOnFail ?? config.abortOnFail ?? false)) break;
      const thinkMs = step.thinkMs ?? config.thinkMs ?? 0;
      if (thinkMs) await sleep(Number(thinkMs));
    }
    results.iterations.push({
      vuId,
      iteration: iter,
      elapsedMs: Number((performance.now() - iterationStarted).toFixed(3)),
      ok: stepResults.every(s => s.ok),
    });
  }
}

function summarize(results) {
  const byStep = {};
  for (const r of results.steps) {
    byStep[r.name] ||= [];
    byStep[r.name].push(r);
  }
  const stepSummary = Object.fromEntries(Object.entries(byStep).map(([name, rows]) => {
    const times = rows.map(r => r.elapsedMs);
    const errors = rows.filter(r => !r.ok).length;
    return [name, {
      count: rows.length,
      errors,
      errorRate: Number((errors / rows.length).toFixed(4)),
      min: Number(Math.min(...times).toFixed(3)),
      p50: percentile(times, 50),
      p95: percentile(times, 95),
      p99: percentile(times, 99),
      max: Number(Math.max(...times).toFixed(3)),
    }];
  }));
  const iterTimes = results.iterations.map(r => r.elapsedMs);
  return {
    totalSteps: results.steps.length,
    totalIterations: results.iterations.length,
    iterationErrors: results.iterations.filter(r => !r.ok).length,
    iterationLatency: iterTimes.length ? {
      p50: percentile(iterTimes, 50),
      p95: percentile(iterTimes, 95),
      p99: percentile(iterTimes, 99),
      max: Number(Math.max(...iterTimes).toFixed(3)),
    } : {},
    steps: stepSummary,
  };
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.config) {
    console.error('Usage: node lifecycle-load-test.mjs --config scenario.json [--out results.json] [--concurrency N] [--iterations N]');
    process.exit(2);
  }
  const config = JSON.parse(await fs.readFile(args.config, 'utf8'));
  const concurrency = Number(args.concurrency || config.concurrency || 1);
  const iterations = Number(args.iterations || config.iterations || 1);
  const results = {
    startedAt: new Date().toISOString(),
    configName: config.name || args.config,
    concurrency,
    iterationsPerVu: iterations,
    steps: [],
    iterations: [],
  };

  const started = performance.now();
  await Promise.all(Array.from({ length: concurrency }, (_, i) => runVu(config, i + 1, iterations, results)));
  results.finishedAt = new Date().toISOString();
  results.elapsedMs = Number((performance.now() - started).toFixed(3));
  results.summary = summarize(results);

  const out = args.out || config.out || `load-results-${Date.now()}.json`;
  await fs.writeFile(out, JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results.summary, null, 2));
  console.error(`Saved results: ${out}`);
}

main().catch(e => { console.error(e); process.exit(1); });
