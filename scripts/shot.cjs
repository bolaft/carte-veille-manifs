const { chromium } = require('playwright');
(async () => {
const file = process.argv[2]; const out = process.argv[3] || '/tmp/shot';
const browser = await chromium.launch();
for (const [name, vw, vh, dark] of [['desktop', 1440, 900, false], ['desktop-dark', 1440, 900, true], ['phone', 400, 860, false]]) {
  const ctx = await browser.newContext({ viewport: { width: vw, height: vh }, deviceScaleFactor: 1, colorScheme: dark ? 'dark' : 'light' });
  const page = await ctx.newPage();
  const errs = [];
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errs.push(m.type() + ': ' + m.text()); });
  page.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
  await page.goto('file://' + file + (process.argv[4] || ''), { waitUntil: 'load' });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${out}-${name}.png`, fullPage: name === 'phone' });
  const sw = await page.evaluate(() => document.documentElement.scrollWidth + ' vs ' + window.innerWidth);
  console.log(name, 'scrollWidth/innerWidth:', sw, errs.length ? '\n  ' + errs.join('\n  ') : 'no console errors');
  await ctx.close();
}
await browser.close();
})();
