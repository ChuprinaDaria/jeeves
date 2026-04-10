const UsageBadge = ({ usage }) => {
  if (!usage) return <span className="text-ink/40">—</span>;
  const parts = Object.entries(usage)
    .filter(([, v]) => Number(v) > 0)
    .map(([k, v]) => `${v} ${k}`);
  if (parts.length === 0) return <span className="text-ink/40">unused</span>;
  return (
    <span className="text-xs text-ink/70 font-mono">{parts.join(' · ')}</span>
  );
};

export default UsageBadge;
