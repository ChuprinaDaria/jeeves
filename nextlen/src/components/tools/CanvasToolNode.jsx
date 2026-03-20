import { useTranslation } from 'react-i18next';
import ToolStatusBadge from './ToolStatusBadge';
import ToolIcon from './ToolIcon';
import { getToolTargets } from './toolTargets';

const CAT_COLORS = {
  communication: { bg: 'bg-green-500/10 dark:bg-green-500/15', text: 'text-green-500', border: 'border-green-500/30' },
  ai:            { bg: 'bg-primary-500/10 dark:bg-primary-500/15', text: 'text-primary-500', border: 'border-primary-500/30' },
  productivity:  { bg: 'bg-orange-500/10 dark:bg-orange-500/15', text: 'text-orange-500', border: 'border-orange-500/30' },
  analytics:     { bg: 'bg-blue-500/10 dark:bg-blue-500/15', text: 'text-blue-500', border: 'border-blue-500/30' },
  crm:           { bg: 'bg-pink-500/10 dark:bg-pink-500/15', text: 'text-pink-500', border: 'border-pink-500/30' },
  custom:        { bg: 'bg-gray-500/10 dark:bg-gray-500/15', text: 'text-gray-500', border: 'border-gray-500/30' },
};

const SCOPE_LABELS = {
  assistant: { label: 'AI', color: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300' },
  manager:   { label: 'HITL', color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' },
  leads:     { label: 'LEADS', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
};

const CanvasToolNode = ({ tool, onClick, isHighlighted, onPortPointerDown, onPortPointerUp, edgeDragging, validDropPorts }) => {
  const { t } = useTranslation();
  const cat = CAT_COLORS[tool.category] || CAT_COLORS.custom;
  const isConnected = tool.connection?.status === 'connected' && tool.connection?.enabled;
  const targets = tool.connection?.target ? [tool.connection.target] : getToolTargets(tool.slug);
  const portId = `${tool.slug}:0`;
  const isValidDrop = validDropPorts?.includes(portId);

  return (
    <div
      id={`canvas-tool-${tool.slug}`}
      role="button"
      tabIndex={0}
      aria-label={`${tool.name} — ${isConnected ? t('tools.connected') : t('tools.notConnected')}`}
      className={`flow-node-enter w-[160px] bg-white dark:bg-gray-800 border rounded-[14px] p-3.5 select-none relative
        transition-all duration-200 cursor-pointer
        ${isConnected ? `${cat.border} border-opacity-100` : 'border-gray-200 dark:border-gray-700'}
        ${isHighlighted === false ? 'opacity-30' : 'opacity-100'}
        hover:shadow-md dark:hover:shadow-lg hover:border-opacity-100`}
      onClick={(e) => onClick?.(tool, e)}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick?.(tool, e); } }}
    >
      {/* Right port */}
      <div
        data-node-id={tool.slug}
        data-port-index={0}
        className={`flow-port absolute right-0 top-1/2 -translate-y-1/2 translate-x-[6px] w-3 h-3 rounded-full border-2 transition-all cursor-crosshair
          ${isConnected
            ? 'border-green-500 bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]'
            : 'border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-800'
          }
          ${edgeDragging && isValidDrop ? 'scale-150 ring-2 ring-primary-400 ring-offset-1' : ''}
          ${edgeDragging && !isValidDrop ? 'opacity-40' : ''}`}
        onPointerDown={(e) => {
          e.stopPropagation();
          onPortPointerDown?.(tool.slug, 0, e);
        }}
        onPointerUp={(e) => {
          e.stopPropagation();
          onPortPointerUp?.(tool.slug, 0, e);
        }}
      />

      <div className="flex items-center gap-2 mb-1.5">
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${cat.bg} ${cat.text}`}>
          <ToolIcon name={tool.icon} className="w-4 h-4" />
        </div>
        <div className="text-[13px] font-medium text-gray-900 dark:text-gray-100 truncate" title={tool.name}>
          {tool.name}
        </div>
      </div>

      {/* Scope chips */}
      {isConnected && targets.length > 0 && (
        <div className="flex gap-1 mb-1.5 flex-wrap">
          {targets.map(target => {
            const scope = SCOPE_LABELS[target];
            if (!scope) return null;
            return (
              <span
                key={target}
                className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold tracking-wide uppercase ${scope.color}`}
              >
                {scope.label}
              </span>
            );
          })}
        </div>
      )}

      <ToolStatusBadge status={tool.connection?.status || 'disconnected'} />
    </div>
  );
};

export default CanvasToolNode;
