import { useTranslation } from 'react-i18next';
import ToolStatusBadge from './ToolStatusBadge';

const ToolCard = ({ tool, onConnect, onConfigure }) => {
  const { t } = useTranslation();
  const conn = tool.connection;
  const isConnected = conn?.status === 'connected' && conn?.enabled;
  const isError = conn?.status === 'error';
  const isPending = conn?.status === 'pending';

  return (
    <div
      className={`relative bg-white dark:bg-gray-800 rounded-xl border p-5 transition-all hover:shadow-md ${
        isConnected
          ? 'border-l-4'
          : isError
          ? 'border-red-300 dark:border-red-700'
          : isPending
          ? 'border-yellow-300 dark:border-yellow-700 animate-pulse'
          : 'border-gray-200 dark:border-gray-700 opacity-80 hover:opacity-100'
      }`}
      style={isConnected ? { borderLeftColor: tool.color || '#6366f1' } : undefined}
    >
      {/* Icon + Name */}
      <div className="flex items-start gap-3 mb-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center text-lg shrink-0"
          style={{ backgroundColor: `${tool.color || '#6366f1'}20` }}
        >
          {tool.icon || '🔧'}
        </div>
        <div className="min-w-0">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 truncate">
            {tool.name}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-2 mt-0.5">
            {tool.tagline}
          </p>
        </div>
      </div>

      {/* Status */}
      <div className="mb-4">
        <ToolStatusBadge status={conn?.status || 'disconnected'} />
      </div>

      {/* Action */}
      {isConnected ? (
        <button
          onClick={() => onConfigure(tool)}
          className="w-full py-2 px-4 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
        >
          {t('tools.configure')}
        </button>
      ) : (
        <button
          onClick={() => onConnect(tool)}
          disabled={isPending}
          className="w-full py-2 px-4 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 transition-colors"
        >
          {isPending ? t('tools.connecting') : isError ? t('tools.retry') : t('tools.connect')}
        </button>
      )}
    </div>
  );
};

export default ToolCard;
