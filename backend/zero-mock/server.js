/**
 * Mock Zero Email Server
 * Эмулятор Zero для тестирования интеграции
 */

const http = require('http');
const url = require('url');

const FRONTEND_PORT = 3000;
const BACKEND_PORT = 8787;

// Mock user session
const mockSession = {
  user: {
    id: "mock-user-123",
    email: "demo@zero.email",
    name: "Demo User",
    image: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  },
  session: {
    id: "mock-session-123",
    expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    ipAddress: "127.0.0.1",
    userAgent: "Mozilla/5.0"
  }
};

// Mock emails
const mockThreads = [
  {
    id: "thread-1",
    subject: "🎉 Добро пожаловать в Zero Email",
    snippet: "Zero - это AI-powered email клиент для управления вашей почтой",
    from: "welcome@zero.email",
    to: ["demo@zero.email"],
    date: new Date().toISOString(),
    unread: false,
    labelIds: ["INBOX"]
  },
  {
    id: "thread-2",
    subject: "📧 Подключите ваш Gmail аккаунт",
    snippet: "Нажмите 'Sign in with Google' чтобы подключить реальный Gmail",
    from: "support@zero.email",
    to: ["demo@zero.email"],
    date: new Date(Date.now() - 3600000).toISOString(),
    unread: true,
    labelIds: ["INBOX", "IMPORTANT"]
  },
  {
    id: "thread-3",
    subject: "🤖 AI функции Zero",
    snippet: "Zero использует AI для автоматической категоризации, ответов и управления почтой",
    from: "ai@zero.email",
    to: ["demo@zero.email"],
    date: new Date(Date.now() - 7200000).toISOString(),
    unread: false,
    labelIds: ["INBOX"]
  }
];

// Backend API server
const backendServer = http.createServer((req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', `http://localhost:${FRONTEND_PORT}`);
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-better-auth');
  res.setHeader('Access-Control-Allow-Credentials', 'true');

  // Handle OPTIONS
  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  const parsedUrl = url.parse(req.url, true);
  const pathname = parsedUrl.pathname;

  console.log(`[Backend] ${req.method} ${pathname}`);

  // Mock API endpoints
  if (pathname === '/api/auth/get-session' || pathname === '/api/auth/session') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(mockSession));
  } 
  else if (pathname === '/api/auth/signin/google') {
    // Redirect to Google OAuth (если есть credentials)
    const clientId = process.env.GOOGLE_CLIENT_ID;
    if (clientId) {
      const googleAuthUrl = `https://accounts.google.com/o/oauth2/v2/auth?` +
        `client_id=${clientId}&` +
        `redirect_uri=http://localhost:${FRONTEND_PORT}/api/auth/callback/google&` +
        `response_type=code&` +
        `scope=https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/gmail.compose&` +
        `access_type=offline&` +
        `prompt=consent`;
      
      res.writeHead(302, { 'Location': googleAuthUrl });
      res.end();
    } else {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ 
        error: "Google OAuth не настроен. Добавьте GOOGLE_CLIENT_ID в .env" 
      }));
    }
  }
  else if (pathname === '/api/threads' || pathname === '/threads') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ 
      threads: mockThreads,
      nextPageToken: null
    }));
  }
  else if (pathname === '/api/labels' || pathname === '/labels') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ 
      labels: [
        { id: "INBOX", name: "Входящие", type: "system", messagesTotal: 3, messagesUnread: 1 },
        { id: "SENT", name: "Отправленные", type: "system", messagesTotal: 0 },
        { id: "DRAFT", name: "Черновики", type: "system", messagesTotal: 0 },
        { id: "SPAM", name: "Спам", type: "system", messagesTotal: 0 },
        { id: "TRASH", name: "Корзина", type: "system", messagesTotal: 0 }
      ]
    }));
  }
  else {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ 
      status: 'ok',
      service: 'Zero Mock Backend',
      endpoint: pathname,
      timestamp: new Date().toISOString()
    }));
  }
});

