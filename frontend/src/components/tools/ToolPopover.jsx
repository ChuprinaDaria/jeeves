import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Plugs } from '@phosphor-icons/react';
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
    <div
      ref={ref}
      style={style}
      className="bg-paper border-[1.5px] border-rule rounded-lg shadow-ink-lg p-3 w-52"
    >
      <div className="text-sm font-semibold text-ink mb-2 truncate">
        {tool.name}
      </div>
      <div className="label-mono flex items-center gap-1.5 text-sage mb-3">
        <span className="w-1.5 h-1.5 rounded-full bg-sage" />
        {t('tools.connected')}
      </div>
      {tool.connections?.filter(c => c.status === 'connected' && c.enabled).length > 0 ? (
        <div className="space-y-1">
          {tool.connections.filter(c => c.status === 'connected' && c.enabled).map(conn => (
            <div
              key={conn.id}
              className="flex items-center justify-between py-1.5 px-2 rounded-sm hover:bg-mist transition-colors"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-xs font-medium text-ink capitalize truncate">{conn.target}</span>
                {conn.scope?.description && (
                  <span className="text-[11px] text-fog truncate">{conn.scope.description}</span>
                )}
              </div>
              {!tool.is_system && (
                <button
                  onClick={() => onDisconnect(tool.slug, conn.target)}
                  className="font-mono text-[11px] uppercase tracking-wider text-rose hover:text-rose/80 shrink-0 cursor-pointer"
                >
                  {t('tools.flow.disconnect') || 'Disconnect'}
                </button>
              )}
            </div>
          ))}
        </div>
      ) : !tool.is_system ? (
        <button
          onClick={() => {
            if (window.confirm(t('tools.confirmDisconnect'))) {
              onDisconnect(tool.slug);
              onClose();
            }
          }}
          className="btn btn-pink w-full justify-center"
        >
          <Plugs weight="light" size={14} />
          {t('tools.disconnect')}
        </button>
      ) : null}
    </div>,
    document.body
  );
};

export default ToolPopover;
