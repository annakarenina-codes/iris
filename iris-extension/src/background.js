const MENU_CHECK_SELECTION = "iris-check-selection";
const MENU_CHECK_IMAGE = "iris-check-image";

// SightEngine is called straight from this worker: there is no local model and no
// local server anymore, so this is the only authenticity endpoint there is.
const SIGHTENGINE_API_URL = "https://api.sightengine.com/1.0/check.json";

// Written by scripts/set-backend-url.mjs. Each laptop that loads this folder unpacked gets its
// own extension ID, so chrome.storage.sync does not carry the address between them and every
// laptop would otherwise have to be configured by hand.
const IRIS_DEFAULT_BACKEND_URL = "https://iris-production-8342.up.railway.app"; // iris:backend-url

// The slowest post measured took 195 seconds, so the deadline sits above that and below the
// five minutes a hosting edge proxy usually allows. With no deadline at all a connection
// dropped on mobile data left the panel waiting for a result that was never coming.
const REQUEST_TIMEOUT_MS = 180000;
// A dropped connection earns one retry. Per-claim verdicts are cached on the backend, so the
// second attempt usually answers in seconds instead of running the whole pipeline again.
const RETRY_DELAY_MS = 1500;
// SightEngine answers in seconds when it answers at all; half a minute is already generous
// for an image upload that has to fail as "not assessed" rather than hang the panel.
const SIGHTENGINE_TIMEOUT_MS = 30000;

// Manifest V3 runs this script as a service worker that Chrome stops after about thirty
// seconds of inactivity. An image check takes a minute or more, and when the worker was stopped
// mid-request the backend finished while the panel waited for a result that could never arrive.
// Touching a chrome API on a timer keeps the worker awake until the work is done.
const KEEP_AWAKE_MS = 20000;

// History mirrors the Android app's HistoryStore: one entry per successful check, capped,
// and best-effort — chrome.storage.local, because sync quota is about 100 KB in total and a
// single raw payload can eat it, and because a person's checks must not roam devices.
const HISTORY_KEY = "irisHistory";
const HISTORY_LIMIT = 200;
const HISTORY_PREVIEW_LIMIT = 160;
const IMAGE_CHECK_SUFFIX = "/verify-image";
const IMAGE_FALLBACK_TEXT = "Image selected for OCR.";

// The context-image pipeline that is currently running for each tab, from the
// moment verifyImage starts until it reaches a terminal push. Cancel in the
// panel sends IRIS_CONTEXT_IMAGE_ABORT; this is what lets the worker stop the
// work instead of merely declining to report it. An invocation keeps its own
// aborted flag plus every AbortController it has in flight, so the abort is a
// flag flip plus a few .abort() calls, and an aborted invocation pushes neither
// IRIS_CONTEXT_IMAGE_RESULT nor IRIS_CONTEXT_IMAGE_ERROR.
const contextImageRuns = new Map();

function normalizeBackendUrl(value) {
  const raw = String(value || IRIS_DEFAULT_BACKEND_URL).trim();
  return raw.replace(/\/+$/, "");
}

function readSettings() {
  return chrome.storage.sync.get({
    irisBackendUrl: IRIS_DEFAULT_BACKEND_URL,
    sightengineApiUser: "",
    sightengineApiSecret: "",
    irisDebugMode: false
  });
}

