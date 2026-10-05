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

async function fixture(t, settings = {}, local = {}) {
  const page = await browser.newPage({ viewport: { width: 1100, height: 850 } });
  t.after(() => page.close());
  await page.route('https://iris.test/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/page') {
      await route.fulfill({
        contentType: 'text/html',
        body:
          '<p id="post">A factual claim on the page with additional context.</p>' +
          '<div id="fb-caption" dir="auto"><span>The mayor announced that the new flood control project will be finished before the rainy season starts next year.</span></div>' +
          '<img id="post-image" src="/assets/iris-logo-mark.png" width="300" height="300" style="display:block;margin-top:150px">'
      });
    } else if (url.pathname === '/src/content.css') {
      await route.fulfill({ contentType: 'text/css', body: await readFile(path.join(extensionRoot, 'src/content.css')) });
    } else if (url.pathname === '/assets/iris-logo-mark.png') {
      await route.fulfill({ contentType: 'image/png', body: await readFile(path.join(extensionRoot, 'assets/iris-logo-mark.png')) });
    } else {
      await route.abort();
    }
  });
  await page.goto('https://iris.test/page');
  await page.evaluate(({ settings, local }) => {
    const listeners = [];
    const changes = [];
    const values = { ...settings };
    const localValues = { ...local };
    window.irisTest = {
      requests: [],
      message(message) { for (const listener of listeners) listener(message, {}, () => {}); },
      change(items, area = 'sync') { for (const listener of changes) listener(items, area); },
      seedHistory(entries) {
        localValues.irisHistory = entries;
        window.irisTest.change({ irisHistory: { newValue: entries } }, 'local');
      },
      reply(response) { window.irisTest.pending(response); },
      root() { return document.getElementById('iris-extension-root').shadowRoot; }
    };
    window.chrome = {
      runtime: {
        id: 'iris-test',
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
        local: {
          get(defaults, callback) { callback({ ...defaults, ...localValues }); }
        },
        onChanged: { addListener: (fn) => changes.push(fn) }
      }
    };
  }, { settings, local });
  // Mirrors the manifest's content_scripts order: i18n.js defines irisT /
  // IRIS_LANGUAGES, content.js consumes them.
  await page.addScriptTag({ path: path.join(extensionRoot, 'src/i18n.js') });
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

// Shape matches what background.js records into chrome.storage.local.
const historyFixture = [
  {
    checkedAt: Date.parse('2026-09-25T14:05:00'),
    inputType: 'text',
    preview: 'A factual claim on the page with additional context.',
    verdict: 'Partially Verified',
    fallback: '',
    rawJson: JSON.stringify(payload)
  },
  {
    checkedAt: Date.parse('2026-09-25T09:30:00'),
    inputType: 'image',
    preview: 'Headline lifted from a photo',
    verdict: 'Refuted',
    fallback: '',
    rawJson: '{not json'
  },
  // Post-merge shape: rawJson carries the merged payload (SightEngine block
  // included) and the flat fields recordCheckHistory writes ride alongside it.
  {
    checkedAt: Date.parse('2026-09-25T18:40:00'),
    inputType: 'image',
    preview: 'Photo from the field with an OCR excerpt',
    verdict: 'Partially Verified',
    fallback: 'Image selected for OCR.',
    rawJson: JSON.stringify({
      claims: [{
        claim_text: 'The photo shows last week\u2019s rally.',
        verdict: 'Partially Verified',
        message: 'Fixture evidence used to test the interface only.',
        evidence_sources: [{
          url: 'https://example.com/evidence/ai/0', title: 'Evidence article 1',
          source: 'Test source', status: 'extracted'
        }]
      }],
      image_authenticity_checked: true,
      ai_generated: { status: 'ok', confidence: 0.97, is_ai_generated: true, model: 'SightEngine' }
    }),
    imageAi: { confidence: 0.97, isAi: true },
    image: { name: 'field-photo.png', url: 'https://example.com/photos/field-photo.png' }
  }
];

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
  assert.equal(await page.locator('.source-card:visible').count(), 3, 'Only three evidence cards show while the list is folded');
  assert.match(await page.locator('.corroboration-row').first().textContent(), /5\s+evidence sources used/,
    'The evidence counter keeps the true total while the list is folded');
  assert.equal(await page.locator('[data-action="show-more-sources"]').textContent(), 'Show 2 more',
    'The reveal control counts the hidden cards');
  await page.locator('[data-action="show-more-sources"]').click();
  assert.equal(await page.locator('.source-card:visible').count(), 5, 'Show more reveals the folded cards in place');
  assert.equal(await page.locator('[data-action="show-more-sources"]').count(), 0,
    'The control retires once every card is visible');
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

