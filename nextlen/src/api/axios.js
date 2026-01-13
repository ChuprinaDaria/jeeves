import axios from 'axios';

const MOCK_MODE = import.meta.env.VITE_MOCK_MODE === 'true' || !import.meta.env.VITE_API_URL;

// Використовуємо production URL якщо VITE_API_URL не встановлений
// Це захищає від використання localhost в production
const getApiUrl = () => {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl) {
    return envUrl;
  }
  // В production режимі не використовуємо localhost fallback
  if (import.meta.env.PROD) {
    console.error('VITE_API_URL не встановлений в production!');
    return 'https://api.nexelin.com/api'; // Production fallback
  }
  // Тільки в development використовуємо localhost
  return 'http://localhost:8000/api';
};

const api = axios.create({
  baseURL: getApiUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor для додавання токена та API ключа
api.interceptors.request.use((config) => {
  // Зчитуємо tag з URL і встановлюємо X-Client-Token для цього конкретного запиту
  // НЕ зберігаємо глобально в localStorage, щоб уникнути конфліктів між різними тегами
  let currentTag = null;
  try {
    const urlParams = new URLSearchParams(window.location.search);
    currentTag = urlParams.get('tag');
  } catch (_) {}
  
  // Пріоритет авторизації:
  // 1. X-API-Key (якщо є)
  // 2. X-Client-Token з URL (для client-only потоку БЕЗ JWT) - пріоритет над localStorage
  // 3. X-Client-Token з localStorage (fallback для збереженої сесії)
  // 4. JWT Bearer token (тільки якщо немає client_tag - для admin/user потоку)
  
  const apiKey = localStorage.getItem('api_key');
  const storedClientTag = localStorage.getItem('client_tag');
  const accessToken = localStorage.getItem('access_token');
  
  // Визначаємо який tag використовувати: URL має пріоритет над localStorage
  const effectiveTag = currentTag || storedClientTag;
  
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  } else if (effectiveTag) {
    // Client-only потік: використовуємо тільки X-Client-Token, НЕ додаємо JWT
    config.headers['X-Client-Token'] = effectiveTag;
  } else if (accessToken && !effectiveTag) {
    // Admin/User потік: використовуємо JWT, тільки якщо немає client_tag
    config.headers['Authorization'] = `Bearer ${accessToken}`;
  }
  
  return config;
});

// Interceptor для обробки помилок та refresh token
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Якщо це помилка мережі, додаємо мок позначку для обробки в AuthContext
    if (error.code === 'ERR_NETWORK' || error.code === 'ERR_CONNECTION_REFUSED') {
      error.mock = true;
      return Promise.reject(error);
    }

    // Якщо 401 і це не був повтор
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      // Якщо є API ключ — просто повторюємо запит (ключ уже в headers)
      const apiKey = localStorage.getItem('api_key');
      if (apiKey) {
        return api(originalRequest);
      }

      // Перевіряємо чи є tag параметр в URL (bootstrap авторизація)
      const urlParams = new URLSearchParams(window.location.search);
      const hasTag = urlParams.has('tag');

      // Якщо є tag в URL — повторюємо запит (tag буде підставлений interceptor'ом)
      if (hasTag) {
        return api(originalRequest);
      }

      // Якщо є збережений client_tag в localStorage — теж повторюємо запит
      const clientTagRetry = localStorage.getItem('client_tag');
      if (clientTagRetry) {
        return api(originalRequest);
      }

      // Перевіряємо чи це iframe (для mg.nexelin.com)
      const isInIframe = window.self !== window.top;

      // Перенаправляємо на login ТІЛЬКИ якщо:
      // 1. Це не запит на auth endpoints
      // 2. Немає tag параметра (не bootstrap процес)
      // 3. Не в iframe (щоб не ламати вбудовування в mg.nexelin.com)
      // 4. Немає API ключа (якщо є API ключ, не редиректимо)
      const isAuthRequest = originalRequest.url?.includes('/auth/') ||
                           originalRequest.url?.includes('/rag/auth/');
      const hasApiKey = localStorage.getItem('api_key');

      if (!isAuthRequest && !hasTag && !isInIframe && !hasApiKey && !clientTagRetry) {
        // Затримка перед редиректом, щоб дати час на обробку
        setTimeout(() => {
          window.location.href = '/login';
        }, 100);
      }
    }

    return Promise.reject(error);
  }
);

export default api;
export { MOCK_MODE };
