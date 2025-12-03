'use strict';

// Local, per-browser memory for chat sessions.
// Hybrid model idea:
// - Persistent, cross-device history lives in backend (via web-conversations endpoint)
// - Fast local cache lives in chrome.storage.local

const SESSIONS_KEY = 'nexelin_chat_sessions';
const SESSION_ID_KEY = 'nexelin_current_session_id';

function readLocal(keys) {
  return new Promise((resolve) => {
    try {
      const storage = chrome && chrome.storage && chrome.storage.local;
      if (!storage) {
        resolve({});
        return;
      }
      storage.get(keys, (result) => {
        if (chrome.runtime && chrome.runtime.lastError) {
          // eslint-disable-next-line no-console
          console.warn('Nexelin extension: local storage get error:', chrome.runtime.lastError.message);
          resolve({});
          return;
        }
        resolve(result || {});
      });
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn('Nexelin extension: local storage get exception:', e);
      resolve({});
    }
  });
}

function writeLocal(obj) {
  return new Promise((resolve) => {
    try {
      const storage = chrome && chrome.storage && chrome.storage.local;
      if (!storage) {
        resolve(false);
        return;
      }
      storage.set(obj, () => {
        if (chrome.runtime && chrome.runtime.lastError) {
          // eslint-disable-next-line no-console
          console.warn('Nexelin extension: local storage set error:', chrome.runtime.lastError.message);
          resolve(false);
          return;
        }
        resolve(true);
      });
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn('Nexelin extension: local storage set exception:', e);
      resolve(false);
    }
  });
}

function generateSessionId() {
  const rand = Math.random().toString(36).slice(2, 10);
  const ts = Date.now().toString(36);
  return `ext_${ts}_${rand}`;
}

export async function getOrCreateSessionId() {
  const data = await readLocal([SESSION_ID_KEY]);
  let sessionId = data && data[SESSION_ID_KEY];
  if (typeof sessionId === 'string' && sessionId.trim()) {
    return sessionId.trim();
  }
  sessionId = generateSessionId();
  await writeLocal({ [SESSION_ID_KEY]: sessionId });
  return sessionId;
}

export async function loadMessages(sessionId) {
  if (!sessionId) return [];
  const data = await readLocal([SESSIONS_KEY]);
  const sessions = (data && data[SESSIONS_KEY]) || {};
  const messages = sessions[sessionId] || [];
  if (!Array.isArray(messages)) return [];
  return messages;
}

export async function saveMessages(sessionId, messages) {
  if (!sessionId) return;
  const data = await readLocal([SESSIONS_KEY]);
  const sessions = (data && data[SESSIONS_KEY]) || {};
  sessions[sessionId] = Array.isArray(messages) ? messages : [];
  await writeLocal({ [SESSIONS_KEY]: sessions });
}

export async function appendMessage(sessionId, message) {
  if (!sessionId || !message) return;
  const messages = await loadMessages(sessionId);
  messages.push(message);
  await saveMessages(sessionId, messages);
}

export async function clearSession(sessionId) {
  if (!sessionId) return;
  const data = await readLocal([SESSIONS_KEY]);
  const sessions = (data && data[SESSIONS_KEY]) || {};
  if (sessions[sessionId]) {
    delete sessions[sessionId];
    await writeLocal({ [SESSIONS_KEY]: sessions });
  }
}


