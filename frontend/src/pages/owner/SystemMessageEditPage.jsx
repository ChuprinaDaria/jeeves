import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { systemMessagesAPI } from '../../api/owner';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';
const secondaryClass =
  'px-4 py-2 border border-ink/20 rounded-sm hover:bg-ink/5 text-sm';
const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-cream text-ink text-sm';

const Field = ({ label, children, error }) => (
  <label className="block space-y-1">
    <span className="text-xs label-mono text-ink/60">{label}</span>
    {children}
    {error && <p className="text-xs text-red-600">{String(error)}</p>}
  </label>
);

const emptyTranslationRow = () => ({ lang: 'en', text: '' });

const SystemMessageEditPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = id && id !== 'new';

  const [key, setKey] = useState('');
  const [description, setDescription] = useState('');
  const [translationRows, setTranslationRows] = useState([emptyTranslationRow()]);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!isEdit) return;
    systemMessagesAPI.detail(id).then(({ data }) => {
      setKey(data.key || '');
      setDescription(data.description || '');
      const translations = data.translations || {};
      const rows = Object.entries(translations).map(([lang, text]) => ({ lang, text }));
      setTranslationRows(rows.length > 0 ? rows : [emptyTranslationRow()]);
    });
  }, [id, isEdit]);

  const updateRow = (index, field, value) => {
    setTranslationRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    );
  };

  const addRow = () => {
    setTranslationRows((prev) => [...prev, { lang: '', text: '' }]);
  };

  const removeRow = (index) => {
    setTranslationRows((prev) => prev.filter((_, i) => i !== index));
  };

  const buildTranslations = () => {
    const obj = {};
    for (const row of translationRows) {
      const lang = row.lang.trim();
      if (lang) obj[lang] = row.text;
    }
    return obj;
  };

  const handleSave = async () => {
    setBusy(true);
    setErrors({});
    try {
      const payload = {
        key,
        description,
        translations: buildTranslations(),
      };
      if (isEdit) {
        await systemMessagesAPI.update(id, payload);
      } else {
        await systemMessagesAPI.create(payload);
      }
      navigate('/owner/system-messages');
    } catch (e) {
      setErrors(e?.response?.data || { detail: 'Save failed' });
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete message "${key}"?`)) return;
    try {
      await systemMessagesAPI.delete(id);
      navigate('/owner/system-messages');
    } catch (e) {
      alert(e?.response?.data?.error || 'Delete failed');
    }
  };

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-2xl font-semibold text-ink">
        {isEdit ? `Edit Message: ${key || id}` : 'New System Message'}
      </h1>

      <div className="space-y-4">
        <Field label="Key" error={errors.key}>
          <input
            className={`${inputClass} font-mono`}
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="e.g. welcome_message"
            required
          />
        </Field>

        <Field label="Description" error={errors.description}>
          <textarea
            className={`${inputClass} resize-none`}
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>

        <div>
          <span className="text-xs label-mono text-ink/60 block mb-2">
            Translations
          </span>
          <div className="space-y-2">
            {translationRows.map((row, index) => (
              <div key={index} className="flex gap-2 items-start">
                <input
                  className="w-20 px-2 py-2 border border-ink/20 rounded-sm bg-cream text-ink text-sm font-mono"
                  value={row.lang}
                  onChange={(e) => updateRow(index, 'lang', e.target.value)}
                  placeholder="en"
                  maxLength={10}
                />
                <input
                  className="flex-1 px-3 py-2 border border-ink/20 rounded-sm bg-cream text-ink text-sm"
                  value={row.text}
                  onChange={(e) => updateRow(index, 'text', e.target.value)}
                  placeholder="Translation text"
                />
                <button
                  type="button"
                  onClick={() => removeRow(index)}
                  className="px-2 py-2 text-ink/40 hover:text-red-600 text-sm"
                  title="Remove"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={addRow}
            className="mt-2 text-sm text-ink/60 hover:text-ink underline"
          >
            + Add Translation
          </button>
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
          onClick={() => navigate('/owner/system-messages')}
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

export default SystemMessageEditPage;
