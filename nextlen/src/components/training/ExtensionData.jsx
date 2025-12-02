import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import api from '../../api/axios';
import {
  Globe2,
  Mail,
  Phone,
  MapPin,
  Loader2,
  RefreshCcw,
  Pencil,
  Trash2,
  X,
  Check,
} from 'lucide-react';

const ExtensionData = () => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [reloading, setReloading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState({ enabled: false, sites: [] });
  const [editingSite, setEditingSite] = useState(null);
  const [draftEmails, setDraftEmails] = useState('');
  const [draftPhones, setDraftPhones] = useState('');
  const [draftAddresses, setDraftAddresses] = useState('');
  const [savingSite, setSavingSite] = useState(false);
  const [deletingSite, setDeletingSite] = useState(false);

  const loadData = async (silent = false) => {
    if (!silent) {
      setLoading(true);
    } else {
      setReloading(true);
    }
    setError('');
    try {
      const res = await api.get('/clients/extension/data/');
      setData(res.data || { enabled: false, sites: [] });
      // Якщо редагуємо, оновлюємо драфти з актуальних даних
      if (editingSite && res.data?.sites) {
        const updated = res.data.sites.find((s) => s.site === editingSite);
        if (updated) {
          setDraftEmails((updated.emails || []).join('\n'));
          setDraftPhones((updated.phones || []).join('\n'));
          setDraftAddresses((updated.addresses || []).join('\n'));
        }
      }
    } catch (err) {
      console.error('Failed to load extension data:', err);
      const status = err.response?.status;
      if (status === 401) {
        setError('Client not found or invalid token.');
      } else {
        setError(err.response?.data?.error || 'Failed to load extension data');
      }
    } finally {
      setLoading(false);
      setReloading(false);
    }
  };

  const startEdit = (site) => {
    setEditingSite(site.site);
    setDraftEmails((site.emails || []).join('\n'));
    setDraftPhones((site.phones || []).join('\n'));
    setDraftAddresses((site.addresses || []).join('\n'));
    setError('');
  };

  const cancelEdit = () => {
    setEditingSite(null);
    setDraftEmails('');
    setDraftPhones('');
    setDraftAddresses('');
  };

  const saveEdit = async (site) => {
    try {
      setSavingSite(true);
      setError('');
      const payload = {
        site: site.site,
        emails: draftEmails
          .split('\n')
          .map((v) => v.trim())
          .filter(Boolean),
        phones: draftPhones
          .split('\n')
          .map((v) => v.trim())
          .filter(Boolean),
        addresses: draftAddresses
          .split('\n')
          .map((v) => v.trim())
          .filter(Boolean),
      };
      const res = await api.patch('/clients/extension/data/', payload);
      setData(res.data || { enabled: true, sites: [] });
      setEditingSite(null);
    } catch (err) {
      console.error('Failed to save extension data edits:', err);
      setError(err.response?.data?.error || 'Failed to save changes');
    } finally {
      setSavingSite(false);
    }
  };

  const deleteSite = async (site) => {
    if (!window.confirm(`Delete all extension data for ${site.site}?`)) {
      return;
    }
    try {
      setDeletingSite(true);
      setError('');
      // axios delete with body
      await api.delete('/clients/extension/data/', { data: { site: site.site } });
      // Reload data
      await loadData(true);
      if (editingSite === site.site) {
        cancelEdit();
      }
    } catch (err) {
      console.error('Failed to delete extension site data:', err);
      setError(err.response?.data?.error || 'Failed to delete site data');
    } finally {
      setDeletingSite(false);
    }
  };

  useEffect(() => {
    loadData(false);
  }, []);

  if (loading) {
    return (
      <div className="card flex items-center justify-center py-10">
        <Loader2 className="animate-spin text-primary-500 dark:text-primary-400 mr-2" size={20} />
        <span className="text-sm text-gray-600 dark:text-gray-400">
          {t('extensionData.loading') || 'Loading extension data...'}
        </span>
      </div>
    );
  }

  if (!data.enabled) {
    return (
      <div className="card">
        <div className="flex items-start gap-3">
          <Globe2 className="text-gray-400 dark:text-gray-500 mt-0.5" size={20} />
          <div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">
              {t('extensionData.disabledTitle') || 'Chrome extension is disabled for this client'}
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {t('extensionData.disabledText') ||
                'Ask Nexelin support to enable the browser extension for your account in the admin panel.'}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Globe2 className="text-primary-600 dark:text-primary-400" size={20} />
            {t('extensionData.title') || 'Extension data by websites'}
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {t('extensionData.subtitle') ||
              'Collected emails, phones and addresses from pages scraped via Chrome extension.'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => loadData(true)}
          disabled={reloading}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-60"
        >
          <RefreshCcw
            size={14}
            className={reloading ? 'animate-spin text-primary-600 dark:text-primary-400' : ''}
          />
          {reloading ? t('common.loading') || 'Loading' : t('extensionData.refresh') || 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 text-sm text-red-700 dark:text-red-200">
          {error}
        </div>
      )}

      {(!data.sites || data.sites.length === 0) && !error && (
        <div className="card">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {t('extensionData.empty') ||
              'No extension data yet. Install the extension, set your client token and click “Scrap text / Collect mails” on your websites.'}
          </p>
        </div>
      )}

      {data.sites && data.sites.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="py-2 pr-4 text-gray-700 dark:text-gray-300">Site</th>
                <th className="py-2 pr-4 text-gray-700 dark:text-gray-300">Pages</th>
                <th className="py-2 pr-4 text-gray-700 dark:text-gray-300">
                  <span className="inline-flex items-center gap-1">
                    <Mail size={14} /> Emails
                  </span>
                </th>
                <th className="py-2 pr-4 text-gray-700 dark:text-gray-300">
                  <span className="inline-flex items-center gap-1">
                    <Phone size={14} /> Phones
                  </span>
                </th>
                <th className="py-2 pr-4 text-gray-700 dark:text-gray-300">
                  <span className="inline-flex items-center gap-1">
                    <MapPin size={14} /> Addresses
                  </span>
                </th>
                <th className="py-2 text-gray-700 dark:text-gray-300">Last updated</th>
              </tr>
            </thead>
            <tbody>
              {data.sites.map((site) => {
                const isEditing = editingSite === site.site;
                return (
                  <tr
                    key={site.site}
                    className="border-t border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/60 align-top"
                  >
                    <td className="py-2 pr-4 font-medium text-gray-900 dark:text-gray-100">
                      <div className="flex items-center justify-between gap-2">
                        <span>{site.site}</span>
                        <div className="flex items-center gap-1">
                          {!isEditing && (
                            <>
                              <button
                                type="button"
                                onClick={() => startEdit(site)}
                                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-300"
                                title="Edit"
                              >
                                <Pencil size={14} />
                              </button>
                              <button
                                type="button"
                                onClick={() => deleteSite(site)}
                                className="p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500 dark:text-red-400"
                                title="Delete all data for this site"
                              >
                                <Trash2 size={14} />
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    </td>
                  <td className="py-2 pr-4 text-gray-700 dark:text-gray-300">
                    {site.pages_count || site.urls?.length || 0}
                  </td>
                    <td className="py-2 pr-4 text-gray-700 dark:text-gray-300">
                      {site.pages_count || site.urls?.length || 0}
                    </td>
                    <td className="py-2 pr-4 align-top">
                      {isEditing ? (
                        <textarea
                          className="w-full text-xs rounded border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 p-1 resize-y min-h-[60px]"
                          value={draftEmails}
                          onChange={(e) => setDraftEmails(e.target.value)}
                          placeholder="One email per line"
                        />
                      ) : (
                        <div className="space-y-1 max-w-xs">
                          {site.emails && site.emails.length > 0 ? (
                            site.emails.map((e) => (
                              <div
                                key={e}
                                className="px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-900/30 text-xs text-blue-800 dark:text-blue-200 truncate"
                                title={e}
                              >
                                {e}
                              </div>
                            ))
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="py-2 pr-4 align-top">
                      {isEditing ? (
                        <textarea
                          className="w-full text-xs rounded border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 p-1 resize-y min-h-[60px]"
                          value={draftPhones}
                          onChange={(e) => setDraftPhones(e.target.value)}
                          placeholder="One phone per line"
                        />
                      ) : (
                        <div className="space-y-1 max-w-xs">
                          {site.phones && site.phones.length > 0 ? (
                            site.phones.map((p) => (
                              <div
                                key={p}
                                className="px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-900/30 text-xs text-emerald-800 dark:text-emerald-200 truncate"
                                title={p}
                              >
                                {p}
                              </div>
                            ))
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="py-2 pr-4 align-top">
                      {isEditing ? (
                        <textarea
                          className="w-full text-xs rounded border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 p-1 resize-y min-h-[60px]"
                          value={draftAddresses}
                          onChange={(e) => setDraftAddresses(e.target.value)}
                          placeholder="One address per line"
                        />
                      ) : (
                        <div className="space-y-1 max-w-xs">
                          {site.addresses && site.addresses.length > 0 ? (
                            site.addresses.map((a) => (
                              <div
                                key={a}
                                className="px-2 py-0.5 rounded bg-purple-50 dark:bg-purple-900/30 text-xs text-purple-800 dark:text-purple-200 truncate"
                                title={a}
                              >
                                {a}
                              </div>
                            ))
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="py-2 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap align-top">
                      <div className="flex flex-col items-end gap-1">
                        <span>
                          {site.last_seen
                            ? new Date(site.last_seen).toLocaleString()
                            : t('extensionData.never') || '—'}
                        </span>
                        {isEditing && (
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              disabled={savingSite}
                              onClick={() => saveEdit(site)}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded bg-emerald-600 text-white text-xs hover:bg-emerald-700 disabled:opacity-60"
                            >
                              <Check size={12} />
                              {savingSite ? t('common.save') || 'Save' : t('common.save') || 'Save'}
                            </button>
                            <button
                              type="button"
                              disabled={savingSite}
                              onClick={cancelEdit}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded border border-gray-300 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-60"
                            >
                              <X size={12} />
                              {t('common.cancel') || 'Cancel'}
                            </button>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default ExtensionData;


