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
  const [discovered, setDiscovered] = useState(null); // {type:'live', server_name, tools} or {type:'parsed', ...}
  const [discoverError, setDiscoverError] = useState('');

  // Env vars state (shown when server needs API keys)
  const [envVars, setEnvVars] = useState({}); // {VAR_NAME: 'value'}
  const [needsEnv, setNeedsEnv] = useState(null); // response from backend

  // Form state
  const [form, setForm] = useState({
    name: '',
    icon: 'puzzle',
    color: '#6366f1',
    category: 'custom',
    targets: ['assistant'],
    api_key: '',
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
      const { data } = await mcpServersAPI.discover(url, form.api_key);
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
          api_key: form.api_key,
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
          <div>
            <h3 className="text-sm font-medium text-ink">Connect a remote MCP server</h3>
            <p className="text-xs text-ink/60 mt-0.5">
              Paste the server&apos;s endpoint URL (SSE or streamable HTTP). We connect live and
              read its tools — nothing is installed. This is the most reliable way to add a server.
            </p>
          </div>
          <Field label="MCP Server URL">
            <input
              className={inputClass}
              placeholder="https://mcp-server.example.com/sse"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </Field>
          <Field label="API key (optional — if the server requires auth)">
            <input
              className={inputClass}
              type="password"
              placeholder="Sent as a Bearer token to the server"
              value={form.api_key}
              onChange={(e) => set('api_key', e.target.value)}
            />
          </Field>
          <button
            className={buttonClass}
            onClick={handleDiscover}
            disabled={discovering || !url}
          >
            {discovering ? 'Connecting…' : 'Discover tools'}
          </button>
          {discoverError && (
            <p className="text-sm text-red-600">{discoverError}</p>
          )}
        </div>
      )}

      {/* Parsed catalog page — server info card */}
      {discovered?.type === 'parsed' && (
        <div className="space-y-3">
          <div className="p-3 border border-amber/40 bg-amber/[0.06] rounded-sm text-xs text-ink/70">
            <span className="font-medium">Advanced — self-hosted install.</span>{' '}
            This URL isn&apos;t a live MCP endpoint, so the server would have to be installed and
            run inside the platform. That&apos;s less reliable (build, env, version drift). If the
            project offers a hosted endpoint URL, paste that above instead.
          </div>
          <div className="p-4 border border-ink/10 rounded-sm bg-ink/[0.02] space-y-3">
            <h3 className="text-sm font-medium text-ink">
              {discovered.server_name || 'MCP Server'}
            </h3>
            {discovered.description && (
              <p className="text-sm text-ink/60">{discovered.description}</p>
            )}

            <div className="grid grid-cols-2 gap-2 text-sm">
              {discovered.npm_package && (
                <div>
                  <span className="text-xs label-mono text-ink/50">npm</span>
                  <p className="font-mono text-xs">{discovered.npm_package}</p>
                </div>
              )}
              {discovered.pip_package && (
                <div>
                  <span className="text-xs label-mono text-ink/50">pip</span>
                  <p className="font-mono text-xs">{discovered.pip_package}</p>
                </div>
              )}
              {discovered.github_url && (
                <div className="col-span-2">
                  <span className="text-xs label-mono text-ink/50">GitHub</span>
                  <p className="text-xs">
                    <a href={discovered.github_url} target="_blank" rel="noreferrer" className="text-iris hover:underline">
                      {discovered.github_url.replace('https://github.com/', '')}
                    </a>
                  </p>
                </div>
              )}
            </div>

            {discovered.mcp_config && Object.keys(discovered.mcp_config).length > 0 && (
              <div>
                <span className="text-xs label-mono text-ink/50">MCP Config</span>
                <pre className="mt-1 p-2 bg-ink/5 rounded-sm text-xs font-mono overflow-x-auto">
                  {JSON.stringify(discovered.mcp_config, null, 2)}
                </pre>
              </div>
            )}

            {/* Install section — show when npm or pip package found */}
            {(discovered.npm_package || discovered.pip_package) && (
              <div className="pt-3 border-t border-ink/10 space-y-3">
                <div className="space-y-2">
                  <span className="text-xs label-mono text-ink/60">Connect to targets</span>
                  <div className="flex gap-4">
                    {TARGETS.map((t) => (
                      <label key={t.value} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={form.targets.includes(t.value)}
                          onChange={() => toggleTarget(t.value)}
                        />
                        {t.label}
                      </label>
                    ))}
                  </div>
                </div>

                {errors.error && (
                  <p className="text-sm text-red-600 p-2 bg-red-50 rounded-sm">{String(errors.error)}</p>
                )}

                {busy && (
                  <div className="flex items-center gap-3 p-3 bg-iris/5 border border-iris/20 rounded-sm">
                    <div className="w-4 h-4 border-2 border-iris/30 border-t-iris rounded-full animate-spin" />
                    <div className="text-sm text-ink/70">
                      <p className="font-medium">Installing package...</p>
                      <p className="text-xs text-ink/50">This may take up to 2 minutes (npm install + tool discovery)</p>
                    </div>
                  </div>
                )}

                {/* Env vars form — shown when server needs API keys */}
                {needsEnv && (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-sm space-y-3">
                    <p className="text-sm font-medium text-amber-800">{needsEnv.message}</p>
                    {needsEnv.env_vars.map((v) => (
                      <Field key={v.name} label={v.name}>
                        <input
                          className={inputClass}
                          type="password"
                          placeholder={`Enter ${v.name}`}
                          value={envVars[v.name] || ''}
                          onChange={(e) => setEnvVars((prev) => ({ ...prev, [v.name]: e.target.value }))}
                        />
                      </Field>
                    ))}
                  </div>
                )}

                <div className="flex gap-2">
                  <button
                    className={buttonClass}
                    disabled={busy || (needsEnv && needsEnv.env_vars.some((v) => !envVars[v.name]))}
                    onClick={async () => {
                      setBusy(true);
                      setErrors({});
                      setNeedsEnv(null);
                      try {
                        const pkg = needsEnv?.package_name || discovered.npm_package || discovered.pip_package;
                        const pkgType = needsEnv?.package_type || (discovered.npm_package ? 'npm' : 'pypi');
                        const cfg = discovered.mcp_config || {};
                        const mergedEnv = { ...(cfg.env || {}), ...envVars };
                        await mcpServersAPI.install({
                          package_name: pkg,
                          package_type: pkgType,
                          run_command: needsEnv?.run_command || cfg.command || '',
                          run_args: needsEnv?.run_args || cfg.args || [],
                          env_config: Object.keys(mergedEnv).length ? mergedEnv : {},
                          name: discovered.server_name || pkg,
                          icon: form.icon,
                          color: form.color,
                          category: form.category,
                          targets: form.targets,
                          source_url: url,
                        });
                        navigate('/owner/mcp-servers');
                      } catch (e) {
                        const data = e?.response?.data;
                        if (data?.error === 'needs_env') {
                          setNeedsEnv(data);
                        } else {
                          setErrors(data || { error: 'Install failed' });
                        }
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    {busy
                      ? 'Installing...'
                      : needsEnv
                        ? 'Retry with API Key'
                        : `Install ${discovered.npm_package ? '(npm)' : '(pip)'} & Connect All Clients`}
                  </button>
                  <button
                    className={secondaryClass}
                    onClick={() => navigate('/owner/mcp-servers')}
                    disabled={busy}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {/* No installable package found */}
            {!discovered.npm_package && !discovered.pip_package && (
              <div className="pt-2 border-t border-ink/10">
                <p className="text-sm text-ink/50">
                  No installable package found. Check the GitHub repo for manual setup instructions.
                </p>
              </div>
            )}

            {/* SSE endpoint shortcut */}
            {discovered.sse_endpoint && (
              <div className="pt-2 border-t border-ink/10">
                <button
                  className={secondaryClass}
                  onClick={() => {
                    setUrl(discovered.sse_endpoint);
                    setDiscovered(null);
                  }}
                >
                  Or try remote endpoint: {discovered.sse_endpoint}
                </button>
              </div>
            )}
          </div>

          {!discovered.npm_package && !discovered.pip_package && (
            <button className={secondaryClass} onClick={() => navigate('/owner/mcp-servers')}>
              Back
            </button>
          )}
        </div>
      )}

      {/* Live discovery — tools preview + config form */}
      {discovered?.type === 'live' && (
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

          {/* API Key — optional, for servers that require auth */}
          {!isEdit && (
            <Field label="API Key (optional — for servers that require authentication)">
              <input
                className={inputClass}
                type="password"
                placeholder="sk-..."
                value={form.api_key}
                onChange={(e) => set('api_key', e.target.value)}
              />
            </Field>
          )}

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

      {/* Edit mode — show tools when loaded from existing */}
      {isEdit && discovered && !discovered.type && (
        <div className="space-y-3">
          <div className="p-4 border border-ink/10 rounded-sm bg-ink/[0.02]">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-ink">
                Available Tools ({discovered.tools.length})
              </h3>
              {!existing?.is_builtin && (
                <button className={secondaryClass} onClick={handleRefresh} disabled={busy}>
                  Refresh Tools
                </button>
              )}
            </div>
            <div className="space-y-1">
              {discovered.tools.map((tool, i) => (
                <div key={i} className="text-sm py-1 border-b border-ink/5 last:border-0">
                  <span className="font-mono text-xs text-ink/80">{tool.name}</span>
                  {tool.description && <span className="ml-2 text-ink/50">{tool.description}</span>}
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Name" error={errors.name}>
              <input className={inputClass} value={form.name} onChange={(e) => set('name', e.target.value)} disabled={existing?.is_builtin} />
            </Field>
            <Field label="Category">
              <select className={inputClass} value={form.category} onChange={(e) => set('category', e.target.value)}>
                {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </Field>
            <Field label="Icon (name)">
              <input className={inputClass} value={form.icon} onChange={(e) => set('icon', e.target.value)} />
            </Field>
            <Field label="Color">
              <div className="flex gap-2 items-center">
                <input type="color" value={form.color} onChange={(e) => set('color', e.target.value)} className="w-10 h-10 border border-ink/20 rounded-sm cursor-pointer" />
                <input className={inputClass} value={form.color} onChange={(e) => set('color', e.target.value)} maxLength={7} />
              </div>
            </Field>
          </div>

          <div className="space-y-2">
            <span className="text-xs label-mono text-ink/60">Connect to targets</span>
            <div className="flex gap-4">
              {TARGETS.map((t) => (
                <label key={t.value} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={form.targets.includes(t.value)} onChange={() => toggleTarget(t.value)} disabled={existing?.is_builtin} />
                  {t.label}
                </label>
              ))}
            </div>
          </div>

          {errors.detail && <p className="text-sm text-red-600">{String(errors.detail)}</p>}
          {errors.error && <p className="text-sm text-red-600">{String(errors.error)}</p>}

          <div className="flex gap-2">
            {!existing?.is_builtin && (
              <button className={buttonClass} onClick={handleSave} disabled={busy}>Save</button>
            )}
            <button className={secondaryClass} onClick={() => navigate('/owner/mcp-servers')}>
              {existing?.is_builtin ? 'Back' : 'Cancel'}
            </button>
            {!existing?.is_builtin && (
              <button className="ml-auto px-4 py-2 border border-red-600 text-red-600 rounded-sm text-sm" onClick={handleDelete}>Delete</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MCPServerEditPage;
