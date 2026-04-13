import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { branchesAPI } from '../../api/owner';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';

const BranchesPage = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const refresh = () => {
    setLoading(true);
    branchesAPI
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
      await branchesAPI.delete(row.id);
      refresh();
    } catch (e) {
      alert(e?.response?.data?.error || 'Delete failed');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold text-ink">Branches</h1>
        <button
          className={buttonClass}
          onClick={() => navigate('/owner/branches/new')}
        >
          + Add Branch
        </button>
      </div>

      {loading && <p className="text-sm text-ink/60">Loading...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && rows.length === 0 && (
        <div className="border border-dashed border-ink/20 rounded-sm p-8 text-center">
          <p className="text-ink/70">No branches configured yet.</p>
          <Link
            to="/owner/branches/new"
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
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Slug</th>
              <th className="px-3 py-2">Embedding Model</th>
              <th className="px-3 py-2">Documents</th>
              <th className="px-3 py-2">Clients</th>
              <th className="px-3 py-2">Active</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-ink/10">
                <td className="px-3 py-2 font-medium">{row.name}</td>
                <td className="px-3 py-2 font-mono text-xs">{row.slug}</td>
                <td className="px-3 py-2 text-xs">
                  {row.embedding_model?.name || '—'}
                </td>
                <td className="px-3 py-2">{row.documents_count ?? 0}</td>
                <td className="px-3 py-2">{row.clients_count ?? 0}</td>
                <td className="px-3 py-2">{row.is_active ? 'yes' : 'no'}</td>
                <td className="px-3 py-2 text-right space-x-2">
                  <Link
                    to={`/owner/branches/${row.id}`}
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

export default BranchesPage;