// The token is typed into the options page and kept in the browser, never in a file. This
// repository is public, and a token committed to it is a token anyone can spend.
async function readAccessToken() {
  try {
    const stored = await chrome.storage.sync.get({ irisAccessToken: "" });
    return String(stored.irisAccessToken || "").trim();
  } catch (_error) {
    return "";
  }
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

// After the extension is reloaded, tabs that stayed open are the gap: their old
// content script zombies (the watchdog tears it down within a second and clears
// the guard), and nothing re-injects until a right-click or a page refresh.
// Re-inject the guarded content script into every page tab now — the guard
// makes this a cheap no-op where a script already runs — then once more after
// the watchdog has had time to clear the old flag, which is the pass that
// actually lands on the torn-down tabs.
function injectTopFrame(tabId) {
  return chrome.scripting
    .executeScript({ target: { tabId, frameIds: [0] }, files: ["src/content.js"] })
    .catch(() => {});
}

async function reviveOpenTabs() {
  const tabs = await chrome.tabs.query({});
  const pageTabs = tabs.filter((tab) => tab.id && /^https?:/i.test(tab.url || ""));

  await Promise.all(pageTabs.map((tab) => injectTopFrame(tab.id)));
  await new Promise((resolve) => setTimeout(resolve, 1500));
  await Promise.all(pageTabs.map((tab) => injectTopFrame(tab.id)));
}

chrome.runtime.onInstalled.addListener(() => {
  reviveOpenTabs();
});

async function sendToTab(tabId, message) {
  // Top frame ONLY, both directions. The manifest's content script is
  // top-frame; a broadcast would reach any frame a past fallback ever
  // injected, and those frames mount their own floating panel — the
  // "two panels on screen" bug. frameId 0 is the page's main frame.
  try {
    await chrome.tabs.sendMessage(tabId, message, { frameId: 0 });
  } catch (_error) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId, frameIds: [0] },
        files: ["src/content.js"]
      });
      await chrome.tabs.sendMessage(tabId, message, { frameId: 0 });
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

// `run` is the context-image invocation this request belongs to, when there is
// one: registering the controller with it is what lets a cancel abort the
// request mid-flight rather than wait out the deadline.
async function postJson(url, payload, run = null) {
  const token = await readAccessToken();
  const controller = new AbortController();
  if (run) {
    run.controllers.add(controller);
    // The abort may have landed between the invocation's start and this request.
    if (run.aborted) controller.abort();
  }
  const timeoutId = REQUEST_TIMEOUT_MS > 0
    ? setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
    : null;

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: token
        ? { "Content-Type": "application/json", "X-IRIS-Token": token }
        : { "Content-Type": "application/json" },
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
    // A cancel aborts exactly like the deadline does, and the two must not be
    // conflated: the deadline's message would be a lie for a cancelled request.
    if (error?.name === "AbortError" && run?.aborted) {
      const cancelled = new Error("IRIS cancelled this image check before it finished.");
      cancelled.cancelled = true;
      throw cancelled;
    }

    if (error?.name === "AbortError" && REQUEST_TIMEOUT_MS > 0) {
      const expired = new Error(`IRIS did not finish the request within ${REQUEST_TIMEOUT_MS / 1000} seconds. Check your connection and that the backend is running, then try again.`);
      expired.timedOut = true;
      throw expired;
    }

    throw error;
  } finally {
    if (run) run.controllers.delete(controller);
    if (timeoutId !== null) clearTimeout(timeoutId);
  }
}

async function postJsonWithRetry(url, payload, run = null, recordHistory = true) {
  let result;
  try {
    result = await postJson(url, payload, run);
  } catch (error) {
    // A deadline that has already passed is not worth waiting through twice, and a second
    // 180 seconds would exceed what the host will hold a connection open for anyway.
    // A cancelled request is not worth retrying either: the reader already said no.
    if (error?.timedOut || error?.cancelled) throw error;

    await new Promise((resume) => setTimeout(resume, RETRY_DELAY_MS));
    result = await postJson(url, payload, run);
  }

  // Text and image checks both arrive here with a finished body, so this is the one place
  // history is written: a request the backend did not answer successfully never reaches it.
  // The image flow passes recordHistory: false — only its post-merge write below can carry
  // the SightEngine verdict, which this raw claims response never contains.
  if (recordHistory && result?.ok) await recordCheckHistory(url, payload, result.payload);

  return result;
}

