import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Unplug } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const ToolPopover = ({ tool, anchorRect, onDisconnect, onClose }) => {
  const { t } = useTranslation();
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  if (!anchorRect) return null;

  const top = anchorRect.bottom + 8;
  const left = anchorRect.left + anchorRect.width / 2;
  const flipAbove = top + 120 > window.innerHeight;

  const style = {
    position: 'fixed',
    left: `${left}px`,
    transform: 'translateX(-50%)',
    ...(flipAbove
      ? { bottom: `${window.innerHeight - anchorRect.top + 8}px` }
      : { top: `${top}px` }),
    zIndex: 60,
  };

  return createPortal(
    <div ref={ref} style={style}
      className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-xl p-3 w-48"
    >
      <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2 truncate">
        {tool.name}
      </div>
      <div className="text-xs text-green-600 dark:text-green-400 mb-3 flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
        {t('tools.connected')}
      </div>
      {tool.connections?.filter(c => c.status === 'connected' && c.enabled).length > 0 ? (
        <div className="space-y-1">
          {tool.connections.filter(c => c.status === 'connected' && c.enabled).map(conn => (
            <div key={conn.id} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700/50">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-700 dark:text-gray-300 capitalize">{conn.target}</span>
                {conn.scope?.description && (
                  <span className="text-xs text-gray-400 dark:text-gray-500">{conn.scope.description}</span>
                )}
              </div>
              <button
                onClick={() => onDisconnect(tool.slug, conn.target)}
                className="text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 font-medium"
              >
                {t('tools.flow.disconnect') || 'Disconnect'}
              </button>
            </div>
          ))}
        </div>
      ) : (
        <button
          onClick={() => {
            if (window.confirm(t('tools.confirmDisconnect'))) {
              onDisconnect(tool.slug);
              onClose();
            }
          }}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
        >
          <Unplug className="w-4 h-4" />
          {t('tools.disconnect')}
        </button>
      )}
    </div>,
    document.body
  );
};

export default ToolPopover;
