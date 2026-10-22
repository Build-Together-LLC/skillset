// Records every scene of flow.json as a real browser screen recording, timed to the narration.
//   node record.js --project DIR [sceneId ...]
// Each step runs when its sentence starts ("s": sentence index, "d": extra delay in seconds), so picture and voice stay together.
const fs = require('fs');
const path = require('path');
const HOME = process.env.FLOWVIDEO_HOME || path.join(process.env.HOME, '.cache', 'flow-video-builder');
const { chromium } = require(path.join(HOME, 'node_modules', 'playwright-core'));

const argv = process.argv.slice(2);
const pi = argv.indexOf('--project');
const PROJ = path.resolve(pi >= 0 ? argv[pi + 1] : '.');
const only = argv.filter((a, i) => a !== '--project' && !(pi >= 0 && i === pi + 1));
const flow = JSON.parse(fs.readFileSync(path.join(PROJ, 'flow.json'), 'utf8'));
const cfg = flow.config || {};
const timing = JSON.parse(fs.readFileSync(path.join(PROJ, 'audio', 'timing.json'), 'utf8'));
const VIEW = cfg.viewport || { width: 1440, height: 900 };
const BASE = (cfg.base || '').replace(/\/$/, '');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const abs = (u) => (/^(https?|file):/.test(u) ? u : BASE + u);

function chromePath() {
  for (const c of [process.env.CHROME_PATH, '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']) if (c && fs.existsSync(c)) return c;
  throw new Error('No Chrome or Chromium found. Install one or set CHROME_PATH.');
}

// Red cursor dot, plus the privacy scrub from config.scrub (a JS snippet run every 150 ms on every page).
const INIT = `
(() => {
  const mk = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div'); c.id = '__cur';
    c.style.cssText = 'position:fixed;z-index:2147483647;width:22px;height:22px;border-radius:50%;background:rgba(229,57,53,.55);border:2px solid #fff;box-shadow:0 0 0 2px rgba(229,57,53,.6);pointer-events:none;left:-40px;top:-40px;transition:left .35s ease,top .35s ease;transform:translate(-50%,-50%)';
    document.documentElement.appendChild(c);
  };
  addEventListener('mousemove', (e) => { mk(); const c = document.getElementById('__cur'); c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
  addEventListener('DOMContentLoaded', mk);
  const scrub = () => { try { ${(cfg.scrub || []).join('\n')} } catch (e) {} };
  ${(cfg.scrub || []).length ? 'setInterval(scrub, 150);' : ''}
})();`;

const envFill = (v) => String(v).replace(/\$\{(\w+)\}/g, (_, n) => process.env[n] || '');

async function login(browser) {
  if (!cfg.login) return undefined;
  const ctx = await browser.newContext({ viewport: VIEW });
  const p = await ctx.newPage();
  await p.goto(abs(cfg.login.url || '/login'));
  for (const [sel, val] of Object.entries(cfg.login.fill || {})) await p.fill(sel, envFill(val));
  await p.press(cfg.login.submit, 'Enter');
  await p.waitForTimeout(cfg.login.wait || 7000);
  const state = await ctx.storageState();
  await ctx.close();
  return state;
}

async function hl(page, sel, opts = {}) {
  const loc = page.locator(sel).first();
  await loc.scrollIntoViewIfNeeded().catch(() => {});
  const box = await loc.boundingBox();
  if (!box) return;
  await page.evaluate(([b, pad, keep]) => {
    if (!keep) document.querySelectorAll('.__hl').forEach((e) => e.remove());
    const d = document.createElement('div'); d.className = '__hl';
    d.style.cssText = `position:fixed;z-index:2147483646;pointer-events:none;border:3px solid #e53935;border-radius:8px;box-shadow:0 0 0 4px rgba(229,57,53,.18);left:${b.x - pad}px;top:${b.y - pad}px;width:${b.width + 2 * pad}px;height:${b.height + 2 * pad}px`;
    document.documentElement.appendChild(d);
  }, [box, opts.pad ?? 6, !!opts.keep]);
}

async function moveTo(page, sel) {
  const loc = page.locator(sel).first();
  await loc.scrollIntoViewIfNeeded().catch(() => {});
  const b = await loc.boundingBox();
  if (b) await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 12 });
  await sleep(450);
}

