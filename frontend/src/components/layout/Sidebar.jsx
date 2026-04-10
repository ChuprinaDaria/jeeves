import { NavLink, useSearchParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import {
  LayoutDashboard,
  GraduationCap,
  FlaskConical,
  Bot,
  Plug2,
  Puzzle,
  MessageSquare,
  BookOpen,
  Settings,
  CreditCard,
  Menu,
  X,
  Users
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../context/AuthContext';
import { clientAPI } from '../../api/client';
import { ensureSupportWidgetForClientType } from '../../utils/supportWidget';

const Sidebar = () => {
  const { t } = useTranslation();
  const { isAuthenticated, user } = useAuth();
  const [searchParams] = useSearchParams();
  const [isOpen, setIsOpen] = useState(false);
  
  // Функція для визначення назви клієнта
  const getClientName = (clientData) => {
    // Тільки для white_label клієнтів показуємо назву компанії
    const isWhiteLabel = clientData?.client_type === 'white_label';
    const hasCompanyName = !!clientData?.company_name;
    
    console.log('getClientName check:', {
      client_type: clientData?.client_type,
      company_name: clientData?.company_name,
      isWhiteLabel,
      hasCompanyName,
      willReturn: isWhiteLabel && hasCompanyName ? clientData.company_name : 'CONCIERGE'
    });
    
    if (isWhiteLabel && hasCompanyName) {
      return clientData.company_name;
    }
    // Для всіх інших клієнтів (включаючи тих, хто має company_name, але не white_label) - CONCIERGE
    return 'CONCIERGE';
  };
  
  // Ініціалізуємо назву з user контексту, якщо він вже є і містить всі потрібні дані
  const [clientName, setClientName] = useState(() => {
    // Для залогінованих користувачів використовуємо дані з контексту
    if (user?.client_type === 'white_label' && user?.company_name) {
      return user.company_name;
    }
    // Для клієнтів з тегом буде завантажено через API, поки що показуємо CONCIERGE
    return 'CONCIERGE';
  });
  
  const [clientLogo, setClientLogo] = useState(() => {
    if (user?.logo_url || user?.logo) {
      const logoUrl = user.logo_url || user.logo;
      if (logoUrl.startsWith('/')) {
        const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        return `${baseURL}${logoUrl}`;
      }
      return logoUrl;
    }
    return null;
  });
  
  // Зберігаємо тег з URL для навігації
  const tag = searchParams.get('tag');

  const navItems = [
    { to: '/dashboard', icon: LayoutDashboard, label: t('nav.dashboard') },
    { to: '/training', icon: GraduationCap, label: t('nav.training') },
    user?.feature_flags?.mcp_knowledge_split
      ? { to: '/sandbox', icon: Bot, label: t('nav.assistant') || 'Assistant' }
      : { to: '/sandbox', icon: FlaskConical, label: t('nav.sandbox'), badge: t('nav.sandboxBadge') || 'Also in Train AI' },
    { to: '/integrations', icon: Plug2, label: t('nav.integrations') },
    ...(user?.feature_flags?.mcp_tools_dashboard
      ? [{ to: '/tools', icon: Puzzle, label: t('nav.tools') || 'Tools' }]
      : []),
    { to: '/history', icon: MessageSquare, label: t('nav.history') },
    ...(user?.leads_enabled ? [{ to: '/leads', icon: Users, label: t('nav.leads') || 'Leads' }] : []),
    { to: '/setup', icon: BookOpen, label: t('nav.promptBook') || 'Prompt Book' },
    { to: '/settings', icon: Settings, label: t('nav.settings') || 'Settings' },
  ];
  
  // Завантажуємо дані клієнта завжди для клієнтів з тегом, або якщо user контекст порожній/неповний
  useEffect(() => {
    if (!isAuthenticated) {
      // Якщо не авторизовано, показуємо CONCIERGE і не прив'язуємо віджет до конкретного клієнта
      setClientName('CONCIERGE');
      setClientLogo(null);
      return;
    }
    
    // Для клієнтів з тегом завжди завантажуємо дані через API
    // Для залогінованих користувачів також завантажуємо, якщо user контекст не містить потрібних полів
    const shouldLoadData = tag || !user || !user.client_type;
    
    if (!shouldLoadData && user) {
      // Якщо user вже містить всі дані (є client_type), використовуємо їх
      const name = getClientName(user);
      setClientName(name);
      
      const logoUrl = user.logo_url || user.logo;
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

      // Налаштовуємо віджет підтримки для поточного типу клієнта
      ensureSupportWidgetForClientType(user.client_type);
      return;
    }
    
    // Завантажуємо дані клієнта для логотипа і назви
    const loadClientData = async () => {
      try {
        const response = await clientAPI.getMe();
        const data = response.data;

        // Логуємо дані для дебагу
        console.log('Sidebar - Client data loaded:', {
          client_type: data?.client_type,
          company_name: data?.company_name,
          tag: tag,
          hasTag: !!tag
        });

        // Встановлюємо назву: для white label — назва компанії, для інших — CONCIERGE
        const name = getClientName(data);
        console.log('Sidebar - Setting client name to:', name, 'because client_type is:', data?.client_type);
        setClientName(name);
        
        // Встановлюємо логотип
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

        // Налаштовуємо віджет підтримки для поточного типу клієнта
        ensureSupportWidgetForClientType(data?.client_type);
      } catch (err) {
        console.error('Failed to load client data:', err);
        // При помилці завантаження показуємо CONCIERGE
        setClientName('CONCIERGE');
        setClientLogo(null);
      }
    };

    loadClientData();
  }, [isAuthenticated, user, tag]);

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
                  e.target.style.display = 'none';
                }}
              />
            )}
            <div className="text-xl font-bold text-primary-600 dark:text-primary-400" role="banner">
              {clientName}
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 overflow-y-auto">
          {navItems.map((item) => {
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
                <div className="flex-1">
                  <span className="font-medium">{item.label}</span>
                  {item.badge && (
                    <span className="block text-[10px] text-purple-500 dark:text-purple-400 font-normal mt-0.5">
                      {item.badge}
                    </span>
                  )}
                </div>
              </NavLink>
            );
          })}
        </nav>
      </div>
    </>
  );
};

export default Sidebar;


