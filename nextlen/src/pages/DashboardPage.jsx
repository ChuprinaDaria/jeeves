import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import StatsCard from '../components/dashboard/StatsCard';
import InfoCenter from '../components/dashboard/InfoCenter';
import { MessageSquare, Users, TrendingUp, Percent, Loader2, Sparkles, ThumbsUp, X } from 'lucide-react';
import { clientAPI } from '../api/client';
import api from '../api/axios';

const DashboardPage = () => {
  const { t } = useTranslation();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [stats, setStats] = useState([
    { label: t('dashboard.totalChats'), value: '0', icon: MessageSquare, change: '+0%', color: 'primary' },
    { label: t('dashboard.activeUsers'), value: '0', icon: Users, change: '+0%', color: 'accent' },
    { label: t('dashboard.messages'), value: '0', icon: TrendingUp, change: '+0%', color: 'green' },
    { label: t('dashboard.conversion'), value: '0%', icon: Percent, change: '+0%', color: 'blue' },
  ]);
  const [loadingStats, setLoadingStats] = useState(false);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [topPrompts, setTopPrompts] = useState([]);
  const [loadingPrompts, setLoadingPrompts] = useState(false);
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  const [dashboardConfig, setDashboardConfig] = useState({
    layout: 'default',
    showInfoCenter: false,
    showTopPrompts: false,
    customWidgets: null,
    customStyle: null,
  });

  // Завантажити поточний логотип клієнта, топ питання та статистику
  // Тільки після того як автентифікація завершена
  useEffect(() => {
    // Чекаємо поки AuthContext завантажиться
    if (authLoading) {
      return;
    }

    // Якщо не авторизований, не робимо запити
    if (!isAuthenticated) {
      return;
    }

    // Невелика затримка для гарантії що токен встановлений
    const timer = setTimeout(() => {
      if (!dataLoaded) {
        loadDashboardConfig();
        loadStats();
        loadTopPrompts();
        setDataLoaded(true);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [authLoading, isAuthenticated, dataLoaded]);

  const loadDashboardConfig = async () => {
    try {
      const response = await clientAPI.getMe();
      const client = response.data;
      
      setDashboardConfig({
        layout: client.dashboard_layout || 'default',
        showInfoCenter: client.dashboard_show_info_center !== false,
        showTopPrompts: client.dashboard_show_top_prompts !== false,
        customWidgets: client.dashboard_custom_widgets || null,
        customStyle: client.dashboard_custom_style || null,
      });
    } catch (err) {
      console.error('Failed to load dashboard config:', err);
      // Fallback на дефолтну конфігурацію
    }
  };

  const loadStats = async () => {
    setLoadingStats(true);
    try {
      const response = await clientAPI.getStats();
      const data = response.data;
      
      setStats([
        {
          label: t('dashboard.totalChats'),
          value: String(data.total_chats || 0),
          icon: MessageSquare,
          change: `${data.chats_change >= 0 ? '+' : ''}${data.chats_change || 0}%`,
          color: 'primary'
        },
        {
          label: t('dashboard.activeUsers'),
          value: String(data.active_users || 0),
          icon: Users,
          change: `${data.users_change >= 0 ? '+' : ''}${data.users_change || 0}%`,
          color: 'accent'
        },
        {
          label: t('dashboard.messages'),
          value: String(data.total_messages || 0),
          icon: TrendingUp,
          change: `${data.messages_change >= 0 ? '+' : ''}${data.messages_change || 0}%`,
          color: 'green'
        },
        {
          label: t('dashboard.conversion'),
          value: `${data.conversion_rate || 0}%`,
          icon: Percent,
          change: `${data.conversion_change >= 0 ? '+' : ''}${data.conversion_change || 0}%`,
          color: 'blue'
        },
      ]);
    } catch (err) {
      console.error('Failed to load stats:', err);
      // Fallback на дефолтні значення
      setStats([
        { label: t('dashboard.totalChats'), value: '0', icon: MessageSquare, change: '+0%', color: 'primary' },
        { label: t('dashboard.activeUsers'), value: '0', icon: Users, change: '+0%', color: 'accent' },
        { label: t('dashboard.messages'), value: '0', icon: TrendingUp, change: '+0%', color: 'green' },
        { label: t('dashboard.conversion'), value: '0%', icon: Percent, change: '+0%', color: 'blue' },
      ]);
    } finally {
      setLoadingStats(false);
    }
  };

  const loadTopPrompts = async () => {
    setLoadingPrompts(true);
    try {
      const response = await api.get('/clients/top-prompts/');
      setTopPrompts(response.data.top_prompts || []);
    } catch (err) {
      console.error('Failed to load top prompts:', err);
      setTopPrompts([]);
    } finally {
      setLoadingPrompts(false);
    }
  };

  // Показуємо loading поки автентифікація не завершена
  if (authLoading || !isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary-500 dark:text-primary-400 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">{t('common.loading') || 'Loading...'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('dashboard.title')}</h1>
        <p className="text-gray-600 dark:text-gray-400">{t('dashboard.subtitle')}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {loadingStats ? (
          <div className="col-span-4 flex items-center justify-center py-8">
            <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={24} />
          </div>
        ) : (
          stats.map((stat, index) => (
          <StatsCard key={index} {...stat} />
          ))
        )}
      </div>

      {/* Conditional widgets based on dashboard layout */}
      {dashboardConfig.layout === 'minimal' ? (
        // Minimal layout: only stats, nothing else
        null
      ) : dashboardConfig.layout === 'white_label' ? (
        // White Label: only custom widgets (if configured)
        dashboardConfig.customWidgets && dashboardConfig.customWidgets.widgets ? (
          <div className="space-y-6">
            {/* TODO: Render custom widgets here */}
            <div className="card">
              <p className="text-gray-600 dark:text-gray-400">
                Custom widgets coming soon...
              </p>
            </div>
          </div>
        ) : null
      ) : (
        // Default or Hybrid: show standard widgets
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Info Center - conditionally rendered */}
          {dashboardConfig.showInfoCenter && (
            <div className="lg:col-span-2">
              <InfoCenter />
            </div>
          )}

          {/* Top Prompts - conditionally rendered */}
          {dashboardConfig.showTopPrompts && (
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                  <Sparkles size={20} className="text-primary-600 dark:text-primary-400" />
                  {t('dashboard.topPrompts') || 'Top Prompts'}
                </h3>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {t('dashboard.topPromptsSubtitle') || 'Most rated prompts by clients'}
                </span>
              </div>

              {loadingPrompts ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={24} />
                </div>
              ) : topPrompts.length > 0 ? (
                <div className="space-y-3">
                  {topPrompts.map((prompt, index) => (
                    <div
                      key={prompt.id}
                      onClick={() => setSelectedPrompt(prompt)}
                      className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-semibold text-primary-600 dark:text-primary-400">
                              #{index + 1}
                            </span>
                            <span className="text-xs px-2 py-1 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                              {prompt.category}
                            </span>
                          </div>
                          <h4 className="font-semibold text-sm text-gray-900 dark:text-gray-100 mb-1">
                            {prompt.title}
                          </h4>
                          <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2 mb-2">
                            {prompt.description}
                          </p>
                          <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                            <div className="flex items-center gap-1">
                              <ThumbsUp size={14} />
                              <span>{prompt.likes_count || 0}</span>
                            </div>
                            <span>
                              {prompt.like_ratio ? `${Math.round(prompt.like_ratio * 100)}%` : '0%'} positive
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
                  {t('dashboard.noTopPrompts') || 'No top prompts available yet.'}
                </div>
              )}
            </div>
          )}

          {/* Custom widgets for hybrid layout */}
          {dashboardConfig.layout === 'hybrid' && dashboardConfig.customWidgets && dashboardConfig.customWidgets.widgets && (
            <div className="lg:col-span-2">
              {/* TODO: Render custom widgets here */}
              <div className="card">
                <p className="text-gray-600 dark:text-gray-400">
                  Custom widgets for hybrid layout coming soon...
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {selectedPrompt && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelectedPrompt(null);
          }}
        >
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl max-w-lg w-full mx-4 p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                {selectedPrompt.category && (
                  <p className="text-xs uppercase tracking-wide text-primary-600 dark:text-primary-400 mb-1">
                    {selectedPrompt.category}
                  </p>
                )}
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {selectedPrompt.title}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedPrompt(null)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <X size={18} />
              </button>
            </div>

            {selectedPrompt.description && (
              <div className="mb-4">
                <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
                  {t('dashboard.promptDescription') || 'Description'}
                </h4>
                <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-line">
                  {selectedPrompt.description}
                </p>
              </div>
            )}

            {selectedPrompt.prompt_template && (
              <div>
                <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
                  {t('dashboard.promptTemplate') || 'Prompt Template'}
                </h4>
                <pre className="text-xs text-gray-800 dark:text-gray-200 bg-gray-50 dark:bg-gray-800 rounded-lg p-3 overflow-auto max-h-64 whitespace-pre-wrap">
                  {selectedPrompt.prompt_template}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default DashboardPage;
