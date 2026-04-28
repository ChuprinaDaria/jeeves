import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { clientsAPI } from '../../api/owner';
import MaskedPasswordInput from '../../components/owner/forms/MaskedPasswordInput';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';
const secondaryClass =
  'px-4 py-2 border border-ink/20 rounded-sm hover:bg-ink/5 text-sm';
const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-cream text-ink text-sm';

const emptyForm = {
  company_name: '',
  tag: '',
  description: '',
  client_type: '',
  is_active: true,
  branch_id: '',
  specialization_id: '',
  greeting_message: '',
  llm_provider_model_id: '',
  embedding_model_id: '',
  telegram_enabled: false,
  whatsapp_meta_enabled: false,
  whatsapp_bridge_enabled: false,
  email_smtp_enabled: false,
  widget_enabled: false,
  email_smtp_host: '',
  email_smtp_port: 587,
  email_smtp_use_tls: true,
  email_smtp_username: '',
  email_smtp_password: '',
  email_from_address: '',
  email_from_name: '',
  email_report_enabled: false,
  email_report_recipients: '',
  notification_language: '',
  leads_enabled: false,
  extension_enabled: false,
  pixel_dashboard_enabled: false,
};

const Field = ({ label, children, error }) => (
  <label className="block space-y-1">
    <span className="text-xs label-mono text-ink/60">{label}</span>
    {children}
    {error && <p className="text-xs text-red-600">{String(error)}</p>}
  </label>
);

const SectionTitle = ({ children }) => (
  <h2 className="text-base font-semibold text-ink border-b border-ink/10 pb-1 mt-2">
    {children}
  </h2>
);