/**
 * Records one successful check. Everything is swallowed after a console.warn: a storage
 * problem must never fail a verification the backend has already answered.
 */
async function recordCheckHistory(url, request, payload, extras = null) {
  try {
    // The unit-test sandbox models sync storage only; with no local area there is
    // simply nowhere to write, and that is not a failure worth logging.
    const area = chrome?.storage?.local;
    if (!area) return;

    const inputType = String(url || "").endsWith(IMAGE_CHECK_SUFFIX) ? "image" : "text";
    const fallback = inputType === "image" ? IMAGE_FALLBACK_TEXT : String(request?.text || "");
    const claims = Array.isArray(payload?.claims) ? payload.claims : [];
    const firstClaim = claims[0] || {};

    let preview = String(firstClaim.claim_text || firstClaim.original_text || "").trim() || fallback;
    if (preview.length > HISTORY_PREVIEW_LIMIT) {
      preview = `${preview.slice(0, HISTORY_PREVIEW_LIMIT)}...`;
    }

    const entry = {
      checkedAt: Date.now(),
      inputType,
      preview,
      verdict: firstClaim.verdict ? String(firstClaim.verdict) : "",
      fallback,
      rawJson: JSON.stringify(payload ?? null)
    };

    // Image entries carry two FLAT summary fields on top of rawJson: the row badge
    // must not parse every stored payload (the detail view stays the lazy parser),
    // and entries recorded before this schema simply lack them — no pill, no crash.
    if (inputType === "image") {
      const ai = payload?.ai_generated;
      if (ai?.status === "ok" && Number.isFinite(Number(ai.confidence))) {
        entry.imageAi = { confidence: Number(ai.confidence), isAi: Boolean(ai.is_ai_generated) };
      }
      const source = extras?.source;
      if (source) {
        // Never the image bytes: the name identifies the file and the url lets a
        // later eval re-fetch it. data_url sources carry an empty url on purpose.
        entry.image = {
          name: String(source.name || "").slice(0, 120),
          url: String(source.url || "")
        };
      }
    }

    // Newest first, oldest shed at the cap: rawJson stores the whole payload, so an
    // unbounded list would walk past the local storage quota.
    const stored = await area.get({ [HISTORY_KEY]: [] });
    const history = Array.isArray(stored[HISTORY_KEY]) ? stored[HISTORY_KEY] : [];
    await area.set({ [HISTORY_KEY]: [entry, ...history].slice(0, HISTORY_LIMIT) });
  } catch (error) {
    console.warn("[IRIS] Could not record check history.", error);
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
    debug: Boolean(settings.irisDebugMode),
    language: settings.irisUiLanguage || "en"
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

async function imageBase64ForAuthenticity(source, payload) {
  const imageBase64 = String(payload?.image_base64 || "").trim();

  if (imageBase64) {
    const commaIndex = imageBase64.indexOf(",");
    return imageBase64.startsWith("data:") && commaIndex !== -1
      ? imageBase64.slice(commaIndex + 1)
      : imageBase64;
  }

  if (source.kind === "url") {
    const response = await fetch(source.url);
    if (!response.ok) {
      throw new Error(`IRIS could not download the image for the authenticity check (HTTP ${response.status}).`);
    }

    const bytes = new Uint8Array(await response.arrayBuffer());
    let binary = "";
    const CHUNK_BYTES = 0x8000;

    for (let offset = 0; offset < bytes.length; offset += CHUNK_BYTES) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + CHUNK_BYTES));
    }

    return btoa(binary);
  }

  throw new Error("IRIS had no image bytes for the authenticity check.");
}

function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

/**
 * Reads one probability key out of a SightEngine sub-object. SightEngine has shipped
 * numbers, missing keys and unparseable strings; an unknown reads as 0, the same way the
 * backend reads it -- an unknown is an observation of nothing, not a verdict of "clear".
 */
