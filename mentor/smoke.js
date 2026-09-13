const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  const errs = [];
  p.on('pageerror', e => errs.push('pageerror: ' + e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });

  await p.goto('file://' + __dirname + '/dist/mentor.html');
  await p.waitForTimeout(300);

  // add a block
  await p.fill('#f-time', '06:30');
  await p.fill('#f-what', 'Write the opening scene');
  await p.fill('#f-why', "it decides whether the script exists");
  await p.click('#add button[type=submit]');
  await p.waitForTimeout(150);
  const blockText = await p.textContent('#blocks');
  if (!/Write the opening scene/.test(blockText)) throw new Error('block not rendered');

  // skip it -> goes to stuck tab with context
  await p.click('#blocks .block .acts button.bad');
  await p.waitForTimeout(200);
  if (await p.isHidden('#panel-stuck')) throw new Error('stuck panel did not open');
  const ctx = await p.textContent('#stuck-for');
  if (!/Write the opening scene/.test(ctx)) throw new Error('context missing');

  // type -> candidates filter
  await p.fill('#belief', 'my idea already exists, someone has done it');
  await p.waitForTimeout(200);
  const n = await p.locator('#chips button').count();
  if (n !== 6) throw new Error('expected 6 candidates, got ' + n);
  const first = await p.locator('#chips button').first().textContent();

  // pick it -> answer renders
  await p.locator('#chips button').first().click();
  await p.waitForTimeout(250);
  const ans = await p.textContent('#answer');
  for (const needle of ['Goethe', 'Smaller version', 'Maxims']) {
    if (!ans.includes(needle)) throw new Error('answer missing ' + needle + ' :: ' + ans.slice(0,200));
  }
  if (await p.locator('#answer .badge').count() !== 1) throw new Error('attribution badge missing');
  await p.screenshot({ path: 'dist/shot-answer.png' });

  // mark done -> log
  await p.click('#answer button.primary');
  await p.waitForTimeout(250);
  const log = await p.textContent('#panel-log');
  if (!/beat/.test(log)) throw new Error('log did not record the win');
  if (!new RegExp(first.slice(0, 20).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).test(log)) throw new Error('belief missing from log');
  await p.screenshot({ path: 'dist/shot-log.png' });

  // persistence across reload
  await p.reload();
  await p.waitForTimeout(300);
  if (!/Write the opening scene/.test(await p.textContent('#blocks'))) throw new Error('state did not persist');

  await b.close();
  if (errs.length) { console.log(errs.join('\n')); process.exit(1); }
  console.log('smoke: all steps passed (add block, skip, filter, answer, log, persist)');
})().catch(e => { console.error('FAIL: ' + e.message); process.exit(1); });
