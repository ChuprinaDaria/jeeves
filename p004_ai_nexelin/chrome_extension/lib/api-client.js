'use strict';

// Simple API client for Nexelin backend, used by the Chrome extension popup/background.
// Responsibilities:
// - Resolve base API URL (with optional override from chrome.storage)
// - Attach X-Client-Token header
// - Provide helpers for chat + conversation logging

const DEFAULT_API_BASE_URL = 'https://api.nexelin.com';

function normalizeBaseUrl(url) {
  if (!url || typeof url !== 'string') return DEFAULT_API_BASE_URL;
  return url.trim().replace(/\/+$/, '');
}

function readFromStorage(area, keys) {
  return new Promise((resolve) => {
    try {
      const storage = chrome && chrome.storage && chrome.storage[area];
      if (!storage) {
        resolve({});
        return;
      }
      storage.get(keys, (result) => {
        if (chrome.runtime && chrome.runtime.lastError) {
          // eslint-disable-next-line no-console
          console.warn('Nexelin extension: storage get error:', chrome.runtime.lastError.message);
          resolve({});
          return;
        }
        resolve(result || {});
      });
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn('Nexelin extension: storage get exception:', e);
      resolve({});
    }
  });
}

async function getApiBaseUrl() {
  const result = await readFromStorage('sync', ['backendBaseUrl']);
  if (result && typeof result.backendBaseUrl === 'string' && result.backendBaseUrl.trim()) {
    return normalizeBaseUrl(result.backendBaseUrl);
  }
  return DEFAULT_API_BASE_URL;
}

async function getClientTokenFromStorage() {
  const result = await readFromStorage('sync', ['clientToken']);
  if (result && typeof result.clientToken === 'string') {
    return result.clientToken.trim();
  }
  return '';
}

async function doJsonRequest(path, options) {
  const baseUrl = await getApiBaseUrl();
  const url = `${baseUrl.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`;

  const finalOptions = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(options && options.headers ? options.headers : {}),
    },
    body: options && options.body ? JSON.stringify(options.body) : '{}',
  };

  const res = await fetch(url, finalOptions);
  const contentType = res.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');

  if (!res.ok) {
    let msg = `HTTP ${res.status}: ${res.statusText}`;
    if (isJson) {
      try {
        const data = await res.json();
        if (data && (data.error || data.detail)) {
          msg = data.error || data.detail;
        }
      } catch (e) {
        // ignore JSON parse error here
      }
    } else {
      try {
        const text = await res.text();
        msg = text.slice(0, 300);
      } catch (e) {
        // ignore
      }
    }
    throw new Error(msg);
  }

  if (!isJson) {
    const preview = await res.text();
    throw new Error(
      `Unexpected non-JSON response from ${url}. Status: ${res.status}. Preview: ${preview.slice(0, 300)}`
    );
  }

  return res.json();
}

/**
 * Send chat message to Nexelin PublicRAGChatView.
 *
 * @param {Object} params
 * @param {string} params.message - User message text
 * @param {string} [params.sessionId] - Optional session identifier
 * @param {string} [params.language] - Optional language code (en, de, it, etc.)
 * @param {string} [params.clientToken] - Optional client token override
 * @returns {Promise<{ response: string, sources?: any[], num_chunks?: number, total_tokens?: number }>}
 */
export async function sendChatMessage({ message, sessionId, language, clientToken }) {
  if (!message || typeof message !== 'string') {
    throw new Error('Message is required');
  }

  const token = (clientToken && clientToken.trim()) || (await getClientTokenFromStorage());
  if (!token) {
    throw new Error('Client token is missing. Please configure it in the extension popup.');
  }

  const headers = {
    'X-Client-Token': token,
  };

  const body = {
    message,
  };

  if (sessionId) {
    body.session_id = sessionId;
  }
  if (language) {
    body.language = language;
  }

  return doJsonRequest('/api/chat/', { headers, body });
}

/**
 * Log web conversation (user + assistant message) for analytics/history.
 *
 * @param {Object} params
 * @param {string} params.sessionId
 * @param {string} params.message
 * @param {string} params.response
 * @param {string} [params.platform='chrome_extension']
 * @param {string} [params.clientToken]
 */
export async function logWebConversation({ sessionId, message, response, platform = 'chrome_extension', clientToken }) {
  if (!sessionId) return;

  const token = (clientToken && clientToken.trim()) || (await getClientTokenFromStorage());
  if (!token) {
    // Logging is optional; do not throw
    return;
  }

  const headers = {
    'X-Client-Token': token,
  };

  const body = {
    session_id: sessionId,
    message: message || '',
    response: response || '',
    platform,
  };

  try {
    await doJsonRequest('/api/clients/web-conversations/', { headers, body });
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn('Nexelin extension: failed to log web conversation:', e);
  }
}

/**
 * Placeholder for potential future backend-powered history.
 * For now, popup uses local storage via memory-manager.
 */
export async function fetchChatHistoryFromBackend(_sessionId) {
  return [];
}


