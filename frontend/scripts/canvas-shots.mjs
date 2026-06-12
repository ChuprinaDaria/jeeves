/* eslint-disable no-undef */
/* Visual check for the Tools canvas. Not part of the build/CI.
   Usage:
     npm i -D puppeteer          # one-off, not committed
     npx vite --port 5199 &      # serves /preview.html
     node scripts/canvas-shots.mjs
*/
import puppeteer from 'puppeteer';

const BASE = 'http://localhost:5199/preview.html';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const browser = await puppeteer.launch({
  headless: 'new',
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--font-render-hinting=none'],
});
const page = await browser.newPage();
await page.setViewport({ width: 1480, height: 980, deviceScaleFactor: 2 });
await page.goto(BASE, { waitUntil: 'networkidle0' });
await sleep(2500); // fonts, node-enter animations, first activity poll

// 1 — live canvas (dark stage, glow edges, pulses)
await page.screenshot({ path: '/tmp/canvas-live.png' });

// 2 — heatmap mode
const heatBtn = await page.$('button[aria-label*="Теплокарта"]');
if (heatBtn) await heatBtn.click();
await sleep(800);
await page.screenshot({ path: '/tmp/canvas-heatmap.png' });
if (heatBtn) await heatBtn.click(); // back to live
await sleep(300);

// 3 — copilot dock: Jeeves connects Telegram, node appears
await page.evaluate(() => window.__setCopilot(true));
await sleep(400);
await page.type('input[placeholder*="Jeeves"]', 'Підключи Telegram і направ повідомлення консьєржу');
await page.keyboard.press('Enter');
await sleep(3500); // fake stream + node pop-in
await page.screenshot({ path: '/tmp/canvas-copilot.png' });

await browser.close();
console.log('done');
