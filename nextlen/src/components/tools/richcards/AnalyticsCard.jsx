import { BarChart3 } from 'lucide-react';

const AnalyticsCard = () => {
  const bars = [30, 55, 40, 70, 50, 85, 65];
  return (
    <div className="space-y-1.5 py-1">
      <div className="flex items-center gap-1.5">
        <BarChart3 className="w-3 h-3 text-blue-400" />
        <span className="text-[10px] text-gray-300 font-medium">Activity</span>
      </div>
      <div className="flex items-end gap-[3px] h-[40px] px-1">
        {bars.map((h, i) => (
          <div
            key={i}
            className="flex-1 rounded-sm bg-blue-500/30 transition-all hover:bg-blue-500/60"
            style={{ height: `${h}%` }}
          />
        ))}
      </div>
    </div>
  );
};

export default AnalyticsCard;