test('image detection renders all three states, and renders nothing when the payload carries no detection', async (t) => {
  const page = await fixture(t, { quietMode: true });
  await page.evaluate(() => irisTest.message({ type: 'IRIS_CONTEXT_IMAGE_STARTED', imageUrl: 'https://example.com/photo.jpg' }));
  await page.locator('.iris-panel').waitFor({ state: 'visible' });

  const imageClaim = {
    claim_text: 'Claim from an image: a factual statement.',
    verdict: 'Partially Verified',
    message: 'Fixture evidence used to test the interface only.',
    evidence_sources: [{ url: 'https://example.com/evidence/1', title: 'Evidence article', source: 'Test source', status: 'extracted' }]
  };

  // Wait for the state we expect, not merely for a node: the badge persists across
  // re-renders, so "a badge exists" is already true before the new payload lands.
  const render = async (resultPayload, expectedClass) => {
    await page.evaluate((value) => irisTest.message({ type: 'IRIS_CONTEXT_IMAGE_RESULT', payload: value }), resultPayload);
    if (expectedClass) {
      await page.waitForFunction((cls) => {
        const node = irisTest.root().querySelector('.image-auth');
        return !!node && node.className.includes(cls);
      }, expectedClass);
    } else {
      await page.waitForFunction(() => !irisTest.root().querySelector('.image-auth') &&
        !!irisTest.root().querySelector('.verdict-card'));
    }
  };

  const readBadge = () => page.evaluate(() => {
    const node = irisTest.root().querySelector('.image-auth');
    if (!node) return null;
    // Rows inside the closed pill report no client rects — and checkVisibility()
    // is the signal that survives it — so this list doubles as proof that the
    // pill starts collapsed and that only result + confidence show.
    const COLLAPSED_VISIBLE =
      '.image-auth__feature, .image-auth__verdict, .image-auth__score';
    // The badge node IS the <details> in the pill design — not a wrapper of it.
    const details = node.tagName === 'DETAILS' ? node : node.querySelector('details');
    return {
      text: node.textContent,
      className: node.className,
      score: node.querySelector('.image-auth__score')?.textContent || null,
      // A second detector that fired. Read through the same visibility check as the
      // rest of the pill, so a flag that only existed in the markup would not pass.
      flags: [...node.querySelectorAll('.image-auth__flag')]
        .filter((el) => el.checkVisibility())
        .map((el) => el.textContent.trim()),
      caveat: node.querySelector('.image-auth__caveat')?.textContent || null,
      chevron: !!node.querySelector('.image-auth__chevron'),
      visible: [...node.querySelectorAll(COLLAPSED_VISIBLE)]
        .filter((el) => el.checkVisibility())
        .map((el) => el.textContent.trim()),
      detailsOpen: details ? details.open : null
    };
  });

  // Decision support, not a decision: the collapsed pill carries the feature
  // title, the bare verdict, and the detector's confidence — quiet enough that
  // the claim verdict below stays the headline. The independence line, splice
  // caveat, and detector notes open with the pill, so the reader, not IRIS,
  // decides when to read the qualifiers.
  const DISCLAIMER =
    'Note: Results are probabilistic and may be affected by compression, resizing, screenshots, or subsequent editing.';
  const SCOPE =
    'This describes the image file only. An AI-generated image can still illustrate a true event.';
  const assertFraming = async (badge, verdict) => {
    const feature = badge.text.indexOf('Image Authenticity Analysis');
    const result = badge.text.indexOf(verdict);
    const scope = badge.text.indexOf(SCOPE);
    const disclaimer = badge.text.indexOf(DISCLAIMER);
    assert.notEqual(feature, -1, 'the feature title is rendered');
    assert.notEqual(result, -1, 'the bare verdict is rendered');
    assert.notEqual(scope, -1, 'the independence line is rendered');
    assert.notEqual(disclaimer, -1, 'the disclaimer is rendered');
    assert.equal(badge.text.indexOf('AI Generation Analysis'), -1, 'the redundant branch label is gone');
    assert.equal(badge.text.indexOf('Manipulation: Not assessed'), -1,
      'no manipulation claim appears: this pipeline has no manipulation check');
    assert.equal(badge.text.indexOf('Two'), -1,
      'no count of detectors is claimed: the copy names only what each one saw');
    assert.ok(feature < result, 'the feature title precedes the verdict');
    assert.ok(result < scope, 'the verdict precedes the independence line');
    assert.ok(scope < disclaimer, 'the independence line precedes the probabilistic caveat');
    assert.equal(badge.detailsOpen, false, 'the pill starts collapsed');
    assert.equal(badge.chevron, true, 'the collapsed pill carries its open-hint');
    assert.equal(await page.locator('.image-auth__scope').isVisible(), false,
      'collapsed: the independence line waits behind the pill');
    assert.deepEqual(badge.visible, [
      'Image Authenticity Analysis',
      verdict,
      ...(badge.score ? [badge.score] : [])
    ], 'collapsed, only the heading, verdict, and AI probability show');

    // The pill is the control: it opens and closes in place in every tone,
    // with no re-render.
    const control = page.locator('.image-auth__pill');
    await control.click();
    assert.equal(await page.locator('.image-auth__note').isVisible(), true, 'the pill reveals the per-state note');
    assert.equal(await page.locator('.image-auth__disclaimer').isVisible(), true, 'the pill reveals the probabilistic caveat');
    assert.equal(await page.locator('.image-auth__scope').isVisible(), true, 'the independence line opens with the pill');
    if (badge.caveat) {
      assert.equal(await page.locator('.image-auth__caveat').isVisible(), true,
        'the splice caveat opens with the pill');
    }
    await control.click();
    assert.equal(await page.locator('.image-auth__note').isVisible(), false, 'the pill closes again');
  };

  // Flagged: publishes the detector's AI probability with the verdict.
  await render({
    claims: [imageClaim],
    image_authenticity_checked: true,
    ai_generated: { status: 'ok', is_ai_generated: true, confidence: 0.529 }
  }, 'is-flagged');
  let badge = await readBadge();
  assert.match(badge.className, /is-flagged/);
  assert.match(badge.text, /Potentially AI-generated/);
  assert.match(badge.text, /SightEngine's AI-image detector flagged this image\./);
  assert.equal(badge.score, 'AI probability: 53%');
  await assertFraming(badge, 'Potentially AI-generated');

  // Clear: the verdict states only what the detector observed (never a
  // conclusion like "real"), the detector's own AI probability must appear in
  // the collapsed pill, and the splice caveat must exist one click away.
  await render({
    claims: [imageClaim],
    image_authenticity_checked: true,
    ai_generated: { status: 'ok', is_ai_generated: false, confidence: 0.04 }
  }, 'is-clear');
  badge = await readBadge();
  assert.match(badge.className, /is-clear/);
  assert.match(badge.text, /No AI generation detected/);
  assert.match(badge.text, /could still be spliced or human-edited/);
  assert.ok(badge.caveat, 'the splice caveat element exists');
  assert.equal(badge.score, 'AI probability: 4%',
    'a clear result publishes the probability the detector actually returned');
  await assertFraming(badge, 'No AI generation detected');

  // Degraded: a check that did not run is not a check that passed.
  await render({
    claims: [imageClaim],
    image_authenticity_checked: false,
    ai_generated: { status: 'model_unavailable', is_ai_generated: false }
  }, 'is-unknown');
  badge = await readBadge();
  assert.match(badge.className, /is-unknown/);
  assert.match(badge.text, /IRIS could not run image detection on this image\./);
  assert.equal(badge.score, null, 'An unassessed check must never publish a probability figure');
  await assertFraming(badge, 'Not assessed');

  // A second detector that FIRED rides beside genai's verdict as its own observation,
  // and only the detector that fired is shown: a quiet one says nothing, because with
  // image type out of scope "clear" and "never looked" are indistinguishable.
  await render({
    claims: [imageClaim],
    image_authenticity_checked: true,
    ai_generated: { status: 'ok', is_ai_generated: true, confidence: 0.529 },
    deepfake: { status: 'ok', is_suspicious: true, confidence: 0.82, model: 'deepfake' },
    embedded_text: { status: 'ok', is_suspicious: false, confidence: 0.01, model: 'text' }
  }, 'is-flagged');
  badge = await readBadge();
  assert.deepEqual(badge.flags, ['Face swap: flagged (82%)'],
    'only the detector that fired renders, and it keeps its own score');
  assert.equal(badge.score, 'AI probability: 53%', "genai's figure stays independent of the flag");
  await assertFraming(badge, 'Potentially AI-generated');

  // A detector firing while genai stays quiet must flip the card to flagged: a green
  // "No AI generation detected" beside a live face-swap flag would contradict itself.
  // The flag becomes the verdict, and genai's own reading is stated underneath it.
  await render({
    claims: [imageClaim],
    image_authenticity_checked: true,
    ai_generated: { status: 'ok', is_ai_generated: false, confidence: 0.04 },
    deepfake: { status: 'ok', is_suspicious: true, confidence: 0.82, model: 'deepfake' }
  }, 'is-flagged');
  badge = await readBadge();
  assert.match(badge.className, /is-flagged/, 'a fired detector outranks the clear AI verdict');
  assert.deepEqual(badge.flags, [], 'the flag already IS the verdict, so it is not repeated');
  assert.equal(badge.score, 'AI probability: 4%');
  await assertFraming(badge, 'Face swap: flagged (82%)');
  assert.match(badge.text, /SightEngine did not flag this image\. That is not proof it is authentic\./,
    "genai's quiet reading is still stated rather than hidden");

  // Added text alone must NOT repaint the card. It fires on nearly every news image
  // (a chyron, a watermark, an overlay are all "text added after the shot"), so
  // colouring it would turn routine noise into a standing alarm — and a green card
  // carrying a flag would be a contradiction of its own. The card keeps genai's
  // honest verdict; the text detector gets its own line beside it.
  await render({
    claims: [imageClaim],
    image_authenticity_checked: true,
    ai_generated: { status: 'ok', is_ai_generated: false, confidence: 0.04 },
    embedded_text: { status: 'ok', is_suspicious: true, confidence: 0.91, model: 'text' }
  }, 'is-clear');
  badge = await readBadge();
  assert.match(badge.className, /is-clear/,
    'added text never repaints the card: colour belongs to genai and deepfake');
  assert.deepEqual(badge.flags, ['Text added after capture: flagged (91%)'],
    'the text detector still speaks — it just does so as its own line');
  assert.match(badge.text, /No AI generation detected/,
    'the card states what genai actually saw');
  await assertFraming(badge, 'No AI generation detected');

  // Both fired while genai stayed quiet: deepfake carries the stronger claim so it
  // takes the headline, red wins because a face swap IS involved, and the text flag
  // rides along as its own line instead of being swallowed or repeated.
  await render({
    claims: [imageClaim],
    image_authenticity_checked: true,
    ai_generated: { status: 'ok', is_ai_generated: false, confidence: 0.04 },
    deepfake: { status: 'ok', is_suspicious: true, confidence: 0.82, model: 'deepfake' },
    embedded_text: { status: 'ok', is_suspicious: true, confidence: 0.91, model: 'text' }
  }, 'is-flagged');
  badge = await readBadge();
  assert.match(badge.className, /is-flagged/, 'a face swap keeps the card red');
  assert.deepEqual(badge.flags, ['Text added after capture: flagged (91%)'],
    'the headline flag is not repeated as a second line');
  await assertFraming(badge, 'Face swap: flagged (82%)');

  // A detector that did not fire — or whose check failed — contributes nothing: it
  // must never grow into a "checked and clear" claim the payload never made.
  await render({
    claims: [imageClaim],
    image_authenticity_checked: true,
    ai_generated: { status: 'ok', is_ai_generated: false, confidence: 0.04 },
    deepfake: { status: 'ok', is_suspicious: false, confidence: 0.01 },
    embedded_text: { status: 'error', error: 'quota' }
  }, 'is-clear');
  badge = await readBadge();
  assert.deepEqual(badge.flags, [], 'a quiet or failed detector is silent, never a "clear" claim');
  await assertFraming(badge, 'No AI generation detected');

  // No detection keys at all: the badge must not render rather than default to a state.
  await render({ claims: [imageClaim] });
  assert.equal(await page.locator('.image-auth').count(), 0);
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

test('Recent checks load collapsed, expand in place, and leave when history clears', async (t) => {
  const page = await fixture(t, {}, { irisHistory: historyFixture });
  await page.locator('.recent-checks').waitFor();
  assert.equal(await page.locator('.recent-checks__count').textContent(), '3');
  assert.equal(await page.locator('.recent-check__summary').count(), 0, 'The section starts collapsed');

  const header = page.locator('[data-action="toggle-recent-checks"]');
  await header.click();
  assert.equal(await header.getAttribute('aria-expanded'), 'true');
  assert.equal(await page.locator('.recent-check__summary').count(), 3, 'Rows appear when the section opens');
  assert.equal(await page.locator('[data-action="open-history"]').count(), 1, 'See all history stays reachable');

  const firstSummary = page.locator('.recent-check__summary').first();
  assert.match(await firstSummary.textContent(), /Partially Verified/);
  assert.match(await firstSummary.textContent(), /Text/);

  await firstSummary.click();
  const firstDetail = page.locator('.recent-check__detail').first();
  await firstDetail.waitFor();
  assert.match(await firstDetail.textContent(), /5 evidence sources/);
  assert.match(await firstDetail.textContent(), /Fixture evidence used to test the interface only\./);
  assert.equal(await firstDetail.locator('.recent-check__source:visible').count(), 9,
    'Each of the three claims shows three article links');
  assert.equal(await firstDetail.locator('.recent-check__source--collapsed').count(), 6,
    'The remaining links wait behind Show N more');
  assert.equal(await firstDetail.locator('.recent-check__source-more').count(), 3);
  assert.equal(await firstDetail.locator('.recent-check__source-more').first().textContent(), 'Show 2 more');
  assert.equal(
    await firstDetail.locator('.recent-check__source').first().getAttribute('data-url'),
    'https://example.com/evidence/0/0'
  );
  await firstDetail.locator('.recent-check__source-more').first().click();
  assert.equal(await firstDetail.locator('.recent-check__source:visible').count(), 11,
    'Show more reveals the hidden links in place');
  assert.equal(await firstDetail.locator('.recent-check__source-more').count(), 2);

  await page.locator('[data-action="toggle-recent-check"]').nth(1).click();
  const secondDetail = page.locator('.recent-check__detail').nth(1);
  await secondDetail.waitFor();
  assert.match(await secondDetail.textContent(), /No claim details were stored/);

  // The stored SightEngine score rides as a flat field: row pill, image source in
  // the meta, and the full authenticity badge in the detail — no payload parse
  // needed for the row, and text/legacy entries stay pill-free.
  const thirdSummary = page.locator('.recent-check__summary').nth(2);
  assert.match(await thirdSummary.textContent(), /AI probability: 97%/,
    'The stored SightEngine score shows as a row pill');
  assert.match(await thirdSummary.textContent(), /Image \u00b7 field-photo.png/,
    'The stored image source rides in the row meta');
  assert.equal(await page.locator('.recent-check__ai').count(), 1,
    'Only image entries with a stored score show a pill');
  await thirdSummary.click();
  const thirdDetail = page.locator('.recent-check__detail').nth(2);
  await thirdDetail.waitFor();
  assert.equal(await thirdDetail.locator('.image-auth').count(), 1,
    'The stored verdict opens the full authenticity badge');
  assert.match(await thirdDetail.locator('.image-auth__verdict').textContent(), /Potentially AI-generated/);
  assert.match(await thirdDetail.locator('.image-auth__score').textContent(), /97/);

  await page.evaluate(() => irisTest.change({ irisHistory: { newValue: undefined } }, 'local'));
  await page.locator('.recent-checks').waitFor({ state: 'detached' });
});

test('Hover to check arms over a Facebook-style caption, survives transit, and opens detected', async (t) => {
  const page = await fixture(t, { hoverCheck: true });
  const pillVisible = () => page.evaluate(() =>
    document.getElementById('iris-extension-root')?.shadowRoot
      ?.querySelector('.iris-hover-pill')?.classList.contains('is-visible'));

  // Word gate: the 9-word fixture paragraph never arms.
  const post = await page.locator('#post').boundingBox();
  await page.mouse.move(post.x + post.width / 2, post.y + post.height / 2);
  await page.waitForTimeout(900);
  assert.equal(await pillVisible(), false, 'text under the 15-word threshold stays un-armed');

  // Facebook renders captions as <div dir="auto"><span>…</span></div> with no
  // <p> anywhere — the caption must arm anyway.
  const caption = await page.locator('#fb-caption').boundingBox();
  await page.mouse.move(caption.x + caption.width / 2, caption.y + caption.height / 2);
  const pill = page.locator('.iris-hover-pill.is-visible');
  await pill.waitFor({ timeout: 3000 });

  // Transit: pointer just below the caption (whitespace, no eligible block)
  // must not kill the pill before the click lands.
  await page.mouse.move(caption.x + caption.width / 2, caption.y + caption.height + 40);
  await page.waitForTimeout(300);
  assert.equal(await pillVisible(), true, 'the pill survives whitespace inside its region');

  await pill.click();
  const claim = page.locator('[data-role="detected-claim"]');
  await claim.waitFor();
  assert.match(await claim.textContent(), /The mayor announced/,
    'the caption text, not a swallowed container, becomes the claim');
});

test('Hover to check over a post image requests image verification', async (t) => {
  const page = await fixture(t, { hoverCheck: true });
  const image = await page.locator('#post-image').boundingBox();
  await page.mouse.move(image.x + image.width / 2, image.y + image.height / 2);
  const pill = page.locator('.iris-hover-pill.is-visible');
  await pill.waitFor({ timeout: 3000 });
  assert.match(await pill.textContent(), /Check this image with IRIS/,
    'the pill announces the image variant');

  await pill.click();
  await page.waitForFunction(() =>
    irisTest.requests.some((message) => message.type === 'IRIS_VERIFY_IMAGE_SOURCE'));
  assert.equal(await page.locator('.iris-panel').getAttribute('aria-busy'), 'true',
    'the image check takes the panel into its scanning state');
});

test('Quiet Mode hands Hover to check back exactly what its nudge took', async (t) => {
  const page = await fixture(t, { hoverCheck: true });
  await page.locator('[data-action="open-settings"]').click();
  const quietSwitch = page.locator('[data-action="toggle-quiet-mode"]');
  const hoverSwitch = page.locator('[data-action="toggle-hover-check"]');
  assert.equal(await hoverSwitch.getAttribute('aria-checked'), 'true');

  // Quiet ON suppresses hover (the nudge).
  await quietSwitch.click();
  assert.equal(await hoverSwitch.getAttribute('aria-checked'), 'false',
    'turning Quiet on switches Hover to check off');

  // Quiet OFF hands it back.
  await quietSwitch.click();
  assert.equal(await hoverSwitch.getAttribute('aria-checked'), 'true',
    'turning Quiet off restores the hover its own nudge took');

  // A hand-made choice made while Quiet was on wins over the restore.
  await quietSwitch.click();   // quiet on → nudge suppresses and records
  await hoverSwitch.click();   // reader turns hover back on by hand
  await hoverSwitch.click();   // reader turns hover off by hand
  assert.equal(await hoverSwitch.getAttribute('aria-checked'), 'false');
  await quietSwitch.click();   // quiet off
  assert.equal(await hoverSwitch.getAttribute('aria-checked'), 'false',
    'only the nudge restores — a hand-made choice survives quiet off');
});

test('A settled scroll re-arms the pill under a parked cursor', async (t) => {
  const page = await fixture(t, { hoverCheck: true });
  const pillVisible = () => page.evaluate(() =>
    document.getElementById('iris-extension-root')?.shadowRoot
      ?.querySelector('.iris-hover-pill')?.classList.contains('is-visible'));

  const caption = await page.locator('#fb-caption').boundingBox();
  await page.mouse.move(caption.x + caption.width / 2, caption.y + caption.height / 2);
  const pill = page.locator('.iris-hover-pill.is-visible');
  await pill.waitFor({ timeout: 3000 });

  // Any scroll clears the pill — but a wheel/trackpad scroll leaves the cursor
  // parked with no mousemove to re-arm on, so the settle probe must bring it
  // back by itself once the page goes quiet.
  await page.evaluate(() => window.dispatchEvent(new Event('scroll')));
  await page.waitForTimeout(50);
  assert.equal(await pillVisible(), false, 'the scroll clears the pill immediately');

  await page.waitForTimeout(150 + 400 + 400);
  assert.equal(await pillVisible(), true,
    'after the page settles the pill re-arms under the parked cursor');
});

test('An orphaned content script tears itself down after an extension reload', async (t) => {
  const page = await fixture(t);
  assert.equal(await page.locator('#iris-extension-root').count(), 1,
    'the panel is mounted while the extension context is alive');

  // Reloading the extension invalidates this script's runtime: chrome.* calls
  // start failing but the DOM and page listeners stay — a zombie panel. The
  // watchdog must remove it and clear the guard so the next fallback
  // injection can re-mount a fresh, working panel.
  await page.evaluate(() => { chrome.runtime.id = undefined; });
  await page.waitForTimeout(1400);

  assert.equal(await page.locator('#iris-extension-root').count(), 0,
    'the zombie panel is removed');
  assert.equal(await page.evaluate(() => window.__IRIS_EXTENSION_CONTENT_LOADED__), false,
    'the guard clears so a re-injection can take over');
});

test('A dragged photo page link falls through to the real image in the HTML fragment', async (t) => {
  const page = await fixture(t);
  await page.locator('[data-action="collapse"]').click();
  await page.evaluate(() => {
    // Facebook's shape: uri-list carries the photo PAGE link, the image itself
    // only appears in the HTML fragment. Right-click would have given srcUrl
    // of the image — the drop path must not check the page URL instead.
    const transfer = new DataTransfer();
    transfer.setData('text/uri-list', 'https://www.facebook.com/photo/?fbid=123');
    transfer.setData('text/html', '<img src="https://scontent.example.com/v/t1/photo.jpg">');
    const pill = irisTest.root().querySelector('.iris-pill');
    pill.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: transfer }));
    pill.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: transfer }));
  });
  await page.locator('.iris-state--scanning').waitFor();
  assert.equal(await page.evaluate(() => irisTest.requests.at(-1).source.url),
    'https://scontent.example.com/v/t1/photo.jpg',
    'the page link is skipped and the real image URL is checked');
});

