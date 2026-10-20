#!/usr/bin/env node
// Render clean diagrams (flows and file trees) to PNG from a JSON plan.
//   node diagram.js plan.json
//
// { "theme": "green", "outDir": "img", "width": 1100,   (each diagram may also set its own "width")
//   "diagrams": [
//     { "name": "arch", "type": "flow", "title": "How the pieces talk", "note": "optional footnote",
//       "items": [
//         { "box":   { "title": "Browser", "sub": "inbox page", "color": "neutral" } },
//         { "arrow": { "dir": "both", "labels": ["HTTPS", "login"] } },
//         { "arrow": { "stack": [ {"dir":"right","labels":["1. REST","X-Api-Key"]}, {"dir":"left","labels":["2. Webhook"]} ] } },
//         { "panel": { "label": "VPS", "items": [ { "box": {...} }, { "arrow": {...} }, { "box": {...} } ] } } ] },
//     { "name": "layout", "type": "tree", "title": "Files on the server",
//       "lines": ["/opt/waha/", "!├── docker-compose.yml   # the stack", "└── sessions/"], "note": "lines starting with ! are highlighted" } ] }
// box colors: neutral green blue yellow purple red
const fs = require('fs');
const path = require('path');
const home = process.env.DEMO_DOC_HOME || path.join(process.env.HOME, '.cache', 'demo-doc-builder');
const { chromium } = require(path.join(home, 'node_modules', 'playwright-core'));

const ACCENT = { navy: '#2E75B6', green: '#0F764A', blue: '#1D4ED8', purple: '#6D28D9', orange: '#C2410C', teal: '#0F766E', slate: '#334155' };
const BOX = {
  neutral: ['#F8FAFC', '#334155'], green: ['#ECFDF5', '#16A34A'], blue: ['#EFF6FF', '#2563EB'],
  yellow: ['#FFFBEB', '#D97706'], purple: ['#F5F3FF', '#7C3AED'], red: ['#FEF2F2', '#DC2626'],
};
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function arrowHtml(a, accent) {
  const one = (x) => {
    const glyph = { right: '→', left: '←', both: '↔' }[x.dir || 'right'];
    return `<div class="a1"><div class="g" style="color:${accent}">${glyph}</div>${(x.labels || []).map((l) => `<div class="l">${esc(l)}</div>`).join('')}</div>`;
  };
  return `<div class="arrow">${(a.stack || [a]).map(one).join('')}</div>`;
}
function itemsHtml(items, accent) {
  return items.map((it) => {
    if (it.box) {
      const [bg, edge] = BOX[it.box.color || 'neutral'];
      return `<div class="box" style="background:${bg};border-color:${edge}"><b>${esc(it.box.title)}</b>${it.box.sub ? `<small>${esc(it.box.sub).replace(/\n/g, '<br>')}</small>` : ''}</div>`;
    }
    if (it.arrow) return arrowHtml(it.arrow, accent);
    if (it.panel) return `<div class="panel"><div class="cap">${esc(it.panel.label)}</div><div class="row">${itemsHtml(it.panel.items, accent)}</div></div>`;
    return '';
  }).join('');
}
function treeHtml(d) {
  return `<pre class="tree">${d.lines.map((l) => {
    const hot = l.startsWith('!');
    const raw = hot ? l.slice(1) : l;
    const [code, ...cm] = raw.split('#');
    return `<div class="${hot ? 'hot' : ''}">${esc(code)}${cm.length ? `<span class="cm">#${esc(cm.join('#'))}</span>` : ''}</div>`;
  }).join('')}</pre>`;
}

(async () => {
  const planFile = process.argv[2];
  const plan = JSON.parse(fs.readFileSync(planFile, 'utf8'));
  const accent = ACCENT[plan.theme || 'green'] || ACCENT.green;
  const width = plan.width || 1100;
  const outDir = path.resolve(path.dirname(planFile), plan.outDir || 'img');
  fs.mkdirSync(outDir, { recursive: true });
  const css = `body{margin:0;font-family:'Times New Roman',Times,serif;background:#fff;color:#1f272e}
  .wrap{width:${width}px;padding:26px 30px;box-sizing:border-box}h2{margin:0 0 18px;font-size:24px;color:${accent}}
  .row{display:flex;align-items:center;justify-content:space-between;gap:10px}
  .box{border:2px solid;border-radius:12px;padding:12px 14px;min-width:140px;text-align:center}
  .box b{display:block;font-size:19px;margin-bottom:3px}.box small{font-size:15px;color:#475569}
  .arrow{flex:1;min-width:110px;text-align:center;font-size:15px;color:#334155;line-height:1.35}
  .a1{margin:2px 0}.g{font-size:26px;line-height:1}.l{font-size:15px}
  .panel{border:2px dashed #94a3b8;border-radius:16px;padding:14px;flex:1.2}.cap{font-size:14px;font-weight:700;color:#64748b;margin-bottom:8px;text-transform:uppercase;letter-spacing:.5px}
  .note{margin-top:14px;font-size:15px;color:#475569}
  .fit{width:fit-content;min-width:${width}px}.tree{background:#0f172a;color:#e2e8f0;border-radius:12px;padding:18px 22px;font-family:'Courier New',monospace;font-size:16px;line-height:1.5;margin:0}
  .tree div{padding:0 6px;border-radius:4px}.tree .hot{background:#1e3a8a;color:#fff}.tree .cm{color:#86efac;margin-left:8px}`;
  const html = `<!doctype html><meta charset="utf-8"><style>${css}</style>` + plan.diagrams.map((d) =>
    `<div class="wrap${d.type === 'tree' ? ' fit' : ''}" id="${d.name}"${d.width ? ` style="width:${d.width}px"` : ''}><h2>${esc(d.title || '')}</h2>${d.type === 'tree' ? treeHtml(d) : `<div class="row">${itemsHtml(d.items, accent)}</div>`}${d.note ? `<div class="note">${esc(d.note)}</div>` : ''}</div>`).join('');
  const tmp = path.join(outDir, '_diagrams.html');
  fs.writeFileSync(tmp, html);
  const find = [process.env.CHROME, '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser'].find((p) => p && fs.existsSync(p));
  const browser = await chromium.launch({ executablePath: find, args: ['--no-sandbox'] });
  const page = await (await browser.newContext({ viewport: { width: Math.max(width + 60, 1900, ...plan.diagrams.map((x) => (x.width || 0) + 60)), height: 800 }, deviceScaleFactor: 1.5 })).newPage();
  await page.goto('file://' + tmp);
  for (const d of plan.diagrams) {
    const file = path.join(outDir, `diagram_${d.name}.png`);
    await page.locator('#' + d.name).screenshot({ path: file });
    console.log('diagram', file);
  }
  fs.unlinkSync(tmp);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
