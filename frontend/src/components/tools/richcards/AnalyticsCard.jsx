import { ChartBar } from '@phosphor-icons/react';

const AnalyticsCard = () => {
  const bars = [30, 55, 40, 70, 50, 85, 65];
  return (
    <div className="space-y-1.5 py-1">
      <div className="flex items-center gap-1.5">
        <ChartBar size={12} weight="light" className="text-iris" />
        <span className="font-mono text-[10px] text-slate uppercase tracking-wide">Activity</span>
      </div>
      <div className="flex items-end gap-[3px] h-[40px] px-1">
        {bars.map((h, i) => (
          <div
            key={i}
            className="flex-1 rounded-[2px] bg-iris/30 transition-all hover:bg-iris/60"
            style={{ height: `${h}%` }}
          />
        ))}
      </div>
    </div>
  );
};

export default AnalyticsCard;