test('Returning to the window re-arms the pill without another mouse move', async (t) => {
  const page = await fixture(t, { hoverCheck: true });
  const caption = await page.locator('#fb-caption').boundingBox();
  await page.mouse.move(caption.x + caption.width / 2, caption.y + caption.height / 2);
  await page.locator('.iris-hover-pill.is-visible').waitFor({ timeout: 3000 });

  // Leaving the window (alt-tab, lock, another app) stops the hover — and must
  // also cancel the in-flight animation frame, or the raf gate would wedge every
  // future mousemove until a page reload.
  await page.evaluate(() => window.dispatchEvent(new Event('blur')));
  await page.waitForTimeout(50);
  assert.equal(await page.locator('.iris-hover-pill.is-visible').count(), 0,
    'blur dismisses the pill');

  // Coming back with the cursor physically unmoved fires no mousemove at all:
  // focus must re-probe the last known position on its own.
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await page.locator('.iris-hover-pill.is-visible').waitFor({ timeout: 3000 });
});

test('Clicking the hover pill re-opens a collapsed panel', async (t) => {
  const page = await fixture(t, { hoverCheck: true });

  // Close the panel first (collapse → the small status pill). Every other
  // check entry point re-opens it; the hover pill's text branch used to skip
  // that reset, flipping status to "detected" while the panel stayed hidden.
  await page.locator('[data-action="collapse"]').click();
  await page.locator('.iris-pill').waitFor();

  const caption = await page.locator('#fb-caption').boundingBox();
  await page.mouse.move(caption.x + caption.width / 2, caption.y + caption.height / 2);
  const pill = page.locator('.iris-hover-pill.is-visible');
  await pill.waitFor({ timeout: 3000 });
  await pill.click();

  const claim = page.locator('[data-role="detected-claim"]');
  await claim.waitFor();
  assert.match(await claim.textContent(), /The mayor announced/);
  assert.equal(await page.locator('.iris-panel').isVisible(), true,
    'the detected state is actually visible, not stuck behind a stale collapse');
});

