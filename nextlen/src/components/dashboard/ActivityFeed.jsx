import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageSquare, Calendar, CheckCircle, Loader2, UserPlus, ExternalLink } from 'lucide-react';
import { clientAPI } from '../../api/client';

const ActivityFeed = () => {
  const { t } = useTranslation();
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadActivities();
  }, []);

  const loadActivities = async () => {
    setLoading(true);
    try {
      const response = await clientAPI.getRecentActivity();
      const activitiesData = response.data?.activities || [];

      const formattedActivities = activitiesData.map((activity) => {
        let icon = MessageSquare;
        let color = 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400';

        if (activity.type === 'new_chat') {
          icon = MessageSquare;
          color = 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400';
        } else if (activity.type === 'new_lead') {
          icon = UserPlus;
          color = 'bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400';
        } else if (activity.type === 'booking') {
          icon = Calendar;
          color = 'bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400';
        } else if (activity.type === 'training') {
          icon = CheckCircle;
          color = 'bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400';
        }

        return {
          icon,
          text: activity.text || activity.type,
          time: activity.time || activity.timestamp,
          color,
          timestamp: activity.timestamp,
          session_id: activity.session_id || '',
          type: activity.type,
        };
      });

      setActivities(formattedActivities);
    } catch (err) {
      console.error('Failed to load activities:', err);
      setActivities([]);
    } finally {
      setLoading(false);
    }
  };

  const getChatLink = (activity) => {
    if (!activity.session_id) return null;
    // Підтримка обох форматів URL: /l/:tag/... та /l?tag=...
    const pathMatch = window.location.pathname.match(/^\/l\/([^/]+)/);
    const tag = pathMatch ? pathMatch[1] : new URLSearchParams(window.location.search).get('tag');
    if (!tag) return null;
    // Новий формат — лінк на history з session
    if (pathMatch) {
      return `/l/${tag}/history?session=${encodeURIComponent(activity.session_id)}`;
    }
    return `/l?tag=${tag}&session=${encodeURIComponent(activity.session_id)}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={24} />
      </div>
    );
  }

  if (activities.length === 0) {
    return (
      <div className="text-center text-gray-500 dark:text-gray-400 py-8">
        <p>{t('dashboard.noActivity') || 'No recent activity'}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {activities.map((activity, index) => {
        const chatLink = getChatLink(activity);
        return (
          <div key={index} className="flex items-start gap-3">
            <div className={`p-2 rounded-lg ${activity.color}`}>
              <activity.icon size={16} />
            </div>
            <div className="flex-1">
              <p className="text-sm text-gray-800 dark:text-gray-200">{activity.text}</p>
              <div className="flex items-center gap-2 mt-1">
                <p className="text-xs text-gray-500 dark:text-gray-400">{activity.time}</p>
                {chatLink && (
                  <a
                    href={chatLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300"
                  >
                    <ExternalLink size={12} />
                    {t('dashboard.viewChat') || 'View chat'}
                  </a>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default ActivityFeed;
