const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  for (const day of process.argv.slice(3)) {
    await page.goto('file://' + process.argv[2] + '#' + day, { waitUntil: 'load' }); await page.waitForTimeout(600);
    const tiles = await page.evaluate(() => [...document.querySelectorAll('#cgrid .tile')].map((t) => t.querySelector('.k').textContent + ' = ' + t.querySelector('.v').textContent + ' | ' + t.querySelector('.m').textContent.slice(0, 40) + ' | ' + (t.querySelector('.m2') ? t.querySelector('.m2').textContent.slice(0, 90) : '')).join('\n'));
    console.log('== ' + day + '\n' + tiles);
  }
  await browser.close();
})();