test('Language selection repaints the panel and follows a change from elsewhere', async (t) => {
  const page = await fixture(t);
  await page.locator('[data-action="open-settings"]').click();
  const select = page.locator('select[data-setting="irisUiLanguage"]');
  await select.waitFor();

  // Picking a language swaps the open screen's copy in place — and the body
  // swap must survive while the select keeps focus (the partial-update
  // settings branch would otherwise never repaint the labels).
  await select.focus();
  await select.selectOption('ja');
  assert.equal(await page.locator('.iris-settings h2').textContent(), '設定');
  assert.equal(await select.inputValue(), 'ja');
  assert.equal(await page.locator('.iris-settings .setting-row span').first().textContent(), 'IRISパネルのみ');
  assert.equal(await page.locator('[data-role="header-close"]').getAttribute('aria-label'), 'IRISパネルを折りたたむ',
    'aria labels outside the body swap follow the language too');
  assert.equal(await page.evaluate(() =>
    irisTest.root().activeElement?.dataset?.setting), 'irisUiLanguage',
    'focus stays on the select the reader just used');

  // The choice rides sync storage, so another surface flipping it follows live.
  await page.evaluate(() => irisTest.change({ irisUiLanguage: { newValue: 'tl' } }, 'sync'));
  assert.equal(await page.locator('.iris-settings h2').textContent(), 'Mga Setting');

  // An unknown stored value falls back to English instead of blanking copy.
  await page.evaluate(() => irisTest.change({ irisUiLanguage: { newValue: 'xx' } }, 'sync'));
  assert.equal(await page.locator('.iris-settings h2').textContent(), 'Settings');
});

