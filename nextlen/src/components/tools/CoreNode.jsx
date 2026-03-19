import { forwardRef } from 'react';
import { Bot, UserCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const VARIANTS = {
  assistant: {
    Icon: Bot,
    label: 'tools.flow.aiAssistant',
    subtitle: 'tools.flow.centralEngine',
    tooltip: 'tools.flow.assistantTooltip',
    borderClass: 'border-primary-500/40 dark:border-primary-500/40',
    glowClass: 'shadow-[0_0_40px_rgba(99,102,241,0.08)] dark:shadow-[0_0_40px_rgba(99,102,241,0.15)]',
    iconBg: 'bg-primary-500/10 dark:bg-primary-500/20 border border-primary-500/20 dark:border-primary-500/30',
    iconColor: 'text-primary-500',
  },
  manager: {
    Icon: UserCircle,
    label: 'tools.flow.clientManager',
    subtitle: 'tools.flow.hitlEscalation',
    tooltip: 'tools.flow.managerTooltip',
    borderClass: 'border-green-500/40 dark:border-green-500/40',
    glowClass: 'shadow-[0_0_40px_rgba(34,197,94,0.08)] dark:shadow-[0_0_40px_rgba(34,197,94,0.15)]',
    iconBg: 'bg-green-500/10 dark:bg-green-500/20 border border-green-500/20 dark:border-green-500/30',
    iconColor: 'text-green-500',
  },
};

const CoreNode = forwardRef(({ variant, connectedCount = 0, style }, ref) => {
  const { t } = useTranslation();
  const v = VARIANTS[variant];
  const { Icon } = v;

  return (
    <div
      ref={ref}
      className={`flow-node-enter absolute w-[200px] bg-white dark:bg-gray-800 border-[1.5px] rounded-2xl p-5 text-center
        ${v.borderClass} ${v.glowClass}`}
      style={style}
      title={t(v.tooltip)}
    >
      <div className="absolute left-0 top-0 bottom-0 flex flex-col justify-center gap-2 -translate-x-[6px]">
        {Array.from({ length: Math.max(connectedCount, 1) }).map((_, i) => (
          <div
            key={i}
            className={`w-3 h-3 rounded-full border-2 transition-all
              ${i < connectedCount
                ? 'border-green-500 bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]'
                : 'border-gray-400 dark:border-gray-600 bg-white dark:bg-gray-800'
              }`}
          />
        ))}
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
