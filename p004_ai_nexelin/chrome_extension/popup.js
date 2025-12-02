const STATUS_OK_CLASS = 'ok';
const STATUS_ERROR_CLASS = 'error';

function setStatus(message, type = 'ok') {
  const el = document.getElementById('status');
  if (!el) return;
  el.textContent = message || '';
  el.classList.remove(STATUS_OK_CLASS, STATUS_ERROR_CLASS);
  if (message) {
    el.classList.add(type === 'error' ? STATUS_ERROR_CLASS : STATUS_OK_CLASS);
  }
}

async function getCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

document.addEventListener('DOMContentLoaded', async () => {
  const tokenInput = document.getElementById('clientToken');
  const saveBtn = document.getElementById('saveToken');
  const scrapBtn = document.getElementById('scrapText');
  const collectBtn = document.getElementById('collectMails');

  // Load saved token
  chrome.storage.sync.get(['clientToken'], (res) => {
    if (res.clientToken && tokenInput) {
      tokenInput.value = res.clientToken;
    }
  });

  saveBtn?.addEventListener('click', () => {
    const token = tokenInput.value.trim();
    chrome.storage.sync.set({ clientToken: token }, () => {
      setStatus(token ? 'Token saved.' : 'Token cleared.', 'ok');
    });
  });

  async function sendAction(action) {
    setStatus('');
    const token = tokenInput.value.trim();
    if (!token) {
      setStatus('Client token is required. Paste it from Nexelin portal.', 'error');
      return;
    }

    const tab = await getCurrentTab();
    if (!tab?.id) {
      setStatus('No active tab.', 'error');
      return;
    }

    const payload = { type: action, clientToken: token };

    chrome.tabs.sendMessage(tab.id, payload, (response) => {
      if (chrome.runtime.lastError) {
        setStatus('Cannot inject script on this page or content script not loaded.', 'error');
        return;
      }
      if (!response) {
        setStatus('No response from content script.', 'error');
        return;
      }
      if (response.success) {
        setStatus(response.message || 'Data sent to Nexelin backend.', 'ok');
      } else {
        setStatus(response.error || 'Failed to process page.', 'error');
      }
    });
  }

  scrapBtn?.addEventListener('click', () => sendAction('SCRAP_TEXT'));
  collectBtn?.addEventListener('click', () => sendAction('COLLECT_MAILS'));
});