test('An open FAQ overlay repaints on a language change and keeps focus inside', async (t) => {
  const page = await fixture(t);
  await page.locator('[data-action="open-faq"]').click();
  await page.locator('.faq-modal').waitFor();
  assert.equal(await page.locator('.faq-modal article h3').count(), 4);
  assert.equal(await page.locator('.faq-modal article h3').first().textContent(), 'What does IRIS check?');

  // Park focus on the overlay's close button: the swap must hand it back rather
  // than dropping the keyboard user to the page root.
  await page.evaluate(() => irisTest.root().querySelector('.faq-modal button[data-action="close-faq"]').focus());

  await page.evaluate(() => irisTest.change({ irisUiLanguage: { newValue: 'ja' } }, 'sync'));
  await page.waitForFunction(() => irisTest.root().querySelector('.faq-modal article h3')?.textContent === 'IRISは何を確認しますか？');
  assert.equal(await page.evaluate(() => {
    const overlay = irisTest.root().querySelector('.faq-overlay');
    return Boolean(overlay) && overlay.contains(irisTest.root().activeElement);
  }), true, 'focus stays inside the reopened overlay');
  assert.equal(await page.locator('.faq-modal button[data-action="close-faq"]').getAttribute('aria-label'), 'FAQを閉じる',
    'the close button announces in the new language too');

  // Arabic flips both surfaces to RTL while the overlay rides along.
  await page.evaluate(() => irisTest.change({ irisUiLanguage: { newValue: 'ar' } }, 'sync'));
  await page.waitForFunction(() => irisTest.root().querySelector('.faq-modal article h3')?.textContent === 'ما الذي يتحقق منه IRIS؟');
  assert.equal(await page.evaluate(() => irisTest.root().querySelector('.iris-panel').dir), 'rtl');
  assert.equal(await page.evaluate(() => irisTest.root().querySelector('.iris-pill').dir), 'rtl');

  await page.locator('.faq-modal button[data-action="close-faq"]').click();
  await page.locator('.faq-modal').waitFor({ state: 'detached' });
});

