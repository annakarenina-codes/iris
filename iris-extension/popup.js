const DEFAULTS = {
  irisBackendUrl: "http://127.0.0.1:5000" // iris:backend-url
};

const backendUrl = document.getElementById("backend-url");
const statusText = document.getElementById("popup-status");
const openPanelButton = document.getElementById("open-panel");
const checkSelectionButton = document.getElementById("check-selection");
const openOptionsButton = document.getElementById("open-options");

function setStatus(message) {
  statusText.textContent = message || "";
}

function getActiveTab() {
  return chrome.tabs.query({ active: true, currentWindow: true }).then((tabs) => tabs[0]);
}

async function sendToActiveTab(message) {
  const tab = await getActiveTab();
  if (!tab?.id) {
    throw new Error("No active tab found.");
  }

  try {
    return await chrome.tabs.sendMessage(tab.id, message);
  } catch (_error) {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["src/content.js"]
    });
    return chrome.tabs.sendMessage(tab.id, message);
  }
}

chrome.storage.sync.get(DEFAULTS, (items) => {
  backendUrl.textContent = items.irisBackendUrl || DEFAULTS.irisBackendUrl;
});

openPanelButton.addEventListener("click", async () => {
  try {
    await sendToActiveTab({ type: "IRIS_OPEN_PANEL" });
    setStatus("IRIS panel opened on this page.");
  } catch (error) {
    setStatus(error.message);
  }
});

checkSelectionButton.addEventListener("click", async () => {
  try {
    const response = await sendToActiveTab({ type: "IRIS_CHECK_CURRENT_SELECTION" });
    setStatus(response?.ok ? "Checking selected text." : "Select text on the page first.");
  } catch (error) {
    setStatus(error.message);
  }
});

openOptionsButton.addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});
