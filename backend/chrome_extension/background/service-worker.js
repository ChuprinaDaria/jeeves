'use strict';

// Background service worker for Concierge Chrome extension (Manifest V3).
// Responsibilities (current & future):
// - Central hub for messages between popup and content scripts
// - API calls & memory sync (can offload work from content scripts)
// - Behaviour tracking & proactive suggestions (to be extended)

import { extractCookies, openLoginPopup, pollForCookies } from '../content/cookie-extractor.js';

// Simple debug logger (can be disabled later)
function log(...args) {
  // eslint-disable-next-line no-console
  console.log('[Concierge SW]', ...args);
}

chrome.runtime.onInstalled.addListener(() => {
  log('Service worker installed');
});

// Open side panel when the extension icon is clicked
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ tabId: tab.id });
});

const DEFAULT_API_BASE = 'http://localhost:8000/api';

// Map extension-internal bridge slugs to the matrix bridge network names
// expected by /api/tools/matrix/bridges/<network>/...
const BRIDGE_NETWORK_MAP = {
  'meta-instagram': 'instagram',
  'meta-facebook': 'facebook',
  'instagram': 'instagram',
  'facebook': 'facebook',
  // LinkedIn isn't a Matrix bridge yet — left here for the future endpoint.
  'linkedin': 'linkedin',
};

async function runBridgeAuth({ bridgeType, apiBaseUrl, clientToken }) {
  const tabId = await openLoginPopup(bridgeType);
  if (!tabId) return { error: 'Failed to open login tab' };

  const result = await pollForCookies(bridgeType, tabId);
  if (!result.complete) {
    return {
      error: result.error || 'Cookie extraction failed. Sign in fully and try again.',
      missing: result.missing,
    };
  }

  const network = BRIDGE_NETWORK_MAP[bridgeType] || bridgeType;
  const base = (apiBaseUrl || DEFAULT_API_BASE).replace(/\/$/, '');
  const headers = { 'Content-Type': 'application/json' };
  if (clientToken) headers['X-Client-Token'] = clientToken;

  const resp = await fetch(`${base}/tools/matrix/bridges/${network}/login/cookies/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ cookies: result.cookies }),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) return { error: data.error || `HTTP ${resp.status}` };

  return {
    success: data.status === 'connected',
    status: data.status,
    message: data.message,
    remote_handle: data.remote_handle,
  };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !message.type) {
    return;
  }

  if (message.type === 'BRIDGE_CONNECT') {
    const { bridgeType, apiBaseUrl, clientToken } = message;
    (async () => {
      try {
        const r = await runBridgeAuth({ bridgeType, apiBaseUrl, clientToken });
        sendResponse(r);
      } catch (e) {
        sendResponse({ error: e.message || 'Unknown error' });
      }
    })();
    return true;
  }

  if (message.type === 'BRIDGE_STATE') {
    const { bridgeType, apiBaseUrl, clientToken } = message;
    (async () => {
      try {
        const network = BRIDGE_NETWORK_MAP[bridgeType] || bridgeType;
        const base = (apiBaseUrl || DEFAULT_API_BASE).replace(/\/$/, '');
        const headers = {};
        if (clientToken) headers['X-Client-Token'] = clientToken;
        const resp = await fetch(`${base}/tools/matrix/bridges/${network}/state/`, { headers });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          sendResponse({ error: data.error || `HTTP ${resp.status}` });
          return;
        }
        sendResponse(data);
      } catch (e) {
        sendResponse({ error: e.message || 'Unknown error' });
      }
    })();
    return true;
  }

  if (message.type === 'BEHAVIOUR_EVENT') {
    // Behaviour events from content scripts (scroll depth, form focus, clicks, etc.)
    // For now just log them; later we can aggregate and trigger proactive suggestions.
    log('Behaviour event:', {
      event: message.event,
      payload: message.payload,
      url: sender && sender.tab ? sender.tab.url : undefined,
    });
    sendResponse({ ok: true });
    return true;
  }

  if (message.type === 'AUTOMATION_REQUEST') {
    // Placeholder for future automation engine integration.
    // The idea: popup/content sends high-level task,
    // background may call backend /api/automation/execute/ or similar.
    log('Automation request (stub):', message.task);
    sendResponse({ ok: false, error: 'Automation engine not implemented yet.' });
    return true;
  }

  // Unknown message type – no-op
  return undefined;
});

// ===== Bridge Cookie Extraction (external trigger from /integrations page) =====

chrome.runtime.onMessageExternal.addListener(
  (message, sender, sendResponse) => {
    if (message.action === 'concierge_bridge_auth') {
      const { bridgeType, apiBaseUrl, authToken, clientToken } = message;

      (async () => {
        try {
          const tabId = await openLoginPopup(bridgeType);
          if (!tabId) {
            sendResponse({ error: 'Failed to open login tab' });
            return;
          }

          const result = await pollForCookies(bridgeType, tabId);

          if (result.complete) {
            const network = BRIDGE_NETWORK_MAP[bridgeType] || bridgeType;
            const base = (apiBaseUrl || '').replace(/\/$/, '');
            const headers = { 'Content-Type': 'application/json' };
            if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
            if (clientToken) headers['X-Client-Token'] = clientToken;

            const resp = await fetch(
              `${base}/tools/matrix/bridges/${network}/login/cookies/`,
              {
                method: 'POST',
                headers,
                body: JSON.stringify({ cookies: result.cookies }),
              }
            );

            const data = await resp.json().catch(() => ({}));
            if (!resp.ok) {
              sendResponse({ error: data.error || `HTTP ${resp.status}` });
              return;
            }
            sendResponse({
              success: data.status === 'connected',
              status: data.status,
              message: data.message,
              remote_handle: data.remote_handle,
            });
          } else {
            sendResponse({ error: result.error || 'Cookie extraction failed', missing: result.missing });
          }
        } catch (e) {
          sendResponse({ error: e.message });
        }
      })();

      return true; // async sendResponse
    }

    if (message.action === 'concierge_check_extension') {
      sendResponse({ installed: true, version: chrome.runtime.getManifest().version });
      return;
    }
  }
);
