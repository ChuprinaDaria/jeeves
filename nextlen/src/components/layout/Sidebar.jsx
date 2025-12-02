import { NavLink, useSearchParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import {
  LayoutDashboard,
  GraduationCap,
  FlaskConical,
  Plug2,
  MessageSquare,
  BookOpen,
  Settings,
  CreditCard,
  Menu,
  X
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../context/AuthContext';
import { clientAPI } from '../../api/client';

const Sidebar = () => {
  const { t } = useTranslation();
  const { isAuthenticated, user } = useAuth();
  const [searchParams] = useSearchParams();
  const [isOpen, setIsOpen] = useState(false);
  // Базове значення, поки не підтягнемо дані користувача/клієнта
  const [clientName, setClientName] = useState('User');
  const [clientLogo, setClientLogo] = useState(null);
  
  // Зберігаємо тег з URL для навігації
  const tag = searchParams.get('tag');

  const navItems = [
    { to: '/dashboard', icon: LayoutDashboard, label: t('nav.dashboard') },
    { to: '/training', icon: GraduationCap, label: t('nav.training') },
    { to: '/sandbox', icon: FlaskConical, label: t('nav.sandbox') },
    { to: '/integrations', icon: Plug2, label: t('nav.integrations') },
    { to: '/history', icon: MessageSquare, label: t('nav.history') },
    { to: '/setup', icon: BookOpen, label: t('nav.setup') },
    { to: '/settings', icon: Settings, label: t('nav.settings') || 'Settings' },
  ];
  
  // Debug для діагностики
  console.log('=== SIDEBAR DEBUG ===');
  console.log('isAuthenticated:', isAuthenticated);
  console.log('user:', user);
  console.log('navItems count:', navItems.length);
  console.log('navItems:', navItems);
  console.log('Settings label:', navItems.find(item => item.to === '/settings')?.label);

  useEffect(() => {
    if (!isAuthenticated) return;

    // Завантажуємо дані клієнта (назву і логотип)
    loadClientData();
  }, [isAuthenticated]);

  const loadClientData = async () => {
    try {
      const response = await clientAPI.getMe();
      const data = response.data;

      // Для white label клієнтів (коли є description - назва пакета) показуємо description
      // Для звичайних клієнтів показуємо "NEXELIN"
      if (data?.description) {
        // White label - показуємо назву пакета (наприклад "Test Pack #22")
        setClientName(data.description);
      } else {
        // Звичайний клієнт - показуємо "NEXELIN"
        setClientName('NEXELIN');
      }

      // Встановлюємо логотип
      const logoUrl = data?.logo_url || data?.logo;
      if (logoUrl) {
        // Якщо це відносний шлях, додаємо base URL
        if (logoUrl.startsWith('/')) {
          const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
          setClientLogo(`${baseURL}${logoUrl}`);
        } else {
          setClientLogo(logoUrl);
        }
      }
    } catch (err) {
      console.error('Failed to load client data:', err);
      // Якщо помилка завантаження - показуємо NEXELIN
      setClientName('NEXELIN');
      console.log('API Error details:', err.response?.data || err.message);
    }
  };

  const closeSidebar = () => setIsOpen(false);

  return (
    <>
      {/* Mobile menu button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="md:hidden fixed top-4 left-4 z-50 p-2 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100"
        aria-label="Toggle menu"
      >
        {isOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Overlay for mobile */}
      {isOpen && (
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
        ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
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
                  // Якщо логотип не завантажився, приховуємо його
                  e.target.style.display = 'none';
                }}
              />
            )}
            <h1 className="text-xl font-bold text-primary-600 dark:text-primary-400">{clientName}</h1>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 overflow-y-auto">
          {navItems.map((item) => {
            // Додаємо тег до URL якщо він є
            const to = tag ? `${item.to}?tag=${tag}` : item.to;
            return (
              <NavLink
                key={item.to}
                to={to}
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
                <span className="font-medium">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

      </div>
    </>
  );
};

export default Sidebar;
