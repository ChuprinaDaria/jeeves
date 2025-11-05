import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loader2 } from 'lucide-react';
import Sidebar from '../components/layout/Sidebar';
import Header from '../components/layout/Header';
import DashboardPage from './DashboardPage';

const ClientLoginPage = () => {
  const [searchParams] = useSearchParams();
  const { isAuthenticated, loginByClientToken, loading: authLoading } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loginAttempted, setLoginAttempted] = useState(false);

  useEffect(() => {
    const tag = searchParams.get('tag');
    
    if (!tag) {
      setError('Tag parameter is required');
      setLoading(false);
      return;
    }

    // Якщо вже авторизований, просто показуємо dashboard
    if (isAuthenticated && !authLoading) {
      setLoading(false);
      return;
    }

    // Якщо AuthContext ще завантажується, чекаємо
    if (authLoading) {
      return;
    }

    // Якщо ще не намагалися увійти, робимо автоматичний вхід
    if (!loginAttempted) {
      handleAutoLogin(tag);
    }
  }, [searchParams, isAuthenticated, authLoading, loginByClientToken, loginAttempted]);

  const handleAutoLogin = async (clientToken) => {
    try {
      setLoading(true);
      setLoginAttempted(true);
      
      // Використовуємо метод з AuthContext для входу
      await loginByClientToken(clientToken);
      
      // Чекаємо трохи, щоб AuthContext оновився
      await new Promise(resolve => setTimeout(resolve, 300));
      
      setLoading(false);
    } catch (err) {
      console.error('Auto login error:', err);
      setError(err.response?.data?.error || err.message || 'Failed to login. Please try again.');
      setLoading(false);
    }
  };

  // Показуємо loading поки вхід не завершено
  if (loading || authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-accent-50">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary-500 mx-auto mb-4" />
          <p className="text-gray-600">Вхід до системи...</p>
        </div>
      </div>
    );
  }

  // Показуємо помилку якщо вхід не вдався
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-accent-50">
        <div className="text-center max-w-md mx-auto p-6 bg-white rounded-lg shadow-lg">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Помилка входу</h2>
          <p className="text-gray-700 mb-4">{error}</p>
        </div>
      </div>
    );
  }

  // Якщо авторизований, показуємо dashboard з Layout (але без редиректу, URL залишається /l?tag=xxx)
  if (isAuthenticated) {
    const { user } = useAuth();
    return (
      <div className="flex min-h-screen bg-gray-50">
        <Sidebar />
        <div className="flex-1 flex flex-col w-full md:w-auto">
          {user?.subscription_status === 'trial' && (
            <div className="bg-yellow-100 border-b border-yellow-200 px-4 py-2 text-sm text-yellow-800">
              Trial period active
            </div>
          )}
          <Header />
          <main className="flex-1 p-3 md:p-6 pt-16 md:pt-6 overflow-x-hidden">
            <DashboardPage />
          </main>
        </div>
      </div>
    );
  }

  return null;
};

export default ClientLoginPage;

