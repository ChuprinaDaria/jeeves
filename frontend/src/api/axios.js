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

// Витягуємо tag клієнта з URL — підтримує обидва формати:
// Новий: /l/:tag/dashboard (pathname)
// Старий: /l?tag=xxx (query param)
const getTagFromUrl = () => {
  const pathMatch = window.location.pathname.match(/^\/l\/([^/]+)/);
  if (pathMatch) return pathMatch[1];
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('tag');
};

// Interceptor для додавання токена та API ключа
api.interceptors.request.use((config) => {
  const currentTag = getTagFromUrl();

  const apiKey = localStorage.getItem('api_key');
  const storedClientTag = localStorage.getItem('client_tag');
  const accessToken = localStorage.getItem('access_token');

  // Визначаємо tag: URL (pathname або query) має пріоритет над localStorage
  const effectiveTag = currentTag || storedClientTag;

  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  } else if (effectiveTag) {
    config.headers['X-Client-Token'] = effectiveTag;
  } else if (accessToken) {
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

      // Перевіряємо чи є tag в URL (новий /l/:tag/... або старий ?tag=...)
      const tagFromUrl = getTagFromUrl();
      if (tagFromUrl) {
        return api(originalRequest);
      }

      // Якщо є збережений client_tag в localStorage — теж повторюємо запит
      const clientTagRetry = localStorage.getItem('client_tag');
      if (clientTagRetry) {
        return api(originalRequest);
      }

      // Перевіряємо чи це iframe (для mg.nexelin.com)
      const isInIframe = window.self !== window.top;

      const isAuthRequest = originalRequest.url?.includes('/auth/') ||
                           originalRequest.url?.includes('/rag/auth/');
      const hasApiKey = localStorage.getItem('api_key');

      if (!isAuthRequest && !tagFromUrl && !isInIframe && !hasApiKey && !clientTagRetry) {
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