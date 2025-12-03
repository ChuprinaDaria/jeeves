import { sendChatMessage, logWebConversation } from './lib/api-client.js';
import {
  getOrCreateSessionId,
  loadMessages,
  appendMessage,
} from './lib/memory-manager.js';
import {
  isSpeechRecognitionSupported,
  isSpeechSynthesisSupported,
  startSpeechRecognition,
  speakText,
} from './lib/speech-handler.js';

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
    if (!tab || !tab.url) {
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

function renderMessages(container, messages) {
  if (!container) return;
  container.innerHTML = '';
  if (!Array.isArray(messages) || messages.length === 0) {
    const emptyEl = document.createElement('div');
    emptyEl.className = 'secondary-text';
    emptyEl.textContent = 'No messages yet. Start a conversation with your assistant.';
    container.appendChild(emptyEl);
    return;
  }

  messages.forEach((msg) => {
    const row = document.createElement('div');
    row.style.marginBottom = '6px';
    const roleLabel = msg.role === 'assistant' ? 'Assistant' : 'You';
    const roleColor = msg.role === 'assistant' ? '#93c5fd' : '#bbf7d0';
    row.innerHTML = `<div style="font-size:11px;color:${roleColor};font-weight:500;margin-bottom:1px;">${roleLabel}</div>
      <div style="white-space:pre-wrap;">${msg.content}</div>`;
    container.appendChild(row);
  });

  container.scrollTop = container.scrollHeight;
}

document.addEventListener('DOMContentLoaded', async () => {
  const tokenInput = document.getElementById('clientToken');
  const saveBtn = document.getElementById('saveToken');
  const scrapBtn = document.getElementById('scrapText');
  const collectBtn = document.getElementById('collectMails');
  const autoModeCheckbox = document.getElementById('autoMode');

  const chatMessagesEl = document.getElementById('chatMessages');
  const chatInputEl = document.getElementById('chatInput');
  const chatSendBtn = document.getElementById('chatSend');
  const chatMicBtn = document.getElementById('chatMic');
  const chatMicLabel = document.getElementById('chatMicLabel');
  const chatSpeakBtn = document.getElementById('chatSpeak');

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
    const token = (tokenInput && tokenInput.value ? tokenInput.value : '').trim();
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
    const token = (tokenInput && tokenInput.value ? tokenInput.value : '').trim();
    if (!token) {
      setStatus('Client token is required. Paste it from Nexelin portal.', 'error');
      return;
    }

    const tab = await getCurrentTab();
    if (!tab || !tab.id) {
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

  // --- Chat logic ---
  let currentSessionId = await getOrCreateSessionId();
  let currentMessages = await loadMessages(currentSessionId);
  let isSending = false;
  let recognitionController = null;

  renderMessages(chatMessagesEl, currentMessages);

  // Voice feature availability
  if (!isSpeechRecognitionSupported() && chatMicBtn) {
    chatMicBtn.disabled = true;
    if (chatMicLabel) chatMicLabel.textContent = 'Voice (N/A)';
  }
  if (!isSpeechSynthesisSupported() && chatSpeakBtn) {
    chatSpeakBtn.disabled = true;
  }

  async function sendChat() {
    if (!chatInputEl) return;
    const text = chatInputEl.value.trim();
    if (!text || isSending) return;

    const token = (tokenInput && tokenInput.value ? tokenInput.value : '').trim();
    if (!token) {
      setStatus('Client token is required for chat. Paste it from Nexelin portal.', 'error');
      return;
    }

    isSending = true;
    if (chatSendBtn) chatSendBtn.disabled = true;
    if (chatMicBtn) chatMicBtn.disabled = true;

    const userMessage = {
      id: `u_${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };

    currentMessages.push(userMessage);
    await appendMessage(currentSessionId, userMessage);
    renderMessages(chatMessagesEl, currentMessages);
    chatInputEl.value = '';

    try {
      // Get current page context from active tab
      const pageContext = await getCurrentPageContext();
      
      const apiResult = await sendChatMessage({
        message: text,
        sessionId: currentSessionId,
        clientToken: token,
        pageContext: pageContext,
      });
      const assistantText =
        (apiResult && (apiResult.response || apiResult.answer || apiResult.content)) ||
        'No response from server.';

      const assistantMessage = {
        id: `a_${Date.now()}`,
        role: 'assistant',
        content: assistantText,
        timestamp: new Date().toISOString(),
      };

      currentMessages.push(assistantMessage);
      await appendMessage(currentSessionId, assistantMessage);
      renderMessages(chatMessagesEl, currentMessages);

      // Fire-and-forget logging to backend
      await logWebConversation({
        sessionId: currentSessionId,
        message: text,
        response: assistantText,
        platform: 'chrome_extension',
        clientToken: token,
      });
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Nexelin extension chat error:', e);
      setStatus(e && e.message ? e.message : 'Failed to send chat message.', 'error');
    } finally {
      isSending = false;
      if (chatSendBtn) chatSendBtn.disabled = false;
      if (chatMicBtn && isSpeechRecognitionSupported()) chatMicBtn.disabled = false;
    }
  }

  chatSendBtn?.addEventListener('click', () => {
    sendChat();
  });

  chatInputEl?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChat();
    }
  });

  /**
   * Get current page context from active tab content script
   * @returns {Promise<Object|null>} Page context with url, title, headings, full_text etc.
   */
  chatMicBtn?.addEventListener('click', () => {
    if (!isSpeechRecognitionSupported() || !chatInputEl) return;

    if (recognitionController) {
      recognitionController.stop();
      recognitionController = null;
      if (chatMicLabel) chatMicLabel.textContent = 'Voice';
      return;
    }

    recognitionController = startSpeechRecognition({
      lang: 'en-US',
      onResult: (text) => {
        if (!chatInputEl) return;
        const existing = chatInputEl.value.trim();
        chatInputEl.value = existing ? `${existing} ${text}` : text;
      },
      onError: () => {
        recognitionController = null;
        if (chatMicLabel) chatMicLabel.textContent = 'Voice';
      },
      onEnd: () => {
        recognitionController = null;
        if (chatMicLabel) chatMicLabel.textContent = 'Voice';
      },
    });

    if (chatMicLabel) chatMicLabel.textContent = 'Listening…';
  });

  chatSpeakBtn?.addEventListener('click', () => {
    if (!isSpeechSynthesisSupported()) return;
    if (!currentMessages || currentMessages.length === 0) return;
    const lastAssistant = [...currentMessages].reverse().find((m) => m.role === 'assistant');
    if (!lastAssistant) return;
    speakText(lastAssistant.content || '', { lang: 'en-US' });
  });
});

