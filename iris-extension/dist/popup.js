const DEFAULTS = {
  irisBackendUrl: "https://iris-production-8342.up.railway.app", // iris:backend-url
  irisTheme: "system",
  irisUiLanguage: "en"
};

const backendUrl = document.getElementById("backend-url");
const statusText = document.getElementById("popup-status");
const openPanelButton = document.getElementById("open-panel");
const checkSelectionButton = document.getElementById("check-selection");
const openOptionsButton = document.getElementById("open-options");

let currentLanguage = "en";

// Labels are data-i18n marked in popup.html; the stored language drives them and
// flips the document direction for Arabic. The popup reads its settings once —
// it is recreated on every open, so there is nothing to keep in sync live.
function applyLabels() {
  const language = IRIS_LANGUAGES.some((entry) => entry.code === currentLanguage)
    ? currentLanguage
    : "en";
  for (const element of document.querySelectorAll("[data-i18n]")) {
    element.textContent = irisT(language, element.dataset.i18n);
  }
  document.documentElement.lang = language;
  document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
}

function popT(key) {
  return irisT(currentLanguage, key);
}

// The stored irisTheme setting wins; "system" leaves the attribute off so
// tokens.css follows prefers-color-scheme through color-scheme: light dark.
function applyTheme(theme) {
  if (theme === "light" || theme === "dark") {
    document.documentElement.dataset.theme = theme;
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

function setStatus(message) {
  statusText.textContent = message || "";
}

function getActiveTab() {
  return chrome.tabs.query({ active: true, currentWindow: true }).then((tabs) => tabs[0]);
}

async function sendToActiveTab(message) {
  const tab = await getActiveTab();
  if (!tab?.id) {
    throw new Error(popT("popup.noActiveTab"));
  }

  // Top frame only — same rule as background.js sendToTab: a broadcast or an
  // all-frames injection can mount a second panel inside a page iframe.
  try {
    return await chrome.tabs.sendMessage(tab.id, message, { frameId: 0 });
  } catch (_error) {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id, frameIds: [0] },
      files: ["src/content.js"]
    });
    return chrome.tabs.sendMessage(tab.id, message, { frameId: 0 });
  }
}

chrome.storage.sync.get(DEFAULTS, (items) => {
  currentLanguage = IRIS_LANGUAGES.some((entry) => entry.code === items.irisUiLanguage)
    ? items.irisUiLanguage
    : "en";
  applyLabels();
  // applyLabels painted the loading placeholder; the stored URL — or the
  // shipped default when the setting is empty — replaces it right after.
  backendUrl.textContent = items.irisBackendUrl || DEFAULTS.irisBackendUrl;
  applyTheme(items.irisTheme);
});

openPanelButton.addEventListener("click", async () => {
  try {
    await sendToActiveTab({ type: "IRIS_OPEN_PANEL" });
    setStatus(popT("popup.openedStatus"));
  } catch (error) {
    setStatus(error.message);
  }
});

checkSelectionButton.addEventListener("click", async () => {
  try {
    const response = await sendToActiveTab({ type: "IRIS_CHECK_CURRENT_SELECTION" });
    setStatus(response?.ok ? popT("popup.checkingStatus") : popT("popup.selectFirst"));
  } catch (error) {
    setStatus(error.message);
  }
});

openOptionsButton.addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});
