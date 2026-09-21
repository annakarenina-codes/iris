if (!window.__IRIS_EXTENSION_CONTENT_LOADED__) {
  window.__IRIS_EXTENSION_CONTENT_LOADED__ = true;

  const STORAGE_DEFAULTS = {
    irisBackendUrl: "http://127.0.0.1:5000", // iris:backend-url
    irisPanelEnabled: true,
    irisTheme: "system",
    irisFontSize: "default",
    irisDebugMode: false,
    quietMode: false
  };

  const FONT_OPTIONS = [
    { value: "small", label: "Small", scale: 0.9 },
    { value: "default", label: "Default", scale: 1 },
    { value: "large", label: "Large", scale: 1.15 },
    { value: "xl", label: "XL", scale: 1.3 }
  ];

  const FAQ_ITEMS = [
    {
      question: "What does IRIS check?",
      answer:
        "IRIS checks selected factual claims against VERA Files and approved Philippine news sources."
    },
    {
      question: "What does Not Found mean?",
      answer:
        "It means IRIS did not find enough matching evidence in the approved source scope. It does not mean false."
    },
    {
      question: "What data is sent?",
      answer:
        "Only the text you select or the image you explicitly submit for OCR is sent to your configured backend."
    },
    {
      question: "Does IRIS verify images?",
      answer:
        "IRIS extracts readable text from submitted images. It does not judge whether an image is authentic or edited."
    }
  ];
  const IMAGE_DROP_ERROR = "Drop a PNG, JPEG, WEBP, BMP, or TIFF image. GIFs, videos, and selected text are not sent to IRIS.";
  const IRIS_LOGO_MARK_URL = chrome.runtime.getURL("assets/iris-logo-mark.png");

  const state = {
    status: "idle",
    settingsReturnStatus: "idle",
    selectedText: "",
    claimMode: "text",
    selectedImage: null,
    result: null,
    claimIndex: 0,
    collapsed: false,
    faqOpen: false,
    panelOpenedByAction: false,
    settings: { ...STORAGE_DEFAULTS },
    position: null,
    tabId: null,
    dragging: null,
    dropActive: false,
    dropDepth: 0,
    suppressClick: false,
    ignoreSelectionClearUntil: 0,
    ignoreInternalSelectionUntil: 0,
    pagePointerDown: false,
    selectionSyncTimer: null,
    pendingPositionSave: null
  };

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

  function getVerdictStyle(verdict) {
    const normalized = String(verdict || "").toLowerCase();

    if (normalized === "verified") {
      return {
        icon: "OK",
        color: "#065F46",
        bg: "#ECFDF5",
        border: "#6EE7B7"
      };
    }

    if (normalized === "partially verified") {
      return {
        icon: "!",
        color: "#78350F",
        bg: "#FFFBEB",
        border: "#FCD34D"
      };
    }

    if (normalized === "refuted") {
      return {
        icon: "X",
        color: "#7F1D1D",
        bg: "#FEF2F2",
        border: "#F87171"
      };
    }

    if (normalized.includes("opinion")) {
      return {
        icon: "i",
        color: "#1D4ED8",
        bg: "#EFF6FF",
        border: "#93C5FD"
      };
    }

    if (normalized.includes("failed") || normalized.includes("unavailable") || normalized.includes("configured")) {
      return {
        icon: "!",
        color: "#991B1B",
        bg: "#FEF2F2",
        border: "#FCA5A5"
      };
    }

    return {
      icon: "?",
      color: "#374151",
      bg: "#F9FAFB",
      border: "#D1D5DB"
    };
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
        explanation: rawClaim?.message || rawClaim?.verdict_explanation || "IRIS returned this result from the backend.",
        ...style
      },
      corroboration: {
        count: evidenceCount,
        total: Number(corroboration.total ?? 7)
      },
      sources
    };
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
      claims
    };
  }

  function sourceCards(sources) {
    const validSources = sources.filter((source) => isValidHttpUrl(source.url));
    if (!validSources.length) {
      return '<div class="source-empty">No valid evidence link found.</div>';
    }

    return validSources
      .map((source) => {
        const date = source.date ? `<time>${escapeHtml(source.date)}</time>` : "<time></time>";
        return `
          <button class="source-card" type="button" data-action="open-source" data-url="${escapeHtml(source.url)}">
            <span class="source-card__meta">
              <span>${escapeHtml(source.outlet)}</span>
              ${date}
            </span>
            <span class="source-card__title">${escapeHtml(source.title)}</span>
            ${source.url ? `<span class="source-card__link">${icon("external")} Read full article</span>` : ""}
          </button>
        `;
      })
      .join("");
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
        <p>${total} other ${total === 1 ? "part" : "parts"} of this post were not checked (${formatted}).</p>
      </div>
    `;
  }

  function claimNavigator(totalClaims) {
    return `
      <div class="claim-navigator" aria-label="Claim navigation" ${totalClaims <= 1 ? "hidden" : ""}>
        <button class="claim-navigator__button" type="button" data-action="prev-claim" aria-label="Previous claim" ${state.claimIndex === 0 ? "disabled" : ""}>
          ${icon("chevronLeft")}
        </button>
        <strong>Claim ${state.claimIndex + 1} of ${totalClaims}</strong>
        <button class="claim-navigator__button" type="button" data-action="next-claim" aria-label="Next claim" ${state.claimIndex === totalClaims - 1 ? "disabled" : ""}>
          ${icon("chevronRight")}
        </button>
      </div>
    `;
  }

  function resultClaimBlock(claim, result) {
    return `
      <div class="claim-result-block">
        <div class="result-claim">
          ${state.claimMode === "photo" ? "<span>Text extracted from image</span>" : ""}
          <blockquote>${escapeHtml(truncateText(claim.claim_text))}</blockquote>
        </div>

        ${
          claim.politically_sensitive
            ? `<div class="political-flag">
                <span aria-hidden="true">!</span>
                <div>
                  <strong>Politically Sensitive</strong>
                  <p>Apply extra scrutiny before sharing.</p>
                </div>
              </div>`
            : ""
        }

        <div class="verdict-card" style="background:${claim.verdict.bg};border-color:${claim.verdict.border};color:${claim.verdict.color}">
          <span class="verdict-card__icon">${escapeHtml(claim.verdict.icon)}</span>
          <div>
            <strong>${escapeHtml(claim.verdict.label)}</strong>
            <p>${escapeHtml(claim.verdict.explanation)}</p>
          </div>
        </div>

        <div class="corroboration-row">
          <strong>${claim.corroboration.count}</strong>
          <span>${claim.corroboration.count === 1 ? "evidence source used" : "evidence sources used"}</span>
        </div>

        <div class="related-label">Evidence Sources</div>
        <div class="source-list">${sourceCards(claim.sources)}</div>
        ${state.claimIndex === result.claims.length - 1 ? skippedNote(result.ignored_segments) : ""}
      </div>
    `;
  }

  function idleState() {
    return `
      <section class="iris-state iris-state--idle">
        <div class="idle-search">${icon("search")}</div>
        <h2>Ready to fact-check</h2>
        <p>Highlight a news claim on this page, then use IRIS to verify it against Philippine sources.</p>
        <div class="empty-claim">
          <span>No text selected yet.</span>
          <strong>Select text to begin</strong>
        </div>
        <button class="iris-button iris-button--disabled" type="button" disabled>Check with IRIS</button>
        <button class="iris-button iris-button--upload" type="button" data-action="upload-image">
          ${icon("image")}
          Upload image
        </button>
      </section>
    `;
  }

  function detectedState() {
    return `
      <section class="iris-state">
        <div class="detected-row">
          <span aria-hidden="true"></span>
          <strong>Text detected</strong>
        </div>
        <blockquote data-role="detected-claim">${escapeHtml(truncateText(state.selectedText))}</blockquote>
        <p class="supporting-note">IRIS will check this claim against VERA Files, Rappler, and 9 credible Philippine news sources.</p>
        <button class="iris-button iris-button--primary" type="button" data-action="check-text">
          ${irisEye(18, true)}
          Check with IRIS
        </button>
      </section>
    `;
  }

  function photoState() {
    const fileName = state.selectedImage?.name || "Selected image";
    const previewStyle = state.selectedImage?.dataUrl
      ? `style="background-image:linear-gradient(90deg,rgba(0,0,0,.5),rgba(0,0,0,.12)),url('${escapeHtml(state.selectedImage.dataUrl)}')"`
      : "";

    return `
      <section class="iris-state iris-state--photo">
        <div class="photo-preview" ${previewStyle}>
          <span>${escapeHtml(fileName)}</span>
          <p>IRIS will extract readable text first, then run the verification pipeline.</p>
        </div>
        <div class="ocr-preview">
          <span>Image OCR</span>
          <blockquote>Ready to scan selected image text.</blockquote>
        </div>
        <button class="iris-button iris-button--primary" type="button" data-action="scan-image">
          ${irisEye(18, true)}
          Scan image text
        </button>
        <button class="iris-button iris-button--secondary photo-cancel" type="button" data-action="cancel-image">Cancel</button>
      </section>
    `;
  }

  function scanningState() {
    const text =
      state.claimMode === "photo"
        ? "Extracting image text and scanning sources..."
        : truncateText(state.selectedText);

    return `
      <section class="iris-state iris-state--scanning">
        <blockquote>${escapeHtml(text)}</blockquote>
        <div class="scan-dots" aria-hidden="true"><span></span><span></span><span></span></div>
        <h2>Scanning sources...</h2>
        <p>Checking VERA Files, Rappler, ABS-CBN, GMA, Inquirer, PhilStar, Manila Bulletin, PNA, PIA, DZRH, and OneNews.</p>
        <div class="progress-track" aria-hidden="true"><span></span></div>
      </section>
    `;
  }

  function resultState() {
    const result = state.result || { claims: [], ignored_segments: [] };
    const claims = result.claims.length
      ? result.claims
      : [normalizeClaim({ verdict: "Not Found", message: "IRIS did not return a claim result." }, state.selectedText, [])];
    const activeClaim = claims[Math.min(state.claimIndex, claims.length - 1)];
    const quietCloseButton = `<button class="iris-button iris-button--secondary quiet-close-result" type="button" data-action="quiet-close" ${state.settings.quietMode ? "" : "hidden"}>Close IRIS</button>`;

    return `
      <section class="iris-state iris-state--result">
        ${claimNavigator(claims.length)}
        ${resultClaimBlock(activeClaim, { ...result, claims })}
        <p class="disclaimer">IRIS is an assistant, not an authority. Always read the linked articles before sharing.</p>
        ${quietCloseButton}
        <button class="iris-button iris-button--secondary" type="button" data-action="reset">Check another claim</button>
      </section>
    `;
  }

  function errorState() {
    return `
      <section class="iris-state iris-state--error">
        <div class="verdict-card" style="background:#FEF2F2;border-color:#FCA5A5;color:#991B1B">
          <span class="verdict-card__icon">!</span>
          <div>
            <strong>IRIS could not complete the check</strong>
            <p>${escapeHtml(state.errorMessage || "The backend request failed.")}</p>
          </div>
        </div>
        <p class="supporting-note">Backend URL: ${escapeHtml(normalizeBackendUrl(state.settings.irisBackendUrl))}</p>
        <button class="iris-button iris-button--secondary" type="button" data-action="reset">Back to IRIS</button>
      </section>
    `;
  }

  function settingsState() {
    return `
      <section class="iris-state iris-settings">
        <div class="settings-title">
          <h2>Settings</h2>
          <button class="iris-button iris-button--secondary settings-done" type="button" data-action="close-settings">Done</button>
        </div>

        <div class="setting-row">
          <div>
            <strong>Night mode</strong>
            <span>IRIS panel only</span>
          </div>
          <button class="switch-button ${resolveTheme() === "dark" ? "is-on" : ""}" type="button" role="switch" aria-checked="${resolveTheme() === "dark"}" data-action="toggle-theme">
            <span></span>
          </button>
        </div>

        <div class="setting-row">
          <div>
            <strong>Quiet Mode</strong>
            <span>Only show IRIS after right-click checks</span>
          </div>
          <button class="switch-button ${state.settings.quietMode ? "is-on" : ""}" type="button" role="switch" aria-checked="${state.settings.quietMode}" data-action="toggle-quiet-mode">
            <span></span>
          </button>
        </div>

        <div class="setting-block">
          <strong>Font size</strong>
          <div class="font-options" role="group" aria-label="Font size">
            ${FONT_OPTIONS.map((option) => `
              <button class="${state.settings.irisFontSize === option.value ? "is-active" : ""}" type="button" data-action="set-font" data-value="${option.value}">
                ${escapeHtml(option.label)}
              </button>
            `).join("")}
          </div>
        </div>

        <button class="iris-button iris-button--secondary" type="button" data-action="open-options">Backend and privacy options</button>
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
            <button class="iris-icon-button iris-icon-button--plain" type="button" aria-label="Close FAQ" data-action="close-faq">
              ${icon("close")}
            </button>
          </header>
          <div class="faq-list">
            ${FAQ_ITEMS.map((item) => `
              <article>
                <h3>${escapeHtml(item.question)}</h3>
                <p>${escapeHtml(item.answer)}</p>
              </article>
            `).join("")}
            <button type="button" data-action="open-source" data-url="https://verafiles.org">Open VERA Files</button>
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
        <button class="iris-pill iris-extension-shell" type="button" aria-label="Open IRIS panel" data-drag-handle data-action="expand" hidden>
                ${irisEye(22)}
                <span>IRIS</span>
                <i class="iris-pill__status" aria-hidden="true"></i>
        </button>
        <aside class="iris-panel iris-extension-shell" aria-label="IRIS fact-check panel" hidden>
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
                  <button type="button" aria-label="Open IRIS settings" data-action="open-settings">${icon("gear")}</button>
                  <button type="button" aria-label="Open IRIS FAQ" data-action="open-faq">${icon("question")}</button>
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
      status: null,
      bodyMarkup: null,
      claimIndex: null
    };
  }

  function updatePanelBody() {
    const view = mountedView;
    const markup = bodyForStatus();
    if (view.bodyMarkup === markup && view.status === state.status) return;

    if (view.status !== state.status) {
      view.body.innerHTML = markup;
      view.body.scrollTop = 0;
    } else if (state.status === "detected") {
      updateDetectedText(state.selectedText);
    } else if (state.status === "settings") {
      for (const [action, checked] of [
        ["toggle-theme", resolveTheme() === "dark"],
        ["toggle-quiet-mode", state.settings.quietMode]
      ]) {
        const button = view.body.querySelector(`[data-action="${action}"]`);
        button.classList.toggle("is-on", Boolean(checked));
        button.setAttribute("aria-checked", String(Boolean(checked)));
      }
      for (const button of view.body.querySelectorAll('[data-action="set-font"]')) {
        button.classList.toggle("is-active", button.dataset.value === state.settings.irisFontSize);
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
    if (!shouldRenderPanel()) {
      root.replaceChildren();
      mountedView = null;
      return;
    }
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
    }
    panel.hidden = state.collapsed;
    pill.hidden = !state.collapsed;
    const scanning = state.status === "scanning";
    const ready = ["detected", "photo", "result"].includes(state.status);
    const statusDot = pill.querySelector(".iris-pill__status");
    statusDot.classList.toggle("is-scanning", scanning);
    statusDot.classList.toggle("is-ready", ready);
    pill.setAttribute("aria-label", scanning ? "IRIS is scanning. Open panel" : ready ? "IRIS is ready. Open panel" : "Open IRIS panel");
    panel.setAttribute("aria-busy", String(scanning));

    const closeAction = state.settings.quietMode ? "quiet-close" : "collapse";
    if (headerClose.dataset.action !== closeAction) {
      headerClose.dataset.action = closeAction;
      headerClose.setAttribute("aria-label", state.settings.quietMode ? "Close IRIS panel" : "Collapse IRIS panel");
      headerClose.innerHTML = icon(state.settings.quietMode ? "close" : "minus");
    }
    panel.querySelector('[data-action="open-settings"]').classList.toggle("is-active", state.status === "settings");
    updatePanelBody();

    const faq = panel.querySelector(".faq-overlay");
    if (state.faqOpen && !faq) panel.insertAdjacentHTML("beforeend", faqOverlay());
    if (!state.faqOpen && faq) faq.remove();
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
    state.panelOpenedByAction = false;
    window.getSelection()?.removeAllRanges();
    render();
  }

  async function runTextCheck(text) {
    const cleanText = String(text || "").trim();

    if (!cleanText) {
      state.errorMessage = "No selected text was provided.";
      setStatus("error");
      return;
    }

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
        text: cleanText
      });

      if (!response?.ok) {
        throw new Error(response?.error || "The IRIS backend did not return a successful text result.");
      }

      state.result = normalizeBackendResult(response.payload, cleanText, "text");
      setStatus("result");
    } catch (error) {
      state.errorMessage = error.message;
      setStatus("error");
    }
  }

  async function requestBackgroundImageVerification(source, imageName = "Selected image", previewDataUrl = "") {
    const imageSource = source || {};

    if (!imageSource.dataUrl && !imageSource.url) {
      state.errorMessage = "No image data was provided.";
      setStatus("error");
      return;
    }

    state.panelOpenedByAction = true;
    state.claimMode = "photo";
    state.selectedText = "Image selected for OCR.";
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

      if (!response?.ok) {
        throw new Error(response?.error || "IRIS could not start image verification.");
      }
    } catch (error) {
      failContextImageCheck(error.message);
    }
  }

  async function runImageCheck(imageDataUrl, imageName = "Selected image") {
    if (!imageDataUrl) {
      state.errorMessage = "No image data was provided.";
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
    return runImageUrlDropCheck(imageUrl, "Image from page");
  }

  async function runImageUrlDropCheck(imageUrl, imageName = "Image from page") {
    if (!imageUrl) {
      state.errorMessage = "No image URL was provided.";
      setStatus("error");
      return;
    }

    return requestBackgroundImageVerification({
      kind: "url",
      url: imageUrl,
      name: imageName
    }, imageName);
  }

  function startContextImageCheck(imageUrl, imageName = "Selected image") {
    state.panelOpenedByAction = true;
    state.claimMode = "photo";
    state.selectedText = "Image selected for OCR.";
    state.selectedImage = {
      dataUrl: "",
      name: imageName || (imageUrl ? "Image from page" : "Selected image")
    };
    state.result = null;
    state.claimIndex = 0;
    state.faqOpen = false;
    state.collapsed = false;
    setStatus("scanning");
  }

  function finishContextImageCheck(payload) {
    const fallbackText = payload?.ocr_text || "Image selected for OCR.";
    state.result = normalizeBackendResult(payload, fallbackText, "photo");
    setStatus("result");
  }

  function failContextImageCheck(message) {
    state.panelOpenedByAction = true;
    state.claimMode = "photo";
    state.selectedText = "Image selected for OCR.";
    state.selectedImage = state.selectedImage || {
      dataUrl: "",
      name: "Selected image"
    };
    state.collapsed = false;
    state.errorMessage = message || "IRIS could not verify the selected image.";
    setStatus("error");
  }

  function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("IRIS could not read the selected image file."));
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
    if (uriListUrl) return uriListUrl;

    const htmlUrl = extractImageUrlFromHtml(dataTransfer?.getData("text/html"));
    if (htmlUrl) return htmlUrl;

    const plainTextUrl = extractImageUrlFromPlainText(dataTransfer?.getData("text/plain"));
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
      throw new Error(IMAGE_DROP_ERROR);
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
      showImageDropError(IMAGE_DROP_ERROR);
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
      showImageDropError(IMAGE_DROP_ERROR);
      return;
    }

    try {
      if (isUnsupportedDroppedSource(url)) {
        showImageDropError(IMAGE_DROP_ERROR);
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

      showImageDropError(IMAGE_DROP_ERROR);
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
        name: file.name || "Selected image"
      };
      state.claimMode = "photo";
      state.selectedText = "Image selected for OCR.";
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
    scheduleSelectionSync(state.pagePointerDown ? 16 : 80);
  }

  async function saveQuickSetting(key, value) {
    state.settings[key] = value;
    await writeSyncStorage({ [key]: value });
    render();
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
      saveQuickSetting("quietMode", !state.settings.quietMode);
      return;
    }

    if (action === "set-font") {
      saveQuickSetting("irisFontSize", actionTarget.dataset.value || "default");
      return;
    }

    if (action === "open-faq") {
      state.faqOpen = true;
      render();
      return;
    }

    if (action === "close-faq") {
      if (actionTarget.classList.contains("faq-overlay") && target.closest?.(".faq-modal")) return;
      state.faqOpen = false;
      render();
      return;
    }

    if (action === "open-options") {
      sendRuntimeMessage({ type: "IRIS_OPEN_OPTIONS" });
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
  root.addEventListener("change", handleChange);
  root.addEventListener("dragenter", handleLocalImageDragEnter);
  root.addEventListener("dragover", handleLocalImageDragOver);
  root.addEventListener("dragleave", handleLocalImageDragLeave);
  root.addEventListener("drop", handleLocalImageDrop);
  root.addEventListener("pointerdown", startDrag);
  root.addEventListener("pointermove", moveDrag);
  root.addEventListener("pointerup", endDrag);
  root.addEventListener("pointercancel", endDrag);

  document.addEventListener("pointerdown", handlePagePointerDown, true);
  window.addEventListener("pointerup", handlePagePointerUp, true);
  window.addEventListener("pointercancel", handlePagePointerUp, true);
  document.addEventListener("selectionchange", handleSelectionChange);
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
      startContextImageCheck(message.imageUrl || "", message.imageName || "Selected image");
      sendResponse({ ok: true });
      return false;
    }

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
    readSyncStorage(STORAGE_DEFAULTS)
  ]).then(async ([tabId, items]) => {
    state.tabId = tabId;
    state.settings = {
      ...STORAGE_DEFAULTS,
      irisBackendUrl: normalizeBackendUrl(items.irisBackendUrl),
      irisPanelEnabled: items.irisPanelEnabled !== false,
      irisTheme: items.irisTheme || STORAGE_DEFAULTS.irisTheme,
      irisFontSize: items.irisFontSize || STORAGE_DEFAULTS.irisFontSize,
      irisDebugMode: Boolean(items.irisDebugMode),
      quietMode: Boolean(items.quietMode)
    };

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
