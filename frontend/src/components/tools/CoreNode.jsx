import { forwardRef } from 'react';
import { BellSimple, Target } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import JeevesHat from '../ui/icons/JeevesHat';

// Each variant binds to ONE semantic accent from the Concierge palette.
const VARIANTS = {
  assistant: {
    Icon: JeevesHat,
    label: 'tools.flow.aiAssistant',      // "Jeeves"
    subtitle: 'tools.flow.centralEngine', // "Your AI butler"
    tooltip: 'tools.flow.assistantTooltip',
    border: 'border-iris',
    iconTint: 'text-iris',
    glow: 'shadow-[0_0_32px_rgba(155,126,216,0.12)]',
  },
  manager: {
    Icon: BellSimple,
    label: 'tools.flow.clientManager',    // "Concierge"
    subtitle: 'tools.flow.hitlEscalation',
    tooltip: 'tools.flow.managerTooltip',
    border: 'border-sage',
    iconTint: 'text-sage',
    glow: 'shadow-[0_0_32px_rgba(123,200,159,0.12)]',
  },
  leads: {
    Icon: Target,
    label: 'tools.flow.leads',
    subtitle: 'tools.flow.leadsCapture',
    tooltip: 'tools.flow.leadsTooltip',
    border: 'border-amber',
    iconTint: 'text-amber',
    glow: 'shadow-[0_0_32px_rgba(232,168,109,0.12)]',
  },
};

const PORT_GAP = 20;

const CoreNode = forwardRef(
  ({ variant, connectedCount = 0, onPortPointerDown, onPortPointerUp, validDropPorts, edgeDragging }, ref) => {
    const { t } = useTranslation();
    const v = VARIANTS[variant];
    const { Icon } = v;
    const portCount = Math.max(connectedCount, 1);
    const totalPortsH = (portCount - 1) * PORT_GAP;
    const nodeId = `__${variant}`;

    return (
      <div
        ref={ref}
        id={`core-${variant}`}
        className={`flow-node-enter w-[200px] bg-paper rounded-xl p-5 text-center select-none relative
                    border-[2px] ${v.border} ${v.glow}`}
        title={t(v.tooltip)}
      >
        {/* Left-side ports */}
        <div
          className="absolute left-0 top-1/2 flex flex-col items-center -translate-x-[6px]"
          style={{ marginTop: -totalPortsH / 2, gap: `${PORT_GAP - 12}px` }}
        >
          {Array.from({ length: portCount }).map((_, i) => {
            const portKey = `${nodeId}:${i}`;
            const isValid = validDropPorts?.includes(portKey);
            const isActive = i < connectedCount;
            return (
              <div
                key={i}
                data-port-index={i}
                data-node-id={nodeId}
                className={`flow-port w-3 h-3 rounded-full border-[2px] shrink-0 transition-all cursor-crosshair
                  ${isActive
                    ? 'border-sage bg-sage shadow-[0_0_6px_rgba(123,200,159,0.55)]'
                    : 'border-fog bg-paper'
                  }
                  ${edgeDragging && isValid ? 'scale-150 ring-2 ring-iris ring-offset-1 ring-offset-cream' : ''}
                  ${edgeDragging && !isValid ? 'opacity-40' : ''}`}
                onPointerDown={(e) => {
                  e.stopPropagation();
                  onPortPointerDown?.(nodeId, i, e);
                }}
                onPointerUp={(e) => {
                  e.stopPropagation();
                  onPortPointerUp?.(nodeId, i, e);
                }}
              />
            );
          })}
        </div>

        {/* Icon tile */}
        <div className={`w-12 h-12 rounded-[14px] mx-auto mb-3 flex items-center justify-center
                        border-[1.5px] ${v.border}`}>
          <Icon size={26} weight="light" className={v.iconTint} />
        </div>

        <div className="font-semibold text-[15px] text-ink mb-1 tracking-tightest">
          {t(v.label)}
        </div>
        <div className="font-mono text-[10px] uppercase tracking-wider text-fog">
          {t(v.subtitle)}
        </div>
      </div>
    );
  }
);

CoreNode.displayName = 'CoreNode';
export default CoreNode;
