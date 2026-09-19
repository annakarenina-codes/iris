const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = readFileSync(path.join(__dirname, '../src/background.js'), 'utf8');

function fixture(fetch) {
  const timers = [];
  const listener = { addListener() {} };
  const context = vm.createContext({
    AbortController, fetch,
    setTimeout(fn, ms) { timers.push({ fn, ms }); return timers.length; },
    clearTimeout() {},
    chrome: {
      runtime: { onInstalled: listener, onStartup: listener, onMessage: listener },
      contextMenus: { onClicked: listener }
    }
  });
  vm.runInContext(source, context);
  return { context, timers };
}

test('text and image requests wait without scheduling a deadline', async () => {
  for (const endpoint of ['/verify', '/verify-image']) {
    let complete;
    let signal;
    const { context, timers } = fixture((_url, options) => {
      signal = options.signal;
      return new Promise(resolve => { complete = resolve; });
    });
    const pending = vm.runInContext(`postJson('http://localhost:5000${endpoint}', {})`, context);
    assert.equal(timers.length, 0);
    assert.equal(signal.aborted, false);
    complete({ ok: true, status: 200, text: async () => '{"verdict":"Not Found"}' });
    const result = await pending;
    assert.equal(result.payload.verdict, 'Not Found');
  }
});

test('network and backend errors are still returned', async () => {
  const failure = new Error('Connection lost');
  const network = fixture(async () => { throw failure; });
  await assert.rejects(vm.runInContext("postJson('http://localhost:5000/verify', {})", network.context), /Connection lost/);
  const backend = fixture(async () => ({ ok: false, status: 503, text: async () => '{"message":"Review failed"}' }));
  const result = await vm.runInContext("postJson('http://localhost:5000/verify', {})", backend.context);
  assert.equal(result.ok, false);
  assert.equal(result.status, 503);
});
