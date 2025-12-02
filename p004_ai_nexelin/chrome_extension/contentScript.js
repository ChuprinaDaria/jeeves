// Default backend URL for Nexelin clients.
// You can change this via extension source if you use a different host.
const DEFAULT_BACKEND_URL = 'https://app.nexelin.com/api/clients/extension/page/';

function getBackendUrl() {
  // For now we keep a single constant; can be extended to read from storage later.
  return DEFAULT_BACKEND_URL;
}

function collectStructuredContent() {
  const doc = document;

  // Headings h1-h6 with level and text
  const headings = Array.from(doc.querySelectorAll('h1, h2, h3, h4, h5, h6')).map((h) => ({
    level: h.tagName.toLowerCase(),
    text: h.innerText.trim(),
  }));

  // Lists (ul/ol) – store type and items text
  const lists = Array.from(doc.querySelectorAll('ul, ol')).map((list) => ({
    type: list.tagName.toLowerCase(),
    items: Array.from(list.querySelectorAll('li'))
      .map((li) => li.innerText.trim())
      .filter(Boolean),
  }));

  // Tables – simple representation with header + rows
  const tables = Array.from(doc.querySelectorAll('table')).map((table) => {
    const headers = Array.from(table.querySelectorAll('thead tr th')).map((th) =>
      th.innerText.trim(),
    );
    const bodyRows = table.querySelectorAll('tbody tr');
    const rows =
      bodyRows.length > 0
        ? Array.from(bodyRows).map((tr) =>
            Array.from(tr.querySelectorAll('td')).map((td) => td.innerText.trim()),
          )
        : Array.from(table.querySelectorAll('tr')).map((tr) =>
            Array.from(tr.querySelectorAll('td')).map((td) => td.innerText.trim()),
          );
    return { headers, rows };
  });

  // Quotes / highlights – blockquote + mark elements
  const quoteNodes = new Set([
    ...Array.from(doc.querySelectorAll('blockquote')),
    ...Array.from(doc.querySelectorAll('mark')),
  ]);
  const quotes = Array.from(quoteNodes).map((el) => el.innerText.trim()).filter(Boolean);

  const title = doc.title || '';
  const url = window.location.href;
  const fullText = doc.body ? doc.body.innerText || '' : '';

  let siteName = '';
  try {
    const u = new URL(url);
    siteName = u.host;
  } catch (e) {
    siteName = window.location.host || '';
  }

  return {
    url,
    title,
    site_name: siteName,
    headings,
    lists,
    tables,
    quotes,
    full_text: fullText,
  };
}

async function sendToBackend(mode, clientToken) {
  const backendUrl = getBackendUrl();
  const payload = collectStructuredContent();
  payload.mode = mode || 'both';

  const res = await fetch(backendUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Client-Token': clientToken,
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data.error) {
        msg = data.error;
      }
    } catch (e) {
      // ignore
    }
    throw new Error(msg);
  }

  const data = await res.json();
  return data;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !message.type) {
    return;
  }

  const { type, clientToken } = message;
  if (!clientToken) {
    sendResponse({ success: false, error: 'Client token is missing.' });
    return;
  }

  let mode = 'both';
  if (type === 'SCRAP_TEXT') {
    mode = 'scrap';
  } else if (type === 'COLLECT_MAILS') {
    mode = 'collect';
  }

  (async () => {
    try {
      const result = await sendToBackend(mode, clientToken);
      const collected =
        result && result.entities
          ? [
              (result.entities.emails || []).length,
              (result.entities.phones || []).length,
              (result.entities.addresses || []).length,
            ]
          : [0, 0, 0];
      const [emailsCount, phonesCount, addressesCount] = collected;

      let messageText = 'Page content sent to Nexelin backend.';
      if (mode === 'collect' || mode === 'both') {
        messageText += ` Found emails: ${emailsCount}, phones: ${phonesCount}, addresses: ${addressesCount}.`;
      }

      sendResponse({ success: true, message: messageText });
    } catch (e) {
      console.error('Nexelin extension error:', e);
      sendResponse({ success: false, error: e.message || 'Failed to send data to backend.' });
    }
  })();

  // Indicate that we will respond asynchronously
  return true;
});


