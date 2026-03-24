import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Loader2, Search, ExternalLink, ChevronDown, Globe, MessageCircle, Smartphone, Mail, Users } from 'lucide-react';
import api from '../api/axios';

/* ── Heat Indicator (replaces InterestStars) ── */
const HeatIndicator = ({ score }) => {
  const levels = [
    { label: 'Cold', color: 'bg-blue-400', textColor: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-900/20' },
    { label: 'Cool', color: 'bg-cyan-400', textColor: 'text-cyan-600 dark:text-cyan-400', bg: 'bg-cyan-50 dark:bg-cyan-900/20' },
    { label: 'Warm', color: 'bg-amber-400', textColor: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-900/20' },
    { label: 'Hot', color: 'bg-orange-500', textColor: 'text-orange-600 dark:text-orange-400', bg: 'bg-orange-50 dark:bg-orange-900/20' },
    { label: 'Fire', color: 'bg-red-500', textColor: 'text-red-600 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-900/20' },
  ];
  const level = levels[Math.max(0, Math.min(4, (score || 1) - 1))];

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${level.bg} ${level.textColor}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${level.color}`} />
      {level.label}
    </span>
  );
};

/* ── Status config & dropdown ── */
const STATUS_CONFIG = {
  new: { label: 'New', icon: '\u25CF', color: 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-800' },
  contacted: { label: 'Contacted', icon: '\u25D0', color: 'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-800' },
  converted: { label: 'Converted', icon: '\u2713', color: 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 border-green-200 dark:border-green-800' },
  lost: { label: 'Lost', icon: '\u2715', color: 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-200 dark:border-red-800' },
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
    <div className="relative" ref={ref}>
      <button
        onClick={() => !loading && setOpen(!open)}
        disabled={loading}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border cursor-pointer transition-all hover:shadow-sm ${config.color}`}
        aria-label={`Status: ${config.label}. Click to change.`}
      >
        {loading ? (
          <Loader2 size={10} className="animate-spin" />
        ) : (
          <span className="text-[10px]">{config.icon}</span>
        )}
        {config.label}
        <ChevronDown size={10} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute z-50 mt-1 left-0 w-36 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl py-1 animate-in">
          {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
            <button
              key={key}
              onClick={() => { onStatusChange(key); setOpen(false); }}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer ${key === status ? 'font-semibold' : ''}`}
            >
              <span className={`text-[10px] ${STATUS_CONFIG[key].color.split(' ').filter(c => c.startsWith('text-'))[0]}`}>{cfg.icon}</span>
              <span className="text-gray-700 dark:text-gray-300">{cfg.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

/* ── Source badge ── */
const SOURCE_ICONS = {
  web: Globe,
  telegram: MessageCircle,
  whatsapp: Smartphone,
  email: Mail,
};

const SOURCE_COLORS = {
  web: 'text-indigo-500',
  telegram: 'text-sky-500',
  whatsapp: 'text-green-500',
  email: 'text-red-400',
};

const SourceBadge = ({ source }) => {
  const Icon = SOURCE_ICONS[source] || Globe;
  const color = SOURCE_COLORS[source] || 'text-gray-400';
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
      <Icon size={13} className={color} />
      <span className="capitalize">{source || '\u2014'}</span>
    </span>
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

  const PER_PAGE = 25;

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

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [search, statusFilter, sourceFilter]);

  const handleStatusChange = async (leadId, newStatus) => {
    setUpdatingId(leadId);
    try {
      await api.patch(`/clients/leads/${leadId}/`, { status: newStatus });
      setLeads((prev) =>
        prev.map((lead) => (lead.id === leadId ? { ...lead, status: newStatus } : lead))
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
    return new Date(dateStr).toLocaleDateString(undefined, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          {t('leads.title')}
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          {t('leads.subtitle')}
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('leads.searchPlaceholder')}
            aria-label="Search leads"
            className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter by status"
          className="px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <option value="">{t('leads.allStatuses')}</option>
          <option value="new">{t('leads.statusNew')}</option>
          <option value="contacted">{t('leads.statusContacted')}</option>
          <option value="converted">{t('leads.statusConverted')}</option>
          <option value="lost">{t('leads.statusLost')}</option>
        </select>

        {/* Source filter */}
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          aria-label="Filter by source"
          className="px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <option value="">{t('leads.allSources')}</option>
          <option value="web">Web</option>
          <option value="telegram">Telegram</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="email">Email</option>
        </select>
      </div>

      {/* Stats bar */}
      {!loading && leads.length > 0 && (
        <div className="flex gap-4 mb-4">
          {Object.entries(
            leads.reduce((acc, l) => { acc[l.status || 'new'] = (acc[l.status || 'new'] || 0) + 1; return acc; }, {})
          ).map(([status, count]) => {
            const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.new;
            return (
              <div key={status} className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${cfg.color.split(' ').slice(0, 2).join(' ')}`}>
                <span className="text-xs font-semibold">{count}</span>
                <span className="text-xs">{cfg.label}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={28} className="animate-spin text-primary-500" />
          </div>
        ) : error ? (
          <div className="text-center py-16 text-red-500 dark:text-red-400 text-sm">{error}</div>
        ) : leads.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 px-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-600 flex items-center justify-center mb-4 shadow-lg shadow-emerald-500/20">
              <Users size={28} className="text-white" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">No leads yet</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-sm mb-4">
              Leads are automatically collected from customer conversations across all connected channels.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => navigate('/tools')}
                className="px-4 py-2 text-xs font-medium rounded-lg bg-primary-500 text-white hover:bg-primary-600 transition-colors cursor-pointer"
              >
                Connect channels
              </button>
              <button
                onClick={() => navigate('/sandbox')}
                className="px-4 py-2 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer"
              >
                Test in Sandbox
              </button>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">
                    {t('leads.name')}
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">
                    {t('leads.email')}
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">
                    {t('leads.phone')}
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">
                    {t('leads.source')}
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">
                    {t('leads.interest')}
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">
                    {t('leads.status')}
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">
                    {t('leads.date')}
                  </th>
                  <th className="px-4 py-3" aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr
                    key={lead.id}
                    className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                  >
                    {/* Name */}
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                      {lead.name || <span className="text-gray-400 dark:text-gray-500 italic">Anonymous #{lead.id}</span>}
                    </td>

                    {/* Email */}
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                      {lead.email || <span className="text-gray-300 dark:text-gray-600">{'\u2014'}</span>}
                    </td>

                    {/* Phone */}
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                      {lead.phone || <span className="text-gray-300 dark:text-gray-600">{'\u2014'}</span>}
                    </td>

                    {/* Source */}
                    <td className="px-4 py-3">
                      <SourceBadge source={lead.source} />
                    </td>

                    {/* Interest */}
                    <td className="px-4 py-3">
                      <HeatIndicator score={lead.interest_score || 0} />
                    </td>

                    {/* Status dropdown */}
                    <td className="px-4 py-3">
                      <StatusDropdown
                        status={lead.status || 'new'}
                        onStatusChange={(newStatus) => handleStatusChange(lead.id, newStatus)}
                        loading={updatingId === lead.id}
                      />
                    </td>

                    {/* Date */}
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                      {formatDate(lead.created_at)}
                    </td>

                    {/* Conversation link */}
                    <td className="px-4 py-3">
                      {lead.conversation_id ? (
                        <button
                          onClick={() => handleViewConversation(lead.conversation_id)}
                          title={t('leads.viewConversation')}
                          aria-label={t('leads.viewConversation')}
                          className="text-primary-500 hover:text-primary-700 dark:hover:text-primary-300 transition-colors cursor-pointer"
                        >
                          <ExternalLink size={16} />
                        </button>
                      ) : (
                        <span className="text-gray-300 dark:text-gray-600" title="No conversation linked">
                          <ExternalLink size={16} />
                        </span>
                      )}
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
        <div className="flex items-center justify-center gap-2 mt-6">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            aria-label="Previous page"
            className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            &larr;
          </button>
          <span className="text-sm text-gray-600 dark:text-gray-400">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            aria-label="Next page"
            className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            &rarr;
          </button>
        </div>
      )}
    </div>
  );
};

export default LeadsPage;
