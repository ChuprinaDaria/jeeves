import { NavLink, useSearchParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import {
  SquaresFour,
  GraduationCap,
  Flask,
  Robot,
  PlugsConnected,
  PuzzlePiece,
  ChatDots,
  BookOpen,
  GearSix,
  UsersThree,
  List,
  X,
  BellSimple,
} from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../context/AuthContext';
import { clientAPI } from '../../api/client';
import { ensureSupportWidgetForClientType } from '../../utils/supportWidget';

const Sidebar = () => {
  const { t } = useTranslation();
  const { isAuthenticated, user } = useAuth();
  const [searchParams] = useSearchParams();
  const [isOpen, setIsOpen] = useState(false);

  const getClientName = (d) => {
    if (d?.client_type === 'white_label' && d?.company_name) return d.company_name;
    return 'Concierge';
  };

  const [clientName, setClientName] = useState(() =>
    user?.client_type === 'white_label' && user?.company_name ? user.company_name : 'Concierge'
  );
  const [clientLogo, setClientLogo] = useState(() => {
    const raw = user?.logo_url || user?.logo;
    if (!raw) return null;
    if (raw.startsWith('/')) {
      const baseURL = import.meta.env.VITE_API_URL?.replace('/api', '') || 'http://localhost:8000';
      return `${baseURL}${raw}`;
    }
    return raw;
  });

  const tag = searchParams.get('tag');

  useEffect(() => {
    if (!isAuthenticated) {
      setClientName('Concierge');
      setClientLogo(null);
      return;
    }

    const shouldLoad = tag || !user || !user.client_type;
    if (!shouldLoad && user) {
      setClientName(getClientName(user));
      const raw = user.logo_url || user.logo;
      setClientLogo(
        raw
          ? raw.startsWith('/')
            ? `${import.meta.env.VITE_API_URL?.replace('/api', '') || 'http://localhost:8000'}${raw}`
            : raw
          : null
      );
      ensureSupportWidgetForClientType(user.client_type);
      return;
    }

    (async () => {
      try {
        const { data } = await clientAPI.getMe();
        setClientName(getClientName(data));
        const raw = data?.logo_url || data?.logo;
        setClientLogo(
          raw
            ? raw.startsWith('/')
              ? `${import.meta.env.VITE_API_URL?.replace('/api', '') || 'http://localhost:8000'}${raw}`
              : raw
            : null
        );
        ensureSupportWidgetForClientType(data?.client_type);
      } catch {
        setClientName('Concierge');
        setClientLogo(null);
      }
    })();
  }, [isAuthenticated, user, tag]);

  // Nav sections — grouped for the stationery vibe
  const mainNav = [
    { to: '/dashboard', icon: SquaresFour,    label: t('nav.dashboard') },
    { to: '/history',   icon: ChatDots,       label: t('nav.history') },
    { to: '/training',  icon: GraduationCap,  label: t('nav.training') },
    ...(user?.leads_enabled ? [{ to: '/leads', icon: UsersThree, label: t('nav.leads') || 'Leads' }] : []),
  ];

  const configureNav = [
    { to: '/integrations', icon: PlugsConnected, label: t('nav.integrations') },
    user?.feature_flags?.mcp_knowledge_split
      ? { to: '/sandbox', icon: Robot, label: t('nav.assistant') || 'Assistant' }
      : { to: '/sandbox', icon: Flask, label: t('nav.sandbox') },
    ...(user?.feature_flags?.mcp_tools_dashboard
      ? [{ to: '/tools', icon: PuzzlePiece, label: t('nav.tools') || 'Tools' }]
      : []),
    { to: '/setup',    icon: BookOpen, label: t('nav.promptBook') || 'Prompt Book' },
    { to: '/settings', icon: GearSix,  label: t('nav.settings') || 'Settings' },
  ];

  const withTag = (to) => (tag ? `${to}?tag=${tag}` : to);
  const closeSidebar = () => setIsOpen(false);

  const userInitials = (user?.username || user?.email || clientName || 'C')
    .slice(0, 2)
    .toUpperCase();

  const renderItem = (item) => (
    <NavLink
      key={item.to}
      to={withTag(item.to)}
      onClick={closeSidebar}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-sm text-[14px] transition-all duration-200
         border-[1.5px] ${
           isActive
             ? 'border-iris text-ink'
             : 'border-transparent text-slate hover:bg-linen hover:text-ink'
         }`
      }
    >
      {({ isActive }) => (
        <>
          <item.icon
            size={20}
            weight="light"
            className={`shrink-0 ${isActive ? 'text-iris' : ''}`}
          />
          <span className="flex-1 truncate">{item.label}</span>
        </>
      )}
    </NavLink>
  );

  return (
    <>
      {/* Mobile hamburger */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="md:hidden fixed top-4 left-4 z-50 p-2 bg-paper rounded-sm
                   border-[1.5px] border-rule shadow-ink-sm text-ink"
        aria-label="Toggle menu"
      >
        {isOpen ? <X size={22} weight="light" /> : <List size={22} weight="light" />}
      </button>

      {/* Mobile scrim */}
      {isOpen && (
        <div
          className="md:hidden fixed inset-0 bg-ink/30 z-30 backdrop-blur-[2px]"
          onClick={closeSidebar}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed md:static inset-y-0 left-0 z-40
          w-[260px] min-h-screen bg-paper border-r border-rule
          flex flex-col p-4 gap-1
          transform transition-transform duration-300 ease-in-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-3 py-2 mb-6">
          <div className="w-10 h-10 border-2 border-iris rounded-md flex items-center justify-center text-iris">
            {clientLogo ? (
              <img
                src={clientLogo}
                alt={clientName}
                className="w-full h-full object-contain rounded-md"
                onError={(e) => { e.currentTarget.style.display = 'none'; }}
              />
            ) : (
              <BellSimple size={22} weight="light" />
            )}
          </div>
          <div>
            <div className="font-bold text-[18px] text-ink leading-tight tracking-tightest">
              {clientName}
            </div>
            <div className="font-mono text-[10px] uppercase tracking-[2px] text-fog">
              AI Platform
            </div>
          </div>
        </div>

        {/* Main section */}
        <div className="label-mono-sm px-3 pt-3 pb-2">{t('nav.sectionMain') || 'Main'}</div>
        {mainNav.map(renderItem)}

        {/* Configure section */}
        <div className="label-mono-sm px-3 pt-5 pb-2">{t('nav.sectionConfigure') || 'Configure'}</div>
        {configureNav.map(renderItem)}

        {/* User footer */}
        <div className="mt-auto pt-4 border-t border-rule flex items-center gap-3 px-3">
          <div className="w-[34px] h-[34px] rounded-[10px] border-2 border-sage text-sage
                          flex items-center justify-center font-bold text-[12px]">
            {userInitials}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[13px] font-medium text-ink truncate">
              {user?.username || user?.email || t('common.guest') || 'Guest'}
            </div>
            <div className="text-[11px] text-fog truncate">
              {user?.client_type || 'Demo'}
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
