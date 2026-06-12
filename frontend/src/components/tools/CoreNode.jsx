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
    glow: 'shadow-[0_0_36px_rgba(155,126,216,0.30)]',
  },
  manager: {
    Icon: BellSimple,
    label: 'tools.flow.clientManager',    // "Concierge"
    subtitle: 'tools.flow.hitlEscalation',
    tooltip: 'tools.flow.managerTooltip',
    border: 'border-sage',
    iconTint: 'text-sage',
    glow: 'shadow-[0_0_36px_rgba(123,200,159,0.30)]',
  },
  leads: {
    Icon: Target,
    label: 'tools.flow.leads',
    subtitle: 'tools.flow.leadsCapture',
    tooltip: 'tools.flow.leadsTooltip',
    border: 'border-amber',
    iconTint: 'text-amber',
    glow: 'shadow-[0_0_36px_rgba(232,168,109,0.30)]',
  },
};

const CoreNode = forwardRef(
  ({ variant, ports, onPortPointerDown, onPortPointerUp, validDropPorts, edgeDragging }, ref) => {
    const { t } = useTranslation();
    const v = VARIANTS[variant];
    const { Icon } = v;
    const nodeId = `__${variant}`;

    /* One port column per side; edges attach to the side facing the tool.
       Port centers sit at 50% of the REAL node height ± i·pitch, matching
       the SVG edge endpoints computed in FlowCanvas. */
    const renderPorts = (side) => {
      const cfg = ports?.[side] || { count: 1, connected: 0, pitch: 0 };
      const count = Math.max(cfg.count, 1);
      return Array.from({ length: count }).map((_, i) => {
        const portIndex = `${side}:${i}`;
        const isValid = validDropPorts?.includes(`${nodeId}:${portIndex}`);
        const isActive = i < cfg.connected;
        const offset = (i - (count - 1) / 2) * cfg.pitch;
        return (
          <div
            key={portIndex}
            data-port-index={portIndex}
            data-node-id={nodeId}
            className={`flow-port absolute w-3 h-3 rounded-full border-[2px] transition-all cursor-crosshair
              after:content-[''] after:absolute after:-inset-2.5 after:rounded-full
              ${side === 'left' ? 'left-0 -translate-x-[6px]' : 'right-0 translate-x-[6px]'}
              ${isActive
                ? 'border-sage bg-sage shadow-[0_0_8px_rgba(123,200,159,0.8)]'
                : 'border-fog bg-paper'
              }
              ${edgeDragging && isValid ? 'scale-150 ring-2 ring-iris' : ''}
              ${edgeDragging && !isValid ? 'opacity-40' : ''}`}
            style={{ top: `calc(50% + ${offset}px - 6px)` }}
            onPointerDown={(e) => {
              e.stopPropagation();
              onPortPointerDown?.(nodeId, portIndex, e);
            }}
            onPointerUp={(e) => {
              e.stopPropagation();
              onPortPointerUp?.(nodeId, portIndex, e);
            }}
          />
        );
      });
    };

    return (
      <div
        ref={ref}
        id={`core-${variant}`}
        className={`flow-node-enter w-[200px] bg-paper rounded-xl p-5 text-center select-none relative
                    border-[2px] ${v.border} ${v.glow}`}
        title={t(v.tooltip)}
      >
        {renderPorts('left')}
        {renderPorts('right')}

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
