import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';
import ChatList from '../components/history/ChatList';
import ChatDetail from '../components/history/ChatDetail';
import ActivityFeed from '../components/dashboard/ActivityFeed';
import { clientAPI } from '../api/client';

const HistoryPage = () => {
  const { t } = useTranslation();
  const [selectedChat, setSelectedChat] = useState(null);
  const [topQuestions, setTopQuestions] = useState([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);

  useEffect(() => {
    loadTopQuestions();
  }, []);

  const loadTopQuestions = async () => {
    setLoadingQuestions(true);
    try {
      const response = await clientAPI.getTopQuestions();
      const questions = response.data?.top_questions || [];
      setTopQuestions(questions);
    } catch (err) {
      console.error('Failed to load top questions:', err);
      setTopQuestions([]);
    } finally {
      setLoadingQuestions(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('history.title')}</h1>
        <p className="text-gray-600 dark:text-gray-400">{t('history.subtitle')}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <ChatList onSelectChat={setSelectedChat} selectedChatId={selectedChat?.id} />
        </div>

        <div className="lg:col-span-2">
          {selectedChat ? (
            <ChatDetail chat={selectedChat} />
          ) : (
            <div className="card h-full flex items-center justify-center">
              <div className="text-center text-gray-500 dark:text-gray-400">
                <p className="text-lg">{t('history.selectChat')}</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Recent Activity and Top Questions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">{t('dashboard.recentActivity')}</h3>
          <ActivityFeed />
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">{t('dashboard.topQuestions') || t('dashboard.topServices')}</h3>
          {loadingQuestions ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={24} />
            </div>
          ) : topQuestions.length === 0 || topQuestions.every(q => !q.question) ? (
            <div className="text-center text-gray-500 dark:text-gray-400 py-8">
              <p>{t('dashboard.noQuestions') || 'No questions yet'}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {topQuestions.filter(q => q.question).map((item, index) => (
                <div key={index} className="flex items-start justify-between gap-3">
                  <span className="text-gray-700 dark:text-gray-300 text-sm flex-1 line-clamp-2">{item.question}</span>
                  <span className="font-semibold text-primary-600 dark:text-primary-400 whitespace-nowrap">{item.count} {t('dashboard.requests') || t('dashboard.bookingsCount')}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default HistoryPage;
