import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowRight, Loader2, Plug, Cpu, Sparkles, Megaphone, Info } from 'lucide-react';
import api from '../../api/axios';

const InfoCenter = () => {
  const { t, i18n } = useTranslation();
  const [newsItems, setNewsItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedNews, setSelectedNews] = useState(null);

  useEffect(() => {
    loadNews();
  }, [i18n.language]); // Reload news when language changes

  const loadNews = async () => {
    try {
      setLoading(true);
      // Get current language from i18n
      const currentLang = i18n.language || 'en';
      // Map i18n language codes to backend codes (uk is not in i18n, use en as fallback)
      const langMap = {
        'en': 'en',
        'de': 'de',
        'es': 'es',
        'fr': 'fr',
        'it': 'it',
        'nl': 'nl',
        'da': 'da',
      };
      const backendLang = langMap[currentLang] || 'en';
      
      const response = await api.get('/clients/news/', {
        params: { lang: backendLang }
      });
      const news = response.data.results || response.data || [];
      // Беремо всі доступні новини з бекенду (бекенд вже обмежує їх кількість пагінацією)
      setNewsItems(news);
    } catch (error) {
      console.error('Error loading news:', error);
      // Fallback на порожній масив
      setNewsItems([]);
    } finally {
      setLoading(false);
    }
  };

  // Конфіг для категорій новин (типи з бекенду: integration, model, feature, update, announcement)
  const CATEGORY_CONFIG = {
    integration: {
      icon: Plug,
      label: t('infoCenter.categories.integration') || 'Integrations',
      pillClass: 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
    },
    feature: {
      icon: Sparkles,
      label: t('infoCenter.categories.feature') || 'Features & improvements',
      pillClass: 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300',
    },
    model: {
      icon: Cpu,
      label: t('infoCenter.categories.model') || 'AI models',
      pillClass: 'bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300',
    },
    update: {
      icon: Megaphone,
      label: t('infoCenter.categories.update') || 'Product updates',
      pillClass: 'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300',
    },
    announcement: {
      icon: Megaphone,
      label: t('infoCenter.categories.announcement') || 'Announcements',
      pillClass: 'bg-sky-50 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300',
    },
    other: {
      icon: Info,
      label: t('infoCenter.categories.other') || 'Other updates',
      pillClass: 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300',
    },
  };

  return (
    <div className="card">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('infoCenter.title') || 'Info Center'}</h3>
        <span className="text-xs text-gray-500 dark:text-gray-400">{t('infoCenter.subtitle') || 'Latest updates and news'}</span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={24} />
        </div>
      ) : newsItems.length > 0 ? (
        <>
          {/* Групування новин за категоріями */}
          <div className="grid gap-4 md:grid-cols-2">
            {(() => {
              const groups = newsItems.reduce((acc, item) => {
                const type = item.news_type || 'other';
                if (!acc[type]) acc[type] = [];
                acc[type].push(item);
                return acc;
              }, {});

              const order = ['integration', 'feature', 'model', 'update', 'announcement', 'other'];
              const orderedTypes = order.filter((type) => groups[type]?.length);

              if (orderedTypes.length === 0) {
                return (
                  <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                    {t('infoCenter.noNews') || 'No news available at the moment.'}
                  </div>
                );
              }

              return orderedTypes.map((type) => {
                const items = groups[type];
                const config = CATEGORY_CONFIG[type] || CATEGORY_CONFIG.other;
                const Icon = config.icon;

                return (
                  <section
                    key={type}
                    className="space-y-2 rounded-xl border border-violet-100/70 dark:border-violet-900/40 bg-gradient-to-br from-violet-50/70 via-white to-orange-50/60 dark:from-violet-950/60 dark:via-slate-950 dark:to-orange-950/40 p-3 sm:p-4"
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <div className={`inline-flex items-center justify-center w-6 h-6 sm:w-7 sm:h-7 rounded-full shadow-sm flex-shrink-0 ${config.pillClass}`}>
                          <Icon size={12} className="sm:w-3.5 sm:h-3.5" />
                        </div>
                        <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wide text-gray-800 dark:text-gray-100 truncate">
                          {config.label}
                        </span>
                      </div>
                      <span className="text-[10px] sm:text-[11px] font-medium text-violet-600 dark:text-violet-300 whitespace-nowrap flex-shrink-0">
                        {items.length} {t('infoCenter.itemsLabel') || 'items'}
                      </span>
                    </div>

                    <div className="space-y-1.5">
                      {items.map((item) => {
                        let dateLabel = '';
                        if (item.created_at) {
                          try {
                            const d = new Date(item.created_at);
                            dateLabel = d.toLocaleDateString(i18n.language || 'en', {
                              day: '2-digit',
                              month: 'short',
                            });
                          } catch (e) {
                            dateLabel = '';
                          }
                        }

                        return (
                          <button
                            key={item.id}
                            type="button"
                            onClick={() => setSelectedNews(item)}
                            className="w-full group flex items-start gap-2 sm:gap-3 rounded-lg border border-white/80 dark:border-gray-800 bg-white/80 dark:bg-gray-950/40 px-2 sm:px-3 py-2 hover:bg-violet-50/80 dark:hover:bg-violet-950/40 hover:border-violet-200 dark:hover:border-violet-500 transition-all text-left shadow-[0_1px_2px_rgba(15,23,42,0.05)]"
                          >
                            {item.image_url ? (
                              <div className="mt-0.5 h-8 w-8 sm:h-9 sm:w-9 rounded-md overflow-hidden flex-shrink-0 border border-gray-200/80 dark:border-gray-700/80 bg-gray-50 dark:bg-gray-900">
                                <img
                                  src={item.image_url}
                                  alt={item.title}
                                  className="h-full w-full object-cover"
                                  onError={(e) => {
                                    e.target.style.display = 'none';
                                  }}
                                />
                              </div>
                            ) : (
                              <div className="mt-1 h-1.5 w-1.5 sm:h-2 sm:w-2 rounded-full bg-primary-500 dark:bg-primary-400 flex-shrink-0 group-hover:scale-110 transition-transform" />
                            )}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-start justify-between gap-1 sm:gap-2">
                                <p className="text-xs sm:text-sm font-medium text-gray-900 dark:text-gray-100 line-clamp-2 group-hover:text-primary-600 dark:group-hover:text-primary-400 flex-1">
                                  {item.title}
                                </p>
                                {item.is_featured && (
                                  <span className="inline-flex items-center rounded-full bg-emerald-50 dark:bg-emerald-900/30 px-1.5 sm:px-2 py-0.5 text-[9px] sm:text-[10px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-300 whitespace-nowrap flex-shrink-0">
                                    {t('infoCenter.badgeFeatured') || 'Highlight'}
                                  </span>
                                )}
                              </div>
                              <p className="mt-0.5 text-[11px] sm:text-xs text-gray-600 dark:text-gray-400 line-clamp-2">
                                {item.description}
                              </p>
                              {dateLabel && (
                                <p className="mt-1 text-[10px] sm:text-[11px] text-gray-400 dark:text-gray-500">
                                  {dateLabel}
                                </p>
                              )}
                            </div>
                            <ArrowRight
                              size={12}
                              className="mt-1 text-gray-300 dark:text-gray-600 group-hover:text-primary-500 dark:group-hover:text-primary-400 transition-colors flex-shrink-0 sm:w-3.5 sm:h-3.5"
                            />
                          </button>
                        );
                      })}
                    </div>
                  </section>
                );
              });
            })()}
          </div>

          {/* Модалка з повним описом новини */}
          {selectedNews && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
              <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl max-w-lg w-full mx-4 overflow-hidden">
                {selectedNews.image_url && (
                  <div className="h-40 overflow-hidden bg-gray-100 dark:bg-gray-800">
                    <img
                      src={selectedNews.image_url}
                      alt={selectedNews.title}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.target.style.display = 'none';
                      }}
                    />
                  </div>
                )}
                <div className="p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        selectedNews.news_type === 'integration' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300' :
                        selectedNews.news_type === 'model' ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300' :
                        selectedNews.news_type === 'feature' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300' :
                        selectedNews.news_type === 'update' ? 'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300' :
                        selectedNews.news_type === 'announcement' ? 'bg-sky-50 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300' :
                        'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                      }`}>
                        {selectedNews.news_type}
                      </span>
                      {selectedNews.is_featured && (
                        <span className="text-xs px-2 py-1 rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300">
                          {t('infoCenter.badgeFeatured') || 'Highlight'}
                        </span>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedNews(null)}
                      className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-sm"
                    >
                      ✕
                    </button>
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
                    {selectedNews.title}
                  </h3>
                  <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-line">
                    {selectedNews.description}
                  </p>
                </div>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          {t('infoCenter.noNews') || 'No news available at the moment.'}
        </div>
      )}
    </div>
  );
};

export default InfoCenter;

