import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Loader2, LogIn, KeyRound,
  LayoutDashboard, GraduationCap, FlaskConical, MessageSquare,
  Plug2, BookOpen, Settings, Menu, X, Users
} from 'lucide-react';
import Header from '../components/layout/Header';
import DashboardPage from './DashboardPage';
import TrainingPage from './TrainingPage';
import SandboxPage from './SandboxPage';
import HistoryPage from './HistoryPage';
import IntegrationsPage from './IntegrationsPage';
import SetupInstructionsPage from './SetupInstructionsPage';
import SettingsPage from './SettingsPage';
import LeadsPage from './LeadsPage';
import { useTranslation } from 'react-i18next';
import { clientAPI } from '../api/client';
import { ensureSupportWidgetForClientType } from '../utils/supportWidget';
import api from '../api/axios';

// Тестовий акаунт — тільки для нього новий flow з /l/:tag/...
// TODO: замінити на прапорець з бекенду коли буде готово для всіх
const NEW_FLOW_TAGS = ['srtyh'];

// ============================================================
// Старий портал (inline sidebar + view switching) для всіх клієнтів крім NEW_FLOW_TAGS
// ============================================================
const OldClientPortal = () => {
  const [searchParams] = useSearchParams();
  const { isAuthenticated, loginByClientToken, loading: authLoading, user } = useAuth();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loginAttempted, setLoginAttempted] = useState(false);
  const [currentView, setCurrentView] = useState('dashboard');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [clientName, setClientName] = useState('NEXELIN');
  const [clientLogo, setClientLogo] = useState(null);

  useEffect(() => {
    const tag = searchParams.get('tag');

    if (!tag) {
      setError('Tag parameter is required');
      setLoading(false);
      return;
    }

    if (isAuthenticated && !authLoading) {
      setLoading(false);
      loadClientData();
      return;
    }

    if (authLoading) return;

    if (!loginAttempted) {
      handleAutoLogin(tag);
    }
  }, [searchParams, isAuthenticated, authLoading, loginByClientToken, loginAttempted]);

  useEffect(() => {
    const handleNavigate = (event) => {
      const { view } = event.detail;
      if (view) setCurrentView(view);
    };
    window.addEventListener('nexelin:navigate', handleNavigate);
    return () => window.removeEventListener('nexelin:navigate', handleNavigate);
  }, []);

  const loadClientData = async () => {
    try {
      const response = await clientAPI.getMe();
      const data = response.data;

      if (data?.client_type === 'white_label' && data?.company_name) {
        setClientName(data.company_name);
      } else {
        setClientName('NEXELIN');
      }

      const logoUrl = data?.logo_url || data?.logo;
      if (logoUrl) {
        if (logoUrl.startsWith('/')) {
          const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
          setClientLogo(`${baseURL}${logoUrl}`);
        } else {
          setClientLogo(logoUrl);
        }
      } else {
        setClientLogo(null);
      }

      ensureSupportWidgetForClientType(data?.client_type);
    } catch (err) {
      console.error('Failed to load client data:', err);
      setClientName('NEXELIN');
    }
  };

  const handleAutoLogin = async (clientToken) => {
    try {
      setLoading(true);
      setLoginAttempted(true);
      await loginByClientToken(clientToken);
      await new Promise(resolve => setTimeout(resolve, 300));
      await loadClientData();
      setLoading(false);
    } catch (err) {
      console.error('Auto login error:', err);
      setError(err.response?.data?.error || err.message || 'Failed to login. Please try again.');
      setLoading(false);
    }
  };

  if (loading || authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 dark:from-primary-900/20 to-accent-50 dark:to-accent-900/20">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary-500 dark:text-primary-400 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Signing in...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 dark:from-primary-900/20 to-accent-50 dark:to-accent-900/20">
        <div className="text-center max-w-md mx-auto p-6 bg-white dark:bg-gray-800 rounded-lg shadow-lg">
          <h2 className="text-2xl font-bold text-red-600 dark:text-red-400 mb-4">Login Error</h2>
          <p className="text-gray-700 dark:text-gray-300 mb-4">{error}</p>
        </div>
      </div>
    );
  }

  if (isAuthenticated) {
    const navItems = [
      { id: 'dashboard', icon: LayoutDashboard, label: t('nav.dashboard') },
      { id: 'training', icon: GraduationCap, label: t('nav.training') },
      { id: 'sandbox', icon: FlaskConical, label: t('nav.sandbox') },
      { id: 'integrations', icon: Plug2, label: t('nav.integrations') },
      { id: 'history', icon: MessageSquare, label: t('nav.history') },
      ...(user?.leads_enabled ? [{ id: 'leads', icon: Users, label: t('nav.leads') || 'Leads' }] : []),
      { id: 'setup', icon: BookOpen, label: t('nav.setup') },
      { id: 'settings', icon: Settings, label: t('nav.settings') || 'Settings' },
    ];

    const renderContent = () => {
      switch (currentView) {
        case 'training': return <TrainingPage />;
        case 'sandbox': return <SandboxPage />;
        case 'integrations': return <IntegrationsPage />;
        case 'history': return <HistoryPage />;
        case 'setup': return <SetupInstructionsPage />;
        case 'settings': return <SettingsPage />;
        case 'leads': return <LeadsPage />;
        default: return <DashboardPage />;
      }
    };

    return (
      <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900">
        <button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className="md:hidden fixed top-4 left-4 z-50 p-2 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100"
          aria-label="Toggle menu"
        >
          {isSidebarOpen ? <X size={24} /> : <Menu size={24} />}
        </button>

        {isSidebarOpen && (
          <div
            className="md:hidden fixed inset-0 bg-black bg-opacity-50 z-30"
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        <div className={`
          fixed md:static inset-y-0 left-0 z-40
          w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 min-h-screen flex flex-col
          transform transition-transform duration-300 ease-in-out
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}>
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-3">
              {clientLogo && (
                <img
                  src={clientLogo}
                  alt={clientName}
                  className="w-8 h-8 object-contain rounded"
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
              )}
              <h1 className="text-xl font-bold text-primary-600 dark:text-primary-400">{clientName}</h1>
            </div>
          </div>

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
                    ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 active:bg-gray-200 dark:active:bg-gray-600'
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
            <div className="bg-yellow-100 dark:bg-yellow-900/30 border-b border-yellow-200 dark:border-yellow-700 px-4 py-2 text-sm text-yellow-800 dark:text-yellow-300">
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

// ============================================================
// Новий ClientLoginPage — роутер між старим і новим flow
// ============================================================
const ClientLoginPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [tagInput, setTagInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const tagFromQuery = searchParams.get('tag');

  // /l?tag=xxx — якщо тег в новому flow → redirect на /l/xxx/dashboard
  if (tagFromQuery && NEW_FLOW_TAGS.includes(tagFromQuery)) {
    return <Navigate to={`/l/${tagFromQuery}/dashboard`} replace />;
  }

  // Старий flow для всіх інших клієнтів
  if (tagFromQuery) {
    return <OldClientPortal />;
  }

  // Без тегу — сторінка логіна
  const handleSubmit = async (e) => {
    e.preventDefault();
    const tag = tagInput.trim();
    if (!tag) return;

    setLoading(true);
    setError(null);

    try {
      const response = await api.get('/clients/me/', {
        headers: { 'X-Client-Token': tag }
      });
      if (response.data) {
        // Якщо тег в новому flow — на нові URL, інакше — старий формат
        if (NEW_FLOW_TAGS.includes(tag)) {
          navigate(`/l/${tag}/dashboard`);
        } else {
          navigate(`/l?tag=${tag}`);
        }
      }
    } catch (err) {
      const status = err.response?.status;
      if (status === 404 || status === 401 || status === 403) {
        setError(t('login.invalidTag') || 'Invalid access code. Please check and try again.');
      } else {
        setError(err.response?.data?.error || t('login.error') || 'Something went wrong. Please try again.');
      }
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-gray-950 dark:via-gray-900 dark:to-indigo-950 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-700 rounded-2xl shadow-lg mb-4">
            <KeyRound className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            NEXELIN
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-2">
            {t('login.subtitle') || 'Enter your access code to continue'}
          </p>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8">
          <form onSubmit={handleSubmit}>
            <div className="mb-6">
              <label
                htmlFor="tag-input"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
              >
                {t('login.accessCode') || 'Access Code'}
              </label>
              <input
                id="tag-input"
                type="text"
                value={tagInput}
                onChange={(e) => {
                  setTagInput(e.target.value);
                  if (error) setError(null);
                }}
                placeholder={t('login.accessCodePlaceholder') || 'Enter your code...'}
                className="w-full px-4 py-3 rounded-xl border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all text-lg tracking-wider"
                autoFocus
                autoComplete="off"
                disabled={loading}
              />
            </div>

            {error && (
              <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !tagInput.trim()}
              className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-primary-600 hover:bg-primary-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 text-white font-medium rounded-xl transition-all shadow-md hover:shadow-lg disabled:shadow-none"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  {t('login.loading') || 'Checking...'}
                </>
              ) : (
                <>
                  <LogIn className="w-5 h-5" />
                  {t('login.submit') || 'Continue'}
                </>
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-gray-400 dark:text-gray-500 mt-6">
          {t('login.hint') || 'Your access code was provided by your administrator'}
        </p>
      </div>
    </div>
  );
};

export default ClientLoginPage;
