// Default backend URL for Concierge clients.
// You can change this via extension source if you use a different host.
const DEFAULT_BACKEND_URL = 'http://localhost:8000/api/clients/extension/page/';

function getBackendUrl() {
  // For now we keep a single constant; can be extended to read from storage later.
  return DEFAULT_BACKEND_URL;
}

// Auto mode: if enabled, automatically scrap & collect on page load
async function maybeAutoRun() {
  try {
    const { clientToken, autoMode } = await chrome.storage.sync.get(['clientToken', 'autoMode']);
    if (!autoMode || !clientToken) {
      return;
    }
    console.log('Concierge extension: Auto mode active, sending both scrap & collect');
    await sendToBackend('both', clientToken.trim());
  } catch (e) {
    console.error('Concierge extension: Auto mode failed:', e);
  }
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

  console.log('Concierge extension: Sending POST to:', backendUrl);
  console.log('Concierge extension: Payload keys:', Object.keys(payload));
  console.log('Concierge extension: Client token:', clientToken ? clientToken.substring(0, 10) + '...' : 'MISSING');

  let res;
  try {
    res = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Client-Token': clientToken,
      },
      body: JSON.stringify(payload),
    });
    console.log('Concierge extension: Response status:', res.status, res.statusText);
    console.log('Concierge extension: Response headers:', Object.fromEntries(res.headers.entries()));
  } catch (networkError) {
    console.error('Concierge extension: Network error:', networkError);
    throw new Error(`Network error: ${networkError.message}. Check if ${backendUrl} is accessible.`);
  }

  // Check Content-Type before parsing
  const contentType = res.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  console.log('Concierge extension: Content-Type:', contentType, 'isJson:', isJson);

  if (!res.ok) {
    let msg = `HTTP ${res.status}: ${res.statusText}`;
    if (isJson) {
      try {
        const data = await res.json();
        if (data.error) {
          msg = data.error;
        } else if (data.detail) {
          msg = data.detail;
        }
      } catch (e) {
        console.error('Failed to parse error response:', e);
      }
    } else {
      // If not JSON, try to get text
      try {
        const text = await res.text();
        // Check if it's HTML (common Django error pages)
        if (text.includes('<!doctype') || text.includes('<html')) {
          msg = `Server returned HTML error page (${res.status}). Check if extension is enabled for your client.`;
        } else {
          msg = text.substring(0, 200); // Limit error message length
        }
      } catch (e) {
        console.error('Failed to read error response:', e);
      }
    }
    throw new Error(msg);
  }

  if (!isJson) {
    // Try to get text to see what we actually received
    let errorText = '';
    let responseText = '';
    try {
      responseText = await res.clone().text();
      console.error('Concierge extension: Non-JSON response received:', responseText.substring(0, 500));
      
      if (responseText.includes('<!doctype') || responseText.includes('<html')) {
        // Extract title or error message from HTML if possible
        const titleMatch = responseText.match(/<title>(.*?)<\/title>/i);
        const title = titleMatch ? titleMatch[1] : 'Unknown error';
        
        errorText = `Server returned HTML instead of JSON (Status: ${res.status} ${res.statusText}).\n\n`;
        errorText += `Possible causes:\n`;
        errorText += `1. Extension is not enabled for your client (check admin panel: extension_enabled=True)\n`;
        errorText += `2. Invalid client token (current: ${clientToken ? clientToken.substring(0, 10) + '...' : 'MISSING'})\n`;
        errorText += `3. CORS issue (chrome-extension:// origin may be blocked)\n`;
        errorText += `4. Server error or wrong URL\n\n`;
        errorText += `Response title: ${title}\n`;
        errorText += `URL: ${backendUrl}`;
      } else {
        errorText = `Server returned non-JSON response.\nContent-Type: ${contentType}\nStatus: ${res.status} ${res.statusText}\nResponse preview: ${responseText.substring(0, 300)}`;
      }
    } catch (e) {
      console.error('Concierge extension: Failed to read response text:', e);
      errorText = `Server did not return JSON response. Content-Type: ${contentType}. Status: ${res.status} ${res.statusText}`;
    }
    throw new Error(errorText);
  }

  try {
    const data = await res.json();
    return data;
  } catch (e) {
    console.error('Failed to parse JSON response:', e);
    throw new Error('Invalid JSON response from server: ' + e.message);
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !message.type) {
    return;
  }

  const { type, clientToken } = message;
  
  // Handle GET_PAGE_CONTEXT request from popup for chat
  if (type === 'GET_PAGE_CONTEXT') {
    try {
      const pageData = collectStructuredContent();
      sendResponse(pageData);
    } catch (err) {
      console.error('Failed to collect page context:', err);
      sendResponse(null);
    }
    return;
  }
  
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
      console.log('Concierge extension: Sending request with mode:', mode, 'token:', clientToken ? clientToken.substring(0, 10) + '...' : 'missing');
      const result = await sendToBackend(mode, clientToken);
      console.log('Concierge extension: Response received:', result);
      
      const collected =
        result && result.entities
          ? [
              (result.entities.emails || []).length,
              (result.entities.phones || []).length,
              (result.entities.addresses || []).length,
            ]
          : [0, 0, 0];
      const [emailsCount, phonesCount, addressesCount] = collected;

      let messageText = 'Page content sent to Concierge backend.';
      if (mode === 'collect' || mode === 'both') {
        messageText += ` Found emails: ${emailsCount}, phones: ${phonesCount}, addresses: ${addressesCount}.`;
      }

      sendResponse({ success: true, message: messageText });
    } catch (e) {
      console.error('Concierge extension error:', e);
      const errorMsg = e.message || 'Failed to send data to backend.';
      console.error('Error details:', errorMsg);
      sendResponse({ success: false, error: errorMsg });
    }
  })();

  // Indicate that we will respond asynchronously
  return true;
});

// Trigger auto mode on page load (non-blocking)
maybeAutoRun();