function sightengineDetectorProbability(container, key) {
  const raw = container && typeof container === "object" ? container[key] : 0;
  const number = Number(raw ?? 0);
  return Number.isFinite(number) ? number : 0;
}

/**
 * One detector's reading, in the shape Android's IrisResultData expects. Every detector
 * answers with the same fields so a client can render any of them without knowing which
 * model produced it. Fields never make one detector's output a conclusion about another's.
 */
function sightengineObservation(score, isSuspicious, extra = {}) {
  return {
    suspicion_score: score,
    confidence: score,
    is_suspicious: isSuspicious,
    model: "SightEngine",
    status: "ok",
    error: null,
    ...extra
  };
}

/**
 * The authenticity half of an image check, asked of SightEngine directly from this worker.
 * It never throws: an unassessed image is an honest result the panel already knows how to
 * render, so every failure collapses into {image_authenticity_checked: false}.
 */
async function analyzeImageAuthenticitySightEngine(source, payload, run = null) {
  const startedAt = Date.now();

  try {
    const settings = await readSettings();
    const apiUser = String(settings.sightengineApiUser || "").trim();
    const apiSecret = String(settings.sightengineApiSecret || "").trim();

    if (!apiUser || !apiSecret) {
      return {
        image_authenticity_checked: false,
        ai_generated: { status: "error", error: "SightEngine credentials not configured." }
      };
    }

    const imageBase64 = await imageBase64ForAuthenticity(source, payload);

    // SightEngine only reads `media` as a file part: a bare string field comes back
    // as HTTP 400 code 1042 "No media sent". Send the decoded bytes as a Blob with a
    // filename, which is the shape its endpoint accepts (verified against the API).
    const mediaBytes = base64ToBytes(imageBase64);

    const formData = new FormData();
    // Deepfake and embedded text ride the same request as genai: one call, one
    // process batch, and the same strictly-greater-than-0.5 rule the backend uses so
    // both halves of one check can never disagree about the same image.
    formData.append("models", "genai,deepfake,text");
    formData.append("api_user", apiUser);
    formData.append("api_secret", apiSecret);
    formData.append("media", new Blob([mediaBytes], { type: "image/jpeg" }), "image.jpg");

    const controller = new AbortController();
    if (run) {
      run.controllers.add(controller);
      // The abort may have landed before this half of the check started.
      if (run.aborted) controller.abort();
    }
    const timeoutId = setTimeout(() => controller.abort(), SIGHTENGINE_TIMEOUT_MS);

    let response;
    try {
      response = await fetch(SIGHTENGINE_API_URL, {
        method: "POST",
        body: formData,
        signal: controller.signal
      });
    } finally {
      if (run) run.controllers.delete(controller);
      clearTimeout(timeoutId);
    }

    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (_error) {
      return {
        image_authenticity_checked: false,
        ai_generated: { status: "error", error: "SightEngine returned non-JSON response." }
      };
    }

    if (!response.ok) {
      return {
        image_authenticity_checked: false,
        ai_generated: { status: "error", error: data?.message || `SightEngine HTTP ${response.status}` }
      };
    }

    // SightEngine has shipped `type` as a plain probability and as an object such as
    // {ai_generated: 0.99}. Read both shapes, and read anything unparseable as 0 rather
    // than as a verdict.
    let aiProbability = data?.type ?? 0;
    if (aiProbability && typeof aiProbability === "object") {
      aiProbability = aiProbability.ai_generated ?? aiProbability.probability ?? 0;
    }
    aiProbability = Number(aiProbability);
    if (!Number.isFinite(aiProbability)) aiProbability = 0;

    const isSuspicious = aiProbability > 0.5;

    // Deepfake and embedded text live in their own sub-objects; both readers fail
    // closed to 0 when the key is absent or malformed, so a partially-shaped response
    // still yields an honest observation rather than a thrown check.
    const typeContainer = data?.type && typeof data.type === "object" ? data.type : {};
    const textContainer = data?.text && typeof data.text === "object" ? data.text : {};
    const deepfakeProbability = sightengineDetectorProbability(typeContainer, "deepfake");
    const artificialText = sightengineDetectorProbability(textContainer, "has_artificial");
    const naturalText = sightengineDetectorProbability(textContainer, "has_natural");
    const deepfakeSuspicious = deepfakeProbability > 0.5;
    const textSuspicious = artificialText > 0.5;

    return {
      image_authenticity_checked: true,
      ai_generated: sightengineObservation(aiProbability, isSuspicious, {
        is_ai_generated: isSuspicious
      }),
      deepfake: sightengineObservation(deepfakeProbability, deepfakeSuspicious, {
        is_deepfake: deepfakeSuspicious
      }),
      // Text present in the scene (has_natural) is not an accusation: only text added
      // after the shot (has_artificial) is flagged.
      embedded_text: sightengineObservation(artificialText, textSuspicious, {
        has_artificial: artificialText,
        has_natural: naturalText
      })
    };
  } catch (error) {
    return {
      image_authenticity_checked: false,
      ai_generated: { status: "error", error: String(error?.message || "SightEngine request failed.") }
    };
  } finally {
    console.log(`[IRIS] SightEngine check finished in ${Date.now() - startedAt} ms.`);
  }
}