test('Verdict badges follow the language while the stored verdict stays raw', async (t) => {
  const page = await fixture(t, {}, { irisHistory: historyFixture });
  await page.locator('.recent-checks').waitFor();
  await page.locator('[data-action="toggle-recent-checks"]').click();
  await page.locator('.recent-check__badge').first().waitFor();
  const badge = page.locator('.recent-check__badge').first();
  assert.equal(await badge.textContent(), 'Partially Verified');

  await page.evaluate(() => irisTest.change({ irisUiLanguage: { newValue: 'tl' } }, 'sync'));
  await page.waitForFunction(() => irisTest.root().querySelector('.recent-check__badge')?.textContent === 'Bahagyang Napatunayan');
  assert.match(await badge.getAttribute('class'), /is-partial/,
    'the tone still keys off the raw English verdict after translation');

  // An unknown language falls back to English instead of blanking the badge.
  await page.evaluate(() => irisTest.change({ irisUiLanguage: { newValue: 'xx' } }, 'sync'));
  assert.equal(await badge.textContent(), 'Partially Verified');
});

test('Quiet idle raises a drop pad for image drags only, and its drop runs the real check', async (t) => {
  const page = await fixture(t, { quietMode: true });
  assert.equal(await page.locator('.iris-panel').count(), 0, 'quiet idle starts unmounted');

  // A text-selection drag carries no uri-list: it must not raise the pad.
  await page.evaluate(() => {
    const transfer = new DataTransfer();
    transfer.setData('text/plain', 'selected words');
    transfer.setData('text/html', '<b>selected words</b>');
    document.body.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer: transfer }));
  });
  assert.equal(await page.locator('.iris-quiet-drop').count(), 0, 'text drags get no pad');

  // An image-shaped drag (uri-list + html, Facebook style) mounts the pad.
  await page.evaluate(() => {
    const transfer = new DataTransfer();
    transfer.setData('text/uri-list', 'https://www.facebook.com/photo/?fbid=9');
    transfer.setData('text/html', '<img src="https://scontent.example.com/v/t1/pad.jpg">');
    document.body.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer: transfer }));
  });
  const pad = page.locator('.iris-quiet-drop');
  await pad.waitFor();
  assert.equal(await pad.getAttribute('aria-label'), 'Drop an image to check it');

  // Ending the drag without a drop takes the pad down with it.
  await page.evaluate(() => {
    document.body.dispatchEvent(new DragEvent('dragend', { bubbles: true, cancelable: true }));
  });
  assert.equal(await page.locator('.iris-quiet-drop').count(), 0, 'dragend cleans the pad up');

  // A second drag lands on the pad; the drop rides the normal root handlers
  // and reaches the same verification path a panel drop uses.
  await page.evaluate(() => {
    const transfer = new DataTransfer();
    transfer.setData('text/uri-list', 'https://www.facebook.com/photo/?fbid=9');
    transfer.setData('text/html', '<img src="https://scontent.example.com/v/t1/pad.jpg">');
    document.body.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer: transfer }));
    const padNode = irisTest.root().querySelector('.iris-quiet-drop');
    padNode.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: transfer }));
    padNode.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: transfer }));
  });
  await page.locator('.iris-state--scanning').waitFor();
  assert.equal(await page.evaluate(() => irisTest.requests.at(-1).source.url),
    'https://scontent.example.com/v/t1/pad.jpg',
    'the pad checks the real image URL, not the photo page link');
  assert.equal(await page.locator('.iris-quiet-drop').count(), 0,
    'the pad is gone once the mounted surface owns the view');
});

