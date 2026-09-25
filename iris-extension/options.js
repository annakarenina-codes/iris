const DEFAULTS = {
  irisBackendUrl: "https://iris-production-8342.up.railway.app", // iris:backend-url
  irisAccessToken: "",
  irisPanelEnabled: true,
  irisTheme: "system",
  irisFontSize: "default",
  irisDebugMode: false,
  quietMode: false
};

const form = document.getElementById("options-form");
const backendUrl = document.getElementById("backend-url");
const accessToken = document.getElementById("access-token");
const panelEnabled = document.getElementById("panel-enabled");
const quietMode = document.getElementById("quiet-mode");
const debugMode = document.getElementById("debug-mode");
const theme = document.getElementById("theme");
const fontSize = document.getElementById("font-size");
const restoreDefaults = document.getElementById("restore-defaults");
const saveStatus = document.getElementById("save-status");
const historyList = document.getElementById("history-list");
const clearHistory = document.getElementById("clear-history");

// Kept in chrome.storage.local, not sync: sync quota is about 100 KB in total and a single
// raw result payload can eat it, and history must not roam across a person's devices.
const HISTORY_KEY = "irisHistory";
// First three article links, then "Show N more" — the same rule the result panel applies.
const HISTORY_SOURCE_LIMIT = 3;
let historyEntries = [];

function normalizeBackendUrl(value) {
  return String(value || DEFAULTS.irisBackendUrl).trim().replace(/\/+$/, "");
}

function setStatus(message) {
  saveStatus.textContent = message || "";
}

function applyValues(values) {
  backendUrl.value = normalizeBackendUrl(values.irisBackendUrl);
  accessToken.value = values.irisAccessToken || "";
  panelEnabled.checked = values.irisPanelEnabled !== false;
  quietMode.checked = Boolean(values.quietMode);
  debugMode.checked = Boolean(values.irisDebugMode);
  theme.value = values.irisTheme || DEFAULTS.irisTheme;
  fontSize.value = values.irisFontSize || DEFAULTS.irisFontSize;
}

function readOptions() {
  chrome.storage.sync.get(DEFAULTS, (items) => applyValues(items));
}

form.addEventListener("submit", (event) => {
  event.preventDefault();

  const values = {
    irisBackendUrl: normalizeBackendUrl(backendUrl.value),
    irisAccessToken: accessToken.value.trim(),
    irisPanelEnabled: panelEnabled.checked,
    quietMode: quietMode.checked,
    irisTheme: theme.value,
    irisFontSize: fontSize.value,
    irisDebugMode: debugMode.checked
  };

  chrome.storage.sync.set(values, () => {
    setStatus("Options saved.");
    window.setTimeout(() => setStatus(""), 1800);
  });
});

restoreDefaults.addEventListener("click", () => {
  chrome.storage.sync.set(DEFAULTS, () => {
    applyValues(DEFAULTS);
    setStatus("Defaults restored.");
    window.setTimeout(() => setStatus(""), 1800);
  });
});

readOptions();

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

