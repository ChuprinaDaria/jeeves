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
  // Додаємо X-API-Key якщо є (працює разом з Bearer token)
  const apiKey = localStorage.getItem('api_key');
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }

  // Зчитуємо tag з URL, зберігаємо як client_tag і додаємо заголовок X-Client-Token
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const tagFromUrl = urlParams.get('tag');
    if (tagFromUrl) {
      localStorage.setItem('client_tag', tagFromUrl);
    }
  } catch (_) {}
  const clientTag = localStorage.getItem('client_tag');
  if (clientTag) {
    config.headers['X-Client-Token'] = clientTag;
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

      // Якщо є client_tag — теж повторюємо запит
      const clientTagRetry = localStorage.getItem('client_tag');
      if (clientTagRetry) {
        return api(originalRequest);
      }

      // Перевіряємо чи є tag параметр в URL (bootstrap авторизація)
      const urlParams = new URLSearchParams(window.location.search);
      const hasTag = urlParams.has('tag');

      // Перевіряємо чи це iframe (для mg.nexelin.com)
      const isInIframe = window.self !== window.top;

      // Перенаправляємо на login ТІЛЬКИ якщо:
      // 1. Це не запит на auth endpoints
      // 2. Немає tag параметра (не bootstrap процес)
      // 3. Не в iframe (щоб не ламати вбудовування в mg.nexelin.com)
      // 4. Немає API ключа (якщо є API ключ, не редиректимо)
      // 5. Немає client_tag (якщо є client_tag, не редиректимо)
      const isAuthRequest = originalRequest.url?.includes('/auth/') ||
                           originalRequest.url?.includes('/rag/auth/');
      const hasApiKey = localStorage.getItem('api_key');
      const hasClientTag = localStorage.getItem('client_tag');

      if (!isAuthRequest && !hasTag && !isInIframe && !hasApiKey && !hasClientTag) {
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
