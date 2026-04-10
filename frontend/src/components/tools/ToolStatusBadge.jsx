import { useTranslation } from 'react-i18next';

const STATUS_CONFIG = {
  connected:    { dot: 'bg-sage',                 text: 'text-sage',  key: 'tools.connected' },
  pending:      { dot: 'bg-amber animate-pulse',  text: 'text-amber', key: 'tools.connecting' },
  error:        { dot: 'bg-rose',                 text: 'text-rose',  key: 'tools.error' },
  disconnected: { dot: 'bg-fog',                  text: 'text-fog',   key: 'tools.notConnected' },
};

const ToolStatusBadge = ({ status }) => {
  const { t } = useTranslation();
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.disconnected;

  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
      <span className={`font-mono text-[10px] uppercase tracking-wider ${cfg.text}`}>
        {t(cfg.key)}
      </span>
    </div>
  );
};

export default ToolStatusBadge;
