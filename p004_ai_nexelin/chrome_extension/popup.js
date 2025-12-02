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

function setProgress(visible, text = 'Working...') {
  const progressEl = document.getElementById('progress');
  const progressText = document.getElementById('progressText');
  if (!progressEl) return;
  if (visible) {
    progressEl.classList.remove('hidden');
    if (progressText) progressText.textContent = text;
  } else {
    progressEl.classList.add('hidden');
  }
}

function setConnectionStatus(text) {
  const badge = document.getElementById('connectionStatus');
  if (!badge) return;
  badge.textContent = text;
}

async function getCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

function updateCurrentDomainLabel() {
  const domainEl = document.getElementById('currentDomain');
  if (!domainEl) return;

  getCurrentTab().then((tab) => {
    if (!tab?.url) {
      domainEl.textContent = 'Current page: unknown';
      return;
    }
    try {
      const url = new URL(tab.url);
      domainEl.textContent = `Current page: ${url.hostname}`;
    } catch (_e) {
      domainEl.textContent = 'Current page: unknown';
    }
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  const tokenInput = document.getElementById('clientToken');
  const saveBtn = document.getElementById('saveToken');
  const scrapBtn = document.getElementById('scrapText');
  const collectBtn = document.getElementById('collectMails');
  const autoModeCheckbox = document.getElementById('autoMode');

  updateCurrentDomainLabel();

  // Load saved token & auto mode
  chrome.storage.sync.get(['clientToken', 'autoMode'], (res) => {
    if (res.clientToken && tokenInput) {
      tokenInput.value = res.clientToken;
      setConnectionStatus('READY');
    } else {
      setConnectionStatus('NO TOKEN');
    }
    if (autoModeCheckbox) {
      autoModeCheckbox.checked = !!res.autoMode;
    }
  });

  saveBtn?.addEventListener('click', () => {
    const token = tokenInput.value.trim();
    chrome.storage.sync.set({ clientToken: token }, () => {
      setStatus(token ? 'Token saved.' : 'Token cleared.', 'ok');
      setConnectionStatus(token ? 'READY' : 'NO TOKEN');
    });
  });

  autoModeCheckbox?.addEventListener('change', (e) => {
    const enabled = e.target.checked;
    chrome.storage.sync.set({ autoMode: enabled }, () => {
      setStatus(
        enabled
          ? 'Auto mode enabled. Extension will scrap & collect on each page automatically.'
          : 'Auto mode disabled. Use buttons to trigger actions.',
        'ok',
      );
    });
  });

  function setLoading(isLoading, label) {
    setProgress(isLoading, label || 'Working...');
    if (scrapBtn) scrapBtn.disabled = isLoading;
    if (collectBtn) collectBtn.disabled = isLoading;
    if (saveBtn) saveBtn.disabled = isLoading;
  }

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

    setLoading(
      true,
      action === 'SCRAP_TEXT' ? 'Scraping page content...' : 'Collecting emails & phones...',
    );

    chrome.tabs.sendMessage(tab.id, payload, (response) => {
      setLoading(false);

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

