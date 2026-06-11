import { useTranslation } from 'react-i18next';
import { Lock } from '@phosphor-icons/react';
import ToolStatusBadge from './ToolStatusBadge';
import ToolIcon from './ToolIcon';
import { getToolTargets } from './toolTargets';
import RichCardWrapper, { hasRichCard } from './richcards/RichCardWrapper';

// Map tool categories to Concierge accent colors.
// Only the accent colour varies — the card surface is always paper-cream.
const CAT_ACCENTS = {
  communication: { border: 'border-sage',  iconTint: 'text-sage'  },
  ai:            { border: 'border-iris',  iconTint: 'text-iris'  },
  productivity:  { border: 'border-amber', iconTint: 'text-amber' },
  analytics:     { border: 'border-iris',  iconTint: 'text-iris'  },
  crm:           { border: 'border-rose',  iconTint: 'text-rose'  },
  custom:        { border: 'border-rule',  iconTint: 'text-slate' },
};

const SCOPE_LABELS = {
  assistant: { label: 'AI',    tooltip: 'tools.flow.scopeAssistant', border: 'border-iris',  text: 'text-iris'  },
  manager:   { label: 'HITL',  tooltip: 'tools.flow.scopeManager',   border: 'border-sage',  text: 'text-sage'  },
  leads:     { label: 'LEADS', tooltip: 'tools.flow.scopeLeads',     border: 'border-amber', text: 'text-amber' },
};

const CanvasToolNode = ({
  tool,
  onClick,
  isHighlighted,
  onPortPointerDown,
  onPortPointerUp,
  edgeDragging,
  validDropPorts,
}) => {
  const { t } = useTranslation();
  const cat = CAT_ACCENTS[tool.category] || CAT_ACCENTS.custom;
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
      className={`flow-node-enter ${hasRichCard(tool.slug) ? 'w-[220px]' : 'w-[160px]'}
                  bg-paper rounded-[14px] p-3.5 select-none relative
                  transition-all duration-200 cursor-pointer border-[1.5px]
                  ${isConnected ? cat.border : 'border-rule'}
                  ${isHighlighted === false ? 'opacity-30' : 'opacity-100'}
                  hover:shadow-ink-sm hover:-translate-y-0.5`}
      onClick={(e) => onClick?.(tool, e)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick?.(tool, e);
        }
      }}
    >
      {/* Right-side output port */}
      <div
        data-node-id={tool.slug}
        data-port-index={0}
        className={`flow-port absolute right-0 top-1/2 -translate-y-1/2 translate-x-[6px]
                    w-3 h-3 rounded-full border-[2px] transition-all cursor-crosshair
                    after:content-[''] after:absolute after:-inset-2.5 after:rounded-full
                    ${isConnected
                      ? 'border-sage bg-sage shadow-[0_0_8px_rgba(123,200,159,0.8)]'
                      : 'border-fog bg-paper'
                    }
                    ${edgeDragging && isValidDrop ? 'scale-150 ring-2 ring-iris' : ''}
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

      {/* Header: icon tile + name */}
      <div className="flex items-center gap-2 mb-1.5">
        <div className={`w-7 h-7 rounded-md flex items-center justify-center shrink-0
                        border-[1.5px] ${cat.border} ${cat.iconTint}`}>
          <ToolIcon name={tool.icon} size={14} />
        </div>
        <div className="text-[13px] font-medium text-ink truncate" title={tool.name}>
          {tool.name}
        </div>
      </div>

      {/* Tagline */}
      {tool.tagline && (
        <p className="font-mono text-[9px] text-fog leading-snug mb-1.5 line-clamp-2 uppercase tracking-wide">
          {tool.tagline}
        </p>
      )}

      {hasRichCard(tool.slug) && <RichCardWrapper slug={tool.slug} />}

      {/* Scope chips */}
      {isConnected && targets.length > 0 && (
        <div className="flex gap-1 mb-1.5 flex-wrap">
          {targets.map((target) => {
            const scope = SCOPE_LABELS[target];
            if (!scope) return null;
            return (
              <span
                key={target}
                title={t(scope.tooltip)}
                className={`inline-flex items-center px-1.5 py-0.5 rounded-[4px]
                            border-[1.5px] font-mono text-[9px] font-semibold tracking-wide uppercase
                            ${scope.border} ${scope.text}`}
              >
                {scope.label}
              </span>
            );
          })}
        </div>
      )}

      {tool.is_system ? (
        <div className="flex items-center gap-1 font-mono text-[10px] text-fog uppercase tracking-wider">
          <Lock size={10} weight="light" />
          <span>System</span>
        </div>
      ) : (
        <ToolStatusBadge status={tool.connection?.status || 'disconnected'} />
      )}
    </div>
  );
};

export default CanvasToolNode;
