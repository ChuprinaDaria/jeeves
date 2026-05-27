import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Search, ExternalLink, ChevronDown, Globe, MessageCircle, Smartphone, Mail, Users, Trash2, Download, X } from 'lucide-react';
import api from '../api/axios';

/* ── Heat pill ── */
const HEAT_LEVELS = [
  { label: 'Cold', cls: 'pill-info' },
  { label: 'Cool', cls: 'pill-info' },
  { label: 'Warm', cls: 'pill-warning' },
  { label: 'Hot', cls: 'pill-alert' },
  { label: 'Fire', cls: 'pill-alert' },
];

const HeatIndicator = ({ score }) => {
  const level = HEAT_LEVELS[Math.max(0, Math.min(4, (score || 1) - 1))];
  return <span className={`pill ${level.cls}`}>{level.label}</span>;
};

/* ── Status config & dropdown ── */
const STATUS_CONFIG = {
  new:       { label: 'New',       cls: 'pill-info' },
  contacted: { label: 'Contacted', cls: 'pill-warning' },
  converted: { label: 'Converted', cls: 'pill-on' },
  lost:      { label: 'Lost',      cls: 'pill-alert' },
};

const StatusDropdown = ({ status, onStatusChange, loading }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.new;

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="relative" ref={ref} data-dropdown-open={open}>
      <button
        onClick={() => !loading && setOpen(!open)}
        disabled={loading}
        className={`pill ${config.cls} cursor-pointer inline-flex items-center gap-1`}
      >
        {config.label}
        <ChevronDown size={10} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute z-50 mt-1 left-0 w-36 bg-paper border border-rule rounded-sm shadow-ink-sm py-1">
          {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
            <button
              key={key}
              onClick={() => { onStatusChange(key); setOpen(false); }}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs text-ink hover:bg-mist cursor-pointer ${key === status ? 'font-semibold' : ''}`}
            >
              {cfg.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

/* ── Source badge ── */
const SOURCE_ICONS = { web: Globe, telegram: MessageCircle, whatsapp: Smartphone, email: Mail };
const SOURCE_COLORS = { web: 'text-iris', telegram: 'text-iris', whatsapp: 'text-sage', email: 'text-rose' };

const SourceBadge = ({ source }) => {
  const Icon = SOURCE_ICONS[source] || Globe;
  const color = SOURCE_COLORS[source] || 'text-fog';
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate">
      <Icon size={13} className={color} />
      <span className="capitalize">{source || '\u2014'}</span>
    </span>
  );
};

/* -- CSV helpers -- */
const INTEREST_LABELS = ['Cold', 'Cool', 'Warm', 'Hot', 'Fire'];

const escapeCsvField = (val) => {
  const str = String(val ?? '');
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
};

/* -- Delete confirmation dialog -- */
const DeleteConfirmDialog = ({ lead, onConfirm, onCancel, t }) => (
  <div className="fixed inset-0 z-[60] flex items-center justify-center">
    <div className="absolute inset-0 bg-ink/40" onClick={onCancel} />
    <div className="relative surface p-6 max-w-sm mx-4 shadow-ink-lg">
      <h3 className="text-lg font-semibold text-ink mb-2">
        {t('leads.deleteConfirmTitle')}
      </h3>
      <p className="text-sm text-slate mb-6">
        {t('leads.deleteConfirmMessage', { name: lead.name || `Anonymous #${lead.id}` })}
      </p>
      <div className="flex justify-end gap-3">
        <button onClick={onCancel} className="btn btn-amber text-sm cursor-pointer">
          {t('leads.deleteCancel')}
        </button>
        <button onClick={onConfirm} className="btn btn-pink text-sm cursor-pointer">
          {t('leads.deleteConfirm')}
        </button>
      </div>
    </div>
  </div>
);

/* -- Slide-in detail panel -- */
const LeadDetailPanel = ({ lead, onClose, onStatusChange, updatingId, onViewConversation, formatDate, t }) => {
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape') {
        if (document.querySelector('[data-dropdown-open="true"]')) return;
        onClose();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-ink/30" onClick={onClose} />
      <div
        className="relative w-full max-w-md bg-paper border-l border-rule shadow-ink-lg overflow-y-auto"
        style={{ animation: 'slideInRight 0.2s ease-out' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-rule">
          <h2 className="text-lg font-semibold text-ink truncate">
            {lead.name || <span className="text-fog italic">Anonymous #{lead.id}</span>}
          </h2>
          <button
            onClick={onClose}
            aria-label={t('leads.close')}
            className="p-1 rounded-sm text-fog hover:text-ink hover:bg-mist cursor-pointer"
          >
            <X size={20} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {/* Contact Info */}
          <div>
            <h3 className="label-mono-sm mb-3">{t('leads.contactInfo')}</h3>
            <div className="space-y-2">
              {[
                [t('leads.email'), lead.email],
                [t('leads.phone'), lead.phone],
              ].map(([label, val]) => (
                <div key={label} className="flex items-center justify-between text-sm">
                  <span className="text-fog">{label}</span>
                  <span className="text-ink">{val || '\u2014'}</span>
                </div>
              ))}
              <div className="flex items-center justify-between text-sm">
                <span className="text-fog">{t('leads.source')}</span>
                <SourceBadge source={lead.source} />
              </div>
            </div>
          </div>

          {/* Status & Interest */}
          <div className="flex items-center gap-6">
            <div>
              <h3 className="label-mono-sm mb-2">{t('leads.status')}</h3>
              <StatusDropdown
                status={lead.status || 'new'}
                onStatusChange={(s) => onStatusChange(lead.id, s)}
                loading={updatingId === lead.id}
              />
            </div>
            <div>
              <h3 className="label-mono-sm mb-2">{t('leads.interest')}</h3>
              <HeatIndicator score={lead.interest_score || 0} />
            </div>
          </div>

          {/* AI Summary */}
          <div>
            <h3 className="label-mono-sm mb-2">{t('leads.aiSummary')}</h3>
            {lead.request_summary ? (
              <p className="text-sm text-slate leading-relaxed bg-linen rounded-sm p-3">
                {lead.request_summary}
              </p>
            ) : (
              <p className="text-sm text-fog italic">{t('leads.noSummary')}</p>
            )}
          </div>

          {/* Date */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-fog">{t('leads.date')}</span>
            <span className="text-ink">{formatDate(lead.created_at)}</span>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-rule">
          <button
            onClick={() => lead.conversation_id && onViewConversation(lead.conversation_id)}
            disabled={!lead.conversation_id}
            className="w-full btn btn-violet flex items-center justify-center gap-2 py-2.5 cursor-pointer disabled:opacity-40"
          >
            <ExternalLink size={16} />
            {t('leads.viewConversationBtn')}
          </button>
          {!lead.conversation_id && (
            <p className="text-xs text-fog text-center mt-2">{t('leads.noConversation')}</p>
          )}
        </div>
      </div>
    </div>
  );
};

/* ── Main page ── */
const LeadsPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [updatingId, setUpdatingId] = useState(null);
  const [deletingLead, setDeletingLead] = useState(null);
  const [selectedLead, setSelectedLead] = useState(null);
  const [exporting, setExporting] = useState(false);

  const PER_PAGE = 25;

  const handleDeleteLead = async (leadId) => {
    try {
      await api.delete(`/clients/leads/${leadId}/`);
      setLeads((prev) => prev.filter((l) => l.id !== leadId));
      setSelectedLead((prev) => prev && prev.id === leadId ? null : prev);
    } catch (err) {
      console.error('Failed to delete lead:', err);
    } finally {
      setDeletingLead(null);
    }
  };

  const handleExportCsv = async () => {
    setExporting(true);
    try {
      const params = { per_page: 10000, export: 'true' };
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      if (sourceFilter) params.source = sourceFilter;

      const response = await api.get('/clients/leads/', { params });
      const allLeads = response.data.results || response.data;

      const headers = ['Name', 'Email', 'Phone', 'Source', 'Interest', 'Status', 'Date', 'AI Summary'];
      const rows = allLeads.map((lead) => [
        lead.name || '',
        lead.email || '',
        lead.phone || '',
        lead.source || '',
        INTEREST_LABELS[Math.max(0, Math.min(4, (lead.interest_score || 1) - 1))],
        lead.status || 'new',
        lead.created_at ? new Date(lead.created_at).toLocaleDateString() : '',
        lead.request_summary || '',
      ]);

      const csv = [headers, ...rows].map((row) => row.map(escapeCsvField).join(',')).join('\n');
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `leads-export-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export leads:', err);
    } finally {
      setExporting(false);
    }
  };

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { page, per_page: PER_PAGE };
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      if (sourceFilter) params.source = sourceFilter;

      const response = await api.get('/clients/leads/', { params });
      const data = response.data;
      setLeads(data.results || data);
      if (data.total !== undefined) {
        setTotalPages(Math.ceil(data.total / PER_PAGE));
      }
    } catch (err) {
      setError(err.message || t('common.error'));
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, sourceFilter, t]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);
  useEffect(() => { setPage(1); }, [search, statusFilter, sourceFilter]);

  const handleStatusChange = async (leadId, newStatus) => {
    setUpdatingId(leadId);
    try {
      await api.patch(`/clients/leads/${leadId}/`, { status: newStatus });
      setLeads((prev) =>
        prev.map((l) => (l.id === leadId ? { ...l, status: newStatus } : l))
      );
    } catch (err) {
      console.error('Failed to update lead status:', err);
    } finally {
      setUpdatingId(null);
    }
  };

  const handleViewConversation = (conversationId) => {
    navigate(`/history?conversation=${conversationId}`);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '\u2014';
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric',
    });
  };

  const inputClass = 'w-full px-3 py-2 border border-rule rounded-sm bg-cream text-ink text-sm focus:outline-none focus:border-iris';
  const selectClass = 'px-3 py-2 text-sm border border-rule rounded-sm bg-cream text-ink focus:outline-none focus:border-iris';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-ink">{t('leads.title')}</h1>
        <p className="text-sm text-fog mt-1">{t('leads.subtitle')}</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-fog" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('leads.searchPlaceholder')}
            aria-label="Search leads"
            className={`${inputClass} pl-9`}
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter by status"
          className={selectClass}
        >
          <option value="">{t('leads.allStatuses')}</option>
          <option value="new">{t('leads.statusNew')}</option>
          <option value="contacted">{t('leads.statusContacted')}</option>
          <option value="converted">{t('leads.statusConverted')}</option>
          <option value="lost">{t('leads.statusLost')}</option>
        </select>

        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          aria-label="Filter by source"
          className={selectClass}
        >
          <option value="">{t('leads.allSources')}</option>
          <option value="web">Web</option>
          <option value="telegram">Telegram</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="email">Email</option>
        </select>

        <button
          onClick={handleExportCsv}
          disabled={leads.length === 0 || exporting}
          className="btn btn-green inline-flex items-center gap-2 cursor-pointer disabled:opacity-40"
        >
          <Download size={14} />
          {exporting ? t('leads.exporting') : t('leads.export')}
        </button>
      </div>

      {/* Stats bar */}
      {!loading && leads.length > 0 && (
        <div className="flex gap-3">
          {Object.entries(
            leads.reduce((acc, l) => { acc[l.status || 'new'] = (acc[l.status || 'new'] || 0) + 1; return acc; }, {})
          ).map(([status, count]) => {
            const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.new;
            return (
              <span key={status} className={`pill ${cfg.cls}`}>
                {count} {cfg.label}
              </span>
            );
          })}
        </div>
      )}

      {/* Table */}
      <div className="surface overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <span className="text-sm text-fog">Loading...</span>
          </div>
        ) : error ? (
          <div className="text-center py-16 text-rose text-sm">{error}</div>
        ) : leads.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-6">
            <Users size={28} className="text-fog mb-3" />
            <h3 className="text-base font-semibold text-ink mb-1">No leads yet</h3>
            <p className="text-sm text-slate text-center max-w-sm mb-4">
              Leads are automatically collected from customer conversations across all connected channels.
            </p>
            <div className="flex gap-2">
              <button onClick={() => navigate('/tools')} className="btn btn-violet cursor-pointer">
                Connect channels
              </button>
              <button onClick={() => navigate('/sandbox')} className="btn btn-amber cursor-pointer">
                Test in Sandbox
              </button>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-rule bg-linen">
                  <th className="text-left px-3 py-2 label-mono-sm">{t('leads.name')}</th>
                  <th className="text-left px-3 py-2 label-mono-sm">{t('leads.email')}</th>
                  <th className="text-left px-3 py-2 label-mono-sm">{t('leads.phone')}</th>
                  <th className="text-left px-3 py-2 label-mono-sm">{t('leads.source')}</th>
                  <th className="text-left px-3 py-2 label-mono-sm">{t('leads.interest')}</th>
                  <th className="text-left px-3 py-2 label-mono-sm">{t('leads.status')}</th>
                  <th className="text-left px-3 py-2 label-mono-sm">{t('leads.date')}</th>
                  <th className="px-3 py-2" aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr
                    key={lead.id}
                    onClick={() => setSelectedLead(lead)}
                    className="border-t border-rule hover:bg-mist cursor-pointer transition-colors"
                  >
                    <td className="px-3 py-2 font-medium text-ink">
                      {lead.name || <span className="text-fog italic">Anonymous #{lead.id}</span>}
                    </td>
                    <td className="px-3 py-2 text-slate">{lead.email || '\u2014'}</td>
                    <td className="px-3 py-2 text-slate">{lead.phone || '\u2014'}</td>
                    <td className="px-3 py-2"><SourceBadge source={lead.source} /></td>
                    <td className="px-3 py-2"><HeatIndicator score={lead.interest_score || 0} /></td>
                    <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                      <StatusDropdown
                        status={lead.status || 'new'}
                        onStatusChange={(s) => handleStatusChange(lead.id, s)}
                        loading={updatingId === lead.id}
                      />
                    </td>
                    <td className="px-3 py-2 text-fog whitespace-nowrap">{formatDate(lead.created_at)}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        {lead.conversation_id ? (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleViewConversation(lead.conversation_id); }}
                            title={t('leads.viewConversation')}
                            className="text-iris hover:text-ink cursor-pointer"
                          >
                            <ExternalLink size={15} />
                          </button>
                        ) : (
                          <span className="text-rule"><ExternalLink size={15} /></span>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); setDeletingLead(lead); }}
                          title="Delete lead"
                          className="text-fog hover:text-rose cursor-pointer"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn btn-amber disabled:opacity-40 cursor-pointer"
          >
            &larr;
          </button>
          <span className="text-sm text-slate">{page} / {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="btn btn-amber disabled:opacity-40 cursor-pointer"
          >
            &rarr;
          </button>
        </div>
      )}

      {deletingLead && (
        <DeleteConfirmDialog
          lead={deletingLead}
          onConfirm={() => handleDeleteLead(deletingLead.id)}
          onCancel={() => setDeletingLead(null)}
          t={t}
        />
      )}
      {selectedLead && (
        <LeadDetailPanel
          lead={selectedLead}
          onClose={() => setSelectedLead(null)}
          onStatusChange={(id, s) => {
            handleStatusChange(id, s);
            setSelectedLead((prev) => prev && prev.id === id ? { ...prev, status: s } : prev);
          }}
          updatingId={updatingId}
          onViewConversation={handleViewConversation}
          formatDate={formatDate}
          t={t}
        />
      )}
    </div>
  );
};

export default LeadsPage;
