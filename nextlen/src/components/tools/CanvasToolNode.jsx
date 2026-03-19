import { forwardRef } from 'react';
import { useTranslation } from 'react-i18next';
import ToolStatusBadge from './ToolStatusBadge';

const CAT_COLORS = {
  communication: { bg: 'bg-green-500/10 dark:bg-green-500/15', text: 'text-green-500', border: 'border-green-500/30' },
  ai:            { bg: 'bg-primary-500/10 dark:bg-primary-500/15', text: 'text-primary-500', border: 'border-primary-500/30' },
  productivity:  { bg: 'bg-orange-500/10 dark:bg-orange-500/15', text: 'text-orange-500', border: 'border-orange-500/30' },
  analytics:     { bg: 'bg-blue-500/10 dark:bg-blue-500/15', text: 'text-blue-500', border: 'border-blue-500/30' },
  crm:           { bg: 'bg-pink-500/10 dark:bg-pink-500/15', text: 'text-pink-500', border: 'border-pink-500/30' },
  custom:        { bg: 'bg-gray-500/10 dark:bg-gray-500/15', text: 'text-gray-500', border: 'border-gray-500/30' },
};

const CanvasToolNode = forwardRef(({ tool, onClick, isHighlighted, style }, ref) => {
  const { t } = useTranslation();
  const cat = CAT_COLORS[tool.category] || CAT_COLORS.custom;
  const isConnected = tool.connection?.status === 'connected' && tool.connection?.enabled;

  return (
    <div
      ref={ref}
      id={`canvas-tool-${tool.slug}`}
      className={`flow-node-enter absolute w-[160px] bg-white dark:bg-gray-800 border rounded-[14px] p-3.5 cursor-pointer
        transition-all duration-300
        ${isConnected ? `${cat.border} border-opacity-100` : 'border-gray-200 dark:border-gray-700'}
        ${isHighlighted === false ? 'opacity-30' : 'opacity-100'}
        hover:shadow-md dark:hover:shadow-lg`}
      style={style}
      onClick={(e) => onClick?.(tool, e)}
    >
      <div
        className={`absolute right-0 top-1/2 -translate-y-1/2 translate-x-[6px] w-3 h-3 rounded-full border-2 transition-all
          ${isConnected
            ? 'border-green-500 bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]'
            : 'border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-800'
          }`}
      />

      <div className="flex items-center gap-2 mb-1.5">
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm shrink-0 ${cat.bg} ${cat.text}`}>
          {tool.icon || '🔧'}
        </div>
        <div className="text-[13px] font-medium text-gray-900 dark:text-gray-100 truncate">
          {tool.name}
        </div>
      </div>

      <ToolStatusBadge status={tool.connection?.status || 'disconnected'} />
    </div>
  );
});

CanvasToolNode.displayName = 'CanvasToolNode';
export default CanvasToolNode;
