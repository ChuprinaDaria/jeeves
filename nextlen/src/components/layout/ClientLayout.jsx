import { useEffect, useState } from 'react';
import { Outlet, useParams, Navigate, NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { clientAPI } from '../../api/client';
import { ensureSupportWidgetForClientType } from '../../utils/supportWidget';
import Header from './Header';
import {
  Loader2,
  LayoutDashboard,
  GraduationCap,
  FlaskConical,
  Bot,
  MessageSquare,
  Plug2,
  Puzzle,
  BookOpen,
  Settings,
  Menu,
  X,
  Users,
  Workflow
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

const ClientLayout = () => {
  const { tag } = useParams();
  const { loginByClientToken, loading: authLoading, isAuthenticated, user } = useAuth();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loginAttempted, setLoginAttempted] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [clientName, setClientName] = useState('NEXELIN');
  const [clientLogo, setClientLogo] = useState(null);

  useEffect(() => {
    if (!tag) return;
    if (authLoading) return;

    if (isAuthenticated && !loginAttempted) {
      // Вже авторизовані (наприклад, через старий flow) — підвантажуємо дані
      setLoginAttempted(true);
      loadClientData().then(() => setLoading(false));
      return;
    }

    if (!loginAttempted) {
      handleLogin(tag);
    }
  }, [tag, authLoading, isAuthenticated, loginAttempted]);

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

  const handleLogin = async (clientToken) => {
    try {
      setLoading(true);
      setLoginAttempted(true);
      await loginByClientToken(clientToken);
      await loadClientData();
      setLoading(false);
    } catch (err) {
      console.error('Client login error:', err);
      setError(err.response?.data?.error || err.message || 'Failed to login');
      setLoading(false);
    }
  };

  if (!tag) {
    return <Navigate to="/l" replace />;
  }

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
          <a
            href="/l"
            className="inline-block px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            Back to Login
          </a>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  const basePath = `/l/${tag}`;

  const navItems = [
    { to: `${basePath}/dashboard`, icon: LayoutDashboard, label: t('nav.dashboard') },
    { to: `${basePath}/training`, icon: GraduationCap, label: t('nav.training') },
    user?.feature_flags?.mcp_knowledge_split
      ? { to: `${basePath}/sandbox`, icon: Bot, label: t('nav.assistant') || 'Assistant' }
      : { to: `${basePath}/sandbox`, icon: FlaskConical, label: t('nav.sandbox'), badge: t('nav.sandboxBadge') || 'Also in Train AI' },
    { to: `${basePath}/integrations`, icon: Plug2, label: t('nav.integrations') },
    ...(user?.feature_flags?.mcp_tools_dashboard
      ? [{ to: `${basePath}/tools`, icon: Puzzle, label: t('nav.tools') || 'Tools' }]
      : []),
    { to: `${basePath}/history`, icon: MessageSquare, label: t('nav.history') },
    ...(user?.leads_enabled ? [{ to: `${basePath}/leads`, icon: Users, label: t('nav.leads') || 'Leads' }] : []),
    ...(user?.feature_flags?.langflow_enabled
      ? [{ to: `${basePath}/langflow`, icon: Workflow, label: t('nav.langflow') || 'Langflow' }]
      : []),
    { to: `${basePath}/setup`, icon: BookOpen, label: t('nav.promptBook') || 'Prompt Book' },
    { to: `${basePath}/settings`, icon: Settings, label: t('nav.settings') || 'Settings' },
  ];

  const closeSidebar = () => setIsSidebarOpen(false);

  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Skip navigation */}
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:z-[100] focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:bg-primary-600 focus:text-white focus:rounded-lg focus:text-sm focus:font-medium">
        Skip to content
      </a>
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
          onClick={closeSidebar}
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
                onError={(e) => { e.target.style.display = 'none'; }}
              />
            )}
            <div className="text-xl font-bold text-primary-600 dark:text-primary-400" role="banner">{clientName}</div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={closeSidebar}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg mb-2 transition-colors ${
                  isActive
                    ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 active:bg-gray-200 dark:active:bg-gray-600'
                }`
              }
            >
              <item.icon size={20} />
              <div className="flex-1">
                <span className="font-medium">{item.label}</span>
                {item.badge && (
                  <span className="block text-[10px] text-purple-500 dark:text-purple-400 font-normal mt-0.5">
                    {item.badge}
                  </span>
                )}
              </div>
            </NavLink>
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
        <main id="main-content" className="flex-1 p-3 md:p-6 pt-16 md:pt-6 overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default ClientLayout;
