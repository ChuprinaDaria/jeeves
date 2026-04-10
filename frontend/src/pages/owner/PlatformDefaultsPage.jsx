import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { platformDefaultsAPI } from '../../api/owner';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';
const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-cream text-ink text-sm';

const Field = ({ label, children, error }) => (
  <label className="block space-y-1">
    <span className="text-xs label-mono text-ink/60">{label}</span>
    {children}
    {error && <p className="text-xs text-red-600">{String(error)}</p>}
  </label>
);

const PlatformDefaultsPage = () => {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [errors, setErrors] = useState({});

  useEffect(() => {
    platformDefaultsAPI.get().then(({ data }) => setData(data));
  }, []);

  const set = (field, value) => setData((d) => ({ ...d, [field]: value }));

  const handleSave = async () => {
    setBusy(true);
    setMessage('');
    setErrors({});
    try {
      const payload = { ...data };
      delete payload.default_llm;
      delete payload.default_embedding;
      const { data: fresh } = await platformDefaultsAPI.update(payload);
      setData(fresh);
      setMessage('Saved.');
    } catch (e) {
      setErrors(e?.response?.data || { detail: 'Save failed' });
    } finally {
      setBusy(false);
    }
  };

  if (!data) return <p className="text-sm text-ink/60">Loading…</p>;

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-3xl font-semibold text-ink">AI behaviour defaults</h1>

      <section className="grid grid-cols-2 gap-4">
        <div className="border border-ink/10 rounded-sm p-4">
          <div className="label-mono text-ink/60 text-xs mb-1">Default LLM</div>
          {data.default_llm ? (
            <Link
              to={`/owner/ai-providers/llm/${data.default_llm.id}`}
              className="text-ink underline"
            >
              {data.default_llm.name}
            </Link>
          ) : (
            <span className="text-ink/40">— none set —</span>
          )}
        </div>
        <div className="border border-ink/10 rounded-sm p-4">
          <div className="label-mono text-ink/60 text-xs mb-1">
            Default Embedding
          </div>
          {data.default_embedding ? (
            <Link
              to={`/owner/ai-providers/embeddings/${data.default_embedding.id}`}
              className="text-ink underline"
            >
              {data.default_embedding.name}
            </Link>
          ) : (
            <span className="text-ink/40">— none set —</span>
          )}
        </div>
      </section>

      <section className="grid grid-cols-2 gap-4">
        <Field label="Temperature (0.0–2.0)" error={errors.default_temperature}>
          <input
            className={inputClass}
            type="number"
            step="0.1"
            value={data.default_temperature ?? ''}
            onChange={(e) =>
              set('default_temperature', Number(e.target.value))
            }
          />
        </Field>
        <Field label="Max tokens" error={errors.default_max_tokens}>
          <input
            className={inputClass}
            type="number"
            value={data.default_max_tokens ?? ''}
            onChange={(e) => set('default_max_tokens', Number(e.target.value))}
          />
        </Field>
        <Field
          label="Similarity threshold (0.0–1.0)"
          error={errors.default_similarity_threshold}
        >
          <input
            className={inputClass}
            type="number"
            step="0.05"
            value={data.default_similarity_threshold ?? ''}
            onChange={(e) =>
              set('default_similarity_threshold', Number(e.target.value))
            }
          />
        </Field>
        <Field
          label="Max context chunks"
          error={errors.default_max_context_chunks}
        >
          <input
            className={inputClass}
            type="number"
            value={data.default_max_context_chunks ?? ''}
            onChange={(e) =>
              set('default_max_context_chunks', Number(e.target.value))
            }
          />
        </Field>
        <Field label="Top K" error={errors.default_top_k}>
          <input
            className={inputClass}
            type="number"
            value={data.default_top_k ?? ''}
            onChange={(e) => set('default_top_k', Number(e.target.value))}
          />
        </Field>
        <Field label="Supported languages (comma separated)">
          <input
            className={inputClass}
            value={(data.supported_languages || []).join(', ')}
            onChange={(e) =>
              set(
                'supported_languages',
                e.target.value
                  .split(',')
                  .map((s) => s.trim())
                  .filter(Boolean),
              )
            }
          />
        </Field>
        <Field label="Default language" error={errors.default_language}>
          <input
            className={inputClass}
            value={data.default_language || ''}
            onChange={(e) => set('default_language', e.target.value)}
          />
        </Field>
        <Field label="Language detection method">
          <select
            className={inputClass}
            value={data.language_detection_method || ''}
            onChange={(e) => set('language_detection_method', e.target.value)}
          >
            <option value="">—</option>
            <option value="llm">LLM-based</option>
            <option value="library">lingua-py</option>
            <option value="none">Disabled</option>
          </select>
        </Field>
        <div className="col-span-2">
          <Field label="Default greeting">
            <textarea
              className={inputClass}
              rows={3}
              value={data.default_greeting || ''}
              onChange={(e) => set('default_greeting', e.target.value)}
            />
          </Field>
        </div>
      </section>

      {errors.detail && (
        <p className="text-sm text-red-600">{String(errors.detail)}</p>
      )}
      {message && <p className="text-sm text-green-700">{message}</p>}

      <button className={buttonClass} onClick={handleSave} disabled={busy}>
        Save
      </button>
    </div>
  );
};

export default PlatformDefaultsPage;
