// Top frame only: the manifest injects here, and the fallback re-injection in
// background.js/popup.js now targets frame 0 — but if content.js ever reaches
// a page iframe anyway, it must not run: a panel mounted there would be a
// second floating surface clipped to that frame (the "two panels" bug).
// Comparing window references is safe cross-origin.
if (!window.__IRIS_EXTENSION_CONTENT_LOADED__ && window === window.top) {
  window.__IRIS_EXTENSION_CONTENT_LOADED__ = true;

  const STORAGE_DEFAULTS = {
    irisBackendUrl: "https://iris-production-8342.up.railway.app", // iris:backend-url
    irisPanelEnabled: true,
    irisTheme: "system",
    irisFontSize: "default",
    irisDebugMode: false,
    quietMode: false,
    hoverCheck: false,
    hoverSuppressedByQuiet: false,
    irisUiLanguage: "en"
  };

  // Labels live in the i18n dictionary (t("font.*")) so they translate with
  // the panel; only the value and the scale matter here.
  const FONT_OPTIONS = [
    { value: "small", scale: 0.9 },
    { value: "default", scale: 1 },
    { value: "large", scale: 1.15 },
    { value: "xl", scale: 1.3 }
  ];

  const FAQ_ITEMS = [
    { questionKey: "faq.q.checks", answerKey: "faq.a.checks" },
    { questionKey: "faq.q.notFound", answerKey: "faq.a.notFound" },
    { questionKey: "faq.q.data", answerKey: "faq.a.data" },
    { questionKey: "faq.q.images", answerKey: "faq.a.images" }
  ];
  const IRIS_LOGO_MARK_URL = chrome.runtime.getURL("assets/iris-logo-mark.png");

  // Mirrors the options page and the background recorder: chrome.storage.local, never
  // sync — sync quota is about 100 KB in total, and history must not roam across devices.
  const HISTORY_KEY = "irisHistory";
  const RECENT_CHECKS_LIMIT = 3;
  // First three article links, then "Show N more" — the same rule the result panel applies.
  const HISTORY_SOURCE_LIMIT = 3;

  const state = {
    status: "idle",
    settingsReturnStatus: "idle",
    selectedText: "",
    claimMode: "text",
    selectedImage: null,
    result: null,
    claimIndex: 0,
    history: [],
    recentChecksOpen: false,
    collapsed: false,
    faqOpen: false,
    faqOpener: null,
    // The check that failed, in replayable form: the error state only offers a
    // retry when it can honestly repeat the exact same request.
    lastCheck: null,
    // Monotonic id of the check the panel currently believes in. beginCheck()
    // opens a new generation and cancelActiveCheck() closes the current one, so
    // every response flow can compare the generation it captured at its own start
    // against this on arrival and drop a stale payload. A boolean could not do
    // that: a *new* check re-armed it, letting an old response through the guard.
    checkGen: 0,
    // The generation recorded by the flows whose verdict arrives as a background
    // push (IRIS_CONTEXT_IMAGE_STARTED/RESULT/ERROR). Those messages carry no id,
    // so the push handlers can only ask whether this generation is still live.
    pushFlowGen: 0,
    // Which check kind is running: "text" | "image" | "context-image". Cancel
    // falls back to the state that matches the kind, not to whichever leftover
    // happens to be staged (runTextCheck never clears a staged image).
    activeCheckKind: null,
    panelOpenedByAction: false,
    settings: { ...STORAGE_DEFAULTS },
    position: null,
    tabId: null,
    dragging: null,
    dropActive: false,
    dropDepth: 0,
    quietDropActive: false,
    suppressClick: false,
    ignoreSelectionClearUntil: 0,
    ignoreInternalSelectionUntil: 0,
    pagePointerDown: false,
    selectionSyncTimer: null,
    pendingPositionSave: null
  };

  // Every visible string in the panel goes through here. irisT (i18n.js,
  // loaded before this file) falls back to English per key, so a partial
  // translation degrades instead of blanking the UI.
  function t(key, ...vars) {
    return irisT(state.settings.irisUiLanguage, key, vars);
  }

  const host = document.createElement("div");
  host.id = "iris-extension-root";
  const shadow = host.attachShadow({ mode: "open" });
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = chrome.runtime.getURL("src/content.css");
  const root = document.createElement("div");
  shadow.append(stylesheet, root);
  document.documentElement.append(host);

  const syncStorage = chrome.storage?.sync;
  const sessionStorage = chrome.storage?.session;
  let mountedView = null;

  // After the extension is reloaded or uninstalled, this script is orphaned:
  // its DOM and page listeners stay alive while every chrome.* call fails, so
  // the old panel becomes a zombie that shadows whatever the next fallback
  // injection mounts. Detect the lost context, tear the zombie down, and clear
  // the guard — the next trigger then re-injects into a clean page.
  let scriptDead = false;
  function extensionContextLost() {
    try {
      return !chrome.runtime || chrome.runtime.id === undefined;
    } catch (_error) {
      return true;
    }
  }
  const orphanWatch = window.setInterval(() => {
    if (scriptDead || !extensionContextLost()) return;
    scriptDead = true;
    window.clearInterval(orphanWatch);
    root.replaceChildren();
    mountedView = null;
    host.remove();
    window.__IRIS_EXTENSION_CONTENT_LOADED__ = false;
  }, 1000);

  function readSyncStorage(defaults) {
    return new Promise((resolve) => {
      if (!syncStorage) {
        resolve(defaults);
        return;
      }

      syncStorage.get(defaults, (items) => resolve(items || defaults));
    });
  }

  function writeSyncStorage(items) {
    return new Promise((resolve) => {
      if (!syncStorage) {
        resolve();
        return;
      }

      syncStorage.set(items, resolve);
    });
  }

  function readSessionStorage(defaults) {
    return new Promise((resolve) => {
      if (!sessionStorage) {
        resolve(defaults);
        return;
      }

      sessionStorage.get(defaults, (items) => resolve(items || defaults));
    });
  }

  function writeSessionStorage(items) {
    return new Promise((resolve) => {
      if (!sessionStorage) {
        resolve();
        return;
      }

      sessionStorage.set(items, resolve);
    });
  }

  const localStore = chrome.storage?.local;

  function readLocalStore(defaults) {
    return new Promise((resolve) => {
      if (!localStore) {
        resolve(defaults);
        return;
      }

      localStore.get(defaults, (items) => resolve(items || defaults));
    });
  }

  function sendRuntimeMessage(payload) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(payload, (response) => {
        const error = chrome.runtime.lastError;
        if (error) {
          reject(new Error(error.message));
          return;
        }

        resolve(response);
      });
    });
  }

  async function getCurrentTabId() {
    try {
      const response = await sendRuntimeMessage({ type: "IRIS_GET_TAB_ID" });
      return response?.tabId ?? null;
    } catch (_error) {
      return null;
    }
  }

  function positionStorageKey() {
    return state.tabId == null ? "" : `iris_position_${state.tabId}`;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => {
      const replacements = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      };
      return replacements[character];
    });
  }

  function truncateText(value, maxLength = 300) {
    const text = String(value || "");
    return text.length > maxLength ? `${text.slice(0, maxLength - 3)}...` : text;
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), Math.max(min, max));
  }

  function normalizePanelPosition(value) {
    if (value?.x == null || value?.y == null) return null;

    return {
      x: Number(value.x),
      y: Number(value.y)
    };
  }

  function positionsMatch(first, second) {
    if (!first && !second) return true;
    if (!first || !second) return false;

    return (
      Math.abs(Number(first.x) - Number(second.x)) < 0.5 &&
      Math.abs(Number(first.y) - Number(second.y)) < 0.5
    );
  }

  function normalizeBackendUrl(value) {
    return String(value || STORAGE_DEFAULTS.irisBackendUrl).trim().replace(/\/+$/, "");
  }

  function resolveTheme() {
    const preferred = state.settings.irisTheme;
    if (preferred === "dark" || preferred === "light") return preferred;

    return window.matchMedia?.("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function activeFontScale() {
    return FONT_OPTIONS.find((option) => option.value === state.settings.irisFontSize)?.scale ?? 1;
  }

  function shouldRenderPanel() {
    if (state.settings.quietMode) {
      if (state.collapsed) return false;
      if (!state.panelOpenedByAction && ["idle", "detected"].includes(state.status)) {
        return false;
      }
    }

    return (
      state.settings.irisPanelEnabled ||
      state.panelOpenedByAction ||
      state.status !== "idle"
    );
  }

  function irisEye(size = 28, _monochrome = false) {
    return `
      <img class="iris-eye" src="${IRIS_LOGO_MARK_URL}" width="${size}" height="${size}" alt="" aria-hidden="true" draggable="false" />
    `;
  }

  function icon(name) {
    const paths = {
      search:
        '<path d="M10.8 18a7.2 7.2 0 1 1 5.1-2.1L20 20" />',
      external:
        '<path d="M6 3h7v7M13 3 6.5 9.5M12 12.5H3.5v-9H8" />',
      image:
        '<rect x="3" y="4" width="18" height="16" rx="2" /><path d="m3 16 4-4 4 4 2-2 8 6" /><circle cx="16" cy="8.5" r="1.5" />',
      gear:
        '<path d="M12 8.2a3.8 3.8 0 1 1 0 7.6 3.8 3.8 0 0 1 0-7.6Zm7.2 4.1c.03-.2.03-.4.03-.6s0-.4-.03-.6l2-1.5-2-3.5-2.4 1a8 8 0 0 0-1-.6L15.5 4h-4l-.4 2.5c-.34.16-.68.36-1 .6l-2.3-1-2 3.5 2 1.5c-.04.2-.04.4-.04.6s0 .4.04.6l-2 1.5 2 3.5 2.3-1c.32.24.66.44 1 .6l.4 2.5h4l.4-2.5c.34-.16.68-.36 1-.6l2.4 1 2-3.5-2.1-1.5Z" />',
      question:
        '<circle cx="12" cy="12" r="8.5" /><path d="M9.8 9.5a2.4 2.4 0 0 1 4.7.6c0 1.9-2.4 2-2.4 3.8M12 17h.01" />',
      close: '<path d="M7 7 17 17M17 7 7 17" />',
      minus: '<path d="M5 12h14" />',
      chevronLeft: '<path d="m14 6-6 6 6 6" />',
      chevronRight: '<path d="m10 6 6 6-6 6" />'
    };

    return `
      <svg class="iris-icon" viewBox="0 0 24 24" aria-hidden="true">
        <g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          ${paths[name] || ""}
        </g>
      </svg>
    `;
  }

  function nodeBelongsToIris(node) {
    if (!node) return false;

    const rootNode = node.getRootNode?.();
    return rootNode === shadow || node === host || host.contains(node);
  }

  function selectionTouchesIris(selection) {
    if (!selection) return false;

    if (nodeBelongsToIris(selection.anchorNode) || nodeBelongsToIris(selection.focusNode)) {
      return true;
    }

    for (let index = 0; index < selection.rangeCount; index += 1) {
      const range = selection.getRangeAt(index);
      if (nodeBelongsToIris(range.commonAncestorContainer)) {
        return true;
      }
    }

    return false;
  }

  function cleanSelectionText(selection) {
    return selection?.toString?.().replace(/\s+/g, " ").trim() || "";
  }

  function getShadowSelection() {
    return typeof shadow.getSelection === "function" ? shadow.getSelection() : null;
  }

  function clearIrisSelection() {
    const selection = getShadowSelection();
    if (selection?.rangeCount) {
      selection.removeAllRanges();
    }
  }

  function hasIrisSelection() {
    const selection = getShadowSelection();
    return selectionTouchesIris(selection);
  }

  function getSelectionInfo() {
    if (hasIrisSelection()) {
      return {
        text: "",
        insideIris: true
      };
    }

    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) {
      return {
        text: "",
        insideIris: false
      };
    }

    if (selectionTouchesIris(selection)) {
      return {
        text: "",
        insideIris: true
      };
    }

    return {
      text: cleanSelectionText(selection),
      insideIris: false
    };
  }

  function getCleanSelection() {
    return getSelectionInfo().text;
  }

  // Tone lives as a class, not as colours in JS: content.css owns the light and
  // dark palettes for these six tones, so the same verdict reads identically in
  // the result card, the badge, and dark mode without a second copy of the hexes.
  function getVerdictStyle(verdict) {
    const normalized = String(verdict || "").toLowerCase();

    if (normalized === "verified") {
      return { icon: "OK", tone: "is-verified" };
    }

    if (normalized === "partially verified") {
      return { icon: "!", tone: "is-partial" };
    }

    if (normalized === "refuted") {
      return { icon: "X", tone: "is-refuted" };
    }

    if (normalized.includes("opinion")) {
      return { icon: "i", tone: "is-opinion" };
    }

    if (normalized.includes("failed") || normalized.includes("unavailable") || normalized.includes("configured")) {
      return { icon: "!", tone: "is-error" };
    }

    return { icon: "?", tone: "is-unknown" };
  }

  function flattenSources(rawSources) {
    if (!Array.isArray(rawSources)) return [];

    const flattened = [];
    const addSource = (source) => {
      if (!source || !isValidHttpUrl(source.url)) return;
      if (source.status && source.status !== "extracted") return;

      flattened.push({
        outlet: source.outlet || source.source || "Approved source",
        date: source.date || source.published_date || "",
        title: source.title || source.url,
        url: source.url.trim()
      });
    };

    for (const item of rawSources) {
      if (Array.isArray(item?.articles)) {
        for (const article of item.articles) {
          addSource({
            outlet: item.source || article.source || article.outlet,
            date: article.date || article.published_date || "",
            title: article.title || article.url,
            url: article.url || "",
            status: article.status
          });
        }
      } else {
        addSource({
          outlet: item.source || item.outlet,
          date: item.date || item.published_date || "",
          title: item.title || item.url,
          url: item.url || "",
          status: item.status
        });
      }
    }

    const seenUrls = new Set();
    return flattened.filter((source) => {
      const normalizedUrl = source.url.toLowerCase().replace(/#.*$/, "").replace(/\/$/, "");
      if (seenUrls.has(normalizedUrl)) return false;

      seenUrls.add(normalizedUrl);
      return true;
    });
  }

  function isValidHttpUrl(value) {
    try {
      const parsedUrl = new URL(String(value || "").trim());
      return ["http:", "https:"].includes(parsedUrl.protocol) && Boolean(parsedUrl.hostname);
    } catch {
      return false;
    }
  }

  function summarizeIgnoredSegments(segments) {
    if (!Array.isArray(segments)) return [];

    const labels = {
      opinion: "opinion",
      recommendation: "recommendation",
      forecast_or_projection: "prediction",
      forecast_or_projection_detected: "prediction",
      satire_or_humor: "satire",
      unclear: "unclear segment",
      uncheckable: "uncheckable segment"
    };
    const counts = new Map();

    for (const segment of segments) {
      const reason = segment.reason || segment.segment_type || "uncheckable";
      const label = labels[reason] || reason.replace(/_/g, " ");
      counts.set(label, (counts.get(label) || 0) + Number(segment.count || 1));
    }

    return [...counts.entries()].map(([label, count]) => ({ label, count }));
  }

  function normalizeClaim(rawClaim, fallbackText, topLevelSources) {
    const verdict = rawClaim?.verdict || "Not Found";
    const style = getVerdictStyle(verdict);
    const corroboration = rawClaim?.corroboration || {};
    const sources = flattenSources(
      rawClaim?.evidence_sources ||
      rawClaim?.supporting_sources ||
      rawClaim?.sources ||
      topLevelSources ||
      []
    );
    const rawEvidenceCount = Number(corroboration.count ?? rawClaim?.corroboration_count ?? sources.length);
    const evidenceCount = Number.isFinite(rawEvidenceCount)
      ? Math.min(rawEvidenceCount, sources.length)
      : sources.length;

    return {
      claim_id: rawClaim?.claim_id || 1,
      claim_text: rawClaim?.claim_text || rawClaim?.original_text || fallbackText || "",
      politically_sensitive: Boolean(rawClaim?.politically_sensitive),
      verdict: {
        label: verdict,
        explanation: rawClaim?.message || rawClaim?.verdict_explanation || t("result.defaultExplanation"),
        ...style
      },
      corroboration: {
        count: evidenceCount,
        // Fallback must match len(ALL_SOURCES) in iris-backend/pipeline/sources.py.
        total: Number(corroboration.total ?? 11)
      },
      sources
    };
  }

  // One detector's number, read the same way genai's is: unparseable becomes an
  // absent figure rather than a rendered 0%.
  function detectorScore(detector) {
    const raw = Number(detector?.confidence ?? detector?.suspicion_score);
    return Number.isFinite(raw) && raw >= 0 ? raw : 0;
  }

  // Three honest states. "Not assessed" is a real outcome, not a failure: when the
  // detectors could not run we must never imply the image was cleared, so a missing
  // or degraded signal renders as unassessed instead of as "authentic".
  function normalizeImageAuthenticity(payload) {
    const ai = payload?.ai_generated;

    if (!payload?.image_authenticity_checked || ai?.status !== "ok") {
      return { state: "not_assessed" };
    }

    // SightEngine's number is the probability the image IS AI-generated, and it
    // travels with clear results too. It is always labelled as that probability,
    // never as "confidence" in authenticity — that label would invert the metric
    // for the reader. Unparseable values become undefined so no figure renders.
    const raw = Number(ai?.confidence ?? ai?.suspicion_score);
    const confidence = Number.isFinite(raw) && raw >= 0 ? raw : undefined;

    const result = ai?.is_ai_generated
      ? { state: "ai_generated", confidence: confidence ?? 0 }
      : { state: "not_ai", confidence };

    // The extra detectors ride along ONLY when they fired. A quiet detector says
    // nothing on purpose: with image type out of scope we cannot tell "checked and
    // clear" from "nothing there to check", so silence is the honest answer for one
    // that did not fire — and each flag stays an observation of its own detector,
    // never a vote counted into the AI verdict above it.
    const flags = [];
    if (payload?.deepfake?.status === "ok" && payload.deepfake.is_suspicious) {
      flags.push({ kind: "deepfake", key: "imageAuth.deepfakeFlagged", confidence: detectorScore(payload.deepfake) });
    }
    if (payload?.embedded_text?.status === "ok" && payload.embedded_text.is_suspicious) {
      flags.push({ kind: "embedded_text", key: "imageAuth.embeddedTextFlagged", confidence: detectorScore(payload.embedded_text) });
    }
    if (flags.length) result.flags = flags;

    return result;
  }

  function normalizeBackendResult(payload, fallbackText, claimMode) {
    const claims = Array.isArray(payload?.claims) && payload.claims.length
      ? payload.claims.map((claim) => normalizeClaim(claim, fallbackText, payload.sources))
      : [
          normalizeClaim(
            {
              claim_id: 1,
              claim_text:
                payload?.ocr_text ||
                payload?.original_text ||
                payload?.text ||
                fallbackText,
              verdict: payload?.verdict || "Not Found",
              message: payload?.message,
              politically_sensitive: payload?.politically_sensitive,
              corroboration_count: payload?.corroboration_count,
              sources: payload?.sources
            },
            fallbackText,
            payload?.sources
          )
        ];

    return {
      inputType: claimMode === "photo" ? "image" : "text",
      total_claims: payload?.total_claims || payload?.claim_count || claims.length,
      ignored_segments: summarizeIgnoredSegments(payload?.ignored_segments),
      ocr_text: payload?.ocr_text || "",
      // Only image checks carry these keys, so text results stay null and the
      // badge never renders for them.
      image_authenticity:
        payload && ("ai_generated" in payload || "image_authenticity_checked" in payload)
          ? normalizeImageAuthenticity(payload)
          : null,
      claims
    };
  }

  // Three cards are enough to prove the evidence is there. A long list pushed the verdict
  // and its actions off the panel, so the rest wait behind a control instead.
  const VISIBLE_SOURCE_CARDS = 3;

  function sourceCards(sources) {
    const validSources = sources.filter((source) => isValidHttpUrl(source.url));
    if (!validSources.length) {
      return `<div class="source-empty">${t("result.noValidLink")}</div>`;
    }

    const cards = validSources.map((source, index) => {
      const date = source.date ? `<time>${escapeHtml(source.date)}</time>` : "<time></time>";
      // Collapsed cards stay in the DOM so unfolding them is a class change, not a re-render.
      const collapsed = index >= VISIBLE_SOURCE_CARDS ? " source-card--collapsed" : "";
      return `
          <button class="source-card${collapsed}" type="button" data-action="open-source" data-url="${escapeHtml(source.url)}">
            <span class="source-card__meta">
              <span>${escapeHtml(source.outlet)}</span>
              ${date}
            </span>
            <span class="source-card__title">${escapeHtml(source.title)}</span>
            ${source.url ? `<span class="source-card__link">${icon("external")} ${t("result.readArticle")}</span>` : ""}
          </button>
        `;
    });

    const hiddenCount = validSources.length - VISIBLE_SOURCE_CARDS;
    if (hiddenCount > 0) {
      cards.push(
        `<button class="source-more" type="button" data-action="show-more-sources">${t("result.showMore", hiddenCount)}</button>`
      );
    }

    return cards.join("");
  }

  function skippedNote(segments) {
    if (!segments.length) return "";

    const total = segments.reduce((sum, segment) => sum + segment.count, 0);
    const formatted = segments
      .map((segment) => `${segment.count} ${escapeHtml(segment.label)}`)
      .join(", ");

    return `
      <div class="skipped-note">
        <span aria-hidden="true">i</span>
        <p>${t(total === 1 ? "result.skippedOne" : "result.skippedMany", total, formatted)}</p>
      </div>
    `;
  }

  function claimNavigator(totalClaims) {
    return `
      <div class="claim-navigator" role="group" aria-label="${t("nav.aria")}" ${totalClaims <= 1 ? "hidden" : ""}>
        <button class="claim-navigator__button" type="button" data-action="prev-claim" aria-label="${t("nav.prev")}" ${state.claimIndex === 0 ? "disabled" : ""}>
          ${icon("chevronLeft")}
        </button>
        <strong>${t("result.claimOf", state.claimIndex + 1, totalClaims)}</strong>
        <button class="claim-navigator__button" type="button" data-action="next-claim" aria-label="${t("nav.next")}" ${state.claimIndex === totalClaims - 1 ? "disabled" : ""}>
          ${icon("chevronRight")}
        </button>
      </div>
    `;
  }

  // Shown once per image check, above the claim card. Decision SUPPORT, not a
  // decision: one feature title scopes the whole block, the verdict line states
  // the result bare, and the scope note directly under it keeps the image result
  // from being read as a claim verdict. The image signal and the claim signal are
  // independent — an AI-generated image can still illustrate a real event — so
  // nothing here may imply that one caused the other.
  // The negative state states only what the detector observed — "No AI
  // generation detected" — never a conclusion like "real"/"authentic": IRIS is a
  // decision aid, not the decider, so no badge line may deliver a verdict the
  // reader should form themselves.
  // The whole block collapses into one pill — result plus the detector's
  // confidence — because this signal is supporting evidence for the claim
  // verdict below it, not a rival headline. The splice caveat, scope note, and
  // caveats open with the pill on click. Three models run (genai, deepfake,
  // embedded text); genai alone decides the AI verdict, and the other two may
  // only flag what they saw. The copy therefore never claims a manipulation or
  // forensics check this pipeline does not perform, and never counts detectors
  // into a majority opinion about the image.
  function imageAuthenticityBadge(info) {
    if (!info) return "";

    const FEATURE_TITLE = t("imageAuth.feature");
    const DISCLAIMER = t("imageAuth.disclaimer");
    // The sentence that stops the image result being read as evidence about the
    // claim: it opens together with the splice caveat the moment the pill is
    // clicked — the collapsed state keeps only result + confidence.
    const SCOPE_LINE = t("imageAuth.scope");

    const TONES = {
      ai_generated: {
        cls: "is-flagged",
        icon: "!",
        verdict: t("imageAuth.aiGenerated"),
        note: t("imageAuth.aiGeneratedNote")
      },
      not_ai: {
        cls: "is-clear",
        icon: "✓",
        verdict: t("imageAuth.notAi"),
        // The qualifier on the verdict: it opens with the pill, one click away,
        // so "not detected" is never far from the line limiting it — IRIS helps
        // decide, it does not decide.
        caveat: t("imageAuth.notAiCaveat"),
        note: t("imageAuth.notAiNote")
      },
      not_assessed: {
        cls: "is-unknown",
        icon: "?",
        verdict: t("imageAuth.notAssessed"),
        note: t("imageAuth.notAssessedNote")
      }
    };

    const flags = Array.isArray(info.flags) ? info.flags : [];
    // genai's own call, kept apart from the flags: the AI score only prints next
    // to genai's verdict, never beside a detector that is reporting something else.
    const aiState = info.state;
    const aiFlagged = aiState === "ai_generated";
    const deepfakeFired = flags.some((f) => f.kind === "deepfake");

    // Card colour answers ONE question — how worried is this about forgery — so only
    // genai and face swaps may set it. Added text is a weaker and far more common
    // claim (a news chyron, a watermark, an overlay are all "text added after the
    // shot"), so it gets its own muted line and never repaints the card: a signal
    // that fires on nearly every image is noise, and noise must not be allowed to
    // cry wolf. The single exception stays — a face swap beside a green "No AI
    // generation detected" would contradict itself — so deepfake still takes the
    // headline and the card when genai stayed quiet.
    let tone;
    let headline = null;

    if (aiState === "not_assessed") {
      tone = TONES.not_assessed;
    } else if (aiFlagged || deepfakeFired) {
      tone = { ...TONES.ai_generated };
      if (!aiFlagged) {
        headline = flags.find((f) => f.kind === "deepfake") || flags[0];
        tone.verdict = t(headline.key, Math.round(headline.confidence * 100));
        // genai's own quiet reading is still stated underneath rather than hidden:
        // the flag says what fired, this says what genai saw, and neither of them is
        // proof about the image as a whole.
        tone.note = t("imageAuth.notAiNote");
      }
    } else {
      tone = TONES.not_ai;
    }

    const hasScore =
      (aiState === "ai_generated" || aiState === "not_ai") &&
      typeof info.confidence === "number";
    const score = hasScore
      ? `<span class="image-auth__score">${t("imageAuth.score", Math.round(info.confidence * 100))}</span>`
      : "";

    // Every fired detector that is NOT already the headline rides as its own line —
    // an independent observation of that detector, never folded into the verdict
    // above it or counted as a second vote on it.
    const extraFlags = flags
      .filter((f) => f !== headline)
      .map(
        (f) =>
          `<span class="image-auth__flag">${escapeHtml(t(f.key, Math.round(f.confidence * 100)))}</span>`
      )
      .join("");

    // The <summary> is the pill: icon, feature title, verdict, and confidence
    // in one row — everything a collapsed reader needs, nothing that competes
    // with the claim verdict below. Native <details>/<summary> is the control:
    // keyboard operable, aria state carried by the platform, no toggle JS.
    return `
      <details class="image-auth image-auth--${tone.cls}">
        <summary class="image-auth__pill">
          <span class="image-auth__icon" aria-hidden="true">${tone.icon}</span>
          <strong class="image-auth__feature">${escapeHtml(FEATURE_TITLE)}</strong>
          <span class="image-auth__verdict">${escapeHtml(tone.verdict)}</span>
          ${score}
          ${extraFlags}
          <span class="image-auth__chevron" aria-hidden="true"></span>
        </summary>
        <div class="image-auth__body">
          ${tone.caveat ? `<p class="image-auth__caveat">${escapeHtml(tone.caveat)}</p>` : ""}
          <p class="image-auth__scope">${escapeHtml(SCOPE_LINE)}</p>
          ${tone.note ? `<p class="image-auth__note">${escapeHtml(tone.note)}</p>` : ""}
          <p class="image-auth__disclaimer">${escapeHtml(DISCLAIMER)}</p>
        </div>
      </details>
    `;
  }

function resultClaimBlock(claim, result) {
    return `
      <div class="claim-result-block">
        <div class="result-claim">
          ${state.claimMode === "photo" ? `<span>${t("result.extracted")}</span>` : ""}
          <blockquote>${escapeHtml(truncateText(claim.claim_text))}</blockquote>
        </div>

        ${
          claim.politically_sensitive
            ? `<div class="political-flag">
                 <span aria-hidden="true">!</span>
                 <div>
                   <strong>${t("result.sensitive")}</strong>
                   <p>${t("result.sensitiveNote")}</p>
                 </div>
               </div>`
            : ""
        }

        <div class="verdict-card ${escapeHtml(claim.verdict.tone || "is-unknown")}">
          <span class="verdict-card__icon">${escapeHtml(claim.verdict.icon)}</span>
          <div>
            <strong>${escapeHtml(verdictLabel(claim.verdict.label))}</strong>
            <p>${escapeHtml(claim.verdict.explanation)}</p>
          </div>
        </div>

        ${state.claimIndex === result.claims.length - 1 ? skippedNote(result.ignored_segments) : ""}

        <div class="corroboration-row">
          <strong>${claim.corroboration.count}</strong>
          <span>${t(claim.corroboration.count === 1 ? "result.sourceUsed" : "result.sourcesUsed")}</span>
        </div>

        <div class="related-label">${t("result.evidenceSources")}</div>
        <div class="source-list">${sourceCards(claim.sources)}</div>
      </div>
    `;
  }

  function formatCheckedAt(value) {
    const timestamp = Number(value);
    if (!Number.isFinite(timestamp)) return "";

    const date = new Date(timestamp);
    const pad = (part) => String(part).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  // The badge shows the verdict in the reader's language; the raw string stays
  // English in storage and in every tone match, so colours and history never
  // depend on the display language. Backend verdicts outside the known four
  // pass through verbatim rather than vanish.
  const VERDICT_KEYS = {
    verified: "verdict.verified",
    "partially verified": "verdict.partially",
    refuted: "verdict.refuted",
    "not found": "verdict.notFound"
  };

  function verdictLabel(verdict) {
    const label = String(verdict || "").trim();
    const key = VERDICT_KEYS[label.toLowerCase()];
    return key ? t(key) : label;
  }

  // Badge tones reuse getVerdictStyle so the same verdict reads identically in the
  // result card, the options history, and this list. Callers pass either a verdict
  // object or a bare label string — a string must not be mistaken for a style, or
  // the row badge renders with no tone at all.
  function historyBadge(verdict, style) {
    const raw = String(verdict || "").trim();
    const tone = style && typeof style === "object" ? style : getVerdictStyle(raw);
    const label = raw ? verdictLabel(raw) : t("recent.badgeFallback");
    return `<span class="recent-check__badge ${escapeHtml(tone.tone || "is-unknown")}">${escapeHtml(label)}</span>`;
  }

  // Flat imageAi rides on the stored entry (see recordCheckHistory in background.js):
  // the row must not parse every payload — the detail below stays the lazy parser —
  // and entries recorded before the field existed simply show no pill. The score text
  // is the result badge's own translated key, so both views word it identically.
  function historyAiPill(entry) {
    const info = entry.imageAi;
    if (!info || !Number.isFinite(Number(info.confidence))) return "";

    const flagged = Boolean(info.isAi);
    return `<span class="recent-check__ai ${flagged ? "is-flagged" : "is-clear"}">${escapeHtml(
      t("imageAuth.score", Math.round(Number(info.confidence) * 100))
    )}</span>`;
  }

  // Detail is parsed from the stored payload through the panel's own normalizer, so
  // the history view counts evidence exactly the way the result view does — and the
  // reader gets verdicts and messages, never a wall of raw backend JSON.
  function historyDetailMarkup(entry) {
    let payload = null;
    try {
      payload = JSON.parse(entry.rawJson);
    } catch (_error) {
      payload = null;
    }

    const result = payload
      ? normalizeBackendResult(payload, entry.fallback, entry.inputType === "image" ? "photo" : "text")
      : null;
    const claims = Array.isArray(result?.claims) ? result.claims : [];
    // New image entries store the merged payload, so the normalizer sees the
    // SightEngine block and hands back a badge; older and text entries normalize
    // to null and stay badge-free, exactly as before.
    const authenticityBadge = imageAuthenticityBadge(result?.image_authenticity);

    if (!claims.length) {
      const text = String(entry.fallback || "").trim() || t("recent.noDetails");
      return `${authenticityBadge}<div class="recent-check__claim"><p>${escapeHtml(text)}</p></div>`;
    }

    return `${authenticityBadge}${claims
      .map((claim) => {
        const count = claim.corroboration.count;
        const sources = claim.sources;
        // The row preview clamps to two lines, so the detail is the only place
        // the full statement is readable — same rule the options history uses.
        const claimText = String(claim.claim_text || "").trim();
        const hiddenCount = Math.max(0, sources.length - HISTORY_SOURCE_LIMIT);
        const links = sources
          .map((source, index) => {
            const collapsed = index >= HISTORY_SOURCE_LIMIT ? " recent-check__source--collapsed" : "";
            return `<button type="button" class="recent-check__source${collapsed}" data-action="open-source" data-url="${escapeHtml(source.url)}">${escapeHtml(source.title)}</button>`;
          })
          .join("");
        const more =
          hiddenCount > 0
            ? `<button class="recent-check__source-more" type="button" data-action="show-more-history-sources">${t("result.showMore", hiddenCount)}</button>`
            : "";

        return `
      <div class="recent-check__claim">
        ${historyBadge(claim.verdict.label, claim.verdict)}
        ${claimText ? `<blockquote>${escapeHtml(claimText)}</blockquote>` : ""}
        <p>${escapeHtml(claim.verdict.explanation)}</p>
        <span class="recent-check__sources">${t(count === 1 ? "recent.evidenceOne" : "recent.evidenceMany", count)}</span>
        ${links ? `<div class="recent-check__source-list">${links}${more}</div>` : ""}
      </div>`;
      })
      .join("")}`;
  }

  // The open body is its own template so the toggle can splice it into the live
  // section: a full body swap would replace the header node, kill the chevron
  // transition, and replay the state-entry fade over the whole panel.
  function recentChecksBody() {
    const rows = state.history
      .slice(0, RECENT_CHECKS_LIMIT)
      .map(
        (entry, index) => `
      <div class="recent-check">
        <button type="button" class="recent-check__summary" aria-expanded="false" data-action="toggle-recent-check" data-index="${index}">
          <span class="recent-check__badges">
            ${historyBadge(entry.verdict)}
            ${historyAiPill(entry)}
          </span>
          <span class="recent-check__preview">${escapeHtml(entry.preview || "")}</span>
          <span class="recent-check__meta">
            <span>${entry.inputType === "image" ? t("recent.image") : t("recent.text")}${entry.image?.name ? ` · ${escapeHtml(entry.image.name)}` : ""}</span>
            <time>${escapeHtml(formatCheckedAt(entry.checkedAt))}</time>
          </span>
        </button>
        <div class="recent-check__detail" hidden></div>
      </div>`
      )
      .join("");

    return `
        <div class="recent-checks__list">${rows}</div>
        <button class="iris-button iris-button--secondary recent-checks__see-all" type="button" data-action="open-history">${t("recent.seeAll")}</button>`;
  }

  function recentChecksSection() {
    if (!state.history.length) return "";

    return `
      <section class="recent-checks ${state.recentChecksOpen ? "is-open" : ""}">
        <button type="button" class="recent-checks__header" aria-expanded="${state.recentChecksOpen}" data-action="toggle-recent-checks">
          <strong>${t("recent.title")}</strong>
          <span class="recent-checks__count">${state.history.length}</span>
          <i aria-hidden="true"></i>
        </button>
        ${state.recentChecksOpen ? recentChecksBody() : ""}
      </section>
    `;
  }

  function idleState() {
    return `
      <section class="iris-state iris-state--idle">
        <div class="idle-search">${icon("search")}</div>
        <h2>${t("idle.title")}</h2>
        <p>${t("idle.body")}</p>
        <div class="empty-claim">
          <span>${t("idle.empty")}</span>
          <strong>${t("idle.emptyHint")}</strong>
        </div>
        <button class="iris-button iris-button--disabled" type="button" disabled>${t("btn.check")}</button>
        <button class="iris-button iris-button--upload" type="button" data-action="upload-image">
          ${icon("image")}
          ${t("btn.upload")}
        </button>
        ${recentChecksSection()}
      </section>
    `;
  }

  function detectedState() {
    return `
      <section class="iris-state">
        <div class="detected-row">
          <span aria-hidden="true"></span>
          <strong>${t("detected.title")}</strong>
        </div>
        <blockquote data-role="detected-claim">${escapeHtml(truncateText(state.selectedText))}</blockquote>
        <p class="supporting-note">${t("detected.note")}</p>
        <button class="iris-button iris-button--primary" type="button" data-action="check-text">
          ${irisEye(18, true)}
          ${t("btn.check")}
        </button>
      </section>
    `;
  }

  function photoState() {
    const fileName = state.selectedImage?.name || t("photo.defaultName");
    const previewStyle = state.selectedImage?.dataUrl
      ? `style="background-image:linear-gradient(90deg,rgba(0,0,0,.5),rgba(0,0,0,.12)),url('${escapeHtml(state.selectedImage.dataUrl)}')"`
      : "";

    return `
      <section class="iris-state iris-state--photo">
        <div class="photo-preview" ${previewStyle}>
          <span>${escapeHtml(fileName)}</span>
          <p>${t("photo.body")}</p>
        </div>
        <div class="ocr-preview">
          <span>${t("photo.ocrLabel")}</span>
          <blockquote>${t("photo.ocrReady")}</blockquote>
        </div>
        <button class="iris-button iris-button--primary" type="button" data-action="scan-image">
          ${irisEye(18, true)}
          ${t("btn.scan")}
        </button>
        <button class="iris-button iris-button--secondary photo-cancel" type="button" data-action="cancel-image">${t("btn.cancel")}</button>
      </section>
    `;
  }

  function scanningState() {
    const text =
      state.claimMode === "photo"
        ? t("scan.photoText")
        : truncateText(state.selectedText);

    return `
      <section class="iris-state iris-state--scanning">
        <blockquote>${escapeHtml(text)}</blockquote>
        <div class="scan-dots" aria-hidden="true"><span></span><span></span><span></span></div>
        <h2>${t("scan.title")}</h2>
        <p>${t("scan.body")}</p>
        <div class="progress-track" aria-hidden="true"><span></span></div>
        <button class="iris-button iris-button--secondary scan-cancel" type="button" data-action="cancel-check">${t("btn.cancel")}</button>
      </section>
    `;
  }

  function resultState() {
    const result = state.result || { claims: [], ignored_segments: [] };
    const claims = result.claims.length
      ? result.claims
      : [normalizeClaim({ verdict: "Not Found", message: t("result.notFoundMsg") }, state.selectedText, [])];
    const activeClaim = claims[Math.min(state.claimIndex, claims.length - 1)];
    const quietCloseButton = `<button class="iris-button iris-button--secondary quiet-close-result" type="button" data-action="quiet-close" ${state.settings.quietMode ? "" : "hidden"}>${t("btn.closeIris")}</button>`;

    return `
      <section class="iris-state iris-state--result">
        ${claimNavigator(claims.length)}
        ${imageAuthenticityBadge(result.image_authenticity)}
        ${resultClaimBlock(activeClaim, { ...result, claims })}
        <p class="disclaimer">${t("result.disclaimer")}</p>
        ${quietCloseButton}
        <button class="iris-button iris-button--secondary" type="button" data-action="reset">${t("btn.checkAnother")}</button>
      </section>
    `;
  }

  function errorState() {
    return `
      <section class="iris-state iris-state--error">
        <div class="verdict-card is-error">
          <span class="verdict-card__icon">!</span>
          <div>
            <strong>${t("err.title")}</strong>
            <p>${escapeHtml(state.errorMessage || t("err.backend"))}</p>
          </div>
        </div>
        <p class="supporting-note">${t("err.backendUrl", escapeHtml(normalizeBackendUrl(state.settings.irisBackendUrl)))}</p>
        ${
          state.lastCheck
            ? `<button class="iris-button iris-button--primary" type="button" data-action="retry">${t("btn.retry")}</button>`
            : ""
        }
        <button class="iris-button iris-button--secondary" type="button" data-action="reset">${t("btn.back")}</button>
      </section>
    `;
  }

  function settingsState() {
    const languageOptions = IRIS_LANGUAGES.map(
      (language) =>
        `<option value="${language.code}" ${state.settings.irisUiLanguage === language.code ? "selected" : ""}>${escapeHtml(language.label)}</option>`
    ).join("");

    return `
      <section class="iris-state iris-settings">
        <div class="settings-title">
          <h2>${t("settings.title")}</h2>
          <button class="iris-button iris-button--secondary settings-done" type="button" data-action="close-settings">${t("btn.done")}</button>
        </div>

        <div class="setting-row">
          <div>
            <strong>${t("settings.night")}</strong>
            <span>${t("settings.nightSub")}</span>
          </div>
          <button class="switch-button ${resolveTheme() === "dark" ? "is-on" : ""}" type="button" role="switch" aria-checked="${resolveTheme() === "dark"}" data-action="toggle-theme">
            <span></span>
          </button>
        </div>

        <div class="setting-row">
          <div>
            <strong>${t("settings.quiet")}</strong>
            <span>${t("settings.quietSub")}</span>
          </div>
          <button class="switch-button ${state.settings.quietMode ? "is-on" : ""}" type="button" role="switch" aria-checked="${state.settings.quietMode}" data-action="toggle-quiet-mode">
            <span></span>
          </button>
        </div>

        <div class="setting-row">
          <div>
            <strong>${t("settings.hover")}</strong>
            <span>${t("settings.hoverSub")}</span>
          </div>
          <button class="switch-button ${state.settings.hoverCheck ? "is-on" : ""}" type="button" role="switch" aria-checked="${state.settings.hoverCheck}" data-action="toggle-hover-check">
            <span></span>
          </button>
        </div>

        <div class="setting-block">
          <strong>${t("settings.font")}</strong>
          <div class="font-options" role="group" aria-label="${t("settings.font")}">
            ${FONT_OPTIONS.map((option) => `
              <button class="${state.settings.irisFontSize === option.value ? "is-active" : ""}" type="button" data-action="set-font" data-value="${option.value}" aria-pressed="${state.settings.irisFontSize === option.value}">
                ${escapeHtml(t(`font.${option.value}`))}
              </button>
            `).join("")}
          </div>
        </div>

        <div class="setting-row">
          <div>
            <strong>${t("settings.language")}</strong>
            <span>${t("settings.languageSub")}</span>
          </div>
          <select data-setting="irisUiLanguage" aria-label="${t("settings.language")}">${languageOptions}</select>
        </div>

        <button class="iris-button iris-button--secondary" type="button" data-action="open-options">${t("settings.options")}</button>
      </section>
    `;
  }

  function faqOverlay() {
    if (!state.faqOpen) return "";

    return `
      <div class="faq-overlay" data-action="close-faq">
        <section class="faq-modal" role="dialog" aria-modal="true" aria-labelledby="iris-faq-title">
          <header>
            <h2 id="iris-faq-title">FAQ</h2>
            <button class="iris-icon-button iris-icon-button--plain" type="button" aria-label="${t("aria.closeFaq")}" data-action="close-faq">
              ${icon("close")}
            </button>
          </header>
          <div class="faq-list">
            ${FAQ_ITEMS.map((item) => `
              <article>
                <h3>${escapeHtml(t(item.questionKey))}</h3>
                <p>${escapeHtml(t(item.answerKey))}</p>
              </article>
            `).join("")}
            <button type="button" data-action="open-source" data-url="https://verafiles.org">${t("faq.openVera")}</button>
          </div>
        </section>
      </div>
    `;
  }

  function bodyForStatus() {
    if (state.status === "detected") return detectedState();
    if (state.status === "photo") return photoState();
    if (state.status === "scanning") return scanningState();
    if (state.status === "result") return resultState();
    if (state.status === "error") return errorState();
    if (state.status === "settings") return settingsState();
    return idleState();
  }

  function mountPanel() {
    root.innerHTML = `
      <div class="iris-floating-wrap">
        <input id="iris-image-input" type="file" accept="image/*" hidden />
        <div class="iris-live-region" role="status" aria-live="polite" aria-atomic="true"></div>
        <button class="iris-pill iris-extension-shell" type="button" aria-label="${t("aria.openPanel")}" data-drag-handle data-action="expand" hidden>
                ${irisEye(22)}
                <span>IRIS</span>
                <i class="iris-pill__status" aria-hidden="true"></i>
        </button>
        <aside class="iris-panel iris-extension-shell" aria-label="${t("aria.panel")}" hidden>
                <header class="iris-panel__header" data-drag-handle>
                  <div class="iris-panel__brand">
                    ${irisEye(28)}
                    <div class="iris-panel__brand-copy">
                      <strong>IRIS</strong>
                      <span class="iris-panel__tagline">
                        <span>INTELLIGENT REAL-TIME</span>
                        <span>INFORMATION SCANNER</span>
                      </span>
                    </div>
                  </div>
                  <button class="iris-icon-button" type="button" data-role="header-close"></button>
                </header>
                <div class="iris-panel__body"></div>
                <footer class="iris-panel__footer">
                  <button type="button" aria-label="${t("aria.openSettings")}" data-action="open-settings">${icon("gear")}</button>
                  <button type="button" aria-label="${t("aria.openFaq")}" data-action="open-faq">${icon("question")}</button>
                </footer>
        </aside>
      </div>
    `;
    mountedView = {
      wrapper: root.querySelector(".iris-floating-wrap"),
      panel: root.querySelector(".iris-panel"),
      pill: root.querySelector(".iris-pill"),
      body: root.querySelector(".iris-panel__body"),
      headerClose: root.querySelector('[data-role="header-close"]'),
      // Lives outside the body so innerHTML swaps on status changes cannot
      // destroy it, and outside the panel so it also speaks when collapsed.
      liveRegion: root.querySelector(".iris-live-region"),
      announcedStatus: null,
      status: null,
      bodyMarkup: null,
      claimIndex: null,
      renderedLanguage: state.settings.irisUiLanguage
    };

    // The entry fade is gated by a class on the body (armed in updatePanelBody).
    // Dropping the class when the animation ends keeps a later same-status body
    // swap — Recent checks opening, a history update — from replaying it.
    mountedView.body.addEventListener("animationend", (event) => {
      if (event.target.classList?.contains("iris-state")) {
        mountedView.body.classList.remove("is-state-enter");
      }
    });
  }

  function updatePanelBody() {
    const view = mountedView;
    const markup = bodyForStatus();
    if (view.bodyMarkup === markup && view.status === state.status) return;

    // A language switch rewrites every label in the body, but the per-status
    // branches below only patch their own controls — they keep live DOM state
    // alive across a theme toggle. So a language change swaps the whole body
    // once, then hands focus back to the select the reader just used: dropping
    // it mid-choice would strand a keyboard user at the page root.
    if (view.renderedLanguage !== state.settings.irisUiLanguage) {
      const keepLanguageFocus = Boolean(
        shadow.activeElement?.matches?.('select[data-setting="irisUiLanguage"]')
      );
      // The FAQ overlay sits on the panel, not in the body, so the swap below
      // would leave it behind in the old language. Drop it here; render's
      // injection re-adds it fresh, and focus that was inside it is handed back
      // after the re-add instead of falling to the page root.
      const openFaq = view.panel.querySelector(".faq-overlay");
      const keepFaqFocus = Boolean(openFaq && shadow.activeElement && openFaq.contains(shadow.activeElement));
      if (openFaq) openFaq.remove();
      view.pendingFaqFocus = keepFaqFocus;
      view.body.innerHTML = markup;
      view.renderedLanguage = state.settings.irisUiLanguage;
      view.status = state.status;
      view.bodyMarkup = markup;
      view.claimIndex = state.claimIndex;
      if (keepLanguageFocus) {
        view.body.querySelector('select[data-setting="irisUiLanguage"]')?.focus();
      }
      return;
    }

    if (view.status !== state.status) {
      view.body.innerHTML = markup;
      view.body.scrollTop = 0;
      // Re-arm the entry fade for this transition only; the animationend
      // listener in mountPanel disarms it once the fade has played.
      view.body.classList.remove("is-state-enter");
      void view.body.offsetWidth;
      view.body.classList.add("is-state-enter");
    } else if (state.status === "detected") {
      updateDetectedText(state.selectedText);
    } else if (state.status === "settings") {
      for (const [action, checked] of [
        ["toggle-theme", resolveTheme() === "dark"],
        ["toggle-quiet-mode", state.settings.quietMode],
        ["toggle-hover-check", state.settings.hoverCheck]
      ]) {
        const button = view.body.querySelector(`[data-action="${action}"]`);
        button.classList.toggle("is-on", Boolean(checked));
        button.setAttribute("aria-checked", String(Boolean(checked)));
      }
      for (const button of view.body.querySelectorAll('[data-action="set-font"]')) {
        const active = button.dataset.value === state.settings.irisFontSize;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
      }
    } else if (state.status === "result") {
      // Keep navigation buttons and unchanged evidence links alive during updates.
      const template = document.createElement("template");
      template.innerHTML = markup;
      const next = template.content;
      const navigator = view.body.querySelector(".claim-navigator");
      const nextNavigator = next.querySelector(".claim-navigator");
      navigator.hidden = nextNavigator.hidden;
      navigator.querySelector("strong").textContent = nextNavigator.querySelector("strong").textContent;
      for (const action of ["prev-claim", "next-claim"]) {
        navigator.querySelector(`[data-action="${action}"]`).disabled =
          nextNavigator.querySelector(`[data-action="${action}"]`).disabled;
      }
      // The detection badge sits between the navigator and the claim block, so the
      // block swap below never reaches it. Without this, a second image check would
      // keep showing the first check's verdict — worse than showing none.
      const badge = view.body.querySelector(".image-auth");
      const nextBadge = next.querySelector(".image-auth");
      if (badge && !nextBadge) {
        badge.remove();
      } else if (!badge && nextBadge) {
        navigator.after(nextBadge);
      } else if (badge && nextBadge && !badge.isEqualNode(nextBadge)) {
        badge.replaceWith(nextBadge);
      }
      const block = view.body.querySelector(".claim-result-block");
      const nextBlock = next.querySelector(".claim-result-block");
      if (!block.isEqualNode(nextBlock)) block.replaceWith(nextBlock);
      view.body.querySelector(".quiet-close-result").hidden = !state.settings.quietMode;
      if (view.claimIndex !== state.claimIndex) view.body.scrollTop = 0;
    } else {
      view.body.innerHTML = markup;
    }
    view.status = state.status;
    view.bodyMarkup = markup;
    view.claimIndex = state.claimIndex;
  }

  function render() {
    if (scriptDead) return;
    if (!shouldRenderPanel()) {
      root.replaceChildren();
      mountedView = null;
      // A live drag keeps its pad across stray re-renders of the unmounted state.
      if (state.quietDropActive) mountQuietDropTarget();
      return;
    }
    // A mounted surface supersedes the drag-only pad: the pill or panel owns
    // the drop from here, and the flag must not resurrect the pad after the
    // next quiet-close.
    state.quietDropActive = false;
    if (!mountedView) mountPanel();

    const { wrapper, panel, pill, headerClose } = mountedView;
    wrapper.classList.toggle("is-positioned", Boolean(state.position));
    if (state.position) {
      applyPositionDuringDrag(state.position.x, state.position.y);
    } else {
      wrapper.removeAttribute("style");
    }
    for (const surface of [panel, pill]) {
      surface.dataset.theme = resolveTheme();
      surface.style.setProperty("--iris-scale", activeFontScale());
      surface.classList.toggle("is-dragging", Boolean(state.dragging));
      surface.classList.toggle("is-drop-target", state.dropActive);
      // Arabic flips both surfaces to RTL; every physical left/right rule in
      // the panel CSS already reads through logical properties.
      surface.dir = state.settings.irisUiLanguage === "ar" ? "rtl" : "ltr";
    }
    panel.hidden = state.collapsed;
    pill.hidden = !state.collapsed;
    const scanning = state.status === "scanning";
    const ready = ["detected", "photo", "result"].includes(state.status);
    const statusDot = pill.querySelector(".iris-pill__status");
    statusDot.classList.toggle("is-scanning", scanning);
    statusDot.classList.toggle("is-ready", ready);
    pill.setAttribute("aria-label", scanning ? t("aria.scanning") : ready ? t("aria.ready") : t("aria.openPanel"));
    panel.setAttribute("aria-busy", String(scanning));
    // The shell mounts once, so its aria labels are refreshed here: switching
    // language re-renders without re-mounting, and a stale English label would
    // contradict the translated body it announces.
    panel.setAttribute("aria-label", t("aria.panel"));

    // One polite announcement per status transition. Claim paging and history
    // toggles re-render the body constantly; those must stay silent.
    if (mountedView.announcedStatus !== state.status) {
      mountedView.announcedStatus = state.status;
      mountedView.liveRegion.textContent = announcementFor(state.status);
    }

    const closeAction = state.settings.quietMode ? "quiet-close" : "collapse";
    // Label sits outside the icon guard below: it must follow a language
    // switch even when the action itself did not change.
    headerClose.setAttribute("aria-label", state.settings.quietMode ? t("aria.closePanel") : t("aria.collapsePanel"));
    if (headerClose.dataset.action !== closeAction) {
      headerClose.dataset.action = closeAction;
      headerClose.innerHTML = icon(state.settings.quietMode ? "close" : "minus");
    }
    const settingsButton = panel.querySelector('[data-action="open-settings"]');
    settingsButton.classList.toggle("is-active", state.status === "settings");
    settingsButton.setAttribute("aria-label", t("aria.openSettings"));
    panel.querySelector('[data-action="open-faq"]').setAttribute("aria-label", t("aria.openFaq"));
    updatePanelBody();

    const faq = panel.querySelector(".faq-overlay");
    if (state.faqOpen && !faq) panel.insertAdjacentHTML("beforeend", faqOverlay());
    if (!state.faqOpen && faq) faq.remove();
    if (mountedView.pendingFaqFocus && state.faqOpen) {
      mountedView.pendingFaqFocus = false;
      panel.querySelector('.faq-modal button[data-action="close-faq"]')?.focus();
    }

    // The pill belongs to idle browsing: any check that starts elsewhere
    // (selection sync, right-click, image drop) takes it down immediately.
    if (hoverIsPending() && state.status !== "idle") stopHoverCheck();

    // The pill's drag clamp only knows the pill's own box (120x36): a pill
    // parked at the right edge fits, but the 310px panel it opens does not -
    // and a bottom-parked pill opens a panel taller than its parking spot.
    // Re-clamp against the surface that is actually visible, after the body
    // has settled to its final height.
    keepSurfaceInViewport();
  }

  function applyPositionDuringDrag(x, y) {
    const wrapper = shadow.querySelector(".iris-floating-wrap");
    if (!wrapper) return;

    wrapper.classList.add("is-positioned");
    wrapper.style.left = `${x}px`;
    wrapper.style.top = `${y}px`;
    wrapper.style.right = "auto";
    wrapper.style.bottom = "auto";
  }

  // Keeps a parked position inside the viewport for the surface that is
  // showing now. Measuring offsetWidth/offsetHeight reads layout, so the
  // enter animation and RTL direction neither skew it nor need mirroring.
  // A live drag owns its own clamp and must not be re-clamped underneath.
  function keepSurfaceInViewport() {
    if (!state.position || !mountedView || state.dragging) return;

    const { panel, pill } = mountedView;
    const surface = !panel.hidden ? panel : pill;
    const width = surface.offsetWidth;
    const height = surface.offsetHeight;
    if (!width || !height) return;

    const x = clamp(state.position.x, 8, window.innerWidth - width - 8);
    const y = clamp(state.position.y, 8, window.innerHeight - height - 8);
    if (x === state.position.x && y === state.position.y) return;

    state.position = { x, y };
    applyPositionDuringDrag(x, y);
  }

  // Screen-reader narration for the live region. Each status speaks once, on
  // transition only — render() re-runs for drags, fonts, and history toggles,
  // and repeating these would turn the panel into a chatterbox. Keys, not
  // strings: the announcement follows the panel's language.
  const STATUS_ANNOUNCEMENT_KEYS = {
    detected: "announce.detected",
    photo: "announce.photo",
    scanning: "announce.scanning",
    result: "announce.result",
    settings: "announce.settings"
  };

  function announcementFor(status) {
    if (status === "error") return state.errorMessage || t("announce.error");
    const key = STATUS_ANNOUNCEMENT_KEYS[status];
    return key ? t(key) : "";
  }

  // One-off line in the shared live region. render() only speaks on a status
  // transition, so a message that must be the *last* word after a transition —
  // "Check cancelled." — writes through here instead of through announcementFor.
  function announceDirectly(message) {
    if (!mountedView) return;
    mountedView.liveRegion.textContent = message;
  }

  function setStatus(status) {
    state.status = status;
    render();
  }

  function resetPanel() {
    if (state.selectionSyncTimer) {
      window.clearTimeout(state.selectionSyncTimer);
      state.selectionSyncTimer = null;
    }

    state.status = "idle";
    state.settingsReturnStatus = "idle";
    state.selectedText = "";
    state.claimMode = "text";
    state.selectedImage = null;
    state.result = null;
    state.claimIndex = 0;
    state.faqOpen = false;
    state.faqOpener = null;
    state.lastCheck = null;
    state.panelOpenedByAction = false;
    window.getSelection()?.removeAllRanges();
    render();
  }

  // Cancels the check the panel is presenting.
  //
  // Suppression design (the whole point of this function):
  //  * Generation — bumping state.checkGen invalidates every in-flight response
  //    flow at once: each flow captured the generation it started under and drops
  //    its arrival when it no longer matches, so a late response can neither
  //    overwrite the cancelled check's fallback state nor overtake a *newer*
  //    check that already began (the re-arm race a boolean could not close).
  //  * Abort — for the context-image pipeline, cancel also tells background.js to
  //    stop the work, so an aborted invocation pushes neither RESULT nor ERROR.
  //    The message is fire-and-forget and always sent (a text check makes it a
  //    harmless no-op), immediately on cancel: the next check is a whole human
  //    interaction away, which is the only thing keeping this single-tab abort
  //    from ever landing on a pipeline that starts *after* the cancel.
  //  * HONESTY — a response flow has no background abort of its own: IRIS_VERIFY_TEXT
  //    runs to completion server-side and only its arrival is dropped here by the
  //    generation guard. The same holds for the {ok} reply of
  //    IRIS_VERIFY_IMAGE_SOURCE (that reply carries no verdict). What the abort
  //    covers is the context-image pipeline itself, whichever flow started it.
  //  * KNOWN LIMIT — the RESULT/ERROR messages carry no id, so content-gen alone
  //    cannot tell cancelled push-flow A's RESULT from a *new* push-flow B's
  //    RESULT: A arriving while B scans matches pushFlowGen === checkGen. That
  //    case is exactly the one the background abort closes — an aborted pipeline
  //    never sends the message in the first place.
  function cancelActiveCheck() {
    if (state.status !== "scanning") return;

    state.checkGen += 1;
    sendRuntimeMessage({ type: "IRIS_CONTEXT_IMAGE_ABORT" }).catch(() => {});

    // The fallback follows the check kind that was running. A text check leaves an
    // earlier staged image in place (runTextCheck never clears it) but is a *text*
    // check, so staged text wins for it; image checks always stage their own image.
    let nextStatus = "idle";
    if (state.activeCheckKind === "text") {
      if (state.selectedText) nextStatus = "detected";
      else if (state.selectedImage) nextStatus = "photo";
    } else if (state.selectedImage) {
      nextStatus = "photo";
    } else if (state.selectedText) {
      nextStatus = "detected";
    }

    // The focused Cancel button dies with the scanning body, which would drop
    // keyboard focus to document.body. Capture where focus was before the swap.
    const hadFocusInside = Boolean(
      mountedView && shadow.activeElement && mountedView.panel.contains(shadow.activeElement)
    );

    // render() would otherwise speak the destination status ("Text detected.")
    // over the cancellation line: mark it already announced, then speak ours.
    if (mountedView) mountedView.announcedStatus = nextStatus;
    setStatus(nextStatus);
    announceDirectly(t("announce.cancelled"));

    if (hadFocusInside) handOffFocusAfterCancel(nextStatus);
  }

  // Re-homes focus the Cancel swap displaced: the restored state's primary action
  // first, then anything focusable in the panel body, then anything focusable in
  // the panel; if there is none, focus is left where it landed. Everything stays
  // inside the shadow root — document.activeElement retargets to the host, but
  // shadow.activeElement keeps tracking the real control.
  const FOCUSABLE_SELECTOR =
    'button:not([disabled]), [href], input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])';

  function handOffFocusAfterCancel(nextStatus) {
    const view = mountedView;
    if (!view) return;

    const primaryAction = { detected: "check-text", photo: "scan-image" }[nextStatus];
    const candidates = [];
    if (primaryAction) {
      const primary = view.body.querySelector(`[data-action="${primaryAction}"]`);
      if (primary) candidates.push(primary);
    }
    candidates.push(...view.body.querySelectorAll(FOCUSABLE_SELECTOR));
    candidates.push(...view.panel.querySelectorAll(FOCUSABLE_SELECTOR));

    const target = candidates.find((element) => !element.disabled && element.offsetParent !== null);
    target?.focus();
  }

  // Every entry point into the scanning state — panel check-text and image flow,
  // context-menu checks, retry, popup-triggered checks — opens a new generation
  // here, before any pre-flight validation error of its own can render, and
  // records which check kind it is so Cancel knows where to fall back to. The
  // returned generation is what a response flow compares against on arrival.
  function beginCheck(kind) {
    state.checkGen += 1;
    state.activeCheckKind = kind;
    return state.checkGen;
  }

  async function runTextCheck(text) {
    const myGen = beginCheck("text");
    state.lastCheck = null;
    const cleanText = String(text || "").trim();

    if (!cleanText) {
      state.errorMessage = t("err.noSelection");
      setStatus("error");
      return;
    }

    state.lastCheck = { kind: "text", text: cleanText };
    state.panelOpenedByAction = true;
    state.selectedText = cleanText;
    state.claimMode = "text";
    state.claimIndex = 0;
    state.faqOpen = false;
    state.collapsed = false;
    setStatus("scanning");

    try {
      const response = await sendRuntimeMessage({
        type: "IRIS_VERIFY_TEXT",
        backendUrl: state.settings.irisBackendUrl,
        debug: state.settings.irisDebugMode,
        language: state.settings.irisUiLanguage,
        text: cleanText
      });

      // Cancelled — or superseded by a newer check — while the request was in
      // flight: the payload is real, but the check it belongs to no longer
      // exists. Dropped on arrival, before it can render.
      if (myGen !== state.checkGen) return;

      if (!response?.ok) {
        throw new Error(response?.error || t("err.textResult"));
      }

      state.result = normalizeBackendResult(response.payload, cleanText, "text");
      setStatus("result");
    } catch (error) {
      if (myGen !== state.checkGen) return;

      state.errorMessage = error.message;
      setStatus("error");
    }
  }

  async function requestBackgroundImageVerification(source, imageName = t("image.selectedName"), previewDataUrl = "") {
    const myGen = beginCheck("image");
    // This flow's verdict arrives as a background push (IRIS_CONTEXT_IMAGE_*),
    // not as the response below — so it records the generation those pushes must
    // match, exactly as the IRIS_CONTEXT_IMAGE_STARTED handler does.
    state.pushFlowGen = myGen;
    state.lastCheck = null;
    const imageSource = source || {};

    if (!imageSource.dataUrl && !imageSource.url) {
      state.errorMessage = t("err.noImageData");
      setStatus("error");
      return;
    }

    state.lastCheck = {
      kind: "image-source",
      source: { ...imageSource, name: imageName },
      imageName,
      previewDataUrl
    };
    state.panelOpenedByAction = true;
    state.claimMode = "photo";
    state.selectedText = t("image.forOcr");
    state.selectedImage = {
      dataUrl: previewDataUrl || imageSource.dataUrl || "",
      name: imageName
    };
    state.result = null;
    state.claimIndex = 0;
    state.faqOpen = false;
    state.collapsed = false;
    setStatus("scanning");

    try {
      const response = await sendRuntimeMessage({
        type: "IRIS_VERIFY_IMAGE_SOURCE",
        source: {
          ...imageSource,
          name: imageName
        }
      });

      // Stale reply (cancelled or superseded): this flow already handed its
      // verdict over to the push handlers, and its generation is no longer live.
      if (myGen !== state.checkGen) return;

      if (!response?.ok) {
        throw new Error(response?.error || "IRIS could not start image verification.");
      }
    } catch (error) {
      if (myGen !== state.checkGen) return;

      failContextImageCheck(error.message);
    }
  }

  async function runImageCheck(imageDataUrl, imageName = t("image.selectedName")) {
    if (!imageDataUrl) {
      // A context-menu image check stages a URL, never a data URL, and Cancel
      // returns to the photo state for exactly that case — so the staged source
      // is the only image there is to scan. Route it through the same
      // verification path a retry uses; failing on the missing data URL would
      // strand the reader on an error for a check that is perfectly replayable.
      const staged = state.lastCheck;
      if (staged?.kind === "image-source") {
        return requestBackgroundImageVerification(staged.source, staged.imageName, staged.previewDataUrl);
      }

      state.errorMessage = t("err.noImageData");
      setStatus("error");
      return;
    }

    return requestBackgroundImageVerification({
      kind: "data_url",
      dataUrl: imageDataUrl,
      name: imageName
    }, imageName, imageDataUrl);
  }

  async function runImageUrlCheck(imageUrl) {
    return runImageUrlDropCheck(imageUrl, t("image.fromPage"));
  }

  async function runImageUrlDropCheck(imageUrl, imageName = t("image.fromPage")) {
    if (!imageUrl) {
      state.errorMessage = t("err.noImageUrl");
      setStatus("error");
      return;
    }

    return requestBackgroundImageVerification({
      kind: "url",
      url: imageUrl,
      name: imageName
    }, imageName);
  }

  function startContextImageCheck(imageUrl, imageName = t("image.selectedName")) {
    const myGen = beginCheck("context-image");
    // The context-menu check is pushed by background.js, which this file never
    // modifies. Storing the URL here lets a failed one retry through the generic
    // IRIS_VERIFY_IMAGE_SOURCE path instead of needing a new background message.
    state.lastCheck = imageUrl
      ? {
          kind: "image-source",
          source: { kind: "url", url: imageUrl, name: imageName },
          imageName,
          previewDataUrl: ""
        }
      : null;
    state.panelOpenedByAction = true;
    state.claimMode = "photo";
    state.selectedText = t("image.forOcr");
    state.selectedImage = {
      dataUrl: "",
      name: imageName || (imageUrl ? t("image.fromPage") : t("image.selectedName"))
    };
    state.result = null;
    state.claimIndex = 0;
    state.faqOpen = false;
    state.collapsed = false;
    setStatus("scanning");
    return myGen;
  }

  function finishContextImageCheck(payload) {
    // Late IRIS_CONTEXT_IMAGE_RESULT: dropped unless the push flow that was
    // recorded at IRIS_CONTEXT_IMAGE_STARTED is still the live one. The message
    // carries no id, so this comparison is the only handle on whose result it is.
    if (state.pushFlowGen !== state.checkGen) return;

    const fallbackText = payload?.ocr_text || t("image.forOcr");
    state.result = normalizeBackendResult(payload, fallbackText, "photo");
    setStatus("result");
  }

  function failContextImageCheck(message) {
    // Late IRIS_CONTEXT_IMAGE_ERROR (or a failed retry) after a cancel: dropped
    // too — a cancelled check must not flip the panel into an error state.
    if (state.pushFlowGen !== state.checkGen) return;

    state.panelOpenedByAction = true;
    state.claimMode = "photo";
    state.selectedText = t("image.forOcr");
    state.selectedImage = state.selectedImage || {
      dataUrl: "",
      name: t("image.selectedName")
    };
    state.collapsed = false;
    // Background-originated failures arrive in English (the worker has no i18n):
    // the one known IRIS-owned message is mapped to the reader's language, and
    // anything else — backend wording included — passes through untouched.
    state.errorMessage = message && message !== "IRIS could not verify the selected image."
      ? message
      : t("err.verifyImage");
    setStatus("error");
  }

  function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error(t("err.readImage")));
      reader.readAsDataURL(file);
    });
  }

  function isImageFile(file) {
    if (!file) return false;
    const fileType = String(file.type || "").toLowerCase();
    const supportedTypes = new Set([
      "image/png",
      "image/jpeg",
      "image/jpg",
      "image/webp",
      "image/bmp",
      "image/tiff"
    ]);
    if (fileType) return supportedTypes.has(fileType);

    return /\.(png|jpe?g|webp|bmp|tiff?)$/i.test(file.name || "");
  }

  function dragHasType(event, type) {
    return Array.from(event.dataTransfer?.types || []).includes(type);
  }

  function dragHasLocalFiles(event) {
    return dragHasType(event, "Files");
  }

  function dragMayContainWebImage(event) {
    return (
      dragHasType(event, "text/uri-list") ||
      dragHasType(event, "text/html") ||
      dragHasType(event, "text/plain")
    );
  }

  function dragHasDropPayload(event) {
    return dragHasLocalFiles(event) || dragMayContainWebImage(event);
  }

  function dragMayContainImage(event) {
    if (dragMayContainWebImage(event)) return true;
    if (!dragHasLocalFiles(event)) return false;

    const items = Array.from(event.dataTransfer?.items || []);
    if (!items.length) return true;

    return items.some((item) => (
      item.kind === "file" &&
      (!item.type || (
        String(item.type).startsWith("image/") &&
        String(item.type).toLowerCase() !== "image/gif"
      ))
    ));
  }

  function getDroppedImageFile(dataTransfer) {
    return Array.from(dataTransfer?.files || []).find(isImageFile) || null;
  }

  function normalizeDroppedUrl(value) {
    const candidate = String(value || "").trim();
    if (!candidate) return "";
    if (/^data:image\//i.test(candidate)) return candidate;
    if (/^blob:/i.test(candidate)) return candidate;

    try {
      const url = new URL(candidate, document.baseURI);
      if (!["http:", "https:"].includes(url.protocol)) return "";
      return url.href;
    } catch (_error) {
      return "";
    }
  }

  function hasSupportedImageExtension(value) {
    return /\.(png|jpe?g|webp|bmp|tiff?)(?:[?#].*)?$/i.test(String(value || ""));
  }

  function hasUnsupportedMediaExtension(value) {
    return /\.(gif|mp4|m4v|mov|avi|webm|mkv|m3u8)(?:[?#].*)?$/i.test(String(value || ""));
  }

  function isUnsupportedDroppedSource(value) {
    const source = String(value || "");
    return /^data:image\/gif[;,]/i.test(source) || hasUnsupportedMediaExtension(source);
  }

  function firstUriListUrl(value) {
    return String(value || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .find((line) => line && !line.startsWith("#")) || "";
  }

  function firstSrcsetUrl(value) {
    const firstCandidate = String(value || "").split(",")[0] || "";
    return firstCandidate.trim().split(/\s+/)[0] || "";
  }

  function extractImageUrlFromHtml(html) {
    if (!html) return "";

    const doc = new DOMParser().parseFromString(html, "text/html");
    const image = doc.querySelector("img[src], image[href], image[xlink\\:href]");
    const source = doc.querySelector('picture source[srcset], source[type^="image/"][srcset]');
    const ogImage = doc.querySelector('meta[property="og:image"], meta[name="twitter:image"]');

    const candidates = [
      image?.getAttribute("src"),
      image?.getAttribute("href"),
      image?.getAttribute("xlink:href"),
      firstSrcsetUrl(source?.getAttribute("srcset")),
      ogImage?.getAttribute("content"),
      ...Array.from(html.matchAll(/url\((['"]?)(.*?)\1\)/gi)).map((match) => match[2]),
    ];

    for (const candidate of candidates) {
      const url = normalizeDroppedUrl(candidate);
      if (url) return url;
    }

    return "";
  }

  function extractImageUrlFromPlainText(value) {
    const text = String(value || "").trim();
    if (!text) return "";

    const directUrl = normalizeDroppedUrl(text);
    if (directUrl) return directUrl;

    const urlMatch = text.match(/https?:\/\/[^\s"'<>]+/i);
    return normalizeDroppedUrl(urlMatch?.[0]);
  }

  function getDroppedImageUrl(dataTransfer) {
    const uriListUrl = normalizeDroppedUrl(firstUriListUrl(dataTransfer?.getData("text/uri-list")));
    const htmlUrl = extractImageUrlFromHtml(dataTransfer?.getData("text/html"));
    const plainTextUrl = extractImageUrlFromPlainText(dataTransfer?.getData("text/plain"));

    // Right-click's srcUrl is always a real image, so drag is held to the same
    // bar: uri-list wins only when it IS an image (a data/blob URL or a file
    // with an image extension). Facebook drags put the photo's PAGE link there,
    // and checking that downloads HTML instead of image bytes — a page link
    // falls through to the HTML fragment, which carries the actual <img src>
    // the right-click path would have seen.
    const uriListIsImage = uriListUrl && (
      /^data:image\//i.test(uriListUrl) ||
      /^blob:/i.test(uriListUrl) ||
      hasSupportedImageExtension(uriListUrl)
    );
    if (uriListIsImage) return uriListUrl;
    if (htmlUrl) return htmlUrl;

    return hasSupportedImageExtension(plainTextUrl) ? plainTextUrl : "";
  }

  async function readBlobUrlAsDataUrl(url) {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Image download failed with HTTP ${response.status}.`);
    }

    const blob = await response.blob();
    const type = String(blob.type || "").toLowerCase();
    if (type && (!type.startsWith("image/") || type === "image/gif")) {
      throw new Error(t("drop.error"));
    }

    return readFileAsDataUrl(blob);
  }

  function setDropTargetActive(active) {
    state.dropActive = active;
    for (const surface of root.querySelectorAll(".iris-panel, .iris-pill")) {
      surface.classList.toggle("is-drop-target", active);
    }
  }

  function showImageDropError(message) {
    state.panelOpenedByAction = true;
    state.collapsed = false;
    state.errorMessage = message;
    setStatus("error");
  }

  async function handleDroppedImageFile(file) {
    if (!file) {
      showImageDropError(t("drop.error"));
      return;
    }

    try {
      const dataUrl = await readFileAsDataUrl(file);
      await runImageCheck(dataUrl, file.name || "Dropped image");
    } catch (error) {
      showImageDropError(error.message);
    }
  }

  async function handleDroppedImageUrl(url) {
    if (!url) {
      showImageDropError(t("drop.error"));
      return;
    }

    try {
      if (isUnsupportedDroppedSource(url)) {
        showImageDropError(t("drop.error"));
        return;
      }

      if (/^data:image\//i.test(url)) {
        await runImageCheck(url, "Dragged image");
        return;
      }

      if (/^blob:/i.test(url)) {
        const dataUrl = await readBlobUrlAsDataUrl(url);
        await runImageCheck(dataUrl, "Dragged image");
        return;
      }

      await runImageUrlDropCheck(url, "Dragged image");
    } catch (error) {
      showImageDropError(error.message);
    }
  }

  function handleDroppedImage(dataTransfer) {
    const files = Array.from(dataTransfer?.files || []);
    if (files.length) {
      const file = files.find(isImageFile);
      if (file) {
        handleDroppedImageFile(file);
        return;
      }

      showImageDropError(t("drop.error"));
      return;
    }

    const file = getDroppedImageFile(dataTransfer);
    if (file) {
      handleDroppedImageFile(file);
      return;
    }

    handleDroppedImageUrl(getDroppedImageUrl(dataTransfer));
  }

  async function handleImageFile(file) {
    if (!file) return;

    try {
      const dataUrl = await readFileAsDataUrl(file);
      state.panelOpenedByAction = true;
      state.selectedImage = {
        dataUrl,
        name: file.name || t("image.selectedName")
      };
      state.claimMode = "photo";
      state.selectedText = t("image.forOcr");
      state.claimIndex = 0;
      state.collapsed = false;
      setStatus("photo");
    } catch (error) {
      state.errorMessage = error.message;
      setStatus("error");
    }
  }

  function updateDetectedText(text) {
    state.selectedText = text;
    const claimBox = shadow.querySelector('[data-role="detected-claim"]');
    if (claimBox) {
      claimBox.textContent = truncateText(text);
    }
  }

  function canSyncPageSelection() {
    if (state.settings.quietMode) return false;
    if (!state.settings.irisPanelEnabled) return;
    if (["scanning", "result", "settings", "photo"].includes(state.status)) return;

    return true;
  }

  function syncPageSelection() {
    state.selectionSyncTimer = null;

    if (!canSyncPageSelection()) return;

    if (Date.now() < state.ignoreInternalSelectionUntil) {
      clearIrisSelection();
      return;
    }

    const selectionInfo = getSelectionInfo();
    if (selectionInfo.insideIris) {
      clearIrisSelection();
      return;
    }

    const text = selectionInfo.text;
    if (text) {
      if (
        state.status === "detected" &&
        state.claimMode === "text" &&
        state.selectedText === text
      ) {
        return;
      }

      state.claimMode = "text";
      state.panelOpenedByAction = true;
      if (state.status === "detected") {
        updateDetectedText(text);
      } else {
        state.selectedText = text;
        state.status = "detected";
        render();
      }
      return;
    }

    if (
      state.status === "detected" &&
      !state.pagePointerDown &&
      Date.now() > state.ignoreSelectionClearUntil
    ) {
      state.selectedText = "";
      state.claimMode = "text";
      state.status = "idle";
      state.panelOpenedByAction = false;
      render();
    }
  }

  function scheduleSelectionSync(delay = 90) {
    if (!canSyncPageSelection()) return;

    if (state.selectionSyncTimer) {
      window.clearTimeout(state.selectionSyncTimer);
    }

    state.selectionSyncTimer = window.setTimeout(syncPageSelection, delay);
  }

  function handleSelectionChange() {
    stopHoverForSelection();
    scheduleSelectionSync(state.pagePointerDown ? 16 : 80);
  }

  // Hover to check: optional (default off). Resting the cursor on a paragraph
  // for a beat fades in a pill; clicking it is an explicit check request and
  // lands in the same "detected" state as a text selection — no auto-run.
  //
  // The pill lives directly under `shadow`, NOT inside `root`: render() clears
  // root's children whenever the panel should not be shown, and hover must
  // survive exactly that (quiet idle / panel disabled).
  const hoverState = {
    timer: 0,
    raf: 0,
    pending: null,
    // Last mousemove seen, kept for the scroll-settle re-probe below: a wheel
    // scroll leaves the cursor parked, so no new mousemove arrives to re-arm on.
    lastEvent: null,
    settleTimer: 0,
    block: null,
    kind: "text",
    text: "",
    imageSrc: "",
    anchorX: 0,
    anchorY: 0,
    visible: false
  };
  // Tags that can legitimately BE the text unit. Semantic ones first (p, li,
  // ...), but social UIs like Facebook render captions as bare
  // <div dir="auto"><span>...</span></div> trees with no <p> anywhere —
  // container tags count too, gated by the word check below.
  const HOVER_BLOCK_TAGS = new Set([
    "P", "LI", "H1", "H2", "H3", "H4", "H5", "H6",
    "BLOCKQUOTE", "TD", "TH", "DD", "DT", "FIGCAPTION",
    "DIV", "SECTION", "ARTICLE", "FIGURE", "MAIN", "ASIDE",
    "TR", "UL", "OL", "DL", "TABLE"
  ]);
  const HOVER_INTERACTIVE_SELECTOR = "a, button, input, textarea, select, summary, label, video, audio";
  const HOVER_DWELL_MS = 400;
  const HOVER_MIN_WORDS = 15;
  const HOVER_DRIFT_PX = 8;
  // Padding around the armed block (and the smallest post image worth
  // checking): the pill lives in this neighborhood, so pointer transit
  // across whitespace, images, or short text keeps it alive.
  const HOVER_NEAR_PX = 96;
  // How long the page must stay quiet after a scroll before the cursor's
  // position is probed again. Dynamic feeds keep emitting scroll events while
  // the pointer never moves; only the settled run can arm.
  const HOVER_SCROLL_SETTLE_MS = 150;

  const hoverPill = document.createElement("button");
  hoverPill.type = "button";
  hoverPill.className = "iris-hover-pill iris-extension-shell";
  hoverPill.setAttribute("aria-label", "Check this paragraph with IRIS");
  hoverPill.innerHTML = `${irisEye(16)}<span>Check with IRIS</span>`;
  shadow.append(hoverPill);
  const hoverPillLabel = hoverPill.querySelector("span");

  function hoverIsPending() {
    return hoverState.visible || Boolean(hoverState.timer);
  }

  function hideHoverPill() {
    if (!hoverState.visible) return;
    hoverState.visible = false;
    hoverPill.classList.remove("is-visible");
  }

  function cancelHoverDwell() {
    if (hoverState.timer) window.clearTimeout(hoverState.timer);
    hoverState.timer = 0;
    hoverState.block = null;
    hoverState.kind = "text";
    hoverState.text = "";
    hoverState.imageSrc = "";
  }

  function stopHoverCheck() {
    // A queued animation frame has no owner but this function: processHoverMove
    // clears it only if the browser actually runs the callback, and rendering is
    // suspended while the window is locked or occluded — if that frame is
    // dropped, the raf gate in onHoverMouseMove wedges every future mousemove
    // until a reload. Cancel it here, before the pending check below: an armed
    // frame with no timer yet is not "pending", but it is exactly the wedge.
    if (hoverState.raf) {
      window.cancelAnimationFrame(hoverState.raf);
      hoverState.raf = 0;
      hoverState.pending = null;
    }
    // A scheduled settle re-probe is an arm in flight; explicit dismissal
    // (Escape, blur, leaving the region) cancels it too. The scroll listener
    // clears this before scheduling its own, so its probe survives.
    if (hoverState.settleTimer) {
      window.clearTimeout(hoverState.settleTimer);
      hoverState.settleTimer = 0;
    }
    if (!hoverIsPending()) return;
    hideHoverPill();
    cancelHoverDwell();
  }

  // Coming back to the window must not depend on a fresh mousemove: alt-tabbing
  // away and returning with the cursor parked fires no mousemove at all, and a
  // frame queued when rendering suspended may never run. Re-probe the last known
  // pointer position instead — the dwell restarts against whatever is under the
  // cursor now. Explicit stops (blur, visibility-hidden) clear timers but keep
  // lastEvent, so there is always a position to come back to.
  function reprobeHoverAfterReturn() {
    if (hoverState.raf || hoverState.settleTimer) return;
    if (!state.settings.hoverCheck || !hoverState.lastEvent) return;
    hoverState.pending = hoverState.lastEvent;
    hoverState.raf = window.requestAnimationFrame(processHoverMove);
  }

  function showHoverPill() {
    hoverState.timer = 0;
    const armed =
      hoverState.kind === "image" ? Boolean(hoverState.imageSrc) : Boolean(hoverState.text);
    if (!armed || !state.settings.hoverCheck || state.status !== "idle") {
      cancelHoverDwell();
      return;
    }

    const forImage = hoverState.kind === "image";
    hoverPillLabel.textContent = forImage ? t("hover.pillImage") : t("hover.pill");
    hoverPill.setAttribute(
      "aria-label",
      forImage ? t("hover.pillImage") : t("hover.ariaParagraph")
    );
    hoverPill.dataset.theme = resolveTheme();
    hoverPill.style.setProperty("--iris-scale", activeFontScale());
    // Measure before the class flip: the pill is laid out while hidden, so
    // the read is honest and also flushes the style writes above.
    const width = hoverPill.offsetWidth || 170;
    const height = hoverPill.offsetHeight || 34;
    const left = Math.max(8, Math.min(hoverState.anchorX + 12, window.innerWidth - width - 8));
    const top = Math.max(8, Math.min(hoverState.anchorY + 12, window.innerHeight - height - 8));
    hoverPill.style.left = `${left}px`;
    hoverPill.style.top = `${top}px`;
    hoverState.visible = true;
    hoverPill.classList.add("is-visible");
  }

  hoverPill.addEventListener("click", () => {
    const kind = hoverState.kind;
    const text = hoverState.text;
    const imageSrc = hoverState.imageSrc;
    stopHoverCheck();

    if (kind === "image") {
      if (imageSrc) runImageUrlCheck(imageSrc);
      return;
    }

    if (!text) return;

    state.claimMode = "text";
    state.panelOpenedByAction = true;
    // Every other check entry point (right-click, selection sync, image drop)
    // re-opens a collapsed panel. Without this, clicking the hover pill while
    // the panel is collapsed flips status to "detected" but leaves the panel
    // hidden — the collapsed pill shows a ready dot and nothing else.
    state.collapsed = false;
    state.selectedText = text;
    state.status = "detected";
    // The click can clear the page selection. Without this window a late
    // selection-sync sees status "detected" + empty text and bounces the
    // panel straight back to idle.
    state.ignoreSelectionClearUntil = Date.now() + 800;
    render();
  });

  function onHoverMouseMove(event) {
    if (scriptDead) return;
    hoverState.lastEvent = event;
    if (!state.settings.hoverCheck) {
      if (hoverIsPending()) stopHoverCheck();
      return;
    }

    hoverState.pending = event;
    if (hoverState.raf) return;
    hoverState.raf = window.requestAnimationFrame(processHoverMove);
  }

  // Deepest-first ancestor walk: the first text-bearing block decides.
  // A span carrying the whole caption is skipped (not a block), so its
  // <div dir="auto"> parent wins on Facebook. Climbing PAST a real text
  // unit that is merely too short would swallow post containers (author,
  // timestamp, caption in one blob) — so a small text unit stops the walk.
  function findHoverBlock(start) {
    for (let el = start; el && el.nodeType === Node.ELEMENT_NODE; el = el.parentElement) {
      if (el === document.body || el === document.documentElement) return null;
      if (!HOVER_BLOCK_TAGS.has(el.tagName)) continue;

      const text = (el.textContent || "").replace(/\s+/g, " ").trim();
      if (!text) continue; // structure-only box, keep climbing
      if (text.split(/\s+/).length < HOVER_MIN_WORDS) return null;
      return { element: el, text };
    }
    return null;
  }

  function pointRectDistance(x, y, rect) {
    const dx = Math.max(rect.left - x, 0, x - rect.right);
    const dy = Math.max(rect.top - y, 0, y - rect.bottom);
    return Math.hypot(dx, dy);
  }

  // A post photo worth checking, not an avatar: rendered at least 120px in
  // both directions (Facebook profile pictures sit at 40–56px; emoji, badges,
  // and verification marks are smaller still).
  function checkableHoverImage(img) {
    const src = img.currentSrc || img.src;
    if (!src || !img.isConnected) return null;
    const rect = img.getBoundingClientRect();
    if (rect.width < 120 || rect.height < 120) return null;
    return { element: img, kind: "image", src, text: "" };
  }

  function armHoverDwell(arm, x, y) {
    if (hoverState.timer) window.clearTimeout(hoverState.timer);
    hoverState.timer = 0;
    hideHoverPill();
    hoverState.block = arm.element;
    hoverState.kind = arm.kind || "text";
    hoverState.text = arm.text || "";
    hoverState.imageSrc = arm.src || "";
    hoverState.anchorX = x;
    hoverState.anchorY = y;
    hoverState.timer = window.setTimeout(showHoverPill, HOVER_DWELL_MS);
  }

  function processHoverMove() {
    hoverState.raf = 0;
    const event = hoverState.pending;
    hoverState.pending = null;
    if (!event || !state.settings.hoverCheck) return;

    // Composed path, not event.target: mouse events over the shadow UI
    // retarget to `host`, which would hide the pill as the cursor crosses
    // onto it. Over the pill itself it stays; over any other IRIS surface
    // it yields.
    const path = typeof event.composedPath === "function" ? event.composedPath() : [];
    if (hoverState.visible && path.includes(hoverPill)) return;
    if (path.includes(host)) {
      stopHoverCheck();
      return;
    }

    if (state.status !== "idle") {
      stopHoverCheck();
      return;
    }

    const selection = window.getSelection();
    if (selection && !selection.isCollapsed && selection.toString().trim()) {
      stopHoverCheck();
      return;
    }

    const x = event.clientX;
    const y = event.clientY;

    // Region = the block or image the dwell armed on, padded by
    // HOVER_NEAR_PX. It answers one question: is the pointer still in the
    // neighborhood the pill belongs to? Long captions count as one region
    // (rect covers them end to end); the pill sitting +12px off-anchor stays
    // comfortably inside it.
    const region = hoverState.block ? hoverState.block.getBoundingClientRect() : null;
    const nearRegion = region ? pointRectDistance(x, y, region) <= HOVER_NEAR_PX : false;

    if (hoverState.visible) {
      // Pill up: whitespace, images, links, and short text inside (or just
      // around) the region keep it — only wandering off cancels it. Every
      // explicit trigger (selection, scroll, Escape, IRIS UI, status) has
      // already been handled above or in its own listener.
      if (!nearRegion) stopHoverCheck();
      return;
    }

    // An image under the pointer wins: caret probing cannot see images, and
    // elementFromPoint is authoritative for what the cursor is actually on.
    const under = document.elementFromPoint(x, y);
    const img = under && under.tagName === "IMG" ? under : under && under.closest ? under.closest("img") : null;
    const image = img ? checkableHoverImage(img) : null;

    let arm = image;
    if (!arm) {
      let hit = null;
      if (typeof document.caretRangeFromPoint === "function") {
        const range = document.caretRangeFromPoint(x, y);
        const node = range && range.startContainer;
        hit = node && (node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement);
      } else if (typeof document.caretPositionFromPoint === "function") {
        const position = document.caretPositionFromPoint(x, y);
        const node = position && position.offsetNode;
        hit = node && (node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement);
      }

      if (hit && (nodeBelongsToIris(hit) || hit.closest(HOVER_INTERACTIVE_SELECTOR))) {
        // Resting on a link or control: no arm, and the dwell does not wait
        // it out — but a pill already up inside the region stays up.
        if (!nearRegion) stopHoverCheck();
        return;
      }
      if (hit) arm = findHoverBlock(hit);
    }

    if (!arm) {
      // Whitespace/short-text transit inside an armed region keeps an
      // in-flight dwell (line breaks no longer reset it); outside every
      // region there is nothing to keep.
      if (!nearRegion) stopHoverCheck();
      return;
    }

    const sameTarget = arm.element === hoverState.block;
    const drifted = Math.hypot(x - hoverState.anchorX, y - hoverState.anchorY) > HOVER_DRIFT_PX;
    if (sameTarget && hoverState.timer && !drifted) return;

    armHoverDwell(arm, x, y);
  }

  function stopHoverForSelection() {
    if (!hoverIsPending()) return;
    const selection = window.getSelection();
    if (selection && !selection.isCollapsed && selection.toString().trim()) stopHoverCheck();
  }

  async function saveQuickSetting(key, value) {
    state.settings[key] = value;
    await writeSyncStorage({ [key]: value });
    render();
  }

  // The FAQ is a real modal (role=dialog, aria-modal): focus moves in on open,
  // Tab cycles inside it, Escape closes it, and focus returns to the opener.
  // Without the trap, everything behind the overlay stays tabbable and
  // aria-modal="true" is a promise the dialog does not keep.
  function closeFaq() {
    const opener = state.faqOpener;
    state.faqOpen = false;
    state.faqOpener = null;
    render();
    if (opener?.isConnected) opener.focus();
  }

  function handleKeydown(event) {
    if (!state.faqOpen) return;

    if (event.key === "Escape") {
      event.preventDefault();
      closeFaq();
      return;
    }

    if (event.key !== "Tab") return;

    const modal = shadow.querySelector(".faq-modal");
    if (!modal) return;

    const focusable = Array.from(
      modal.querySelectorAll('button, [href], input, select, textarea, summary, [tabindex]:not([tabindex="-1"])')
    ).filter((node) => !node.disabled && node.getClientRects().length > 0);

    if (!focusable.length) return;

    const active = shadow.activeElement;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (event.shiftKey) {
      if (active === first || !modal.contains(active)) {
        event.preventDefault();
        last.focus();
      }
    } else if (active === last || !modal.contains(active)) {
      event.preventDefault();
      first.focus();
    }
  }

  function handleClick(event) {
    const target = event.target;
    const actionTarget = target.closest?.("[data-action]");
    if (!actionTarget) return;

    const action = actionTarget.dataset.action;
    if (state.suppressClick) {
      event.preventDefault();
      return;
    }

    if (action === "expand") {
      state.panelOpenedByAction = true;
      state.collapsed = false;
      render();
      return;
    }

    if (action === "collapse") {
      if (state.settings.quietMode) {
        resetPanel();
        return;
      }

      state.collapsed = true;
      render();
      return;
    }

    if (action === "quiet-close") {
      resetPanel();
      return;
    }

    if (action === "check-text") {
      runTextCheck(state.selectedText || getCleanSelection());
      return;
    }

    if (action === "upload-image") {
      shadow.getElementById("iris-image-input")?.click();
      return;
    }

    if (action === "scan-image") {
      runImageCheck(state.selectedImage?.dataUrl, state.selectedImage?.name);
      return;
    }

    if (action === "cancel-image") {
      resetPanel();
      return;
    }

    if (action === "cancel-check") {
      cancelActiveCheck();
      return;
    }

    if (action === "retry") {
      const last = state.lastCheck;
      if (!last) return;

      if (last.kind === "text") {
        runTextCheck(last.text);
      } else if (last.kind === "image-source") {
        requestBackgroundImageVerification(last.source, last.imageName, last.previewDataUrl);
      }
      return;
    }

    if (action === "reset") {
      resetPanel();
      return;
    }

    if (action === "prev-claim") {
      state.claimIndex = Math.max(0, state.claimIndex - 1);
      render();
      return;
    }

    if (action === "next-claim") {
      const max = Math.max(0, (state.result?.claims?.length || 1) - 1);
      state.claimIndex = Math.min(max, state.claimIndex + 1);
      render();
      return;
    }

    if (action === "open-settings") {
      state.settingsReturnStatus = state.status === "settings" ? state.settingsReturnStatus : state.status;
      state.status = "settings";
      state.faqOpen = false;
      render();
      return;
    }

    if (action === "close-settings") {
      if (
        state.settings.quietMode &&
        ["idle", "detected"].includes(state.settingsReturnStatus || "idle")
      ) {
        resetPanel();
        return;
      }

      state.status = state.settingsReturnStatus || "idle";
      render();
      return;
    }

    if (action === "toggle-theme") {
      const nextTheme = resolveTheme() === "dark" ? "light" : "dark";
      saveQuickSetting("irisTheme", nextTheme);
      return;
    }

    if (action === "toggle-quiet-mode") {
      const nextQuiet = !state.settings.quietMode;
      saveQuickSetting("quietMode", nextQuiet);
      // The Quiet nudge: turning Quiet ON switches Hover to check OFF (the
      // setting the Quiet copy promises to suppress) and records that the
      // nudge — not the reader — did it. Turning Quiet OFF gives back
      // exactly what the nudge took; a hover the reader changed by hand
      // while Quiet was on clears the record and wins.
      if (nextQuiet && state.settings.hoverCheck) {
        saveQuickSetting("hoverCheck", false);
        saveQuickSetting("hoverSuppressedByQuiet", true);
      } else if (!nextQuiet && state.settings.hoverSuppressedByQuiet) {
        saveQuickSetting("hoverCheck", true);
        saveQuickSetting("hoverSuppressedByQuiet", false);
      }
      return;
    }

    if (action === "toggle-hover-check") {
      saveQuickSetting("hoverCheck", !state.settings.hoverCheck);
      // Any hand-made choice owns the setting from here on — the nudge's
      // restore no longer applies.
      if (state.settings.hoverSuppressedByQuiet) saveQuickSetting("hoverSuppressedByQuiet", false);
      return;
    }

    if (action === "set-font") {
      saveQuickSetting("irisFontSize", actionTarget.dataset.value || "default");
      return;
    }

    if (action === "open-faq") {
      // Remember what opened the dialog: focus must land inside the modal now
      // and come back to this button when it closes.
      state.faqOpener = actionTarget;
      state.faqOpen = true;
      render();
      shadow.querySelector(".faq-modal .iris-icon-button")?.focus();
      return;
    }

    if (action === "close-faq") {
      if (actionTarget.classList.contains("faq-overlay") && target.closest?.(".faq-modal")) return;
      closeFaq();
      return;
    }

    if (action === "open-options") {
      // Best effort only: a rejection here (extension reloaded, tab restricted)
      // must not surface as an uncaught error in the page console.
      sendRuntimeMessage({ type: "IRIS_OPEN_OPTIONS" }).catch(() => {});
      return;
    }

    if (action === "show-more-sources") {
      // Unfolding in place keeps the panel, the scroll position, and the focused card
      // alive; rebuilding the result would throw all three away.
      const list = actionTarget.closest(".source-list");
      for (const card of list?.querySelectorAll(".source-card--collapsed") || []) {
        card.classList.remove("source-card--collapsed");
      }
      actionTarget.remove();
      return;
    }

    if (action === "show-more-history-sources") {
      const list = actionTarget.closest(".recent-check__source-list");
      for (const link of list?.querySelectorAll(".recent-check__source--collapsed") || []) {
        link.classList.remove("recent-check__source--collapsed");
      }
      actionTarget.remove();
      return;
    }

    if (action === "toggle-recent-checks") {
      state.recentChecksOpen = !state.recentChecksOpen;
      const section = actionTarget.closest(".recent-checks");
      if (!section) {
        render();
        return;
      }
      section.classList.toggle("is-open", state.recentChecksOpen);
      actionTarget.setAttribute("aria-expanded", String(state.recentChecksOpen));
      section.querySelector(".recent-checks__list")?.remove();
      section.querySelector(".recent-checks__see-all")?.remove();
      if (state.recentChecksOpen) {
        section.insertAdjacentHTML("beforeend", recentChecksBody());
      }
      // Keep the render cache aligned with the live DOM so the next render()
      // still detects real changes (for example history clearing while open).
      mountedView.bodyMarkup = bodyForStatus();
      return;
    }

    if (action === "toggle-recent-check") {
      // Toggled in place: a re-render here would drop every row the reader already
      // opened, and parsing every stored payload up front would do work for rows
      // nobody ever opens.
      const summary = actionTarget;
      const detail = summary.nextElementSibling;
      if (!detail) return;

      if (!detail.innerHTML) {
        const index = Number(summary.dataset.index);
        detail.innerHTML =
          Number.isInteger(index) && state.history[index]
            ? historyDetailMarkup(state.history[index])
            : "";
      }

      const expanded = summary.getAttribute("aria-expanded") === "true";
      summary.setAttribute("aria-expanded", String(!expanded));
      detail.hidden = expanded;
      return;
    }

    if (action === "open-history") {
      sendRuntimeMessage({ type: "IRIS_OPEN_OPTIONS" }).catch(() => {});
      return;
    }

    if (action === "open-source") {
      const url = actionTarget.dataset.url;
      if (isValidHttpUrl(url)) window.open(url, "_blank", "noopener,noreferrer");
    }
  }

  function handleChange(event) {
    if (event.target?.id === "iris-image-input") {
      handleImageFile(event.target.files?.[0]);
      event.target.value = "";
    } else if (event.target?.matches?.('select[data-setting="irisUiLanguage"]')) {
      const value = event.target.value;
      const valid = IRIS_LANGUAGES.some((language) => language.code === value);
      saveQuickSetting("irisUiLanguage", valid ? value : "en");
    }
  }

  function handleLocalImageDragEnter(event) {
    if (!dragHasDropPayload(event)) return;

    event.preventDefault();
    event.stopPropagation();
    state.dropDepth += 1;
    setDropTargetActive(dragMayContainImage(event));
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
  }

  function handleLocalImageDragOver(event) {
    if (!dragHasDropPayload(event)) return;

    event.preventDefault();
    event.stopPropagation();
    setDropTargetActive(dragMayContainImage(event));
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
  }

  function handleLocalImageDragLeave(event) {
    if (!dragHasDropPayload(event)) return;

    event.preventDefault();
    event.stopPropagation();
    state.dropDepth = Math.max(0, state.dropDepth - 1);
    if (state.dropDepth === 0) setDropTargetActive(false);
  }

  function handleLocalImageDrop(event) {
    if (!dragHasDropPayload(event)) return;

    event.preventDefault();
    event.stopPropagation();
    state.dropDepth = 0;
    setDropTargetActive(false);
    handleDroppedImage(event.dataTransfer);
    hideQuietDropTarget();
  }

  // Quiet idle (and a hidden panel) unmount every surface, so a drag over the
  // page would have nowhere to land: the drop listeners live on root, and root
  // is empty. The pad mounts only while an image-shaped drag is active and no
  // IRIS surface exists; the drop itself rides the normal root handlers, so a
  // landing here behaves exactly like a landing on the panel.
  function dragIsImageCandidate(event) {
    // Image drags carry uri-list (the photo link) or local Files. A text
    // selection carries only text/plain + text/html and must never raise the
    // pad; GIF files stay out with the rest of the unsupported set.
    if (dragHasLocalFiles(event)) return dragMayContainImage(event);
    return dragHasType(event, "text/uri-list");
  }

  function mountQuietDropTarget() {
    root.innerHTML = `
      <div class="iris-quiet-drop iris-extension-shell" role="group" aria-label="${t("drop.quietTarget")}">
        ${icon("image")}
        <span>${t("drop.quietTarget")}</span>
      </div>
    `;
    const target = root.querySelector(".iris-quiet-drop");
    if (!target) return;
    target.dataset.theme = resolveTheme();
    target.style.setProperty("--iris-scale", activeFontScale());
  }

  function hideQuietDropTarget() {
    if (!state.quietDropActive) return;
    state.quietDropActive = false;
    if (!mountedView) root.replaceChildren();
  }

  function handleDocumentDragEnter(event) {
    // mountedView covers a mounted pill/panel; shouldRenderPanel() covers the
    // moment a surface is due but not yet mounted - the pad must never race it.
    if (scriptDead || mountedView || shouldRenderPanel()) return;
    if (!dragIsImageCandidate(event)) return;
    if (state.quietDropActive && root.querySelector(".iris-quiet-drop")) return;
    state.quietDropActive = true;
    mountQuietDropTarget();
  }

  function preserveSelectionForPanelInteraction() {
    const ignoreUntil = Date.now() + 800;
    state.ignoreSelectionClearUntil = ignoreUntil;
    state.ignoreInternalSelectionUntil = ignoreUntil;
    clearIrisSelection();
  }

  function handlePagePointerDown(event) {
    if (event.composedPath?.().includes(host)) return;

    state.pagePointerDown = true;
  }

  function handlePagePointerUp() {
    if (!state.pagePointerDown) return;

    state.pagePointerDown = false;
    scheduleSelectionSync(0);
  }

  function startDrag(event) {
    const handle = event.target.closest?.("[data-drag-handle]");
    if (!handle) return;

    const interactive = event.target.closest?.("button,a,input,select,textarea");
    if (interactive && interactive !== handle) return;

    const wrapper = shadow.querySelector(".iris-floating-wrap");
    if (!wrapper) return;

    const rect = wrapper.getBoundingClientRect();
    state.dragging = {
      pointerId: event.pointerId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      startX: event.clientX,
      startY: event.clientY,
      width: rect.width,
      height: rect.height,
      moved: false,
      handle
    };

    handle.setPointerCapture?.(event.pointerId);
    handle.closest(".iris-panel, .iris-pill")?.classList.add("is-dragging");
    event.preventDefault();
  }

  function moveDrag(event) {
    const drag = state.dragging;
    if (!drag || event.pointerId !== drag.pointerId) return;

    const distance = Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY);
    if (distance > 4) drag.moved = true;

    const x = clamp(event.clientX - drag.offsetX, 8, window.innerWidth - drag.width - 8);
    const y = clamp(event.clientY - drag.offsetY, 8, window.innerHeight - drag.height - 8);
    state.position = { x, y };
    applyPositionDuringDrag(x, y);
  }

  async function endDrag(event) {
    const drag = state.dragging;
    if (!drag || event.pointerId !== drag.pointerId) return;

    drag.handle?.releasePointerCapture?.(event.pointerId);
    state.suppressClick = drag.moved;
    state.dragging = null;

    for (const surface of root.querySelectorAll(".iris-panel, .iris-pill")) {
      surface.classList.remove("is-dragging");
    }

    if (state.position) {
      const positionToSave = { ...state.position };
      const key = positionStorageKey();
      state.pendingPositionSave = positionToSave;
      if (key) {
        await writeSessionStorage({ [key]: positionToSave });
      }
      window.setTimeout(() => {
        if (positionsMatch(state.pendingPositionSave, positionToSave)) {
          state.pendingPositionSave = null;
        }
      }, 1000);
    }

    window.setTimeout(() => {
      state.suppressClick = false;
    }, 0);
  }

  root.addEventListener("selectstart", (event) => {
    event.preventDefault();
    clearIrisSelection();
  }, true);
  root.addEventListener("pointerdown", preserveSelectionForPanelInteraction, true);
  root.addEventListener("pointerup", preserveSelectionForPanelInteraction, true);
  root.addEventListener("pointercancel", preserveSelectionForPanelInteraction, true);
  root.addEventListener("click", handleClick);
  shadow.addEventListener("keydown", handleKeydown);
  root.addEventListener("change", handleChange);
  root.addEventListener("dragenter", handleLocalImageDragEnter);
  root.addEventListener("dragover", handleLocalImageDragOver);
  root.addEventListener("dragleave", handleLocalImageDragLeave);
  root.addEventListener("drop", handleLocalImageDrop);
  // Page-level drag detection: root has no size while every surface is
  // unmounted, so it can never hear the drag that should mount the pad.
  // Capture runs before root's handlers, whose stopPropagation would
  // otherwise starve the detector. dragend - not drop - is the teardown:
  // a captured drop listener would wipe the target mid-dispatch.
  document.addEventListener("dragenter", handleDocumentDragEnter, true);
  document.addEventListener("dragend", hideQuietDropTarget, true);
  document.addEventListener("dragleave", (event) => {
    // relatedTarget null means the pointer left the document (window drag
    // end, alt-tab); a normal element-to-element leave keeps the pad.
    if (!event.relatedTarget) hideQuietDropTarget();
  }, true);
  // A resize can shrink the viewport under a parked position; the same clamp
  // that opens the panel also keeps it inside afterwards.
  window.addEventListener("resize", () => keepSurfaceInViewport());
  root.addEventListener("pointerdown", startDrag);
  root.addEventListener("pointermove", moveDrag);
  root.addEventListener("pointerup", endDrag);
  root.addEventListener("pointercancel", endDrag);

  document.addEventListener("pointerdown", handlePagePointerDown, true);
  window.addEventListener("pointerup", handlePagePointerUp, true);
  window.addEventListener("pointercancel", handlePagePointerUp, true);
  document.addEventListener("selectionchange", handleSelectionChange);
  document.addEventListener("mousemove", onHoverMouseMove, { passive: true });
  // Capture on window: element scrolls don't bubble, but they do pass
  // through the capture phase — one listener covers the whole page tree.
  window.addEventListener("scroll", () => {
    stopHoverCheck();
    // A scroll does not end the reader's intent: wheel and trackpad scrolling
    // leave the cursor parked where it was, with no mousemove to re-arm on —
    // and dynamic pages emit scroll events while the pointer never moves
    // (layout shifts, lazy loads). Once the page settles, probe what is under
    // the cursor NOW: the dwell restarts against the content that scroll
    // brought there.
    window.clearTimeout(hoverState.settleTimer);
    hoverState.settleTimer = window.setTimeout(() => {
      hoverState.settleTimer = 0;
      if (!state.settings.hoverCheck || !hoverState.lastEvent) return;
      if (hoverState.raf) return;
      hoverState.pending = hoverState.lastEvent;
      hoverState.raf = window.requestAnimationFrame(processHoverMove);
    }, HOVER_SCROLL_SETTLE_MS);
  }, { capture: true, passive: true });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") stopHoverCheck();
  });
  // Leaving the page is detected on the root element, NOT through mouseout:
  // dynamic pages (Facebook re-renders constantly) synthesize mouseout with a
  // null relatedTarget whenever the node under the cursor is replaced, which
  // would kill the pill while the pointer never moved at all.
  document.documentElement.addEventListener("mouseleave", stopHoverCheck);
  window.addEventListener("blur", stopHoverCheck);
  window.addEventListener("focus", reprobeHoverAfterReturn);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      stopHoverCheck();
      return;
    }
    reprobeHoverAfterReturn();
  });
  window.matchMedia?.("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (state.settings.irisTheme === "system") render();
  });
  window.addEventListener("mouseup", () => scheduleSelectionSync(0));
  window.addEventListener("keyup", () => scheduleSelectionSync(0));

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === "IRIS_CONTEXT_TEXT") {
      runTextCheck(message.text || getCleanSelection());
      sendResponse({ ok: true });
      return false;
    }

    if (message?.type === "IRIS_CONTEXT_IMAGE") {
      runImageUrlCheck(message.imageUrl);
      sendResponse({ ok: true });
      return false;
    }

    if (message?.type === "IRIS_CONTEXT_IMAGE_STARTED") {
      // Records this push flow's generation: the RESULT and ERROR branches below
      // only render while it is still the live one (pushFlowGen === checkGen).
      state.pushFlowGen = startContextImageCheck(message.imageUrl || "", message.imageName || t("image.selectedName"));
      sendResponse({ ok: true });
      return false;
    }

    // Both drops are decided inside finish/failContextImageCheck: those messages
    // carry no check id, so the recorded flow generation is the only handle.
    if (message?.type === "IRIS_CONTEXT_IMAGE_RESULT") {
      finishContextImageCheck(message.payload || {});
      sendResponse({ ok: true });
      return false;
    }

    if (message?.type === "IRIS_CONTEXT_IMAGE_ERROR") {
      failContextImageCheck(message.error);
      sendResponse({ ok: true });
      return false;
    }

    if (message?.type === "IRIS_OPEN_PANEL") {
      state.panelOpenedByAction = true;
      state.collapsed = false;
      render();
      sendResponse({ ok: true });
      return false;
    }

    if (message?.type === "IRIS_CHECK_CURRENT_SELECTION") {
      const text = getCleanSelection();
      if (text) {
        runTextCheck(text);
      } else {
        state.panelOpenedByAction = true;
        state.collapsed = false;
        state.status = "idle";
        render();
      }
      sendResponse({ ok: Boolean(text) });
      return false;
    }

    return false;
  });

  Promise.all([
    getCurrentTabId(),
    readSyncStorage(STORAGE_DEFAULTS),
    readLocalStore({ [HISTORY_KEY]: [] })
  ]).then(async ([tabId, items, localItems]) => {
    state.tabId = tabId;
    state.settings = {
      ...STORAGE_DEFAULTS,
      irisBackendUrl: normalizeBackendUrl(items.irisBackendUrl),
      irisPanelEnabled: items.irisPanelEnabled !== false,
      irisTheme: items.irisTheme || STORAGE_DEFAULTS.irisTheme,
      irisFontSize: items.irisFontSize || STORAGE_DEFAULTS.irisFontSize,
      irisDebugMode: Boolean(items.irisDebugMode),
      quietMode: Boolean(items.quietMode),
      hoverCheck: Boolean(items.hoverCheck),
      hoverSuppressedByQuiet: Boolean(items.hoverSuppressedByQuiet),
      irisUiLanguage: items.irisUiLanguage || STORAGE_DEFAULTS.irisUiLanguage
    };
    state.history = Array.isArray(localItems[HISTORY_KEY]) ? localItems[HISTORY_KEY] : [];

    const key = positionStorageKey();
    if (key) {
      const positionItems = await readSessionStorage({ [key]: null });
      state.position = normalizePanelPosition(positionItems[key]);
    }

    render();
  });

  chrome.storage?.onChanged?.addListener((changes, areaName) => {
    let shouldRender = false;

    if (areaName === "sync") {
      for (const key of Object.keys(STORAGE_DEFAULTS)) {
        if (changes[key]) {
          state.settings[key] = changes[key].newValue;
          shouldRender = true;
        }
      }

      // Hover to check switched off (options page or another tab): the pill
      // must not wait for the next mousemove to notice.
      if (changes.hoverCheck && !changes.hoverCheck.newValue) stopHoverCheck();

      // Quiet Mode flipped from somewhere other than this panel's own toggle
      // (the options page, another tab): the nudge must apply there too —
      // quiet promises no IRIS surface until a right-click, and the record is
      // what lets the restore hand hover back. This mirrors toggle-quiet-mode
      // exactly; by the time storage events arrive the local toggle has already
      // updated state, so those paths skip these conditions instead of looping.
      if (changes.quietMode?.newValue === true && state.settings.hoverCheck) {
        saveQuickSetting("hoverCheck", false);
        saveQuickSetting("hoverSuppressedByQuiet", true);
        shouldRender = true;
      } else if (changes.quietMode?.newValue === false && state.settings.hoverSuppressedByQuiet) {
        saveQuickSetting("hoverCheck", true);
        saveQuickSetting("hoverSuppressedByQuiet", false);
        shouldRender = true;
      }

      if (
        changes.quietMode?.newValue === true &&
        ["idle", "detected"].includes(state.status)
      ) {
        state.status = "idle";
        state.selectedText = "";
        state.panelOpenedByAction = false;
        state.collapsed = false;
      }
    }

    if (areaName === "local" && changes[HISTORY_KEY]) {
      // Another tab (or the options page) recorded or cleared a check. The panel
      // reads one shared store, so it has to follow along without a reload.
      state.history = Array.isArray(changes[HISTORY_KEY].newValue)
        ? changes[HISTORY_KEY].newValue
        : [];
      shouldRender = true;
    }

    if (areaName === "session") {
      const key = positionStorageKey();
      if (!key || !changes[key]) return;

      const nextPosition = normalizePanelPosition(changes[key].newValue);
      const localDragSave = positionsMatch(nextPosition, state.pendingPositionSave);

      state.position = nextPosition;
      if (localDragSave) {
        state.pendingPositionSave = null;
      } else {
        shouldRender = true;
      }
    }

    if (shouldRender) render();
  });
}
