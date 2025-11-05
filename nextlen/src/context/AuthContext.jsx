import { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../api/auth';
import { MOCK_MODE } from '../api/axios';

const AuthContext = createContext();

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
    const token = localStorage.getItem('access_token');
    if (token) {
      if (MOCK_MODE) {
        // У мок режимі просто встановлюємо користувача з localStorage
        const savedUser = localStorage.getItem('mock_user');
        if (savedUser) {
          setUser(JSON.parse(savedUser));
        }
        setLoading(false);
        return;
      }
      
      try {
        const { data } = await authAPI.getProfile();
        setUser(data);
      } catch (error) {
        // Якщо помилка мережі і мок режим активний
        if (error.code === 'ERR_NETWORK' || error.code === 'ERR_CONNECTION_REFUSED') {
          const savedUser = localStorage.getItem('mock_user');
          if (savedUser) {
            setUser(JSON.parse(savedUser));
          }
        } else {
          localStorage.removeItem('access_token');
        }
      }
    }
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
      // Отримуємо JWT токен через client_token
      const { data } = await authAPI.getTokenByClientToken(clientToken);

      if (data && data.access) {
        // Зберігаємо токени
        localStorage.setItem('access_token', data.access);
        if (data.refresh) {
          localStorage.setItem('refresh_token', data.refresh);
        }

        // ВАЖЛИВО: Зберігаємо client_tag для можливості повторної авторизації
        // при експірації токенів або перезавантаженні сторінки
        localStorage.setItem('client_tag', clientToken);

        // Отримуємо профіль користувача
        try {
          const profileResponse = await authAPI.getProfile();
          setUser(profileResponse.data);
        } catch (profileError) {
          // Якщо не вдалося отримати профіль, використовуємо дані з токену
          if (data.client) {
            setUser({
              id: data.client.id,
              email: data.client.user || '',
              company_name: data.client.company_name || '',
              client_type: data.client.client_type || 'generic',
            });
          }
        }

        return data;
      }
      throw new Error('Invalid response from server');
    } catch (error) {
      // Мок режим: якщо backend недоступний
      if (MOCK_MODE || error.code === 'ERR_NETWORK' || error.code === 'ERR_CONNECTION_REFUSED') {
        const mockUser = createMockUser();
        const mockToken = 'mock_token_' + Date.now();
        localStorage.setItem('access_token', mockToken);
        localStorage.setItem('refresh_token', mockToken);
        localStorage.setItem('client_tag', clientToken);
        localStorage.setItem('mock_user', JSON.stringify(mockUser));
        setUser(mockUser);
        return { access: mockToken, refresh: mockToken, user: mockUser };
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
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
