import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import StatsCard from '../components/dashboard/StatsCard';
import ActivityFeed from '../components/dashboard/ActivityFeed';
import { MessageSquare, Users, TrendingUp, Percent, Upload, X, Loader2 } from 'lucide-react';
import { clientAPI } from '../api/client';

const DashboardPage = () => {
  const { t } = useTranslation();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [logo, setLogo] = useState(null);
  const [logoUrl, setLogoUrl] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [topQuestions, setTopQuestions] = useState([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [stats, setStats] = useState([
    { label: t('dashboard.totalChats'), value: '0', icon: MessageSquare, change: '+0%', color: 'primary' },
    { label: t('dashboard.activeUsers'), value: '0', icon: Users, change: '+0%', color: 'accent' },
    { label: t('dashboard.messages'), value: '0', icon: TrendingUp, change: '+0%', color: 'green' },
    { label: t('dashboard.conversion'), value: '0%', icon: Percent, change: '+0%', color: 'blue' },
  ]);
  const [loadingStats, setLoadingStats] = useState(false);
  const [dataLoaded, setDataLoaded] = useState(false);

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
        loadClientLogo();
        loadTopQuestions();
        loadStats();
        setDataLoaded(true);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [authLoading, isAuthenticated, dataLoaded]);

  const loadClientLogo = async () => {
    try {
      const response = await clientAPI.getMe();
      // Перевіряємо різні можливі поля для logo URL
      const logoUrlFromAPI = response.data?.logo_url || response.data?.logo;
      if (logoUrlFromAPI) {
        // Якщо це відносний шлях, додаємо base URL
        if (logoUrlFromAPI.startsWith('/')) {
          const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
          setLogoUrl(`${baseURL}${logoUrlFromAPI}`);
        } else {
          setLogoUrl(logoUrlFromAPI);
        }
      }
    } catch (err) {
      console.error('Failed to load client logo:', err);
    }
  };

  const handleLogoSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      // Перевірка типу файлу
      if (!file.type.startsWith('image/')) {
        setError(t('dashboard.logoInvalidType') || 'File must be an image');
        return;
      }

      // Перевірка розміру (макс 5MB)
      if (file.size > 5 * 1024 * 1024) {
        setError(t('dashboard.logoTooLarge') || 'File size must be less than 5MB');
        return;
      }

      setError(null);
      setLogo(file);

      // Показати preview
      const reader = new FileReader();
      reader.onloadend = () => {
        setLogoUrl(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleLogoUpload = async () => {
    if (!logo) return;

    setUploading(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await clientAPI.uploadLogo(logo);
      const uploadedLogoUrl = response.data?.logo_url;
      
      if (uploadedLogoUrl) {
        setLogoUrl(uploadedLogoUrl);
      }
      
      setSuccess(true);
      setLogo(null);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to upload logo:', err);
      setError(t('dashboard.logoUploadError') || 'Failed to upload logo');
    } finally {
      setUploading(false);
    }
  };

  const handleLogoDelete = async () => {
    if (!confirm(t('dashboard.deleteLogoConfirm') || 'Are you sure you want to delete the logo?')) {
      return;
    }

    setUploading(true);
    setError(null);

    try {
      // Видалення логотипу через API (потрібно перевірити чи є endpoint)
      // Поки що використовуємо updateMe з logo = null
      await clientAPI.updateMe({ logo: null });
      setLogoUrl(null);
      setLogo(null);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to delete logo:', err);
      setError(t('dashboard.logoDeleteError') || 'Failed to delete logo');
    } finally {
      setUploading(false);
    }
  };

  const handleCancel = () => {
    setLogo(null);
    setError(null);
    // Відновити оригінальний логотип
    loadClientLogo();
  };

  const loadTopQuestions = async () => {
    setLoadingQuestions(true);
    try {
      const response = await clientAPI.getTopQuestions();
      const questions = response.data?.top_questions || [];
      setTopQuestions(questions);
    } catch (err) {
      console.error('Failed to load top questions:', err);
      // Fallback на порожній список
      setTopQuestions([]);
    } finally {
      setLoadingQuestions(false);
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

  // Показуємо loading поки автентифікація не завершена
  if (authLoading || !isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary-500 mx-auto mb-4" />
          <p className="text-gray-600">Завантаження...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('dashboard.title')}</h1>
        <p className="text-gray-600">{t('dashboard.subtitle')}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {loadingStats ? (
          <div className="col-span-4 flex items-center justify-center py-8">
            <Loader2 className="animate-spin text-primary-500" size={24} />
          </div>
        ) : (
          stats.map((stat, index) => (
          <StatsCard key={index} {...stat} />
          ))
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">{t('dashboard.recentActivity')}</h3>
          <ActivityFeed />
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold mb-4">{t('dashboard.topQuestions') || t('dashboard.topServices')}</h3>
          {loadingQuestions ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="animate-spin text-primary-500" size={24} />
            </div>
          ) : topQuestions.length === 0 || topQuestions.every(q => !q.question) ? (
            <div className="text-center text-gray-500 py-8">
              <p>{t('dashboard.noQuestions') || 'No questions yet'}</p>
            </div>
          ) : (
          <div className="space-y-3">
              {topQuestions.filter(q => q.question).map((item, index) => (
                <div key={index} className="flex items-start justify-between gap-3">
                  <span className="text-gray-700 text-sm flex-1 line-clamp-2">{item.question}</span>
                  <span className="font-semibold text-primary-600 whitespace-nowrap">{item.count} {t('dashboard.requests') || t('dashboard.bookingsCount')}</span>
              </div>
            ))}
            </div>
          )}
        </div>
      </div>

      {/* Logo Upload Section */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">{t('dashboard.uploadLogo')}</h3>
        <p className="text-sm text-gray-600 mb-4">
          {t('dashboard.logoDescription')}
        </p>

        <div className="space-y-4">
          {/* Current Logo Preview */}
          {logoUrl && (
            <div className="relative inline-block">
              <img
                src={logoUrl}
                alt="Company Logo"
                className="max-w-xs max-h-32 object-contain border border-gray-200 rounded-lg p-2 bg-white"
              />
              {logo && (
                <button
                  onClick={handleCancel}
                  className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-1 hover:bg-red-600 transition"
                  title={t('dashboard.cancel') || 'Cancel'}
                >
                  <X size={16} />
                </button>
              )}
            </div>
          )}

          {/* Error/Success Messages */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {error}
            </div>
          )}

          {success && (
            <div className="p-3 bg-green-50 border border-green-200 rounded text-green-700 text-sm">
              {t('dashboard.logoUploadSuccess') || 'Logo uploaded successfully! QR codes will be regenerated with the new logo.'}
            </div>
          )}

          {/* Upload Controls */}
          <div className="flex items-center gap-3">
            <input
              type="file"
              accept="image/*"
              onChange={handleLogoSelect}
              className="hidden"
              id="logo-input"
              disabled={uploading}
            />
            <label
              htmlFor="logo-input"
              className={`btn-secondary flex items-center gap-2 cursor-pointer ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <Upload size={16} />
              {logoUrl ? t('dashboard.changeLogo') : t('dashboard.selectLogo')}
            </label>

            {logo && (
              <>
                <button
                  onClick={handleLogoUpload}
                  disabled={uploading}
                  className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {uploading ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      {t('dashboard.uploading') || 'Uploading...'}
                    </>
                  ) : (
                    <>
                      <Upload size={16} />
                      {t('dashboard.uploadLogoButton') || 'Upload Logo'}
                    </>
                  )}
                </button>
              </>
            )}

            {logoUrl && !logo && (
              <button
                onClick={handleLogoDelete}
                disabled={uploading}
                className="btn-danger flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    {t('dashboard.deleting') || 'Deleting...'}
                  </>
                ) : (
                  <>
                    <X size={16} />
                    {t('dashboard.deleteLogo') || 'Delete Logo'}
                  </>
                )}
              </button>
            )}
          </div>

          {/* Info about QR codes */}
          {logoUrl && (
            <div className="text-xs text-gray-500 bg-blue-50 border border-blue-200 rounded p-2">
              {t('dashboard.logoQRInfo') || 'Your logo will be used in all QR code generations. Existing QR codes will be regenerated automatically.'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
