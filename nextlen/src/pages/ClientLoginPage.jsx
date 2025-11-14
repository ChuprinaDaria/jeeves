import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loader2, LayoutDashboard, GraduationCap, FlaskConical, MessageSquare, Plug2, BookOpen } from 'lucide-react';
import Header from '../components/layout/Header';
import DashboardPage from './DashboardPage';
import TrainingPage from './TrainingPage';
import SandboxPage from './SandboxPage';
import HistoryPage from './HistoryPage';
import IntegrationsPage from './IntegrationsPage';
import SetupInstructionsPage from './SetupInstructionsPage';
import { useTranslation } from 'react-i18next';

const ClientLoginPage = () => {
  const [searchParams] = useSearchParams();
  const { isAuthenticated, loginByClientToken, loading: authLoading, user } = useAuth();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loginAttempted, setLoginAttempted] = useState(false);
  const [currentView, setCurrentView] = useState('integrations');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

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
    const navItems = [
      { id: 'dashboard', icon: LayoutDashboard, label: t('nav.dashboard') },
      { id: 'training', icon: GraduationCap, label: t('nav.training') },
      { id: 'sandbox', icon: FlaskConical, label: t('nav.sandbox') },
      { id: 'integrations', icon: Plug2, label: t('nav.integrations') },
      { id: 'history', icon: MessageSquare, label: t('nav.history') },
      { id: 'setup', icon: BookOpen, label: t('nav.setup') },
    ];

    const renderContent = () => {
      switch (currentView) {
        case 'training':
          return <TrainingPage />;
        case 'sandbox':
          return <SandboxPage />;
        case 'integrations':
          return <IntegrationsPage />;
        case 'history':
          return <HistoryPage />;
        case 'setup':
          return <SetupInstructionsPage />;
        default:
          return <DashboardPage />;
      }
    };

    return (
      <div className="flex min-h-screen bg-gray-50">
        {/* Mobile menu button */}
        <button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className="md:hidden fixed top-4 left-4 z-50 p-2 bg-white rounded-lg shadow-lg border border-gray-200"
          aria-label="Toggle menu"
        >
          {isSidebarOpen ? <Loader2 size={24} /> : <LayoutDashboard size={24} />}
        </button>

        {/* Overlay for mobile */}
        {isSidebarOpen && (
          <div
            className="md:hidden fixed inset-0 bg-black bg-opacity-50 z-30"
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <div className={`
          fixed md:static inset-y-0 left-0 z-40
          w-64 bg-white border-r border-gray-200 min-h-screen flex flex-col
          transform transition-transform duration-300 ease-in-out
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}>
          {/* Logo/Brand area */}
          <div className="p-4 border-b border-gray-200">
            <h1 className="text-xl font-bold text-primary-600">Nexelin</h1>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 overflow-y-auto">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  setCurrentView(item.id);
                  setIsSidebarOpen(false);
                }}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg mb-2 transition-colors w-full text-left ${
                  currentView === item.id
                    ? 'bg-primary-50 text-primary-600'
                    : 'text-gray-700 hover:bg-gray-100 active:bg-gray-200'
                }`}
              >
                <item.icon size={20} />
                <span className="font-medium">{item.label}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="flex-1 flex flex-col w-full md:w-auto">
          {user?.subscription_status === 'trial' && (
            <div className="bg-yellow-100 border-b border-yellow-200 px-4 py-2 text-sm text-yellow-800">
              Trial period active
            </div>
          )}
          <Header />
          <main className="flex-1 p-3 md:p-6 pt-16 md:pt-6 overflow-x-hidden">
            {renderContent()}
          </main>
        </div>
      </div>
    );
  }

  return null;
};

export default ClientLoginPage;

