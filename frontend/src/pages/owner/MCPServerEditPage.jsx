import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { mcpServersAPI } from '../../api/owner';

const CATEGORIES = [
  { value: 'communication', label: 'Communication' },
  { value: 'productivity', label: 'Productivity' },
  { value: 'analytics', label: 'Analytics' },
  { value: 'ai', label: 'AI & Knowledge' },
  { value: 'crm', label: 'CRM & Sales' },
  { value: 'custom', label: 'Custom' },
];

const TARGETS = [
  { value: 'assistant', label: 'AI Assistant' },
  { value: 'manager', label: 'Client Manager' },
  { value: 'leads', label: 'Leads' },
];

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';
const secondaryClass =
  'px-4 py-2 border border-ink/20 rounded-sm hover:bg-ink/5 disabled:opacity-50 text-sm';
const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-cream text-ink text-sm';

const Field = ({ label, children, error }) => (
  <label className="block space-y-1">
    <span className="text-xs label-mono text-ink/60">{label}</span>
    {children}
    {error && <p className="text-xs text-red-600">{String(error)}</p>}
  </label>
);

const MCPServerEditPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = id && id !== 'new';

  // Discovery state (new server flow)
  const [url, setUrl] = useState('');
  const [discovering, setDiscovering] = useState(false);
  const [discovered, setDiscovered] = useState(null); // {server_name, tools}
  const [discoverError, setDiscoverError] = useState('');

  // Form state
  const [form, setForm] = useState({
    name: '',
    icon: 'puzzle',
    color: '#6366f1',
    category: 'custom',
    targets: ['assistant'],
  });
  const [existing, setExisting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!isEdit) return;
    mcpServersAPI.detail(id).then(({ data }) => {
      setExisting(data);
      setForm({
        name: data.name || '',
        icon: data.icon || 'puzzle',
        color: data.color || '#6366f1',
        category: data.category || 'custom',
        targets: data.skill_scopes?.scopes || ['assistant'],
      });
      setDiscovered({ server_name: data.name, tools: data.tools_schema || [] });
    });
  }, [id, isEdit]);

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  const toggleTarget = (target) => {
    setForm((f) => {
      const targets = f.targets.includes(target)
        ? f.targets.filter((t) => t !== target)
        : [...f.targets, target];
      return { ...f, targets: targets.length ? targets : f.targets };
    });
  };

  const handleDiscover = async () => {
    setDiscovering(true);
    setDiscoverError('');
    setDiscovered(null);
    try {
      const { data } = await mcpServersAPI.discover(url);
      setDiscovered(data);
      if (data.server_name && !form.name) {
        set('name', data.server_name);
      }
    } catch (e) {
      setDiscoverError(e?.response?.data?.error || 'Discovery failed');
    } finally {
      setDiscovering(false);
    }
  };

  const handleSave = async () => {
    setBusy(true);
    setErrors({});
    try {
      if (isEdit) {
        await mcpServersAPI.update(id, {
          name: form.name,
          icon: form.icon,
          color: form.color,
          category: form.category,
          skill_scopes: { scopes: form.targets },
        });
      } else {
        await mcpServersAPI.createFromUrl({
          url,
          name: form.name,
          icon: form.icon,
          color: form.color,
          category: form.category,
          targets: form.targets,
        });
      }
      navigate('/owner/mcp-servers');
    } catch (e) {
      setErrors(e?.response?.data || { detail: 'Save failed' });
    } finally {
      setBusy(false);
    }
  };

  const handleRefresh = async () => {
    setBusy(true);
    try {
      const { data } = await mcpServersAPI.refresh(id);
      setDiscovered({ server_name: data.name, tools: data.tools_schema || [] });
      setExisting(data);
    } catch (e) {
      alert(e?.response?.data?.error || 'Refresh failed');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete "${form.name}"?`)) return;
    try {
      await mcpServersAPI.delete(id);
      navigate('/owner/mcp-servers');
    } catch (e) {
      alert(e?.response?.data?.error || 'Delete failed');
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-semibold text-ink">
        {isEdit ? `Edit ${existing?.name || ''}` : 'New MCP Server'}
      </h1>

      {/* Discovery section — only for new */}
      {!isEdit && (
        <div className="space-y-3 p-4 border border-ink/10 rounded-sm">
          <Field label="MCP Server URL">
            <div className="flex gap-2">
              <input
                className={inputClass}
                placeholder="https://mcp-server.example.com/sse"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
              <button
                className={secondaryClass}
                onClick={handleDiscover}
                disabled={discovering || !url}
              >
                {discovering ? 'Discovering...' : 'Discover'}
              </button>
            </div>
          </Field>
          {discoverError && (
            <p className="text-sm text-red-600">{discoverError}</p>
          )}
        </div>
      )}

      {/* Discovered tools preview */}
      {discovered && (
        <div className="space-y-3">
          <div className="p-4 border border-ink/10 rounded-sm bg-ink/[0.02]">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-ink">
                Available Tools ({discovered.tools.length})
              </h3>
              {isEdit && !existing?.is_builtin && (
                <button
                  className={secondaryClass}
                  onClick={handleRefresh}
                  disabled={busy}
                >
                  Refresh Tools
                </button>
              )}
            </div>
            <div className="space-y-1">
              {discovered.tools.map((tool, i) => (
                <div key={i} className="text-sm py-1 border-b border-ink/5 last:border-0">
                  <span className="font-mono text-xs text-ink/80">{tool.name}</span>
                  {tool.description && (
                    <span className="ml-2 text-ink/50">{tool.description}</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Metadata form */}
          <div className="grid grid-cols-2 gap-4">
            <Field label="Name" error={errors.name}>
              <input
                className={inputClass}
                value={form.name}
                onChange={(e) => set('name', e.target.value)}
                disabled={isEdit && existing?.is_builtin}
              />
            </Field>
            <Field label="Category">
              <select
                className={inputClass}
                value={form.category}
                onChange={(e) => set('category', e.target.value)}
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Icon (name)">
              <input
                className={inputClass}
                value={form.icon}
                onChange={(e) => set('icon', e.target.value)}
              />
            </Field>
            <Field label="Color">
              <div className="flex gap-2 items-center">
                <input
                  type="color"
                  value={form.color}
                  onChange={(e) => set('color', e.target.value)}
                  className="w-10 h-10 border border-ink/20 rounded-sm cursor-pointer"
                />
                <input
                  className={inputClass}
                  value={form.color}
                  onChange={(e) => set('color', e.target.value)}
                  maxLength={7}
                />
              </div>
            </Field>
          </div>

          {/* Target checkboxes */}
          <div className="space-y-2">
            <span className="text-xs label-mono text-ink/60">Connect to targets</span>
            <div className="flex gap-4">
              {TARGETS.map((t) => (
                <label key={t.value} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.targets.includes(t.value)}
                    onChange={() => toggleTarget(t.value)}
                    disabled={isEdit && existing?.is_builtin}
                  />
                  {t.label}
                </label>
              ))}
            </div>
          </div>

          {/* Errors */}
          {errors.detail && (
            <p className="text-sm text-red-600">{String(errors.detail)}</p>
          )}
          {errors.error && (
            <p className="text-sm text-red-600">{String(errors.error)}</p>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            {!(isEdit && existing?.is_builtin) && (
              <button className={buttonClass} onClick={handleSave} disabled={busy}>
                {isEdit ? 'Save' : 'Save & Connect All Clients'}
              </button>
            )}
            <button
              className={secondaryClass}
              onClick={() => navigate('/owner/mcp-servers')}
            >
              {isEdit && existing?.is_builtin ? 'Back' : 'Cancel'}
            </button>
            {isEdit && !existing?.is_builtin && (
              <button
                className="ml-auto px-4 py-2 border border-red-600 text-red-600 rounded-sm text-sm"
                onClick={handleDelete}
              >
                Delete
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MCPServerEditPage;
