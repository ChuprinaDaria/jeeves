import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { systemMessagesAPI } from '../../api/owner';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';

const SystemMessagesPage = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const refresh = () => {
    setLoading(true);
    systemMessagesAPI
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
    if (!window.confirm(`Delete message "${row.key}"?`)) return;
    try {
      await systemMessagesAPI.delete(row.id);
      refresh();
    } catch (e) {
      alert(e?.response?.data?.error || 'Delete failed');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold text-ink">System Messages</h1>
        <button
          className={buttonClass}
          onClick={() => navigate('/owner/system-messages/new')}
        >
          + Add Message
        </button>
      </div>

      {loading && <p className="text-sm text-ink/60">Loading...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && rows.length === 0 && (
        <div className="border border-dashed border-ink/20 rounded-sm p-8 text-center">
          <p className="text-ink/70">No system messages configured yet.</p>
          <Link
            to="/owner/system-messages/new"
            className="text-ink underline mt-2 inline-block"
          >
            Add your first one
          </Link>
        </div>
      )}

      {!loading && rows.length > 0 && (
        <table className="w-full text-sm border border-ink/10 rounded-sm overflow-hidden">
          <thead className="bg-ink/5 text-left">
            <tr>
              <th className="px-3 py-2">Key</th>
              <th className="px-3 py-2">Description</th>
              <th className="px-3 py-2">Languages</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-ink/10">
                <td className="px-3 py-2 font-mono font-bold">{row.key}</td>
                <td className="px-3 py-2 text-ink/70">
                  {row.description
                    ? row.description.length > 60
                      ? row.description.slice(0, 60) + '…'
                      : row.description
                    : '—'}
                </td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1">
                    {row.translations && Object.keys(row.translations).length > 0
                      ? Object.keys(row.translations).map((lang) => (
                          <span
                            key={lang}
                            className="text-xs bg-ink/10 text-ink/70 px-1.5 py-0.5 rounded-sm font-mono"
                          >
                            {lang}
                          </span>
                        ))
                      : <span className="text-ink/40 text-xs">—</span>}
                  </div>
                </td>
                <td className="px-3 py-2 text-right space-x-2">
                  <Link
                    to={`/owner/system-messages/${row.id}`}
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

export default SystemMessagesPage;
