import { useState, useEffect, lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import StatsCard from '../components/dashboard/StatsCard';
import ActivityFeed from '../components/dashboard/ActivityFeed';
import { MessageSquare, Users, TrendingUp, Percent, Loader2 } from 'lucide-react';
import { clientAPI } from '../api/client';

const PixelDashboard = lazy(() => import('../modules/pixelDashboard/PixelDashboard'));

const DashboardPage = () => {
  const { t } = useTranslation();
  const { isAuthenticated, loading: authLoading, user } = useAuth();
  const [stats, setStats] = useState([
    { label: t('dashboard.totalChats'), value: '0', icon: MessageSquare, change: '+0%', color: 'primary' },
    { label: t('dashboard.activeUsers'), value: '0', icon: Users, change: '+0%', color: 'accent' },
    { label: t('dashboard.messages'), value: '0', icon: TrendingUp, change: '+0%', color: 'green' },
    { label: t('dashboard.conversion'), value: '0%', icon: Percent, change: '+0%', color: 'blue' },
  ]);
  const [loadingStats, setLoadingStats] = useState(false);
  const [dataLoaded, setDataLoaded] = useState(false);

  // Завантажити статистику
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
        loadStats();
        setDataLoaded(true);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [authLoading, isAuthenticated, dataLoaded]);

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

      {user?.pixel_dashboard_enabled && (
        <Suspense fallback={null}>
          <PixelDashboard enabled={user.pixel_dashboard_enabled} />
        </Suspense>
      )}

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

      {/* Recent Activity */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          {t('dashboard.recentActivity') || 'Recent Activity'}
        </h2>
        <ActivityFeed />
      </div>
    </div>
  );
};

export default DashboardPage;
