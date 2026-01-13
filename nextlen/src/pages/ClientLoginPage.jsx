import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loader2, LayoutDashboard, GraduationCap, FlaskConical, MessageSquare, Plug2, BookOpen, Settings, Menu, X } from 'lucide-react';
import Header from '../components/layout/Header';
import DashboardPage from './DashboardPage';
import TrainingPage from './TrainingPage';
import SandboxPage from './SandboxPage';
import HistoryPage from './HistoryPage';
import IntegrationsPage from './IntegrationsPage';
import SetupInstructionsPage from './SetupInstructionsPage';
import SettingsPage from './SettingsPage';
import { useTranslation } from 'react-i18next';
import { clientAPI } from '../api/client';
import { ensureSupportWidgetForClientType } from '../utils/supportWidget';

const ClientLoginPage = () => {
  const [searchParams] = useSearchParams();
  const { isAuthenticated, loginByClientToken, loading: authLoading, user } = useAuth();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loginAttempted, setLoginAttempted] = useState(false);
  // Starting screen for client - Dashboard, not Integrations
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

    // If already authenticated, just show dashboard
    if (isAuthenticated && !authLoading) {
      setLoading(false);
      loadClientData();
      return;
    }

    // If AuthContext is still loading, wait
    if (authLoading) {
      return;
    }

    // If haven't attempted login yet, do auto login
    if (!loginAttempted) {
      handleAutoLogin(tag);
    }
  }, [searchParams, isAuthenticated, authLoading, loginByClientToken, loginAttempted]);

  const loadClientData = async () => {
    try {
      const response = await clientAPI.getMe();
      const data = response.data;
      
      // Set client name: only for white_label show company name, for others - NEXELIN
      if (data?.client_type === 'white_label' && data?.company_name) {
        setClientName(data.company_name);
      } else {
        setClientName('NEXELIN');
      }
      
      // Set logo
      const logoUrl = data?.logo_url || data?.logo;
      if (logoUrl) {
        // If it's a relative path, add base URL
        if (logoUrl.startsWith('/')) {
          const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
          setClientLogo(`${baseURL}${logoUrl}`);
        } else {
          setClientLogo(logoUrl);
        }
      } else {
        setClientLogo(null);
      }

      // Налаштовуємо віджет підтримки для поточного типу клієнта
      ensureSupportWidgetForClientType(data?.client_type);
    } catch (err) {
      console.error('Failed to load client data:', err);
      // On error, show NEXELIN
      setClientName('NEXELIN');
    }
  };

  const handleAutoLogin = async (clientToken) => {
    try {
      setLoading(true);
      setLoginAttempted(true);
      
      // Use method from AuthContext for login
      await loginByClientToken(clientToken);
      
      // Wait a bit for AuthContext to update
      await new Promise(resolve => setTimeout(resolve, 300));
      
      // Load client data after successful login
      await loadClientData();
      
      setLoading(false);
    } catch (err) {
      console.error('Auto login error:', err);
      setError(err.response?.data?.error || err.message || 'Failed to login. Please try again.');
      setLoading(false);
    }
  };

  // Show loading while login is in progress
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

  // Show error if login failed
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

  // If authenticated, show dashboard with Layout (but without redirect, URL remains /l?tag=xxx)
  if (isAuthenticated) {
    const navItems = [
      { id: 'dashboard', icon: LayoutDashboard, label: t('nav.dashboard') },
      { id: 'training', icon: GraduationCap, label: t('nav.training') },
      { id: 'sandbox', icon: FlaskConical, label: t('nav.sandbox') },
      { id: 'integrations', icon: Plug2, label: t('nav.integrations') },
      { id: 'history', icon: MessageSquare, label: t('nav.history') },
      { id: 'setup', icon: BookOpen, label: t('nav.setup') },
      { id: 'settings', icon: Settings, label: t('nav.settings') || 'Settings' },
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
        case 'settings':
          return <SettingsPage />;
        default:
          return <DashboardPage />;
      }
    };

    return (
      <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900">
        {/* Mobile menu button */}
        <button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className="md:hidden fixed top-4 left-4 z-50 p-2 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100"
          aria-label="Toggle menu"
        >
          {isSidebarOpen ? <X size={24} /> : <Menu size={24} />}
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
          w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 min-h-screen flex flex-col
          transform transition-transform duration-300 ease-in-out
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}>
          {/* Logo/Brand area */}
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-3">
              {clientLogo && (
                <img 
                  src={clientLogo} 
                  alt={clientName}
                  className="w-8 h-8 object-contain rounded"
                  onError={(e) => {
                    // If logo failed to load, hide it
                    e.target.style.display = 'none';
                  }}
                />
              )}
              <h1 className="text-xl font-bold text-primary-600 dark:text-primary-400">{clientName}</h1>
            </div>
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

export default ClientLoginPage;

