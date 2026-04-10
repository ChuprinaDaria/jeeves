import { useTranslation } from 'react-i18next';
import ToolStatusBadge from './ToolStatusBadge';
import ToolIcon from './ToolIcon';

const ToolCard = ({ tool, onConnect, onConfigure }) => {
  const { t } = useTranslation();
  const conn = tool.connection;
  const isConnected = conn?.status === 'connected' && conn?.enabled;
  const isError = conn?.status === 'error';
  const isPending = conn?.status === 'pending';

  return (
    <div
      className={`relative bg-paper rounded-lg p-5 transition-all hover:shadow-ink-sm border-[1.5px] ${
        isConnected
          ? 'border-sage'
          : isError
          ? 'border-rose'
          : isPending
          ? 'border-amber animate-pulse'
          : 'border-rule opacity-80 hover:opacity-100'
      }`}
    >
      {/* Icon + Name */}
      <div className="flex items-start gap-3 mb-3">
        <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 bg-linen border-[1.5px] border-rule text-iris">
          <ToolIcon name={tool.icon} className="w-5 h-5" />
        </div>
        <div className="min-w-0">
          <h3 className="font-semibold text-ink truncate">
            {tool.name}
          </h3>
          <p className="text-sm text-slate line-clamp-2 mt-0.5">
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
          className="btn btn-violet w-full justify-center"
        >
          {t('tools.configure')}
        </button>
      ) : (
        <button
          onClick={() => onConnect(tool)}
          disabled={isPending}
          className="btn btn-violet w-full justify-center disabled:opacity-50"
        >
          {isPending ? t('tools.connecting') : isError ? t('tools.retry') : t('tools.connect')}
        </button>
      )}
    </div>
  );
};

export default ToolCard;
