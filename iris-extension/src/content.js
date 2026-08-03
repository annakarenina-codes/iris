if (!window.__IRIS_EXTENSION_CONTENT_LOADED__) {
  window.__IRIS_EXTENSION_CONTENT_LOADED__ = true;

  const STORAGE_DEFAULTS = {
    irisBackendUrl: "http://127.0.0.1:5000",
    irisPanelEnabled: true,
    irisTheme: "system",
    irisFontSize: "default",
    irisDebugMode: false
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
    dragging: null,
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

  const storage = chrome.storage?.sync;

  function readStorage(defaults) {
    return new Promise((resolve) => {
      if (!storage) {
        resolve(defaults);
        return;
      }

      storage.get(defaults, (items) => resolve(items || defaults));
    });
  }

  function writeStorage(items) {
    return new Promise((resolve) => {
      if (!storage) {
        resolve();
        return;
      }

      storage.set(items, resolve);
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
    return (
      state.settings.irisPanelEnabled ||
      state.panelOpenedByAction ||
      state.status !== "idle"
    );
  }

  function irisEye(size = 28, monochrome = false) {
    const id = `irisGradient-${Math.random().toString(36).slice(2)}`;
    const fill = monochrome ? "currentColor" : `url(#${id})`;
    const innerFill = monochrome ? "none" : "white";
    const innerStroke = monochrome ? "currentColor" : "none";
    const innerStrokeWidth = monochrome ? "4" : "0";

    return `
      <svg class="iris-eye" width="${size}" height="${size}" viewBox="0 0 100 100" fill="none" aria-hidden="true">
        <defs>
          <linearGradient id="${id}" x1="0" y1="100" x2="100" y2="0" gradientUnits="userSpaceOnUse">
            <stop stop-color="#5B21B6" />
            <stop offset="0.55" stop-color="#8B5CF6" />
            <stop offset="1" stop-color="#C4B5FD" />
          </linearGradient>
        </defs>
        <ellipse cx="44" cy="46" rx="30" ry="18" fill="${fill}" />
        <circle cx="50" cy="48" r="20" fill="${innerFill}" opacity="0.9" stroke="${innerStroke}" stroke-width="${innerStrokeWidth}" />
        <circle cx="50" cy="48" r="11" fill="${fill}" />
        <circle cx="44" cy="43" r="4" fill="white" opacity="0.7" />
        <line x1="64" y1="62" x2="78" y2="76" stroke="${fill}" stroke-width="8" stroke-linecap="round" />
      </svg>
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
    for (const item of rawSources) {
      if (Array.isArray(item?.articles)) {
        for (const article of item.articles) {
          flattened.push({
            outlet: item.source || article.source || article.outlet || "Approved source",
            date: article.date || article.published_date || "",
            title: article.title || article.url || "Untitled article",
            url: article.url || ""
          });
        }
      } else {
        flattened.push({
          outlet: item.source || item.outlet || "Approved source",
          date: item.date || item.published_date || "",
          title: item.title || item.url || "Untitled article",
          url: item.url || ""
        });
      }
    }

    return flattened.filter((source) => source.title || source.url);
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
        count: Number(corroboration.count ?? rawClaim?.corroboration_count ?? 0),
        total: Number(corroboration.total ?? 6)
      },
      sources: flattenSources(rawClaim?.sources || topLevelSources || [])
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
    if (!sources.length) {
      return '<div class="source-empty">No direct article match found.</div>';
    }

    return sources
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
    if (totalClaims <= 1) return "";

    return `
      <div class="claim-navigator" aria-label="Claim navigation">
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
          <strong>${claim.corroboration.count} of ${claim.corroboration.total}</strong>
          <span>sources returned related articles</span>
        </div>

        <div class="related-label">Related Articles</div>
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
        <p class="supporting-note">IRIS will check this claim against 6 credible Philippine news sources and VERA Files.</p>
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
        <p>Checking GMA, Inquirer, PhilStar, Manila Bulletin, PNA, PIA, and VERA Files.</p>
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

    return `
      <section class="iris-state iris-state--result">
        ${claimNavigator(claims.length)}
        ${resultClaimBlock(activeClaim, { ...result, claims })}
        <p class="disclaimer">IRIS is an assistant, not an authority. Always read the linked articles before sharing.</p>
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

  function render() {
    if (!shouldRenderPanel()) {
      root.innerHTML = "";
      return;
    }

    const positionStyle = state.position
      ? `left:${state.position.x}px;top:${state.position.y}px;right:auto;bottom:auto;`
      : "";
    const theme = resolveTheme();
    const scale = activeFontScale();
    const detected =
      state.status === "detected" ||
      state.status === "photo" ||
      state.status === "scanning" ||
      state.status === "result";
    const statusClass = state.status === "scanning" ? "is-scanning" : detected ? "is-ready" : "";

    root.innerHTML = `
      <div class="iris-floating-wrap ${state.position ? "is-positioned" : ""}" style="${positionStyle}">
        <input id="iris-image-input" type="file" accept="image/*" hidden />
        ${
          state.collapsed
            ? `<button class="iris-pill iris-extension-shell ${state.dragging ? "is-dragging" : ""}" type="button" aria-label="Open IRIS panel" data-theme="${theme}" style="--iris-scale:${scale}" data-drag-handle data-action="expand">
                ${irisEye(22)}
                <span>IRIS</span>
                <i class="iris-pill__status ${statusClass}" aria-hidden="true"></i>
              </button>`
            : `<aside class="iris-panel iris-extension-shell ${state.dragging ? "is-dragging" : ""}" data-theme="${theme}" style="--iris-scale:${scale}" aria-label="IRIS fact-check panel">
                <header class="iris-panel__header" data-drag-handle>
                  <div class="iris-panel__brand">
                    ${irisEye(28)}
                    <div>
                      <strong>IRIS</strong>
                      <span>INTELLIGENT REAL-TIME INFORMATION SCANNER</span>
                    </div>
                  </div>
                  <button class="iris-icon-button" type="button" aria-label="Collapse IRIS panel" data-action="collapse">
                    ${icon("minus")}
                  </button>
                </header>
                <div class="iris-panel__body">${bodyForStatus()}</div>
                <footer class="iris-panel__footer">
                  <button class="${state.status === "settings" ? "is-active" : ""}" type="button" aria-label="Open IRIS settings" data-action="open-settings">${icon("gear")}</button>
                  <button type="button" aria-label="Open IRIS FAQ" data-action="open-faq">${icon("question")}</button>
                </footer>
                ${faqOverlay()}
              </aside>`
        }
      </div>
    `;
  }

  function applyPositionDuringDrag(x, y) {
    const wrapper = shadow.querySelector(".iris-floating-wrap");
    if (!wrapper) return;

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

  async function runImageCheck(imageDataUrl, imageName = "Selected image") {
    if (!imageDataUrl) {
      state.errorMessage = "No image data was provided.";
      setStatus("error");
      return;
    }

    state.panelOpenedByAction = true;
    state.claimMode = "photo";
    state.selectedText = "Image selected for OCR.";
    state.selectedImage = {
      dataUrl: imageDataUrl,
      name: imageName
    };
    state.claimIndex = 0;
    state.faqOpen = false;
    state.collapsed = false;
    setStatus("scanning");

    try {
      const response = await sendRuntimeMessage({
        type: "IRIS_VERIFY_IMAGE",
        backendUrl: state.settings.irisBackendUrl,
        debug: state.settings.irisDebugMode,
        imageDataUrl
      });

      if (!response?.ok) {
        const fallbackPayload = response?.payload;
        if (fallbackPayload) {
          state.result = normalizeBackendResult(fallbackPayload, fallbackPayload.ocr_text || "Image selected for OCR.", "photo");
          setStatus("result");
          return;
        }

        throw new Error(response?.error || "The IRIS backend did not return a successful OCR result.");
      }

      state.result = normalizeBackendResult(response.payload, response.payload?.ocr_text || "Image selected for OCR.", "photo");
      setStatus("result");
    } catch (error) {
      state.errorMessage = error.message;
      setStatus("error");
    }
  }

  async function runImageUrlCheck(imageUrl) {
    state.panelOpenedByAction = true;
    state.claimMode = "photo";
    state.selectedText = "Image selected for OCR.";
    state.selectedImage = {
      dataUrl: "",
      name: "Image from page"
    };
    state.collapsed = false;
    setStatus("scanning");

    try {
      const response = await sendRuntimeMessage({
        type: "IRIS_FETCH_IMAGE_AS_DATA_URL",
        imageUrl
      });

      if (!response?.ok) {
        throw new Error(response?.error || "IRIS could not read the selected image from the page.");
      }

      await runImageCheck(response.dataUrl, "Image from page");
    } catch (error) {
      state.errorMessage = error.message;
      setStatus("error");
    }
  }

  function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("IRIS could not read the selected image file."));
      reader.readAsDataURL(file);
    });
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
    await writeStorage({ [key]: value });
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
      state.collapsed = true;
      render();
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
      state.status = state.settingsReturnStatus || "idle";
      render();
      return;
    }

    if (action === "toggle-theme") {
      const nextTheme = resolveTheme() === "dark" ? "light" : "dark";
      saveQuickSetting("irisTheme", nextTheme);
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
      if (url) window.open(url, "_blank", "noopener,noreferrer");
    }
  }

  function handleChange(event) {
    if (event.target?.id === "iris-image-input") {
      handleImageFile(event.target.files?.[0]);
      event.target.value = "";
    }
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
    shadow.querySelector(".iris-panel, .iris-pill")?.classList.add("is-dragging");
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

    shadow.querySelector(".iris-panel, .iris-pill")?.classList.remove("is-dragging");

    if (state.position) {
      const positionToSave = { ...state.position };
      state.pendingPositionSave = positionToSave;
      await writeStorage({ irisPanelPosition: positionToSave });
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
  root.addEventListener("pointerdown", startDrag);
  root.addEventListener("pointermove", moveDrag);
  root.addEventListener("pointerup", endDrag);
  root.addEventListener("pointercancel", endDrag);

  document.addEventListener("pointerdown", handlePagePointerDown, true);
  window.addEventListener("pointerup", handlePagePointerUp, true);
  window.addEventListener("pointercancel", handlePagePointerUp, true);
  document.addEventListener("selectionchange", handleSelectionChange);
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

  readStorage({ ...STORAGE_DEFAULTS, irisPanelPosition: null }).then((items) => {
    state.settings = {
      ...STORAGE_DEFAULTS,
      irisBackendUrl: normalizeBackendUrl(items.irisBackendUrl),
      irisPanelEnabled: items.irisPanelEnabled !== false,
      irisTheme: items.irisTheme || STORAGE_DEFAULTS.irisTheme,
      irisFontSize: items.irisFontSize || STORAGE_DEFAULTS.irisFontSize,
      irisDebugMode: Boolean(items.irisDebugMode)
    };

    state.position = normalizePanelPosition(items.irisPanelPosition);

    render();
  });

  chrome.storage?.onChanged?.addListener((changes, areaName) => {
    if (areaName !== "sync") return;

    let shouldRender = false;

    for (const key of Object.keys(STORAGE_DEFAULTS)) {
      if (changes[key]) {
        state.settings[key] = changes[key].newValue;
        shouldRender = true;
      }
    }

    if (changes.irisPanelPosition) {
      const nextPosition = normalizePanelPosition(changes.irisPanelPosition.newValue);
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