const formatDate = (iso) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const ClientEditPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = id && id !== 'new';
  const [form, setForm] = useState(emptyForm);
  const [existing, setExisting] = useState(null);
  const [choices, setChoices] = useState(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (isEdit) {
      Promise.all([clientsAPI.detail(id), clientsAPI.choices()]).then(
        ([{ data: detail }, { data: ch }]) => {
          setChoices(ch);
          setExisting(detail);
          setForm({
            company_name: detail.company_name || '',
            tag: detail.tag || '',
            description: detail.description || '',
            client_type: detail.client_type || '',
            is_active: !!detail.is_active,
            branch_id: detail.branch_id ?? '',
            specialization_id: detail.specialization_id ?? '',
            greeting_message: detail.greeting_message || '',
            llm_provider_model_id: detail.llm_provider_model_id ?? '',
            embedding_model_id: detail.embedding_model_id ?? '',
            telegram_enabled: !!detail.telegram_enabled,
            whatsapp_meta_enabled: !!detail.whatsapp_meta_enabled,
            whatsapp_bridge_enabled: !!detail.whatsapp_bridge_enabled,
            email_smtp_enabled: !!detail.email_smtp_enabled,
            widget_enabled: !!detail.widget_enabled,
            email_smtp_host: detail.email_smtp_host || '',
            email_smtp_port: detail.email_smtp_port ?? 587,
            email_smtp_use_tls: detail.email_smtp_use_tls !== false,
            email_smtp_username: detail.email_smtp_username || '',
            email_smtp_password: '',
            email_from_address: detail.email_from_address || '',
            email_from_name: detail.email_from_name || '',
            email_report_enabled: !!detail.email_report_enabled,
            email_report_recipients: Array.isArray(detail.email_report_recipients)
              ? detail.email_report_recipients.join(', ')
              : detail.email_report_recipients || '',
            notification_language: detail.notification_language || '',
            leads_enabled: !!detail.leads_enabled,
            extension_enabled: !!detail.extension_enabled,
            pixel_dashboard_enabled: !!detail.pixel_dashboard_enabled,
          });
        },
      );
    } else {
      clientsAPI.choices().then(({ data: ch }) => setChoices(ch));
    }
  }, [id, isEdit]);

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  const buildPayload = () => {
    const payload = { ...form };
    if (isEdit && payload.email_smtp_password === '') {
      delete payload.email_smtp_password;
    }
    // Convert comma-separated recipients to array
    if (typeof payload.email_report_recipients === 'string') {
      payload.email_report_recipients = payload.email_report_recipients
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
    }
    // Convert empty strings to null for FK fields
    ['branch_id', 'specialization_id', 'llm_provider_model_id', 'embedding_model_id'].forEach(
      (k) => {
        if (payload[k] === '') payload[k] = null;
      },
    );
    return payload;
  };

  const handleSave = async () => {
    setBusy(true);
    setErrors({});
    try {
      if (isEdit) {
        await clientsAPI.update(id, buildPayload());
      } else {
        await clientsAPI.create(buildPayload());
      }
      navigate('/owner/clients');
    } catch (e) {
      setErrors(e?.response?.data || { detail: 'Save failed' });
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete "${form.company_name}"?`)) return;
    try {
      await clientsAPI.delete(id);
      navigate('/owner/clients');
    } catch (e) {
      const body = e?.response?.data || {};
      alert(
        body.error === 'has_protected_references'
          ? `Cannot delete — ${body.count} references.`
          : 'Delete failed',
      );
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-semibold text-ink">
        {isEdit ? `Edit ${existing?.company_name || ''}` : 'New Client'}
      </h1>

      {/* Section 1 — Basic Info */}
      <div className="space-y-4">
        <SectionTitle>Basic Info</SectionTitle>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Company name" error={errors.company_name}>
            <input
              className={inputClass}
              value={form.company_name}
              onChange={(e) => set('company_name', e.target.value)}
            />
          </Field>
          <Field label="Tag" error={errors.tag}>
            <input
              className={inputClass}
              value={form.tag}
              placeholder="auto-generated"
              onChange={(e) => set('tag', e.target.value)}
            />
          </Field>
          <div className="col-span-2">
            <Field label="Description" error={errors.description}>
              <textarea
                className={inputClass}
                rows={2}
                value={form.description}
                onChange={(e) => set('description', e.target.value)}
              />
            </Field>
          </div>
          <Field label="Client type" error={errors.client_type}>
            <select
              className={inputClass}
              value={form.client_type}
              onChange={(e) => set('client_type', e.target.value)}
            >
              <option value="">— select —</option>
              {choices?.client_types?.map((ct) => (
                <option key={ct.value ?? ct[0]} value={ct.value ?? ct[0]}>
                  {ct.label ?? ct[1]}
                </option>
              ))}
            </select>
          </Field>
          <div className="flex items-end pb-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => set('is_active', e.target.checked)}
              />
              Active
            </label>
          </div>
          <Field label="Branch" error={errors.branch_id}>
            <select
              className={inputClass}
              value={form.branch_id}
              onChange={(e) => set('branch_id', e.target.value)}
            >
              <option value="">— none —</option>
              {choices?.branches?.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Specialization" error={errors.specialization_id}>
            <select
              className={inputClass}
              value={form.specialization_id}
              onChange={(e) => set('specialization_id', e.target.value)}
            >
              <option value="">— none —</option>
              {choices?.specializations?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          <div className="col-span-2">
            <Field label="Greeting message" error={errors.greeting_message}>
              <textarea
                className={inputClass}
                rows={3}
                value={form.greeting_message}
                onChange={(e) => set('greeting_message', e.target.value)}
              />
            </Field>
          </div>
        </div>
      </div>

      {/* Section 2 — AI Config */}
      <div className="space-y-4">
        <SectionTitle>AI Config</SectionTitle>
        <div className="grid grid-cols-2 gap-4">
          <Field label="LLM provider / model" error={errors.llm_provider_model_id}>
            <select
              className={inputClass}
              value={form.llm_provider_model_id}
              onChange={(e) => set('llm_provider_model_id', e.target.value)}
            >
              <option value="">— platform default —</option>
              {choices?.llm_providers?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Embedding model" error={errors.embedding_model_id}>
            <select
              className={inputClass}
              value={form.embedding_model_id}
              onChange={(e) => set('embedding_model_id', e.target.value)}
            >
              <option value="">— platform default —</option>
              {choices?.embedding_models?.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </Field>
        </div>
      </div>

      {/* Section 3 — Channels */}
      <div className="space-y-4">
        <SectionTitle>Channels</SectionTitle>
        <div className="flex flex-wrap gap-6">
          {[
            ['telegram_enabled', 'Telegram'],
            ['whatsapp_meta_enabled', 'WhatsApp (Meta)'],
            ['whatsapp_bridge_enabled', 'WhatsApp (Bridge)'],
            ['email_smtp_enabled', 'Email (SMTP)'],
            ['widget_enabled', 'Web Widget'],
          ].map(([field, label]) => (
            <label key={field} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form[field]}
                onChange={(e) => set(field, e.target.checked)}
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      {/* Section 4 — SMTP Config (conditional) */}
      {form.email_smtp_enabled && (
        <div className="space-y-4">
          <SectionTitle>SMTP Config</SectionTitle>
          <div className="grid grid-cols-2 gap-4">
            <Field label="SMTP host" error={errors.email_smtp_host}>
              <input
                className={inputClass}
                value={form.email_smtp_host}
                onChange={(e) => set('email_smtp_host', e.target.value)}
              />
            </Field>
            <Field label="SMTP port" error={errors.email_smtp_port}>
              <input
                className={inputClass}
                type="number"
                value={form.email_smtp_port}
                onChange={(e) => set('email_smtp_port', Number(e.target.value))}
              />
            </Field>
            <div className="col-span-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.email_smtp_use_tls}
                  onChange={(e) => set('email_smtp_use_tls', e.target.checked)}
                />
                Use TLS
              </label>
            </div>
            <Field label="SMTP username" error={errors.email_smtp_username}>
              <input
                className={inputClass}
                value={form.email_smtp_username}
                onChange={(e) => set('email_smtp_username', e.target.value)}
              />
            </Field>
            <div className="col-span-2">
              <Field
                label={`SMTP password${
                  isEdit && existing?.smtp_password_set
                    ? ` (stored: ${existing.email_smtp_password_masked || 'set'})`
                    : ''
                }`}
                error={errors.email_smtp_password}
              >
                <MaskedPasswordInput
                  value={form.email_smtp_password}
                  onChange={(v) => set('email_smtp_password', v)}
                  placeholder={
                    isEdit && existing?.smtp_password_set
                      ? 'leave empty to keep stored'
                      : ''
                  }
                  onClear={isEdit ? () => set('email_smtp_password', '') : undefined}
                />
              </Field>
            </div>
            <Field label="From address" error={errors.email_from_address}>
              <input
                className={inputClass}
                type="email"
                value={form.email_from_address}
                onChange={(e) => set('email_from_address', e.target.value)}
              />
            </Field>
            <Field label="From name" error={errors.email_from_name}>
              <input
                className={inputClass}
                value={form.email_from_name}
                onChange={(e) => set('email_from_name', e.target.value)}
              />
            </Field>
          </div>
        </div>
      )}

      {/* Section 5 — Email Reports */}
      <div className="space-y-4">
        <SectionTitle>Email Reports</SectionTitle>
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.email_report_enabled}
                onChange={(e) => set('email_report_enabled', e.target.checked)}
              />
              Enable email reports
            </label>
          </div>
          <div className="col-span-2">
            <Field label="Report recipients (comma-separated)" error={errors.email_report_recipients}>
              <input
                className={inputClass}
                value={form.email_report_recipients}
                placeholder="user@example.com, other@example.com"
                onChange={(e) => set('email_report_recipients', e.target.value)}
              />
            </Field>
          </div>
          <Field label="Notification language" error={errors.notification_language}>
            <select
              className={inputClass}
              value={form.notification_language}
              onChange={(e) => set('notification_language', e.target.value)}
            >
              <option value="">— select —</option>
              {choices?.notification_languages?.map((nl) => (
                <option key={nl.value ?? nl[0]} value={nl.value ?? nl[0]}>
                  {nl.label ?? nl[1]}
                </option>
              ))}
            </select>
          </Field>
        </div>
      </div>

      {/* Section 6 — Features */}
      <div className="space-y-4">
        <SectionTitle>Features</SectionTitle>
        <div className="flex flex-wrap gap-6">
          {[
            ['leads_enabled', 'Leads'],
            ['extension_enabled', 'Extension'],
            ['pixel_dashboard_enabled', 'Pixel Dashboard'],
          ].map(([field, label]) => (
            <label key={field} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form[field]}
                onChange={(e) => set(field, e.target.checked)}
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      {/* Section 7 — Metadata (edit only) */}
      {isEdit && existing && (
        <div className="space-y-4">
          <SectionTitle>Metadata</SectionTitle>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-xs text-ink/60">API Key</p>
              <p className="font-mono text-ink/80">{existing.api_key_masked || '—'}</p>
            </div>
            <div>
              <p className="text-xs text-ink/60">Created</p>
              <p className="text-ink/80">{formatDate(existing.created_at)}</p>
            </div>
          </div>
        </div>
      )}

      {errors.detail && (
        <p className="text-sm text-red-600">{String(errors.detail)}</p>
      )}

      <div className="flex gap-2">
        <button className={buttonClass} onClick={handleSave} disabled={busy}>
          Save
        </button>
        <button
          className={secondaryClass}
          onClick={() => navigate('/owner/clients')}
        >
          Cancel
        </button>
        {isEdit && (
          <button
            className="ml-auto px-4 py-2 border border-red-600 text-red-600 rounded-sm text-sm"
            onClick={handleDelete}
          >
            Delete
          </button>
        )}
      </div>
    </div>
  );
};

export default ClientEditPage;
