import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { specializationsAPI } from '../../api/owner';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';
const secondaryClass =
  'px-4 py-2 border border-ink/20 rounded-sm hover:bg-ink/5 text-sm';
const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-cream text-ink text-sm';

const emptyForm = {
  name: '',
  slug: '',
  branch_id: '',
  description: '',
  custom_system_prompt: '',
  embedding_model_id: '',
  is_active: true,
};

const Field = ({ label, children, error }) => (
  <label className="block space-y-1">
    <span className="text-xs label-mono text-ink/60">{label}</span>
    {children}
    {error && <p className="text-xs text-red-600">{String(error)}</p>}
  </label>
);

const SpecializationEditPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = id && id !== 'new';
  const [form, setForm] = useState(emptyForm);
  const [existing, setExisting] = useState(null);
  const [choices, setChoices] = useState({ branches: [], embedding_models: [] });
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    specializationsAPI.choices().then(({ data }) => setChoices(data));

    if (!isEdit) return;
    specializationsAPI.detail(id).then(({ data }) => {
      setExisting(data);
      setForm({
        name: data.name || '',
        slug: data.slug || '',
        branch_id: data.branch?.id ?? '',
        description: data.description || '',
        custom_system_prompt: data.custom_system_prompt || '',
        embedding_model_id: data.embedding_model?.id ?? '',
        is_active: !!data.is_active,
      });
    });
  }, [id, isEdit]);

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  const handleSave = async () => {
    setBusy(true);
    setErrors({});
    try {
      const payload = {
        ...form,
        branch_id: form.branch_id || null,
        embedding_model_id: form.embedding_model_id || null,
      };
      if (isEdit) {
        await specializationsAPI.update(id, payload);
      } else {
        await specializationsAPI.create(payload);
      }
      navigate('/owner/specializations');
    } catch (e) {
      setErrors(e?.response?.data || { detail: 'Save failed' });
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete "${form.name}"?`)) return;
    try {
      await specializationsAPI.delete(id);
      navigate('/owner/specializations');
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
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-2xl font-semibold text-ink">
        {isEdit ? `Edit ${existing?.name || ''}` : 'New Specialization'}
      </h1>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Name" error={errors.name}>
          <input
            className={inputClass}
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
            required
          />
        </Field>
        <Field label="Slug" error={errors.slug}>
          <input
            className={inputClass}
            value={form.slug}
            placeholder="auto-generated"
            onChange={(e) => set('slug', e.target.value)}
          />
        </Field>
        <div className="col-span-2">
          <Field label="Branch" error={errors.branch_id}>
            <select
              className={inputClass}
              value={form.branch_id}
              onChange={(e) => set('branch_id', e.target.value)}
              required={!isEdit}
            >
              <option value="">— Select branch —</option>
              {(choices.branches || []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="col-span-2">
          <Field label="Description" error={errors.description}>
            <textarea
              className={inputClass}
              rows={3}
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
            />
          </Field>
        </div>
        <div className="col-span-2">
          <Field label="Custom System Prompt" error={errors.custom_system_prompt}>
            <textarea
              className={inputClass}
              rows={4}
              value={form.custom_system_prompt}
              placeholder="Leave empty to use branch default"
              onChange={(e) => set('custom_system_prompt', e.target.value)}
            />
          </Field>
        </div>
        <div className="col-span-2">
          <Field label="Embedding Model" error={errors.embedding_model_id}>
            <select
              className={inputClass}
              value={form.embedding_model_id}
              onChange={(e) => set('embedding_model_id', e.target.value)}
            >
              <option value="">— Branch default —</option>
              {(choices.embedding_models || []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="col-span-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => set('is_active', e.target.checked)}
            />
            Active
          </label>
        </div>
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
          onClick={() => navigate('/owner/specializations')}
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

export default SpecializationEditPage;
