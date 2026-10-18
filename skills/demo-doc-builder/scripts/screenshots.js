#!/usr/bin/env node
// Take screenshots from a JSON plan with Playwright (system Chrome, headless).
//   node screenshots.js plan.json
//
// Optional plan keys: "scale": 2 (device pixel ratio, use 2 for slides and print), per-shot "dismiss": true
// (press Escape and remove stray modals/backdrops before the shot, e.g. Frappe "Session Defaults").
// plan.json
// { "base": "http://localhost:9100" (or "file://{{PLAN_DIR}}" for a local html file), "outDir": "shots", "viewport": {"width":1360,"height":780},
//   "contexts": { "default": {"login": {"url":"/login","fill":{"#login_email":"Administrator","#login_password":"admin"},"submit":"#login_password"}},
//                 "agent":   {"login": {...}} },
//   "shots": [ { "name":"01_settings", "url":"/app/settings", "wait":3000, "context":"default",
//                "steps":[ {"click":"text=Save"}, {"fill":["#name","Sales"]}, {"hover":".icon"}, {"press":"Escape"},
//                          {"wait":800}, {"scroll":".section"}, {"eval":"document.title"} ], "fullPage":false } ] }
//
// Use throwaway/demo data. Never screenshot real customers, tokens or personal numbers.
const fs = require('fs');
const path = require('path');
const home = process.env.DEMO_DOC_HOME || path.join(process.env.HOME, '.cache', 'demo-doc-builder');
const { chromium } = require(path.join(home, 'node_modules', 'playwright-core'));

function browserPath() {
  const c = [process.env.CHROME, '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser'];
  return c.find((p) => p && fs.existsSync(p));
}

async function login(page, base, spec) {
  if (!spec) return;
  await page.goto(base + spec.url, { waitUntil: 'domcontentloaded' });
  for (const [sel, val] of Object.entries(spec.fill || {})) await page.fill(sel, val);
  if (spec.submit) await page.press(spec.submit, 'Enter');
  await page.waitForTimeout(spec.wait || 3500);
}

(async () => {
  const planFile = process.argv[2];
  const plan = JSON.parse(fs.readFileSync(planFile, 'utf8'));
  plan.base = plan.base.replace('{{PLAN_DIR}}', path.dirname(path.resolve(planFile)));
  const outDir = path.resolve(path.dirname(planFile), plan.outDir || 'shots');
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ executablePath: browserPath(), args: ['--no-sandbox'] });
  const pages = {};
  const problems = [];
  const contextFor = async (name) => {
    if (pages[name]) return pages[name];
    const ctx = await browser.newContext({ viewport: plan.viewport || { width: 1360, height: 780 }, deviceScaleFactor: plan.scale || 1 });
    const page = await ctx.newPage();
    page.on('pageerror', (e) => problems.push(`[${name}] pageerror ${e.message}`));
    page.on('response', (r) => { if (r.status() >= 400 && !/socket\.io|favicon/.test(r.url())) problems.push(`[${name}] ${r.status()} ${r.url().slice(0, 120)}`); });
    await login(page, plan.base, (plan.contexts || {})[name] && plan.contexts[name].login);
    return (pages[name] = page);
  };
  for (const shot of plan.shots) {
    const page = await contextFor(shot.context || 'default');
    if (shot.url) await page.goto(plan.base + shot.url, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(shot.wait ?? 3000);
    if (shot.dismiss) {
      await page.keyboard.press('Escape');
      await page.evaluate(() => {
        document.querySelectorAll('.modal.show .btn-modal-close, .modal.show .modal-header .close').forEach((b) => b.click());
        document.querySelectorAll('.modal-backdrop').forEach((e) => e.remove());
      });
      await page.waitForTimeout(600);
    }
    for (const step of shot.steps || []) {
      if (step.click) await page.locator(step.click).first().click();
      else if (step.fill) await page.fill(step.fill[0], step.fill[1]);
      else if (step.hover) await page.locator(step.hover).first().hover();
      else if (step.press) await page.keyboard.press(step.press);
      else if (step.scroll) await page.locator(step.scroll).first().scrollIntoViewIfNeeded();
      else if (step.eval) await page.evaluate(step.eval);
      else if (step.mouse) await page.mouse.click(step.mouse[0], step.mouse[1]);
      await page.waitForTimeout(step.wait ?? 600);
    }
    const file = path.join(outDir, shot.name + '.png');
    await page.screenshot({ path: file, fullPage: !!shot.fullPage });
    console.log('shot', file);
  }
  console.log(problems.length ? 'problems seen while shooting:\n' + problems.join('\n') : 'no console or network problems');
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