async function act(page, st) {
  const T = st.sel || null;
  switch (st.do) {
    case 'goto': await page.goto(abs(st.url), { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(st.wait ?? 2500); break;
    case 'hl': await hl(page, T, st); break;
    case 'clear': await page.evaluate(() => document.querySelectorAll('.__hl').forEach((e) => e.remove())); break;
    case 'move': await moveTo(page, T); break;
    case 'click': await moveTo(page, T); await page.locator(T).first().click({ timeout: 8000 }); await page.waitForTimeout(st.wait ?? 700); break;
    case 'fill': await moveTo(page, T); await page.locator(T).first().click(); await page.locator(T).first().fill(envFill(st.val)); await page.waitForTimeout(st.wait ?? 700); break;
    case 'type': await moveTo(page, T); await page.locator(T).first().click(); await page.locator(T).first().pressSequentially(envFill(st.val), { delay: 70 }); await page.waitForTimeout(st.wait ?? 600); break;
    case 'press': await page.keyboard.press(st.key); await page.waitForTimeout(st.wait ?? 400); break;
    case 'scroll': await page.evaluate((y) => window.scrollBy({ top: y, behavior: 'smooth' }), st.y); await page.waitForTimeout(st.wait ?? 900); break;
    case 'scrollTo': await page.locator(T).first().scrollIntoViewIfNeeded(); await page.waitForTimeout(st.wait ?? 600); break;
    case 'eval': await page.evaluate(st.js); await page.waitForTimeout(st.wait ?? 300); break;
    case 'wait': await page.waitForTimeout(st.ms); break;
    // chat.html replay steps
    case 'say': await page.evaluate(([s, t, b]) => window.say(s, t, b), [st.side, st.text, st.btns || null]); await page.waitForTimeout(st.wait ?? 500); break;
    case 'tap': await page.evaluate((t) => window.tapBtn(t), st.title); await page.waitForTimeout(st.wait ?? 700); break;
    case 'openList': await page.evaluate(([t, r]) => window.openList(t, r), [st.title, st.rows]); await page.waitForTimeout(st.wait ?? 800); break;
    case 'pick': {
      const t = await page.evaluate((i) => window.pickRow(i), st.i);
      await page.waitForTimeout(700);
      await page.evaluate(() => window.closeList());
      await page.waitForTimeout(450);
      if (st.reply !== false) await page.evaluate((x) => window.say('out', x), t);
      await page.waitForTimeout(st.wait ?? 500);
      break;
    }
    case 'side': await page.evaluate(([a, b]) => window.side(a, b), [st.a, st.b]); break;
    default: throw new Error('unknown step ' + st.do);
  }
}

async function runScene(browser, state, sc) {
  const tm = timing[sc.id];
  if (!tm) throw new Error('No audio timing for ' + sc.id + '. Run tts.py first.');
  const dir = path.join(PROJ, 'rec', sc.id) + '/';
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  const ctx = await browser.newContext({ viewport: VIEW, storageState: sc.guest ? undefined : state, recordVideo: { dir, size: VIEW } });
  await ctx.addInitScript(INIT);
  const page = await ctx.newPage();
  const tPage = Date.now();
  page.setDefaultTimeout(cfg.timeout || 9000);
  page.setDefaultNavigationTimeout(cfg.nav_timeout || 45000);
  page.on('dialog', (d) => d.dismiss().catch(() => {}));
  await page.goto(abs(sc.url), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(sc.ready ?? 3500);
  await page.mouse.move(VIEW.width / 2, VIEW.height / 2);
  for (const st of sc.pre || []) await act(page, st);
  const T0 = Date.now();
  const lead = 400;
  for (const st of sc.steps || []) {
    const wait = T0 + lead + (tm.starts[st.s ?? 0] || 0) * 1000 + (st.d || 0) * 1000 - Date.now();
    if (wait > 0) await sleep(wait);
    try { await act(page, st); } catch (e) { console.log('  step failed', sc.id, st.do, st.sel || '', String(e.message).split('\n')[0]); }
  }
  const rest = T0 + lead + tm.total * 1000 + 1200 - Date.now();
  if (rest > 0) await sleep(rest);
  await page.screenshot({ path: dir + 'last.png' });
  const vid = page.video();
  await ctx.close();
  fs.writeFileSync(dir + 'meta.json', JSON.stringify({ file: await vid.path(), offset: (T0 - tPage) / 1000, lead: lead / 1000, total: tm.total + 1.2 }));
  console.log('recorded', sc.id, 'offset', ((T0 - tPage) / 1000).toFixed(1));
}

(async () => {
  const browser = await chromium.launch({ executablePath: chromePath(), args: ['--no-sandbox'] });
  const state = await login(browser);
  for (const sc of flow.scenes) {
    if (only.length && !only.includes(sc.id)) continue;
    await runScene(browser, state, sc);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
