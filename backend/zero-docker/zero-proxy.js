const http = require('http');
const { URL } = require('url');

const FRONTEND_ORIGIN = 'http://localhost:3000';
const TARGET = 'http://localhost:8788';
const PORT = 8787;

function setCors(res, req) {
  const origin = req?.headers?.origin || FRONTEND_ORIGIN;
  // Allow any localhost origin for development
  if (origin && origin.includes('localhost')) {
    res.setHeader('Access-Control-Allow-Origin', origin);
  } else {
    res.setHeader('Access-Control-Allow-Origin', FRONTEND_ORIGIN);
  }
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-better-auth');
}

function send(res, status, bodyObj, req) {
  const body = JSON.stringify(bodyObj);
  setCors(res, req);
  res.writeHead(status, { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) });
  res.end(body);
}

function trpcBatch(res, data, req, id = "0") {
  // tRPC batch expects string IDs when sent as {"0": ...}
  const response = [{ id: String(id), result: { type: 'data', data } }];
  console.log(`[TRPC Response] ${JSON.stringify(response).substring(0, 200)}...`);
  send(res, 200, response, req);
}

const defaultUserSettings = {
  language: 'en',
  timezone: 'UTC',
  dynamicContent: false,
  externalImages: true,
  customPrompt: '',
  trustedSenders: [],
  isOnboarded: false,
  colorTheme: 'system',
  zeroSignature: true,
  autoRead: true,
  defaultEmailAlias: '',
  categories: [
    { id: 'Important', name: 'Important', searchValue: 'IMPORTANT', order: 0, icon: 'Lightning', isDefault: false },
    { id: 'All Mail', name: 'All Mail', searchValue: '', order: 1, icon: 'Mail', isDefault: true },
    { id: 'Unread', name: 'Unread', searchValue: 'UNREAD', order: 5, icon: 'ScanEye', isDefault: false },
  ],
  undoSendEnabled: false,
  imageCompression: 'medium',
  animations: false,
};

function handleKnownApi(req, res) {
  const url = req.url || '';
  console.log(`[API Request] ${req.method} ${url.substring(0, 100)}`);

  if (url.startsWith('/api/auth/session') || url.startsWith('/api/auth/get-session')) {
    console.log('[Mock] Returning auth session');
    send(res, 200, {
      user: { id: 'user_local_trial', email: 'test@example.com', name: 'Local Trial User' },
      session: { id: 'sess_local', expiresAt: new Date(Date.now() + 24*3600*1000).toISOString() },
    }, req);
    return true;
  }

  if (url.startsWith('/api/public/providers')) {
    console.log('[Mock] Returning providers');
    send(res, 200, [{ id: 'google', name: 'Google', type: 'oauth' }], req);
    return true;
  }

  if (url.startsWith('/api/autumn/customers')) {
    console.log('[Mock] Returning customer trial');
    send(res, 200, {
      id: 'cus_local_trial', trial_activated: true,
      trial_ends_at: new Date(Date.now() + 7*24*3600*1000).toISOString(),
      message: 'Trial activated (local)'
    }, req);
    return true;
  }
  
  if (url.startsWith('/api/autumn/attach')) {
    console.log('[Mock] Returning attach success');
    send(res, 200, { attached: true }, req);
    return true;
  }

  if (url.startsWith('/monitoring/sentry')) {
    console.log('[Mock] Returning sentry ok');
    send(res, 200, { status: 'ok' }, req);
    return true;
  }

  if (url.startsWith('/api/trpc/')) {
    const endpoint = url.split('?')[0].replace('/api/trpc/', '');
    console.log(`[TRPC] Endpoint: ${endpoint}`);
    
    if (url.includes('settings.get')) {
      console.log('[Mock] Returning user settings');
      trpcBatch(res, { settings: defaultUserSettings }, req);
      return true;
    }
    if (url.includes('connections.getDefault')) { 
      console.log('[Mock] Returning null for connections.getDefault');
      trpcBatch(res, null, req); 
      return true; 
    }
    if (url.includes('connections.list')) { 
      console.log('[Mock] Returning empty connections list');
      trpcBatch(res, [], req); 
      return true; 
    }
    if (url.includes('labels.list')) { 
      console.log('[Mock] Returning empty labels');
      trpcBatch(res, [], req); 
      return true; 
    }
    if (url.includes('mail.listThreads')) { 
      console.log('[Mock] Returning empty threads');
      trpcBatch(res, { threads: [], nextCursor: null }, req); 
      return true; 
    }
    if (url.includes('user.getIntercomToken')) { 
      console.log('[Mock] Returning intercom token');
      trpcBatch(res, { token: 'mock-intercom-token' }, req); 
      return true; 
    }
    
    console.log('[Mock] Returning null for unknown TRPC endpoint');
    trpcBatch(res, null, req);
    return true;
  }

  return false;
}

function proxy(req, res) {
  console.log(`[Proxy] Forwarding ${req.method} ${req.url} to ${TARGET}`);
  const targetUrl = new URL(req.url, TARGET);
  const opts = { method: req.method, headers: { ...req.headers, host: targetUrl.host } };
  const prox = http.request(targetUrl, opts, (pres) => {
    setCors(res, req);
    Object.entries(pres.headers || {}).forEach(([k, v]) => {
      const lk = String(k).toLowerCase();
      if (!lk.startsWith('access-control-')) {
        try { res.setHeader(k, v); } catch {}
      }
    });
    res.writeHead(pres.statusCode || 502);
    pres.pipe(res);
  });
  prox.on('error', (err) => {
    console.log(`[Proxy Error] ${err.message}`);
    send(res, 502, { error: 'Bad gateway', detail: String(err.message || err) }, req);
  });
  req.pipe(prox);
}

// Collect request body for debugging
function collectBody(req, callback) {
  let body = '';
  req.on('data', chunk => body += chunk);
  req.on('end', () => {
    if (body) console.log(`[Request Body] ${body.substring(0, 200)}...`);
    callback(body);
  });
}

const server = http.createServer((req, res) => {
  setCors(res, req);
  if (req.method === 'OPTIONS') { 
    console.log('[CORS] Handling OPTIONS request');
    res.writeHead(204); 
    return res.end(); 
  }
  
  // Log body for POST requests
  if (req.method === 'POST') {
    collectBody(req, () => {
      if (handleKnownApi(req, res)) return;
      return proxy(req, res);
    });
  } else {
    if (handleKnownApi(req, res)) return;
    return proxy(req, res);
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Zero proxy DEBUG running on http://localhost:${PORT} → ${TARGET}`);
  console.log('Monitoring all requests...');
});