// Frontend server (простая HTML страница)
const frontendServer = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true);
  const pathname = parsedUrl.pathname;

  console.log(`[Frontend] ${req.method} ${pathname}`);

  if (pathname === '/') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(`<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zero Email - Mock Version</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 600px;
            width: 100%;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
        }
        .status {
            background: #f0f0f0;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .status h3 {
            margin-top: 0;
            color: #333;
        }
        .status-item {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 5px 0;
            border-bottom: 1px solid #e0e0e0;
        }
        .status-ok { color: #4caf50; font-weight: bold; }
        .status-pending { color: #ff9800; font-weight: bold; }
        .button {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 12px 30px;
            border-radius: 6px;
            text-decoration: none;
            margin: 10px 10px 10px 0;
            transition: background 0.3s;
        }
        .button:hover {
            background: #5a67d8;
        }
        .button-google {
            background: #4285f4;
        }
        .button-google:hover {
            background: #357ae8;
        }
        .emails {
            margin-top: 30px;
        }
        .email-item {
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 15px;
            margin: 10px 0;
            transition: box-shadow 0.3s;
        }
        .email-item:hover {
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .email-subject {
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }
        .email-snippet {
            color: #666;
            font-size: 14px;
        }
        .email-meta {
            color: #999;
            font-size: 12px;
            margin-top: 5px;
        }
        .unread {
            border-left: 3px solid #4285f4;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📧 Zero Email Service</h1>
        <p class="subtitle">Mock версия для тестирования интеграции</p>
        
        <div class="status">
            <h3>Статус системы</h3>
            <div class="status-item">
                <span>Frontend</span>
                <span class="status-ok">✅ Работает (порт ${FRONTEND_PORT})</span>
            </div>
            <div class="status-item">
                <span>Backend API</span>
                <span class="status-ok">✅ Работает (порт ${BACKEND_PORT})</span>
            </div>
            <div class="status-item">
                <span>База данных</span>
                <span class="status-ok">✅ Mock режим</span>
            </div>
            <div class="status-item">
                <span>Google OAuth</span>
                <span class="${process.env.GOOGLE_CLIENT_ID ? 'status-ok' : 'status-pending'}">
                    ${process.env.GOOGLE_CLIENT_ID ? '✅ Настроен' : '⏳ Требует настройки'}
                </span>
            </div>
        </div>

        <div>
            <a href="http://localhost:${BACKEND_PORT}/api/auth/signin/google" class="button button-google">
                🔐 Sign in with Google
            </a>
            <a href="http://localhost:${BACKEND_PORT}/api/threads" class="button" target="_blank">
                📋 API: Threads
            </a>
            <a href="http://localhost:${BACKEND_PORT}/api/auth/session" class="button" target="_blank">
                👤 API: Session
            </a>
        </div>

        <div class="emails">
            <h3>📨 Demo письма</h3>
            ${mockThreads.map(thread => `
                <div class="email-item ${thread.unread ? 'unread' : ''}">
                    <div class="email-subject">${thread.subject}</div>
                    <div class="email-snippet">${thread.snippet}</div>
                    <div class="email-meta">От: ${thread.from} • ${new Date(thread.date).toLocaleString('ru-RU')}</div>
                </div>
            `).join('')}
        </div>

        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
            <p style="color: #666; font-size: 14px;">
                💡 <strong>Совет:</strong> Для работы с реальным Gmail настройте Google OAuth credentials в файле .env
            </p>
            <p style="color: #999; font-size: 12px;">
                Zero Mock Server v1.0 • Django AI Nexelin Integration
            </p>
        </div>
    </div>
</body>
</html>`);
  } else {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('404 Not Found');
  }
});

// Запуск серверов
backendServer.listen(BACKEND_PORT, () => {
  console.log(`\n🚀 Zero Mock Backend запущен на http://localhost:${BACKEND_PORT}`);
});

frontendServer.listen(FRONTEND_PORT, () => {
  console.log(`📧 Zero Mock Frontend запущен на http://localhost:${FRONTEND_PORT}`);
  console.log(`\n✨ Откройте http://localhost:${FRONTEND_PORT} в браузере`);
  
  if (process.env.GOOGLE_CLIENT_ID) {
    console.log(`✅ Google OAuth настроен: ${process.env.GOOGLE_CLIENT_ID.substring(0, 20)}...`);
  } else {
    console.log(`⚠️  Google OAuth не настроен. Добавьте GOOGLE_CLIENT_ID и GOOGLE_CLIENT_SECRET в .env`);
  }
  
  console.log(`\n📚 Документация: /docs/ZERO_INTEGRATION_RU.md`);
});
