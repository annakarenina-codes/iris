const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { readFile, mkdir } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const extensionRoot = path.resolve(__dirname, '..');
let browser;
before(async () => {
  browser = await chromium.launch({ headless: true, channel: process.env.IRIS_TEST_BROWSER || 'chrome' });
});
after(async () => { await browser?.close(); });

async function fixture(t, settings = {}) {
  const page = await browser.newPage({ viewport: { width: 1100, height: 850 } });
  t.after(() => page.close());
  await page.route('https://iris.test/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/page') {
      await route.fulfill({ contentType: 'text/html', body: '<p id="post">A factual claim on the page with additional context.</p>' });
    } else if (url.pathname === '/src/content.css') {
      await route.fulfill({ contentType: 'text/css', body: await readFile(path.join(extensionRoot, 'src/content.css')) });
    } else if (url.pathname === '/assets/iris-logo-mark.png') {
      await route.fulfill({ contentType: 'image/png', body: await readFile(path.join(extensionRoot, 'assets/iris-logo-mark.png')) });
    } else {
      await route.abort();
    }
  });
  await page.goto('https://iris.test/page');
  await page.evaluate((settings) => {
    const listeners = [];
    const changes = [];
    const values = { ...settings };
    window.irisTest = {
      requests: [],
      message(message) { for (const listener of listeners) listener(message, {}, () => {}); },
      change(items, area = 'sync') { for (const listener of changes) listener(items, area); },
      reply(response) { window.irisTest.pending(response); },
      root() { return document.getElementById('iris-extension-root').shadowRoot; }
    };
    window.chrome = {
      runtime: {
        getURL: (file) => `https://iris.test/${file}`,
        onMessage: { addListener: (fn) => listeners.push(fn) },
        sendMessage(message, callback) {
          if (message.type === 'IRIS_GET_TAB_ID') return callback({ tabId: 17 });
          window.irisTest.requests.push(message);
          if (message.type === 'IRIS_VERIFY_TEXT') window.irisTest.pending = callback;
          else callback({ ok: true });
        }
      },
      storage: {
        sync: {
          get(defaults, callback) { callback({ ...defaults, ...values }); },
          set(items, callback) {
            const delta = {};
            for (const [key, value] of Object.entries(items)) delta[key] = { oldValue: values[key], newValue: value };
            Object.assign(values, items);
            window.irisTest.change(delta);
            callback();
          }
        },
        session: {
          get(defaults, callback) { callback(defaults); },
          set(items, callback) {
            window.irisTest.savedPosition = items;
            window.irisTest.change(Object.fromEntries(Object.entries(items).map(([key, newValue]) => [key, { newValue }])), 'session');
            callback();
          }
        },
        onChanged: { addListener: (fn) => changes.push(fn) }
      }
    };
  }, settings);
  await page.addScriptTag({ path: path.join(extensionRoot, 'src/content.js') });
  await page.waitForFunction(() => !!irisTest.root().querySelector('link').sheet);
  if (!settings.quietMode) await page.locator('.iris-panel').waitFor({ state: 'visible' });
  return page;
}

async function remember(page, selectors) {
  await page.evaluate((selectors) => {
    window.kept = Object.fromEntries(selectors.map((selector) => [selector, irisTest.root().querySelector(selector)]));
  }, selectors);
}

async function unchanged(page) {
  assert.equal(await page.evaluate(() => Object.entries(window.kept).every(([selector, node]) =>
    node === irisTest.root().querySelector(selector))), true, 'Existing controls must retain their DOM nodes');
}

async function select(page, length) {
  await page.evaluate((length) => {
    const selection = getSelection();
    selection.removeAllRanges();
    if (length) {
      const range = document.createRange();
      range.setStart(document.getElementById('post').firstChild, 0);
      range.setEnd(document.getElementById('post').firstChild, length);
      selection.addRange(range);
    }
  }, length);
}

const payload = {
  claims: Array.from({ length: 3 }, (_, index) => ({
    claim_text: `Claim ${index + 1}: A factual statement for interface testing.`,
    verdict: index === 1 ? 'Not Found' : 'Partially Verified',
    message: 'Fixture evidence used to test the interface only.',
    evidence_sources: Array.from({ length: 5 }, (_, source) => ({
      url: `https://example.com/evidence/${index}/${source}`, title: `Evidence article ${source + 1}`,
      source: 'Test source', status: 'extracted'
    }))
  }))
};