test('Opening the panel from a pill parked at the edge keeps it fully on screen', async (t) => {
  const page = await fixture(t);
  const vp = page.viewportSize();
  await page.locator('[data-action="collapse"]').click();
  await page.waitForTimeout(50);

  // Park the pill as far right as the pill's own drag clamp allows
  // (innerWidth - 120 - 8): the pill fits, the 310px panel it opens does not.
  const pillBox = await page.locator('.iris-pill').boundingBox();
  await page.mouse.move(pillBox.x + 20, pillBox.y + 15);
  await page.mouse.down();
  await page.mouse.move(vp.width - 2, pillBox.y, { steps: 5 });
  await page.mouse.up();
  await page.waitForTimeout(50);
  const wrapperBox = await page.locator('.iris-floating-wrap').boundingBox();
  assert.ok(wrapperBox.x + wrapperBox.width > vp.width - 200,
    'the pill really is parked at the right edge before expanding');

  await page.locator('.iris-pill').click();
  await page.locator('.iris-panel').waitFor({ state: 'visible' });
  let panelBox = await page.locator('.iris-panel').boundingBox();
  assert.ok(panelBox.x + panelBox.width <= vp.width - 7,
    `the panel overflows the right edge by ${Math.round(panelBox.x + panelBox.width - vp.width)}px`);

  // Same story on the vertical axis: a pill parked low opens a taller panel.
  await page.locator('[data-action="collapse"]').click();
  await page.waitForTimeout(50);
  const lowBox = await page.locator('.iris-pill').boundingBox();
  await page.mouse.move(lowBox.x + 20, lowBox.y + 15);
  await page.mouse.down();
  await page.mouse.move(lowBox.x + 20, vp.height - 2, { steps: 5 });
  await page.mouse.up();
  await page.waitForTimeout(50);

  await page.locator('.iris-pill').click();
  await page.locator('.iris-panel').waitFor({ state: 'visible' });
  panelBox = await page.locator('.iris-panel').boundingBox();
  assert.ok(panelBox.y + panelBox.height <= vp.height - 7,
    `the panel overflows the bottom edge by ${Math.round(panelBox.y + panelBox.height - vp.height)}px`);
});

