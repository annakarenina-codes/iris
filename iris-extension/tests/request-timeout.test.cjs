const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = readFileSync(path.join(__dirname, '../src/background.js'), 'utf8');

const DEADLINE_MS = 180000;

function fixture(fetch, { token = null } = {}) {
  const deadlines = [];
  const calls = [];
  const listener = { addListener() {} };
  const context = vm.createContext({
    AbortController,
    queueMicrotask,
    fetch(url, options) {
      calls.push({ url, options });
      return fetch(url, options);
    },
    // The request deadline is recorded so a test can inspect it. The much shorter retry pause
    // is let through at once, so no test has to wait 1.5 real seconds to see a second attempt.
    setTimeout(fn, ms) {
      if (ms >= 10000) {
        deadlines.push(ms);
        return deadlines.length;
      }
      queueMicrotask(fn);
      return 0;
    },
    clearTimeout() {},
    chrome: {
      runtime: { onInstalled: listener, onStartup: listener, onMessage: listener },
      contextMenus: { onClicked: listener }
    }
  });

  const code = token === null
    ? source
    : source.replace('const IRIS_ACCESS_TOKEN = "";', `const IRIS_ACCESS_TOKEN = ${JSON.stringify(token)};`);

  vm.runInContext(code, context);
  return { context, deadlines, calls };
}

function ok(body = '{"verdict":"Not Found"}') {
  return { ok: true, status: 200, text: async () => body };
}

test('text and image requests are given a 180 second deadline', async () => {
  for (const endpoint of ['/verify', '/verify-image']) {
    const { context, deadlines } = fixture(async () => ok());
    const result = await vm.runInContext(`postJson('http://localhost:5000${endpoint}', {})`, context);

    assert.deepEqual(deadlines, [DEADLINE_MS]);
    assert.equal(result.payload.verdict, 'Not Found');
  }
});

test('no access token means no token header', async () => {
  const { context, calls } = fixture(async () => ok());
  await vm.runInContext("postJson('http://localhost:5000/verify', {})", context);

  assert.equal(calls[0].options.headers['X-IRIS-Token'], undefined);
  assert.equal(calls[0].options.headers['Content-Type'], 'application/json');
});

test('a configured access token is sent with every request', async () => {
  const { context, calls } = fixture(async () => ok(), { token: 'a-shared-secret' });
  await vm.runInContext("postJson('http://localhost:5000/verify', {})", context);

  assert.equal(calls[0].options.headers['X-IRIS-Token'], 'a-shared-secret');
});

test('a dropped connection is retried once, and the retry answers', async () => {
  let attempts = 0;
  const { context, calls } = fixture(async () => {
    attempts += 1;
    if (attempts === 1) throw new Error('Connection lost');
    return ok('{"verdict":"Verified"}');
  });

  const result = await vm.runInContext(
    "postJsonWithRetry('http://localhost:5000/verify', {})", context);

  assert.equal(calls.length, 2);
  assert.equal(result.payload.verdict, 'Verified');
});

test('a retry that also fails reports the failure rather than trying forever', async () => {
  const { context, calls } = fixture(async () => { throw new Error('Connection lost'); });

  await assert.rejects(
    vm.runInContext("postJsonWithRetry('http://localhost:5000/verify', {})", context),
    /Connection lost/);
  assert.equal(calls.length, 2);
});

test('a request that used up its deadline is not retried', async () => {
  const { context, calls } = fixture(async () => {
    const aborted = new Error('The operation was aborted.');
    aborted.name = 'AbortError';
    throw aborted;
  });

  // Waiting another 180 seconds would take the request past what a host will hold a
  // connection open for, so the deadline is reported instead of being spent twice.
  await assert.rejects(
    vm.runInContext("postJsonWithRetry('http://localhost:5000/verify', {})", context),
    /did not finish the request within 180 seconds/);
  assert.equal(calls.length, 1);
});

test('backend errors are returned rather than thrown', async () => {
  const { context } = fixture(async () => ({
    ok: false, status: 503, text: async () => '{"message":"Review failed"}'
  }));
  const result = await vm.runInContext("postJson('http://localhost:5000/verify', {})", context);

  assert.equal(result.ok, false);
  assert.equal(result.status, 503);
});

test('a 401 reaches the panel as the backend worded it', async () => {
  const { context } = fixture(async () => ({
    ok: false,
    status: 401,
    text: async () => '{"message":"This IRIS backend needs an access token. Set it in the IRIS options."}'
  }));
  const result = await vm.runInContext("postJson('http://localhost:5000/verify', {})", context);

  assert.equal(result.ok, false);
  assert.match(vm.runInContext('getBackendError', context)(result), /needs an access token/);
});
