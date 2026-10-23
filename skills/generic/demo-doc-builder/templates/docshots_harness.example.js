// EXAMPLE screenshot harness for a flow that changes data (see references/frappe-demo-data.md, items 26 to 31).
// Follows the product in the order a person would, so reset the demo data first. Target boxes are stored in image pixels,
// so annotate.py can use them as they are: {"box": ["01_form", 1]}.
//   DEMO_PASSWORD=... node docshots.js      -> work/shots/*.png and work/shots/boxes.json
// Copy it, set BASE, then replace the flow at the bottom with your own shots.
const fs = require('fs');
const path = require('path');
const home = process.env.DEMO_DOC_HOME || path.join(process.env.HOME, '.cache', 'demo-doc-builder');
const { chromium } = require(path.join(home, 'node_modules', 'playwright-core'));

const OUT = path.join(__dirname, 'work', 'shots');
const BASE = 'http://localhost:8001';   // the demo site, served on its own port
const W = 1360;                         // css width; shots are taken at scale 2
fs.mkdirSync(OUT, { recursive: true });
const boxes = {};
let page;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const OPT = 'ul[role=listbox]:visible div[role=option]';   // options of a Frappe link field

async function go(url, wait = 6000) {
  await page.goto(BASE + url, { waitUntil: 'domcontentloaded' });
  await sleep(wait);
  // a first-visit tour overlay can open in a fresh browser context
  await page.evaluate(() => [...document.querySelectorAll('button')].find((b) => /Skip tour/.test(b.innerText))?.click());
}
async function click(sel, wait = 800) { await page.locator(sel).first().click({ timeout: 9000 }); await sleep(wait); }
async function pickLink(field, text) {   // type the FULL name: a short one can match another record
  await page.click(`[data-fieldname="${field}"] input`); await page.keyboard.type(text, { delay: 50 }); await sleep(2200);
  await click(OPT + ' >> nth=0', 4500);
}
const rect = (sel) => page.evaluate((s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }, sel);
// exact span of one sentence inside a single text node (a popup message, a comment)
const rectSub = (txt) => page.evaluate((t) => {
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) {
    const i = n.data.indexOf(t);
    if (i < 0 || !n.parentElement.offsetParent) continue;
    const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + t.length);
    const b = r.getBoundingClientRect(); if (b.width) return [b.left, b.top, b.right, b.bottom];
  }
  return null;
}, txt);
const rectRow = (txt) => page.evaluate((t) => { const e = [...document.querySelectorAll('.list-row-container')].find((x) => x.innerText.includes(t)); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }, txt);

// targets: [{n, sel | sub | row | box, pad}]; clip: [x, y, w, h] in viewport css px (boxes are then relative to the clip)
async function shot(name, targets = [], clip = null) {
  const b = {};
  for (const t of targets) {
    const r = t.box || (t.sub ? await rectSub(t.sub) : t.row ? await rectRow(t.row) : await rect(t.sel));
    if (!r) { console.log('  target missing', name, t.n); continue; }
    const p = t.pad ?? 6;
    let [x1, y1, x2, y2] = [r[0] - p, r[1] - p, r[2] + p, r[3] + p];
    if (clip) { x1 -= clip[0]; x2 -= clip[0]; y1 -= clip[1]; y2 -= clip[1]; }
    b[t.n] = [x1, y1, x2, y2].map(Math.round);
  }
  if (targets.length) boxes[name] = b;
  const o = { path: path.join(OUT, name + '.png') };
  if (clip) o.clip = { x: clip[0], y: clip[1], width: clip[2], height: clip[3] };
  await page.screenshot(o);
  console.log('shot', name, `${Object.keys(b).length}/${targets.length}`);
}

(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: W, height: 900 }, deviceScaleFactor: 2 });
  page = await ctx.newPage();
  page.setDefaultTimeout(9000); page.setDefaultNavigationTimeout(45000);
  page.on('dialog', (d) => d.accept().catch(() => {}));   // accept "unsaved changes"; dismissing it cancels the navigation
  await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
  await page.fill('#login_email', 'Administrator'); await page.fill('#login_password', process.env.DEMO_PASSWORD);
  await page.press('#login_password', 'Enter'); await sleep(6000);

  // ---- your flow: one block per shot, in the order the product is used --------------------------------------------
  await go('/app/some-doctype/new', 7000);
  await pickLink('customer', 'Full Customer Name');
  await shot('01_form', [{ n: 1, sel: '[data-fieldname="customer"] .control-input' }, { n: 2, sel: '[data-fieldname="status"]' }]);
  await page.keyboard.press('Control+s'); await sleep(3500);
  await shot('02_refused', [{ n: 1, sub: 'The exact sentence of the message.', pad: 3 }]);   // a popup, with a badge on one sentence
  await page.keyboard.press('Escape');
  // a list view keeps its last filter: pass one in the url
  await go('/app/some-doctype?status=Open', 6000);
  await shot('03_list', [{ n: 1, row: 'Full Customer Name', pad: 2 }]);

  fs.writeFileSync(path.join(OUT, 'boxes.json'), JSON.stringify(boxes, null, 1));
  await browser.close();
  console.log('DOCSHOTS_DONE');
})().catch((e) => { console.error('FATAL', e.message); process.exit(1); });