test('selection updates in place, remains checkable, and clears with the highlight', async (t) => {
  const page = await fixture(t);
  await remember(page, ['.iris-panel', '.iris-panel__header', '#iris-image-input']);
  await select(page, 7);
  await page.waitForFunction(() => irisTest.root().querySelector('[data-role="detected-claim"]')?.textContent === 'A factu');
  await unchanged(page);
  await remember(page, ['.iris-panel', '[data-role="detected-claim"]', '[data-action="check-text"]']);
  await select(page, 15);
  await page.waitForFunction(() => irisTest.root().querySelector('[data-role="detected-claim"]')?.textContent === 'A factual claim');
  await unchanged(page);
  await select(page, 0);
  await page.locator('.iris-state--idle').waitFor();
  await select(page, 15);
  await page.locator('[data-action="check-text"]').click();
  assert.equal(await page.evaluate(() => irisTest.requests.at(-1).text), 'A factual claim');
  await page.locator('.iris-state--scanning').waitFor();
});

test('Settings preserve focused controls and FAQ preserves the underlying state', async (t) => {
  const page = await fixture(t);
  await page.locator('[data-action="open-settings"]').click();
  await remember(page, ['.iris-panel', '.iris-settings', '[data-action="toggle-theme"]', '[data-action="set-font"][data-value="xl"]']);
  await page.locator('[data-action="toggle-theme"]').focus();
  await page.keyboard.press('Space');
  await page.waitForFunction(() => irisTest.root().querySelector('.iris-panel').dataset.theme === 'dark');
  assert.equal(await page.evaluate(() => irisTest.root().activeElement === kept['[data-action="toggle-theme"]']), true);
  await page.locator('[data-action="set-font"][data-value="xl"]').click();
  await page.locator('[data-action="open-faq"]').click();
  await page.locator('.faq-modal').waitFor();
  await page.locator('.faq-modal [data-action="close-faq"]').click();
  await unchanged(page);
  assert.equal(await page.locator('.iris-panel').evaluate((panel) => panel.style.getPropertyValue('--iris-scale')), '1.3');
  await page.waitForFunction(() => irisTest.root().querySelector('.iris-panel').getAnimations().every((animation) => animation.playState !== 'running'));
  await page.locator('.iris-panel__brand').click();
  await page.evaluate(() => irisTest.change({ irisDebugMode: { newValue: true } }));
  assert.equal(await page.locator('.iris-panel').evaluate((panel) => panel.getAnimations().some((animation) => animation.playState === 'running')), false,
    'Clicking the header without dragging must not restart the panel entrance');
});

test('scanning and results retain the pill, navigation, sources, and scroll position', async (t) => {
  const page = await fixture(t);
  await page.evaluate(() => irisTest.message({ type: 'IRIS_CONTEXT_TEXT', text: 'A claim.' }));
  await page.locator('[data-action="collapse"]').click();
  await remember(page, ['.iris-panel', '.iris-pill', '.iris-pill__status']);
  await page.evaluate(() => irisTest.change({ irisDebugMode: { newValue: true } }));
  assert.equal(await page.locator('.iris-pill__status').getAttribute('class'), 'iris-pill__status is-scanning');
  await page.evaluate((payload) => irisTest.reply({ ok: true, payload }), payload);
  await page.waitForFunction(() => irisTest.root().querySelector('.iris-pill__status').classList.contains('is-ready'));
  await unchanged(page);
  await page.locator('.iris-pill').click();
  await remember(page, ['.iris-panel', '.claim-navigator', '[data-action="next-claim"]']);
  await page.locator('[data-action="next-claim"]').click();
  assert.match(await page.locator('.result-claim').textContent(), /Claim 2:/);
  await unchanged(page);
  await remember(page, ['.iris-panel', '.source-card']);
  await page.locator('.source-card').first().focus();
  await page.evaluate(() => {
    irisTest.root().querySelector('.iris-panel__body').scrollTop = 120;
    irisTest.change({ irisTheme: { newValue: 'dark' } });
  });
  assert.equal(await page.evaluate(() => irisTest.root().activeElement === kept['.source-card']), true);
  await page.locator('[data-action="open-faq"]').click();
  await page.locator('.faq-modal [data-action="close-faq"]').click();
  await unchanged(page);
  assert.equal(await page.locator('.iris-panel__body').evaluate((node) => node.scrollTop), 120);
  const screenshots = path.join(extensionRoot, 'build', 'interaction-tests');
  await mkdir(screenshots, { recursive: true });
  await page.locator('.iris-panel__body').evaluate((node) => { node.scrollTop = 0; });
  await page.screenshot({ path: path.join(screenshots, 'desktop-result.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => irisTest.change({ irisFontSize: { newValue: 'xl' } }));
  await page.screenshot({ path: path.join(screenshots, 'narrow-xl-result.png') });
  assert.equal(await page.locator('.iris-panel').evaluate((node) => node.scrollWidth <= node.clientWidth), true);
});

test('drag and storage changes keep the surface alive; image drop still reaches verification', async (t) => {
  const page = await fixture(t);
  await page.locator('[data-action="collapse"]').click();
  await remember(page, ['.iris-pill', '#iris-image-input']);
  const box = await page.locator('.iris-pill').boundingBox();
  await page.mouse.move(box.x + 20, box.y + 15);
  await page.mouse.down();
  await page.mouse.move(400, 250, { steps: 5 });
  await page.evaluate(() => irisTest.change({ irisTheme: { newValue: 'dark' } }));
  await page.mouse.move(350, 230, { steps: 3 });
  await page.mouse.up();
  await unchanged(page);
  assert.equal(await page.locator('.iris-pill').isVisible(), true, 'A drag must not expand the pill');
  assert.ok(await page.evaluate(() => irisTest.savedPosition?.iris_position_17));
  const position = await page.locator('.iris-floating-wrap').boundingBox();
  await page.evaluate(() => irisTest.change({ iris_position_999: { newValue: { x: 10, y: 10 } } }, 'session'));
  assert.deepEqual(await page.locator('.iris-floating-wrap').boundingBox(), position);
  await page.evaluate(() => {
    const transfer = new DataTransfer();
    transfer.setData('text/uri-list', 'https://example.com/photo.jpg');
    const pill = irisTest.root().querySelector('.iris-pill');
    const over = new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: transfer });
    pill.dispatchEvent(over);
    irisTest.preventedDrop = over.defaultPrevented;
    pill.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: transfer }));
  });
  assert.equal(await page.evaluate(() => irisTest.preventedDrop), true);
  await page.locator('.iris-state--scanning').waitFor();
  assert.equal(await page.evaluate(() => irisTest.requests.at(-1).source.url), 'https://example.com/photo.jpg');
  await page.evaluate(() => irisTest.message({ type: 'IRIS_CONTEXT_IMAGE_ERROR', error: 'Backend unavailable' }));
  await page.locator('.iris-state--error').waitFor();
});

