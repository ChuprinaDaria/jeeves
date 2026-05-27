import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { ownerAPI } from '../../api/owner';
import { useAuth } from '../../context/AuthContext';

const CounterCard = ({ label, value }) => (
  <div className="bg-paper border border-ink/10 rounded-sm p-4">
    <div className="label-mono text-ink/60 text-xs uppercase">{label}</div>
    <div className="text-3xl font-semibold text-ink mt-1">{value}</div>
  </div>
);

const HealthItem = ({ ok, label, href }) => (
  <li className="flex items-center gap-2 text-sm py-1">
    <span className={ok ? 'text-green-700' : 'text-red-600'}>
      {ok ? '\u2713' : '\u2717'}
    </span>
    {href ? (
      <Link to={href} className="underline">{label}</Link>
    ) : (
      <span>{label}</span>
    )}
  </li>
);

const OwnerDashboardPage = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    ownerAPI.getDashboardStats()
      .then(({ data }) => setStats(data))
      .catch(() => setError('Could not load dashboard.'));
  }, []);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!stats) return <p className="label-mono">Loading\u2026</p>;

  const c = stats.counters;
  const h = stats.config_health;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold text-ink">
        Welcome, {user?.first_name || 'Owner'}
      </h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <CounterCard label="Branches" value={c.branches} />
        <CounterCard label="Specializations" value={c.specializations} />
        <CounterCard label="Clients" value={c.clients} />
        <CounterCard label="Documents" value={c.documents} />
      </div>

      <div className="bg-paper border border-ink/10 rounded-sm p-4 max-w-lg">
        <h2 className="text-lg font-medium text-ink mb-2">
          Required configuration
        </h2>
        <ul>
          <HealthItem
            ok={h.llm_providers_configured}
            label="LLM provider configured"
            href="/owner/ai-providers"
          />
          <HealthItem
            ok={h.embedding_models_configured}
            label="Embedding model configured"
            href="/owner/ai-providers"
          />
          <HealthItem
            ok={h.branches_exist}
            label="First branch created"
            href="/owner/branches"
          />
        </ul>
      </div>
    </div>
  );
};

export default OwnerDashboardPage;
