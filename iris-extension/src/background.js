const MENU_CHECK_SELECTION = "iris-check-selection";
const MENU_CHECK_IMAGE = "iris-check-image";
// Temporary calibration setting: 0 disables the request deadline. Restore 120000 after testing.
const REQUEST_TIMEOUT_MS = 0;

function normalizeBackendUrl(value) {
  const raw = String(value || "http://127.0.0.1:5000").trim();
  return raw.replace(/\/+$/, "");
}

function readSettings() {
  return chrome.storage.sync.get({
    irisBackendUrl: "http://127.0.0.1:5000",
    irisDebugMode: false
  });
}

function createContextMenus() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: MENU_CHECK_SELECTION,
      title: "Check with IRIS",
      contexts: ["selection"]
    });

    chrome.contextMenus.create({
      id: MENU_CHECK_IMAGE,
      title: "Check image with IRIS",
      contexts: ["image"]
    });
  });
}

chrome.runtime.onInstalled.addListener(createContextMenus);
chrome.runtime.onStartup.addListener(createContextMenus);

async function sendToTab(tabId, message) {
  try {
    await chrome.tabs.sendMessage(tabId, message);
  } catch (_error) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["src/content.js"]
      });
      await chrome.tabs.sendMessage(tabId, message);
    } catch (retryError) {
      console.warn("[IRIS] Could not reach content script.", retryError);
    }
  }
}

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!tab?.id) return;

  if (info.menuItemId === MENU_CHECK_SELECTION) {
    sendToTab(tab.id, {
      type: "IRIS_CONTEXT_TEXT",
      text: info.selectionText || ""
    });
    return;
  }

  if (info.menuItemId === MENU_CHECK_IMAGE) {
    verifyImage({
      kind: "url",
      url: info.srcUrl || "",
      name: "Image from page"
    }, tab.id);
  }
});

// Manifest V3 runs this script as a service worker that Chrome stops after about thirty
// seconds of inactivity. An image check takes a minute or more, and when the worker was stopped
// mid-request the backend finished while the panel waited for a result that could never arrive.
// Touching a chrome API on a timer keeps the worker awake until the work is done.
const KEEP_AWAKE_MS = 20000;

async function withWorkerAwake(work) {
  const ticker = setInterval(() => {
    chrome.runtime.getPlatformInfo().catch(() => {});
  }, KEEP_AWAKE_MS);

  try {
    return await work();
  } finally {
    clearInterval(ticker);
  }
}

async function postJson(url, payload) {
  const controller = new AbortController();
  const timeoutId = REQUEST_TIMEOUT_MS > 0
    ? setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
    : null;

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    const text = await response.text();
    let data = null;

    try {
      data = text ? JSON.parse(text) : null;
    } catch (_error) {
      data = {
        message: text || "IRIS received a non-JSON backend response."
      };
    }

    return {
      ok: response.ok,
      status: response.status,
      payload: data
    };
  } catch (error) {
    if (error?.name === "AbortError" && REQUEST_TIMEOUT_MS > 0) {
      throw new Error(`IRIS did not finish the request within ${REQUEST_TIMEOUT_MS / 1000} seconds. Check your connection and that the backend is running, then try again.`);
    }

    throw error;
  } finally {
    if (timeoutId !== null) clearTimeout(timeoutId);
  }
}

function getBackendError(result) {
  const payload = result?.payload || {};
  return (
    payload.message ||
    payload.error ||
    `IRIS backend request failed with HTTP ${result?.status || "unknown"}.`
  );
}

function normalizeImageSource(source) {
  const input = typeof source === "string" ? { url: source } : (source || {});
  const name = String(input.name || input.imageName || "Selected image");
  const dataUrl = String(input.dataUrl || input.imageDataUrl || input.image_base64 || "").trim();
  const url = String(input.url || input.imageUrl || input.srcUrl || "").trim();

  if (dataUrl) {
    return {
      kind: "data_url",
      dataUrl,
      url: "",
      name
    };
  }

  if (/^data:image\//i.test(url)) {
    return {
      kind: "data_url",
      dataUrl: url,
      url: "",
      name
    };
  }

  if (url) {
    return {
      kind: "url",
      dataUrl: "",
      url,
      name
    };
  }

  return {
    kind: "missing",
    dataUrl: "",
    url: "",
    name
  };
}

function buildImagePayload(source, settings) {
  const payload = {
    platform: "chrome",
    debug: Boolean(settings.irisDebugMode)
  };

  if (source.kind === "data_url") {
    payload.image_base64 = source.dataUrl;
    return payload;
  }

  if (source.kind === "url") {
    if (!/^https?:\/\//i.test(source.url)) {
      throw new Error("IRIS can only verify image URLs from http or https pages. Drag blob images onto the IRIS panel instead.");
    }

    payload.image_url = source.url;
    return payload;
  }

  throw new Error("No image source was provided.");
}

async function verifyImage(sourceInput, tabId) {
  if (!tabId) return;

  const source = normalizeImageSource(sourceInput);

  await sendToTab(tabId, {
    type: "IRIS_CONTEXT_IMAGE_STARTED",
    imageUrl: source.url,
    imageName: source.name
  });

  try {
    const settings = await readSettings();
    const backendUrl = normalizeBackendUrl(settings.irisBackendUrl);
    const result = await withWorkerAwake(
      () => postJson(`${backendUrl}/verify-image`, buildImagePayload(source, settings)));

    if (!result.ok) {
      throw new Error(getBackendError(result));
    }

    await sendToTab(tabId, {
      type: "IRIS_CONTEXT_IMAGE_RESULT",
      imageUrl: source.url,
      imageName: source.name,
      payload: result.payload
    });
  } catch (error) {
    await sendToTab(tabId, {
      type: "IRIS_CONTEXT_IMAGE_ERROR",
      imageUrl: source.url,
      imageName: source.name,
      error: error.message || "IRIS could not verify the selected image."
    });
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "IRIS_GET_TAB_ID") {
    sendResponse({ ok: true, tabId: _sender.tab?.id ?? null });
    return false;
  }

  if (message?.type === "IRIS_VERIFY_TEXT") {
    const backendUrl = normalizeBackendUrl(message.backendUrl);
    postJson(`${backendUrl}/verify`, {
      text: message.text || "",
      platform: "chrome",
      debug: Boolean(message.debug)
    })
      .then((result) => {
        if (!result.ok) {
          sendResponse({
            ok: false,
            status: result.status,
            error: getBackendError(result),
            payload: result.payload
          });
          return;
        }

        sendResponse({ ok: true, status: result.status, payload: result.payload });
      })
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }

  if (message?.type === "IRIS_VERIFY_IMAGE_SOURCE" || message?.type === "IRIS_VERIFY_IMAGE") {
    const tabId = _sender.tab?.id ?? message.tabId ?? null;
    if (!tabId) {
      sendResponse({ ok: false, error: "IRIS could not identify the tab that requested image verification." });
      return false;
    }

    // Answer only when the check is finished: an open message channel is what keeps the
    // service worker alive while the backend works.
    verifyImage(message.source || {
      kind: message.imageUrl ? "url" : "data_url",
      url: message.imageUrl || "",
      dataUrl: message.imageDataUrl || "",
      name: message.imageName || "Selected image"
    }, tabId)
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: error?.message || "Image check failed." }));
    return true;
  }

  if (message?.type === "IRIS_OPEN_OPTIONS") {
    chrome.runtime.openOptionsPage();
    sendResponse({ ok: true });
    return false;
  }

  return false;
});
