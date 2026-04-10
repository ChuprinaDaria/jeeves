import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { modelPairsAPI } from '../../api/owner';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 text-sm';

const ModelPairsPage = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const refresh = () => {
    setLoading(true);
    modelPairsAPI
      .list()
      .then(({ data }) => setRows(Array.isArray(data) ? data : data.results || []))
      .catch((e) => setError(e?.response?.data?.detail || 'Failed to load'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleDelete = async (row) => {
    if (!window.confirm(`Delete pair #${row.id}?`)) return;
    try {
      await modelPairsAPI.delete(row.id);
      refresh();
    } catch {
      alert('Delete failed');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold text-ink">Model Pairs</h1>
        <button
          className={buttonClass}
          onClick={() => navigate('/owner/ai-providers/pairs/new')}
        >
          + Add new pair
        </button>
      </div>
      {loading && <p className="text-sm text-ink/60">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && rows.length === 0 && (
        <div className="border border-dashed border-ink/20 rounded-sm p-8 text-center text-ink/70">
          No model pairs configured.
        </div>
      )}
      {!loading && rows.length > 0 && (
        <table className="w-full text-sm border border-ink/10 rounded-sm overflow-hidden">
          <thead className="bg-ink/5 text-left">
            <tr>
              <th className="px-3 py-2">LLM</th>
              <th className="px-3 py-2">Embedding</th>
              <th className="px-3 py-2">GUID</th>
              <th className="px-3 py-2">Active</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-ink/10">
                <td className="px-3 py-2">{row.llm_provider?.name}</td>
                <td className="px-3 py-2">{row.embedding_model?.name}</td>
                <td className="px-3 py-2 font-mono text-xs">
                  {row.external_guid}
                </td>
                <td className="px-3 py-2">{row.is_active ? 'yes' : 'no'}</td>
                <td className="px-3 py-2 text-right space-x-2">
                  <Link
                    to={`/owner/ai-providers/pairs/${row.id}`}
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

export default ModelPairsPage;
