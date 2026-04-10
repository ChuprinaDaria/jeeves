import Card from './Card';

/**
 * Dashboard metric card. One per stat — accent stripe on top,
 * icon tinted to match, mono label, big number, delta below.
 */
export default function StatCard({
  accent = 'iris',
  icon: Icon,
  label,
  value,
  delta,
  trend = 'up',
}) {
  const iconTint = {
    rose:  'text-rose',
    sage:  'text-sage',
    iris:  'text-iris',
    amber: 'text-amber',
  }[accent] || 'text-iris';

  const deltaColor = trend === 'up' ? 'text-sage' : 'text-rose';

  return (
    <Card accent={accent} hover className="animate-fade-up">
      {Icon && <Icon size={22} weight="light" className={`${iconTint} mb-2.5`} />}
      <div className="label-mono mb-1.5">{label}</div>
      <div className="text-[32px] font-bold text-ink tracking-tightest leading-none">
        {value}
      </div>
      {delta && (
        <div className={`font-mono text-[12px] mt-1.5 ${deltaColor}`}>{delta}</div>
      )}
    </Card>
  );
}