/**
 * One user action, two INDEPENDENT checks. The claim/OCR request and the SightEngine
 * authenticity request run side by side, and either one can carry the result alone:
 * a dead claims backend still shows the SightEngine badge (with the backend failure as
 * the claim message), a SightEngine miss only marks the badge "not assessed", and only
 * when BOTH fail does the panel show a plain error.
 */
async function verifyImage(sourceInput, tabId) {
  if (!tabId) return;

  const source = normalizeImageSource(sourceInput);

  // Registered before anything is sent: an IRIS_CONTEXT_IMAGE_ABORT can only
  // find the invocation if it is already on the map, and every terminal path
  // below leaves through the finally that retires it. A newer invocation for the
  // same tab replaces this entry, so the finally only clears its own run.
  const run = { aborted: false, controllers: new Set() };
  contextImageRuns.set(tabId, run);

  try {
    await sendToTab(tabId, {
      type: "IRIS_CONTEXT_IMAGE_STARTED",
      imageUrl: source.url,
      imageName: source.name
    });

    try {
      const settings = await readSettings();
      const backendUrl = normalizeBackendUrl(settings.irisBackendUrl);
      const imagePayload = buildImagePayload(source, settings);

      const [claimCheck, authenticityCheck] = await Promise.allSettled([
        // recordHistory: false — this raw claims response predates the merge, so a
        // history entry written here could never contain the SightEngine verdict.
        // verifyImage records the merged payload itself, after both halves settle.
        withWorkerAwake(() => postJsonWithRetry(`${backendUrl}/verify-image`, imagePayload, run, false)),
        withWorkerAwake(() => analyzeImageAuthenticitySightEngine(source, imagePayload, run))
      ]);

      // An aborted invocation reports nothing: the reader cancelled, so neither
      // the merged result below nor the "both halves failed" error is news. The
      // fetch failures the abort itself produced are swallowed here for the same
      // reason — they are the cancel, not a backend problem.
      if (run.aborted) return;

      // Independent verdicts: neither failure is allowed to discard the other's result.
      let claimError = null;
      let claimPayload = null;

      if (claimCheck.status === "rejected") {
        claimError = claimCheck.reason?.message || String(claimCheck.reason || "Claim check failed.");
      } else if (!claimCheck.value.ok) {
        claimError = getBackendError(claimCheck.value);
      } else if (claimCheck.value.payload && Object.keys(claimCheck.value.payload).length) {
        claimPayload = { ...claimCheck.value.payload };
      } else {
        claimError = "The IRIS backend returned an empty result.";
      }

      const authenticity = authenticityCheck.status === "fulfilled"
        ? authenticityCheck.value
        : {
            image_authenticity_checked: false,
            ai_generated: {
              status: "error",
              error: String(authenticityCheck.reason?.message || authenticityCheck.reason || "SightEngine check failed.")
            }
          };
      const authenticityOk = authenticity.image_authenticity_checked === true;

      if (!claimPayload && !authenticityOk) {
        // Both halves failed: there is no honest result to render.
        throw new Error(claimError || authenticity.ai_generated?.error || "IRIS could not verify the selected image.");
      }

      // Whichever half succeeded (or both) is merged into one payload. content.js reads
      // payload.message for the claim card when no claims exist, and the presence of the
      // authenticity keys to choose between a verdict and the honest "Not assessed" badge.
      const payload = claimPayload || { message: claimError };
      payload.image_authenticity_checked = authenticityOk;
      payload.ai_generated = authenticity.ai_generated;
      // The extra detectors ride along exactly as Android's mergeInto carries them.
      // Absent stays absent: a payload whose check never ran must not grow empty
      // verdicts for detectors that never fired.
      if (authenticity.deepfake) payload.deepfake = authenticity.deepfake;
      if (authenticity.embedded_text) payload.embedded_text = authenticity.embedded_text;

      if (run.aborted) return;

      // Image history is written HERE instead of inside postJsonWithRetry: only the
      // merged payload carries the SightEngine verdict, and this stored entry is the
      // only durable copy of a score the panel otherwise shows once and drops.
      // Claim-payload parity with the old path: no claims response, no entry.
      if (claimPayload) {
        await recordCheckHistory(`${backendUrl}/verify-image`, imagePayload, payload, { source });
      }

      await sendToTab(tabId, {
        type: "IRIS_CONTEXT_IMAGE_RESULT",
        imageUrl: source.url,
        imageName: source.name,
        payload
      });
    } catch (error) {
      if (run.aborted) return;

      await sendToTab(tabId, {
        type: "IRIS_CONTEXT_IMAGE_ERROR",
        imageUrl: source.url,
        imageName: source.name,
        error: error?.message || "IRIS could not verify the selected image."
      });
    }
  } finally {
    if (contextImageRuns.get(tabId) === run) contextImageRuns.delete(tabId);
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "IRIS_GET_TAB_ID") {
    sendResponse({ ok: true, tabId: _sender.tab?.id ?? null });
    return false;
  }

  if (message?.type === "IRIS_VERIFY_TEXT") {
    const backendUrl = normalizeBackendUrl(message.backendUrl);
    postJsonWithRetry(`${backendUrl}/verify`, {
      text: message.text || "",
      platform: "chrome",
      debug: Boolean(message.debug),
      // The reader's UI language, so the backend can answer in it when it
      // supports that; unknown fields are ignored by the current backend.
      language: message.language || "en"
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

  // Cancel in the panel: stop this tab's context-image pipeline at the source.
  // Synchronous answer (no pending channel): aborting is a flag flip plus a few
  // .abort() calls, and the aborted invocation pushes neither RESULT nor ERROR.
  // With no pipeline running — a text check, or a cancel that raced the finish —
  // this is a no-op. The message itself is sent the instant Cancel is pressed,
  // a whole human interaction before any *subsequent* check could register, which
  // is the only ordering this single-tab lookup depends on.
  if (message?.type === "IRIS_CONTEXT_IMAGE_ABORT") {
    const tabId = _sender.tab?.id ?? null;
    const run = tabId == null ? null : contextImageRuns.get(tabId);
    if (run) {
      run.aborted = true;
      for (const controller of [...run.controllers]) {
        try {
          controller.abort();
        } catch (_error) {
          // An already-settled controller has nothing left to abort.
        }
      }
    }

    sendResponse({ ok: true });
    return false;
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
