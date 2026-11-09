const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  const errs = []; page.on('pageerror', (e) => errs.push(e.message)); page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  await page.goto('file://' + process.argv[2] + '#2026-10-17', { waitUntil: 'load' }); await page.waitForTimeout(800);
  const nCircles = await page.locator('circle.ev').count(); const nInc = await page.locator('path.inc').count();
  // click the biggest circle (Paris)
  await page.evaluate(() => { const cs = [...document.querySelectorAll('circle.ev')].sort((a, b) => +b.getAttribute('r') - +a.getAttribute('r')); cs[0].dispatchEvent(new MouseEvent('click', { bubbles: true })); });
  await page.waitForTimeout(300);
  const summary = await page.locator('#summary').innerText(); const cards = await page.locator('.card').count();
  // clear city, switch to cumul mode
  await page.evaluate(() => document.querySelector('#clearcity') && document.querySelector('#clearcity').click());
  await page.click('#mode-cumul'); await page.waitForTimeout(300);
  const summary2 = await page.locator('#summary').innerText(); const cards2 = await page.locator('.card').count(); const more = await page.locator('#more').count();
  // keyboard navigation
  await page.click('#mode-day'); await page.keyboard.press('ArrowRight'); await page.waitForTimeout(200);
  const date = await page.locator('#date').innerText(); const hash = await page.evaluate(() => location.hash);
  // filter chip off: police
  await page.click('.chip[data-f="police"]'); await page.waitForTimeout(200); const nInc2 = await page.locator('path.inc').count();
  // search
  await page.fill('#q', 'mamou'); await page.waitForTimeout(200); const s3 = await page.locator('#summary').innerText();
  // counter tiles
  await page.fill('#q', ''); await page.click('.chip[data-f="police"]');
  const tiles = await page.evaluate(() => [...document.querySelectorAll('#cgrid .tile')].map((t) => t.querySelector('.k').textContent + ' = ' + t.querySelector('.v').textContent + ' | ' + t.querySelector('.m').textContent + ' | ' + (t.querySelector('.m2') ? t.querySelector('.m2').textContent : '')).join('\n'));
  console.log({ nCircles, nInc, summary, cards, summary2, cards2, more, date, hash, nInc2, s3, errs });
  console.log(tiles);
  await browser.close();
})();
