import { forwardRef } from 'react';
import { Bot, UserCircle, Target } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const VARIANTS = {
  assistant: {
    Icon: Bot,
    label: 'tools.flow.aiAssistant',
    subtitle: 'tools.flow.centralEngine',
    tooltip: 'tools.flow.assistantTooltip',
    borderClass: 'border-[#6c5ce7]/40',
    glowClass: 'shadow-[0_0_40px_rgba(108,92,231,0.08)] dark:shadow-[0_0_40px_rgba(108,92,231,0.15)]',
    iconBg: 'bg-[#6c5ce7]/10 dark:bg-[#6c5ce7]/20 border border-[#6c5ce7]/20 dark:border-[#6c5ce7]/30',
    iconColor: 'text-[#6c5ce7]',
  },
  manager: {
    Icon: UserCircle,
    label: 'tools.flow.clientManager',
    subtitle: 'tools.flow.hitlEscalation',
    tooltip: 'tools.flow.managerTooltip',
    borderClass: 'border-[#00a67e]/40',
    glowClass: 'shadow-[0_0_40px_rgba(0,166,126,0.08)] dark:shadow-[0_0_40px_rgba(0,166,126,0.15)]',
    iconBg: 'bg-[#00a67e]/10 dark:bg-[#00a67e]/20 border border-[#00a67e]/20 dark:border-[#00a67e]/30',
    iconColor: 'text-[#00a67e]',
  },
  leads: {
    Icon: Target,
    label: 'tools.flow.leads',
    subtitle: 'tools.flow.leadsCapture',
    tooltip: 'tools.flow.leadsTooltip',
    borderClass: 'border-[#f59e0b]/40',
    glowClass: 'shadow-[0_0_40px_rgba(245,158,11,0.08)] dark:shadow-[0_0_40px_rgba(245,158,11,0.15)]',
    iconBg: 'bg-[#f59e0b]/10 dark:bg-[#f59e0b]/20 border border-[#f59e0b]/20 dark:border-[#f59e0b]/30',
    iconColor: 'text-[#f59e0b]',
  },
};

const PORT_GAP = 20;

const CoreNode = forwardRef(({ variant, connectedCount = 0, onPortPointerDown, onPortPointerUp, validDropPorts, edgeDragging }, ref) => {
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
      className={`flow-node-enter w-[200px] bg-white dark:bg-gray-800 border-[1.5px] rounded-2xl p-5 text-center select-none relative
        ${v.borderClass} ${v.glowClass}`}
      title={t(v.tooltip)}
    >
      {/* Left-side ports — vertically distributed */}
      <div
        className="absolute left-0 top-1/2 flex flex-col items-center -translate-x-[6px]"
        style={{ marginTop: -totalPortsH / 2, gap: `${PORT_GAP - 12}px` }}
      >
        {Array.from({ length: portCount }).map((_, i) => {
          const isValid = validDropPorts?.includes(`${nodeId}:${i}`);
          const isActive = i < connectedCount;
          return (
            <div
              key={i}
              data-port-index={i}
              data-node-id={nodeId}
              className={`flow-port w-3 h-3 rounded-full border-2 shrink-0 transition-all cursor-crosshair
                ${isActive
                  ? 'border-green-500 bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]'
                  : 'border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-800'
                }
                ${edgeDragging && isValid ? 'scale-150 ring-2 ring-primary-400 ring-offset-1' : ''}
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

      <div className={`w-12 h-12 rounded-[14px] mx-auto mb-3 flex items-center justify-center ${v.iconBg}`}>
        <Icon className={`w-6 h-6 ${v.iconColor}`} />
      </div>
      <div className="font-semibold text-[15px] text-gray-900 dark:text-gray-100 mb-1">
        {t(v.label)}
      </div>
      <div className="text-[11px] text-gray-500 dark:text-gray-400">
        {t(v.subtitle)}
      </div>
    </div>
  );
});

CoreNode.displayName = 'CoreNode';
export default CoreNode;
