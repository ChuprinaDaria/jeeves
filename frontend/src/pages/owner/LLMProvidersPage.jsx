import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { llmProvidersAPI } from '../../api/owner';
import UsageBadge from '../../components/owner/forms/UsageBadge';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';

const LLMProvidersPage = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const refresh = () => {
    setLoading(true);
    llmProvidersAPI
      .list()
      .then(({ data }) => {
        setRows(Array.isArray(data) ? data : data.results || []);
        setError('');
      })
      .catch((e) => setError(e?.response?.data?.detail || 'Failed to load'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleDelete = async (row) => {
    if (!window.confirm(`Delete "${row.name}"?`)) return;
    try {
      await llmProvidersAPI.delete(row.id);
      refresh();
    } catch (e) {
      const body = e?.response?.data || {};
      if (body.error === 'has_protected_references') {
        alert(
          `Cannot delete — ${body.count} references. Deactivate instead?`,
        );
      } else {
        alert('Delete failed');
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold text-ink">LLM Providers</h1>
        <button
          className={buttonClass}
          onClick={() => navigate('/owner/ai-providers/llm/new')}
        >
          + Add new LLM
        </button>
      </div>

      {loading && <p className="text-sm text-ink/60">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && rows.length === 0 && (
        <div className="border border-dashed border-ink/20 rounded-sm p-8 text-center">
          <p className="text-ink/70">No LLM providers configured yet.</p>
          <Link
            to="/owner/ai-providers/llm/new"
            className="text-ink underline mt-2 inline-block"
          >
            Add your first one →
          </Link>
        </div>
      )}

      {!loading && rows.length > 0 && (
        <table className="w-full text-sm border border-ink/10 rounded-sm overflow-hidden">
          <thead className="bg-ink/5 text-left">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Model</th>
              <th className="px-3 py-2">Default</th>
              <th className="px-3 py-2">Active</th>
              <th className="px-3 py-2">Key</th>
              <th className="px-3 py-2">Usage</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-ink/10">
                <td className="px-3 py-2 font-medium">{row.name}</td>
                <td className="px-3 py-2 font-mono text-xs">{row.model_name}</td>
                <td className="px-3 py-2">
                  {row.is_default ? (
                    <span className="text-xs bg-ink text-cream px-2 py-0.5 rounded-sm">
                      default
                    </span>
                  ) : (
                    <span className="text-ink/40">—</span>
                  )}
                </td>
                <td className="px-3 py-2">{row.is_active ? 'yes' : 'no'}</td>
                <td className="px-3 py-2 font-mono text-xs">
                  {row.api_key_masked || (row.api_key_set ? 'set' : '—')}
                </td>
                <td className="px-3 py-2">
                  <UsageBadge usage={row.usage} />
                </td>
                <td className="px-3 py-2 text-right space-x-2">
                  <Link
                    to={`/owner/ai-providers/llm/${row.id}`}
                    className="text-ink underline text-xs"
                  >
                    Edit
                  </Link>
                  <button
                    onClick={() => handleDelete(row)}
                    className="text-red-600 text-xs"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default LLMProvidersPage;
