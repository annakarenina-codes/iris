const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const net = require('node:net');
const {
  spawn
} = require('node:child_process');
const {
  chromium
} = require(process.env.IRIS_PLAYWRIGHT_PATH || path.join(__dirname, '../../iris-extension/node_modules/playwright'));
let fixtureServer;
const screenshotDirectory = process.env.IRIS_TRACE_UI_OUTPUT || fs.mkdtempSync(path.join(os.tmpdir(), 'iris-trace-screens-'));
fs.mkdirSync(screenshotDirectory, {
  recursive: true
});
const assert = require('node:assert/strict');
(async () => {
  const port = await new Promise(resolve => {
    const s = net.createServer();
    s.listen(0, '127.0.0.1', () => {
      const port = s.address().port;
      s.close(() => resolve(port))
    })
  });
  const base = 'http://127.0.0.1:' + port;
  fixtureServer = spawn(process.env.IRIS_TEST_PYTHON || 'python', [path.join(__dirname, 'trace_ui_server.py'), '--port', String(port)], {
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8'
    }
  });
  await new Promise((resolve, reject) => {
    let output = '';
    const timer = setTimeout(() => reject(Error('Fixture server startup timeout: ' + output.slice(-1500))), 20000);
    fixtureServer.stdout.on('data', chunk => {
      output += chunk;
      if (output.includes('TRACE_UI_READY')) {
        clearTimeout(timer);
        resolve()
      }
    });
    fixtureServer.stderr.on('data', chunk => {
      output += chunk
    });
    fixtureServer.on('error', reject);
    fixtureServer.on('exit', code => {
      if (code) reject(Error('Fixture server exited: ' + output.slice(-1500)))
    })
  });
  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true
  });
  const page = await browser.newPage({
    viewport: {
      width: 1440,
      height: 1000
    }
  });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  try {
    await page.goto(base + '/debug/trace');
    await page.locator('.history-item').first().waitFor();
    const records = await page.request.get(base + '/debug/traces').then(r => r.json());
    const text = records.items.find(r => r.platform === 'chrome'),
      image = records.items.find(r => r.platform === 'android');
    await page.locator(`[data-id="${text.id}"]`).click();
    let ws = page.locator('.workspace:visible');
    await ws.getByRole('combobox', {
      name: 'Claim scope'
    }).selectOption('2');
    await ws.getByRole('button', {
      name: 'Claims',
      exact: true
    }).click();
    await ws.getByRole('heading', {
      name: 'Claim 2',
      exact: true
    }).waitFor();
    assert.equal(await ws.getByRole('heading', {
      name: 'Claim 1',
      exact: true
    }).count(), 0);
    assert.equal(await page.evaluate(() => window.BAD), undefined);
    await page.locator(`[data-id="${image.id}"]`).click();
    ws = page.locator('.workspace:visible');
    await ws.getByRole('button', {
      name: 'Input and OCR',
      exact: true
    }).click();
    await ws.locator('svg').waitFor();
    assert.equal(await ws.locator('svg').getAttribute('viewBox'), '0 0 200 200');
    assert.equal(await ws.locator('polygon.ocr-retained').count(), 1);
    assert.equal(await ws.locator('polygon.ocr-rejected').count(), 1);
    await page.screenshot({
      path: path.join(screenshotDirectory, 'ocr.png'),
      fullPage: true
    });
    assert.equal(await page.getByRole('tab').count(), 2);
    await page.locator(`[data-id="${text.id}"]`).click();
    assert.equal(await page.getByRole('tab').count(), 2);
    await page.getByRole('tab', {
      selected: true
    }).focus();
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.getByRole('tab', {
      selected: true
    }).count(), 1);
    await page.reload();
    await page.getByRole('tab').first().waitFor();
    assert.equal(await page.getByRole('tab').count(), 2);
    await page.getByRole('button', {
      name: 'Close request ' + text.id.slice(0, 8),
      exact: true
    }).click();
    assert.equal(await page.getByRole('tab').count(), 1);
    await page.locator(`[data-id="${text.id}"]`).click();
    assert.equal(await page.getByRole('tab').count(), 2);
    await page.locator('.compare summary').click();
    await page.locator('#baseline').fill(text.id);
    await page.locator('#candidate').fill(image.id);
    await page.getByRole('button', {
      name: 'Compare stage outputs'
    }).click();
    await page.locator('#comparison p').waitFor();
    await page.locator('#calibration summary').click();
    await page.locator('#case').fill(JSON.stringify({
      case_id: 'UI-OFFLINE-001',
      mode: 'layout',
      input: {
        regions: []
      },
      assertions: [{
        path: 'text',
        expected: ''
      }]
    }));
    const started = page.waitForResponse(r => r.url().endsWith('/debug/calibration/runs'));
    await page.getByRole('button', {
      name: 'Run case',
      exact: true
    }).click();
    const run = await (await started).json();
    await page.locator('#tab-' + run.trace_id).filter({
      hasText: 'completed'
    }).waitFor({
      timeout: 10000
    });
    ws = page.locator('.workspace:visible');
    await ws.getByRole('button', {
      name: 'Decisions',
      exact: true
    }).click();
    await ws.getByText(/calibration.result/).waitFor();
    await page.screenshot({
      path: path.join(screenshotDirectory, 'calibration.png'),
      fullPage: true
    });
    assert.deepEqual(errors, []);
    assert.equal((await page.locator('body').innerText()).includes('Ã'), false);
    console.log('PASS: request tabs, claim scope, escaping, OCR coordinates, reload/reopen, keyboard tabs, comparison and offline calibration.');
  } finally {
    await browser.close();
    fixtureServer.kill()
  }
})().catch(e => {
  fixtureServer?.kill();
  console.error(e);
  process.exitCode = 1
});
