import axios from 'axios';

const MOCK_MODE = import.meta.env.VITE_MOCK_MODE === 'true' || !import.meta.env.VITE_API_URL;

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor для додавання токена та API ключа
api.interceptors.request.use((config) => {
  // Додаємо Bearer token якщо є
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  
  // Додаємо X-API-Key якщо є (працює разом з Bearer token)
  const apiKey = localStorage.getItem('api_key');
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
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

    // Якщо 401 і це не був спроб refresh token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const refreshToken = localStorage.getItem('refresh_token');

      // Якщо є refresh token, намагаємося оновити access token
      if (refreshToken) {
        try {
          const { authAPI } = await import('./auth');
          const response = await authAPI.refreshToken(refreshToken);

          if (response.data?.access) {
            localStorage.setItem('access_token', response.data.access);
            if (response.data.refresh) {
              localStorage.setItem('refresh_token', response.data.refresh);
            }

            // Повторюємо оригінальний запит з новим токеном
            originalRequest.headers.Authorization = `Bearer ${response.data.access}`;
            return api(originalRequest);
          }
        } catch (refreshError) {
          console.error('Token refresh failed:', refreshError);

          // Якщо refresh не вдався, спробуємо використати збережений client_tag
          const clientTag = localStorage.getItem('client_tag');
          if (clientTag) {
            try {
              const { authAPI } = await import('./auth');
              const tagResponse = await authAPI.getTokenByClientToken(clientTag);

              if (tagResponse.data?.access) {
                localStorage.setItem('access_token', tagResponse.data.access);
                if (tagResponse.data.refresh) {
                  localStorage.setItem('refresh_token', tagResponse.data.refresh);
                }

                // Повторюємо оригінальний запит з новим токеном
                originalRequest.headers.Authorization = `Bearer ${tagResponse.data.access}`;
                return api(originalRequest);
              }
            } catch (tagError) {
              console.error('Client tag re-authentication failed:', tagError);
            }
          }

          // Якщо все не вдалося, очищаємо токени
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        }
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
      const isAuthRequest = originalRequest.url?.includes('/auth/') ||
                           originalRequest.url?.includes('/rag/auth/');

      if (!isAuthRequest && !hasTag && !isInIframe) {
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
