const MENU_CHECK_SELECTION = "iris-check-selection";
const MENU_CHECK_IMAGE = "iris-check-image";

function normalizeBackendUrl(value) {
  const raw = String(value || "http://127.0.0.1:5000").trim();
  return raw.replace(/\/+$/, "");
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
    sendToTab(tab.id, {
      type: "IRIS_CONTEXT_IMAGE",
      imageUrl: info.srcUrl || ""
    });
  }
});

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";

  for (let index = 0; index < bytes.length; index += chunkSize) {
    const chunk = bytes.subarray(index, index + chunkSize);
    binary += String.fromCharCode(...chunk);
  }

  return btoa(binary);
}

async function fetchImageAsDataUrl(url) {
  if (!url) {
    throw new Error("No image URL was provided.");
  }

  const response = await fetch(url, {
    credentials: "omit",
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Image download failed with HTTP ${response.status}.`);
  }

  const contentType = response.headers.get("content-type") || "image/png";
  const buffer = await response.arrayBuffer();
  const base64 = arrayBufferToBase64(buffer);
  return `data:${contentType};base64,${base64}`;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
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
}

function getBackendError(result) {
  const payload = result?.payload || {};
  return (
    payload.message ||
    payload.error ||
    `IRIS backend request failed with HTTP ${result?.status || "unknown"}.`
  );
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "IRIS_FETCH_IMAGE_AS_DATA_URL") {
    fetchImageAsDataUrl(message.imageUrl)
      .then((dataUrl) => sendResponse({ ok: true, dataUrl }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
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

  if (message?.type === "IRIS_VERIFY_IMAGE") {
    const backendUrl = normalizeBackendUrl(message.backendUrl);
    postJson(`${backendUrl}/verify-image`, {
      image_base64: message.imageDataUrl || "",
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

  if (message?.type === "IRIS_OPEN_OPTIONS") {
    chrome.runtime.openOptionsPage();
    sendResponse({ ok: true });
    return false;
  }

  return false;
});