function formatCheckedAt(value) {
  const timestamp = Number(value);
  if (!Number.isFinite(timestamp)) return "";

  const date = new Date(timestamp);
  const pad = (part) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function verdictTone(verdict) {
  const normalized = String(verdict || "").toLowerCase();
  if (normalized === "verified") return "is-verified";
  if (normalized.includes("partially")) return "is-partial";
  if (normalized.includes("refuted") || normalized.includes("false")) return "is-refuted";
  return "is-unknown";
}

function historyBadge(verdict) {
  const label = String(verdict || "").trim() || "Result";
  return `<span class="history-badge ${verdictTone(label)}">${escapeHtml(label)}</span>`;
}

// Same filtering the result panel applies: only extracted http(s) entries, deduped by
// URL. Returns the entries so history can both count them and link to them.
function flattenClaimSources(claim, payload) {
  const rawSources =
    claim?.evidence_sources || claim?.supporting_sources || claim?.sources || payload?.sources || [];
  const seen = new Set();
  const flattened = [];

  const add = (source) => {
    const url = String(source?.url || "").trim();
    const status = source?.status;
    if (status && status !== "extracted") return;
    let parsed;
    try {
      parsed = new URL(url);
    } catch (_error) {
      return;
    }
    if (!["http:", "https:"].includes(parsed.protocol) || !parsed.hostname) return;

    const key = `${parsed.origin}${parsed.pathname}${parsed.search}`.toLowerCase().replace(/\/$/, "");
    if (seen.has(key)) return;

    seen.add(key);
    flattened.push({ url, title: String(source?.title || "").trim() || url });
  };

  if (Array.isArray(rawSources)) {
    for (const item of rawSources) {
      if (Array.isArray(item?.articles)) {
        for (const article of item.articles) add(article);
      } else {
        add(item);
      }
    }
  }

  return flattened;
}

// Mirrors how the result panel counts sources for a claim (flatten, drop the non-extracted
// ones, dedupe, then let the corroboration count speak) so history agrees with the panel.
function countClaimSources(claim, payload) {
  const sourceCount = flattenClaimSources(claim, payload).length;
  const raw = claim?.corroboration?.count ?? claim?.corroboration_count ?? sourceCount;
  const count = Number(raw);
  return Number.isFinite(count) ? Math.min(Math.max(count, 0), sourceCount) : sourceCount;
}

function historyRowMarkup(entry, index) {
  const date = formatCheckedAt(entry.checkedAt);
  const typeLabel = entry.inputType === "image" ? "Image" : "Text";

  return `
    <div class="history-row">
      <button type="button" class="history-row__summary" aria-expanded="false" data-index="${index}">
        ${historyBadge(entry.verdict)}
        <span class="history-row__preview">${escapeHtml(entry.preview || "")}</span>
        <span class="history-row__meta">
          <span>${typeLabel}</span>
          <time>${escapeHtml(date)}</time>
        </span>
      </button>
      <div class="history-row__detail" hidden></div>
    </div>
  `;
}

// Detail is built from the stored payload itself, never from the raw JSON text: the reader
// gets verdicts, messages, and source counts, not a wall of backend output.
function historyDetailMarkup(entry) {
  let payload = null;
  try {
    payload = JSON.parse(entry.rawJson);
  } catch (_error) {
    payload = null;
  }

  const claims = Array.isArray(payload?.claims) ? payload.claims : [];
  if (!claims.length) {
    const text = String(entry.fallback || "").trim() || "No claim details were stored for this check.";
    return `<div class="history-claim"><p>${escapeHtml(text)}</p></div>`;
  }

  return claims
    .map((claim) => {
      const message = String(claim?.message || claim?.verdict_explanation || "").trim();
      // The row preview clamps to two lines, so the detail is the only place the full
      // statement is readable — never truncate it here.
      const claimText = String(claim?.claim_text || claim?.claim || claim?.text || "").trim();
      const count = countClaimSources(claim, payload);
      const sources = flattenClaimSources(claim, payload);
      const hiddenCount = Math.max(0, sources.length - HISTORY_SOURCE_LIMIT);
      const links = sources
        .map((source, index) => {
          const collapsed = index >= HISTORY_SOURCE_LIMIT ? " history-source--collapsed" : "";
          return `<a class="history-source${collapsed}" href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.title)}</a>`;
        })
        .join("");
      const more =
        hiddenCount > 0
          ? `<button type="button" class="history-source-more">Show ${hiddenCount} more</button>`
          : "";

      return `
      <div class="history-claim">
        ${historyBadge(claim?.verdict || entry.verdict)}
        ${claimText ? `<blockquote class="history-claim__text">${escapeHtml(claimText)}</blockquote>` : ""}
        ${message ? `<p>${escapeHtml(message)}</p>` : ""}
        <span class="history-claim__sources">${count} evidence ${count === 1 ? "source" : "sources"}</span>
        ${links ? `<div class="history-source-list">${links}${more}</div>` : ""}
      </div>
    `;
    })
    .join("");
}

function renderHistory(entries) {
  historyEntries = Array.isArray(entries) ? entries : [];
  clearHistory.hidden = historyEntries.length === 0;

  if (!historyEntries.length) {
    historyList.innerHTML = '<p class="history-empty">No checks yet.</p>';
    return;
  }

  historyList.innerHTML = historyEntries.map((entry, index) => historyRowMarkup(entry, index)).join("");
}

historyList.addEventListener("click", (event) => {
  const more = event.target.closest(".history-source-more");
  if (more && historyList.contains(more)) {
    // Reveal in place: the reader keeps their spot instead of losing it to a rebuild.
    const list = more.closest(".history-source-list");
    for (const link of list?.querySelectorAll(".history-source--collapsed") || []) {
      link.classList.remove("history-source--collapsed");
    }
    more.remove();
    return;
  }

  const summary = event.target.closest(".history-row__summary");
  if (!summary || !historyList.contains(summary)) return;

  const detail = summary.nextElementSibling;
  if (!detail) return;

  if (!detail.innerHTML) {
    // Built on first open: parsing every stored payload up front would do the work for
    // rows nobody ever opens.
    const index = Number(summary.dataset.index);
    detail.innerHTML = Number.isInteger(index) && historyEntries[index]
      ? historyDetailMarkup(historyEntries[index])
      : "";
  }

  const expanded = summary.getAttribute("aria-expanded") === "true";
  summary.setAttribute("aria-expanded", String(!expanded));
  detail.hidden = expanded;
});

let clearArmed = false;
let clearTimer = 0;

function disarmClearHistory() {
  clearArmed = false;
  window.clearTimeout(clearTimer);
  clearHistory.textContent = "Clear history";
  clearHistory.classList.remove("is-armed");
}

clearHistory.addEventListener("click", () => {
  if (!clearArmed) {
    // Clearing cannot be undone, so the first click only arms the button; a second
    // click within four seconds is the one that deletes.
    clearArmed = true;
    clearHistory.textContent = "Confirm clear?";
    clearHistory.classList.add("is-armed");
    clearTimer = window.setTimeout(disarmClearHistory, 4000);
    return;
  }

  chrome.storage.local.remove(HISTORY_KEY, () => {
    disarmClearHistory();
    renderHistory([]);
    setStatus("History cleared.");
    window.setTimeout(() => setStatus(""), 1800);
  });
});

chrome.storage.local.get({ [HISTORY_KEY]: [] }, (items) => renderHistory(items[HISTORY_KEY]));

// A check that finishes while this page is open still lands in the list.
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local" || !changes[HISTORY_KEY]) return;
  renderHistory(changes[HISTORY_KEY].newValue || []);
});
