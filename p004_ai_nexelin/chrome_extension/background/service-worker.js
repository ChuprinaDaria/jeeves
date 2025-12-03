'use strict';

// Background service worker for Nexelin Chrome extension (Manifest V3).
// Responsibilities (current & future):
// - Central hub for messages between popup and content scripts
// - API calls & memory sync (can offload work from content scripts)
// - Behaviour tracking & proactive suggestions (to be extended)

// Simple debug logger (can be disabled later)
function log(...args) {
  // eslint-disable-next-line no-console
  console.log('[Nexelin SW]', ...args);
}

chrome.runtime.onInstalled.addListener(() => {
  log('Service worker installed');
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


