import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { clientsAPI } from '../../api/owner';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';

const CHANNEL_BADGES = [
  { key: 'tg', label: 'TG' },
  { key: 'wa', label: 'WA' },
  { key: 'email', label: 'Email' },
  { key: 'web', label: 'Web' },
];

const getChannels = (row) => {
  const enabled = [];
  if (row.telegram_enabled) enabled.push('TG');
  if (row.whatsapp_meta_enabled || row.whatsapp_bridge_enabled) enabled.push('WA');
  if (row.email_smtp_enabled) enabled.push('Email');
  if (row.widget_enabled) enabled.push('Web');
  return enabled;
};

const formatDate = (iso) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
};

const ClientsPage = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const refresh = () => {
    setLoading(true);
    clientsAPI
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
    if (!window.confirm(`Delete client "${row.company_name}"?`)) return;
    try {
      await clientsAPI.delete(row.id);
      refresh();
    } catch (e) {
      alert(e?.response?.data?.error || 'Delete failed');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold text-ink">Clients</h1>
        <button
          className={buttonClass}
          onClick={() => navigate('/owner/clients/new')}
        >
          + Add Client
        </button>
      </div>

      {loading && <p className="text-sm text-ink/60">Loading...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && rows.length === 0 && (
        <div className="border border-dashed border-ink/20 rounded-sm p-8 text-center">
          <p className="text-ink/70">No clients configured yet.</p>
          <Link
            to="/owner/clients/new"
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
              <th className="px-3 py-2">Company</th>
              <th className="px-3 py-2">Tag</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Active</th>
              <th className="px-3 py-2">Channels</th>
              <th className="px-3 py-2">Created</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-ink/10">
                <td className="px-3 py-2 font-bold">{row.company_name}</td>
                <td className="px-3 py-2 font-mono text-xs">{row.tag}</td>
                <td className="px-3 py-2 text-xs">{row.client_type}</td>
                <td className="px-3 py-2">{row.is_active ? 'yes' : 'no'}</td>
                <td className="px-3 py-2">
                  <div className="flex gap-1 flex-wrap">
                    {getChannels(row).map((ch) => (
                      <span
                        key={ch}
                        className="text-xs bg-ink/10 text-ink/70 px-1.5 py-0.5 rounded-sm"
                      >
                        {ch}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-3 py-2 text-xs">{formatDate(row.created_at)}</td>
                <td className="px-3 py-2 text-right space-x-2">
                  <Link
                    to={`/owner/clients/${row.id}`}
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

export default ClientsPage;
