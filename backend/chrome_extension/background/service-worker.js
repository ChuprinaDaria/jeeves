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

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !message.type) {
    return;
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

// ===== Bridge Cookie Extraction =====

chrome.runtime.onMessageExternal.addListener(
  (message, sender, sendResponse) => {
    if (message.action === 'concierge_bridge_auth') {
      const { bridgeType, apiBaseUrl, authToken } = message;

      (async () => {
        try {
          const tabId = await openLoginPopup(bridgeType);
          if (!tabId) {
            sendResponse({ error: 'Failed to open login tab' });
            return;
          }

          const result = await pollForCookies(bridgeType, tabId);

          if (result.complete) {
            const resp = await fetch(`${apiBaseUrl}/clients/bridges/${bridgeType}/login/cookies/`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`,
              },
              body: JSON.stringify({ cookies: result.cookies }),
            });

            const data = await resp.json();
            sendResponse({ success: true, status: data.status });
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