test('Quiet Mode mounts for a triggered image check and removes the UI when closed', async (t) => {
  const page = await fixture(t, { quietMode: true });
  assert.equal(await page.locator('.iris-panel').count(), 0);
  assert.equal(await page.locator('.iris-pill').count(), 0);
  await page.evaluate(() => irisTest.message({ type: 'IRIS_CONTEXT_IMAGE_STARTED', imageUrl: 'https://example.com/photo.jpg' }));
  await page.locator('.iris-panel').waitFor({ state: 'visible' });
  assert.equal(await page.locator('.iris-pill').isVisible(), false);
  await page.evaluate((payload) => irisTest.message({ type: 'IRIS_CONTEXT_IMAGE_RESULT', payload }), payload);
  await page.locator('.quiet-close-result').click();
  assert.equal(await page.locator('.iris-panel').count(), 0);
  assert.equal(await page.locator('.iris-pill').count(), 0);
});

test('motion preferences change live, preserve scanning status, and retain static pressed feedback', async (t) => {
  const page = await fixture(t);
  await page.evaluate(() => irisTest.message({ type: 'IRIS_CONTEXT_TEXT', text: 'A claim.' }));
  await page.locator('[data-action="collapse"]').click();
  assert.equal(await page.locator('.iris-pill__status').evaluate((node) => getComputedStyle(node).animationName), 'scan-pulse');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  assert.equal(await page.locator('.iris-pill__status').evaluate((node) => getComputedStyle(node).animationName), 'none');
  assert.equal(await page.locator('.iris-pill__status').evaluate((node) => getComputedStyle(node).backgroundColor), 'rgb(139, 92, 246)');
  await page.locator('.iris-pill').click();
  assert.equal(await page.locator('.scan-dots span').first().evaluate((node) => getComputedStyle(node).animationName), 'none');
  await page.locator('[data-action="open-settings"]').click();
  const button = page.locator('[data-action="set-font"][data-value="xl"]');
  const box = await button.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  assert.equal(await button.evaluate((node) => getComputedStyle(node).transform), 'none');
  assert.equal(await button.evaluate((node) => getComputedStyle(node).filter), 'brightness(0.92)');
  await page.mouse.up();
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  const resizedBox = await button.boundingBox();
  await page.mouse.move(resizedBox.x + resizedBox.width / 2, resizedBox.y + resizedBox.height / 2);
  await page.mouse.down();
  await page.waitForFunction(() => getComputedStyle(irisTest.root().querySelector('[data-action="set-font"][data-value="xl"]')).transform.startsWith('matrix(0.97'));
  await page.mouse.up();
});
