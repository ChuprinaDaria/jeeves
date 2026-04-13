import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { featureFlagsAPI } from '../../api/owner';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';
const secondaryClass =
  'px-4 py-2 border border-ink/20 rounded-sm hover:bg-ink/5 text-sm';
const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-cream text-ink text-sm';

const emptyForm = {
  key: '',
  description: '',
  rollout: 'off',
  enabled_clients: [],
};

const Field = ({ label, children, error }) => (
  <label className="block space-y-1">
    <span className="text-xs label-mono text-ink/60">{label}</span>
    {children}
    {error && <p className="text-xs text-red-600">{String(error)}</p>}
  </label>
);

const FeatureFlagEditPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = id && id !== 'new';

  const [form, setForm] = useState(emptyForm);
  const [choices, setChoices] = useState({ rollout_options: [], clients: [] });
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    featureFlagsAPI.choices().then(({ data }) => setChoices(data));
    if (!isEdit) return;
    featureFlagsAPI.detail(id).then(({ data }) => {
      setForm({
        key: data.key || '',
        description: data.description || '',
        rollout: data.rollout || 'off',
        enabled_clients: data.enabled_clients || [],
      });
    });
  }, [id, isEdit]);

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  const toggleClient = (clientId) => {
    setForm((f) => {
      const current = f.enabled_clients;
      const next = current.includes(clientId)
        ? current.filter((c) => c !== clientId)
        : [...current, clientId];
      return { ...f, enabled_clients: next };
    });
  };

  const handleSave = async () => {
    setBusy(true);
    setErrors({});
    try {
      const payload = {
        key: form.key,
        description: form.description,
        rollout: form.rollout,
        enabled_clients: form.enabled_clients,
      };
      if (isEdit) {
        await featureFlagsAPI.update(id, payload);
      } else {
        await featureFlagsAPI.create(payload);
      }
      navigate('/owner/feature-flags');
    } catch (e) {
      setErrors(e?.response?.data || { detail: 'Save failed' });
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete flag "${form.key}"?`)) return;
    try {
      await featureFlagsAPI.delete(id);
      navigate('/owner/feature-flags');
    } catch (e) {
      alert(e?.response?.data?.error || 'Delete failed');
    }
  };

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-2xl font-semibold text-ink">
        {isEdit ? `Edit Flag: ${form.key || id}` : 'New Feature Flag'}
      </h1>

      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <Field label="Key" error={errors.key}>
            <input
              className={`${inputClass} font-mono`}
              value={form.key}
              onChange={(e) => set('key', e.target.value)}
              placeholder="e.g. enable_new_chat_ui"
              required
            />
          </Field>
        </div>

        <div className="col-span-2">
          <Field label="Description" error={errors.description}>
            <textarea
              className={`${inputClass} resize-none`}
              rows={3}
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
            />
          </Field>
        </div>

        <Field label="Rollout" error={errors.rollout}>
          <select
            className={inputClass}
            value={form.rollout}
            onChange={(e) => set('rollout', e.target.value)}
          >
            {choices.rollout_options.length > 0
              ? choices.rollout_options.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))
              : ['off', 'selected', 'all'].map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
          </select>
        </Field>

        {form.rollout === 'selected' && (
          <div className="col-span-2">
            <span className="text-xs label-mono text-ink/60 block mb-2">
              Enabled Clients
            </span>
            {choices.clients.length === 0 ? (
              <p className="text-sm text-ink/50">No clients available.</p>
            ) : (
              <div className="space-y-1 border border-ink/10 rounded-sm p-3 max-h-60 overflow-y-auto">
                {choices.clients.map((client) => (
                  <label
                    key={client.id}
                    className="flex items-center gap-2 text-sm cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={form.enabled_clients.includes(client.id)}
                      onChange={() => toggleClient(client.id)}
                    />
                    <span>
                      {client.company_name}{' '}
                      <span className="font-mono text-xs text-ink/50">
                        ({client.tag})
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {errors.detail && (
        <p className="text-sm text-red-600">{String(errors.detail)}</p>
      )}

      <div className="flex gap-2">
        <button className={buttonClass} onClick={handleSave} disabled={busy}>
          Save
        </button>
        <button
          className={secondaryClass}
          onClick={() => navigate('/owner/feature-flags')}
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

export default FeatureFlagEditPage;
