const DEFAULTS = {
  irisBackendUrl: "http://127.0.0.1:5000",
  irisPanelEnabled: true,
  irisTheme: "system",
  irisFontSize: "default",
  irisDebugMode: false,
  quietMode: false
};

const form = document.getElementById("options-form");
const backendUrl = document.getElementById("backend-url");
const panelEnabled = document.getElementById("panel-enabled");
const quietMode = document.getElementById("quiet-mode");
const debugMode = document.getElementById("debug-mode");
const theme = document.getElementById("theme");
const fontSize = document.getElementById("font-size");
const restoreDefaults = document.getElementById("restore-defaults");
const saveStatus = document.getElementById("save-status");

function normalizeBackendUrl(value) {
  return String(value || DEFAULTS.irisBackendUrl).trim().replace(/\/+$/, "");
}

function setStatus(message) {
  saveStatus.textContent = message || "";
}

function applyValues(values) {
  backendUrl.value = normalizeBackendUrl(values.irisBackendUrl);
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
