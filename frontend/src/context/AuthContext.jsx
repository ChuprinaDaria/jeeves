import { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../api/auth';
import { clientAPI } from '../api/client';
import { MOCK_MODE } from '../api/axios';

const AuthContext = createContext();

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};

// Мок дані для демонстрації
const createMockUser = (email, salonName) => ({
  id: 1,
  email: email || 'demo@salon.com',
  salon_name: salonName || 'Demo Salon',
  is_trial: true,
  trial_end_date: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
});

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    // Пріоритет: робота без JWT — якщо є tag у URL або в localStorage, авторизуємо клієнта по ньому
    try {
      // Підтримуємо обидва формати URL:
      // Новий: /l/:tag/dashboard (pathname)
      // Старий: /l?tag=xxx (query param)
      const pathMatch = window.location.pathname.match(/^\/l\/([^/]+)/);
      const tagFromPath = pathMatch ? pathMatch[1] : null;
      const urlParams = new URLSearchParams(window.location.search);
      const tagFromQuery = urlParams.get('tag');
      const tagFromUrl = tagFromPath || tagFromQuery;
      const storedClientTag = localStorage.getItem('client_tag');

      const effectiveTag = tagFromUrl || storedClientTag;
      
      if (effectiveTag) {
        // Очищуємо JWT токени при використанні client tag
        if (tagFromUrl) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        }
        
        try {
          const { data } = await clientAPI.getMe();
          setUser(data);
          setLoading(false);
          return;
        } catch {
          // Якщо бекенд тимчасово недоступний — не ламаємось
        }
      }
    } catch { /* ignore */ }

    // JWT більше не обов'язковий — просто завершуємо завантаження
    setLoading(false);
  };

  const login = async (email, password) => {
    try {
      const { data } = await authAPI.login({ email, password });
      localStorage.setItem('access_token', data.access);
      localStorage.setItem('refresh_token', data.refresh);
      setUser(data.user);
      return data;
    } catch (error) {
      // Мок режим: якщо backend недоступний, використовуємо мок дані
      if (MOCK_MODE || error.code === 'ERR_NETWORK' || error.code === 'ERR_CONNECTION_REFUSED' || error.mock) {
        const mockUser = createMockUser(email);
        const mockToken = 'mock_token_' + Date.now();
        localStorage.setItem('access_token', mockToken);
        localStorage.setItem('refresh_token', mockToken);
        localStorage.setItem('mock_user', JSON.stringify(mockUser));
        setUser(mockUser);
        return { access: mockToken, refresh: mockToken, user: mockUser };
      }
      throw error;
    }
  };

  const register = async (userData) => {
    try {
      const { data } = await authAPI.register(userData);
      localStorage.setItem('access_token', data.access);
      localStorage.setItem('refresh_token', data.refresh);
      setUser(data.user);
      return data;
    } catch (error) {
      // Мок режим: якщо backend недоступний, використовуємо мок дані
      if (MOCK_MODE || error.code === 'ERR_NETWORK' || error.code === 'ERR_CONNECTION_REFUSED' || error.mock) {
        const mockUser = createMockUser(userData.email, userData.salon_name);
        const mockToken = 'mock_token_' + Date.now();
        localStorage.setItem('access_token', mockToken);
        localStorage.setItem('refresh_token', mockToken);
        localStorage.setItem('mock_user', JSON.stringify(mockUser));
        setUser(mockUser);
        return { access: mockToken, refresh: mockToken, user: mockUser };
      }
      throw error;
    }
  };

  const logout = async () => {
    try {
      if (!MOCK_MODE) {
        await authAPI.logout();
      }
    } catch (error) {
      console.error('Logout error:', error);
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('client_tag');
    localStorage.removeItem('mock_user');
    setUser(null);
  };

  const loginByClientToken = async (clientToken) => {
    try {
      // Новий потік без JWT: очищуємо JWT токени і використовуємо тільки client_tag
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.setItem('client_tag', clientToken);
      
      const { data } = await clientAPI.getMe();
      setUser(data);
      return { user: data };
    } catch (error) {
      // Fallback для мок/мережевих помилок
      if (MOCK_MODE || error.code === 'ERR_NETWORK' || error.code === 'ERR_CONNECTION_REFUSED') {
        const mockUser = createMockUser();
        localStorage.setItem('client_tag', clientToken);
        localStorage.setItem('mock_user', JSON.stringify(mockUser));
        setUser(mockUser);
        return { user: mockUser };
      }
      throw error;
    }
  };

  const value = {
    user,
    loading,
    login,
    register,
    logout,
    loginByClientToken,
    isAuthenticated: !!user,
    isOwner: user?.role === 'owner',
    setUserDirect: setUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