test('A quiet drag raises a floating bubble, not a panel-sized box', async (t) => {
  const page = await fixture(t, { quietMode: true });
  await page.evaluate(() => {
    const transfer = new DataTransfer();
    transfer.setData('text/uri-list', 'https://example.com/photo.jpg');
    document.body.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer: transfer }));
  });
  const box = await page.locator('.iris-quiet-drop').boundingBox();
  assert.ok(box.width <= 100 && box.height <= 100,
    `the drop marker is a bubble, not a card — got ${Math.round(box.width)}x${Math.round(box.height)}`);
  assert.ok(Math.abs(box.width - box.height) <= 1,
    'a bubble is round — the two axes must match');
  // The instruction still reaches assistive tech and the native tooltip even
  // though the caption no longer renders.
  const pad = page.locator('.iris-quiet-drop');
  assert.equal(await pad.getAttribute('aria-label'), 'Drop an image to check it');
  assert.equal(await pad.getAttribute('title'), 'Drop an image to check it');
});

test('A quiet drag that never lands on the bubble still takes the bubble down', async (t) => {
  // Three ways a drag ends. dragend only fires when the dragged source lives
  // in this document, so a photo dragged in from another tab, window or the
  // desktop ends on one of the other two — and used to strand the bubble.
  const endings = {
    'dragend (source in this page)': "document.body.dispatchEvent(new DragEvent('dragend', { bubbles: true, cancelable: true }))",
    'drop elsewhere on the page': "document.body.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true }))",
    'dragleave (left the window)': "document.body.dispatchEvent(new DragEvent('dragleave', { bubbles: true, cancelable: true, relatedTarget: null }))",
  };

  for (const [label, ending] of Object.entries(endings)) {
    const page = await fixture(t, { quietMode: true });
    await page.evaluate(() => {
      const transfer = new DataTransfer();
      transfer.setData('text/uri-list', 'https://example.com/photo.jpg');
      document.body.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer: transfer }));
    });
    await page.locator('.iris-quiet-drop').waitFor();
    await page.evaluate((body) => { new Function(body)(); }, ending);
    assert.equal(await page.locator('.iris-quiet-drop').count(), 0,
      `${label} must not strand the bubble`);
    await page.close();
  }
});
