import { useTranslation } from 'react-i18next';

const STATUS_CONFIG = {
  connected: {
    dot: 'bg-green-500',
    text: 'text-green-700 dark:text-green-400',
    key: 'tools.connected',
  },
  pending: {
    dot: 'bg-yellow-500 animate-pulse',
    text: 'text-yellow-700 dark:text-yellow-400',
    key: 'tools.connecting',
  },
  error: {
    dot: 'bg-red-500',
    text: 'text-red-700 dark:text-red-400',
    key: 'tools.error',
  },
  disconnected: {
    dot: 'bg-gray-400',
    text: 'text-gray-500 dark:text-gray-400',
    key: 'tools.notConnected',
  },
};

const ToolStatusBadge = ({ status }) => {
  const { t } = useTranslation();
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.disconnected;

  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${config.dot}`} />
      <span className={`text-xs font-medium ${config.text}`}>
        {t(config.key)}
      </span>
    </div>
  );
};

export default ToolStatusBadge;
