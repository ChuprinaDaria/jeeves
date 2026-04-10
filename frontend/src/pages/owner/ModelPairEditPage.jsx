import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import {
  embeddingModelsAPI,
  llmProvidersAPI,
  modelPairsAPI,
} from '../../api/owner';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';
const secondaryClass =
  'px-4 py-2 border border-ink/20 rounded-sm hover:bg-ink/5 text-sm';
const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-cream text-ink text-sm';

const Field = ({ label, children }) => (
  <label className="block space-y-1">
    <span className="text-xs label-mono text-ink/60">{label}</span>
    {children}
  </label>
);

const ModelPairEditPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = id && id !== 'new';
  const [llms, setLlms] = useState([]);
  const [embeds, setEmbeds] = useState([]);
  const [form, setForm] = useState({
    llm_provider_id: '',
    embedding_model_id: '',
    external_guid: '',
    is_active: true,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([llmProvidersAPI.list(), embeddingModelsAPI.list()]).then(
      ([l, e]) => {
        setLlms(Array.isArray(l.data) ? l.data : l.data.results || []);
        setEmbeds(Array.isArray(e.data) ? e.data : e.data.results || []);
      },
    );
  }, []);

  useEffect(() => {
    if (!isEdit) return;
    modelPairsAPI.detail(id).then(({ data }) => {
      setForm({
        llm_provider_id: data.llm_provider?.id || '',
        embedding_model_id: data.embedding_model?.id || '',
        external_guid: data.external_guid || '',
        is_active: !!data.is_active,
      });
    });
  }, [id, isEdit]);

  const set = (f, v) => setForm((s) => ({ ...s, [f]: v }));

  const handleSave = async () => {
    setBusy(true);
    setError('');
    try {
      if (isEdit) {
        await modelPairsAPI.update(id, form);
      } else {
        await modelPairsAPI.create(form);
      }
      navigate('/owner/ai-providers/pairs');
    } catch (e) {
      setError(JSON.stringify(e?.response?.data || 'Save failed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-2xl font-semibold text-ink">
        {isEdit ? 'Edit pair' : 'New pair'}
      </h1>
      <div className="grid grid-cols-2 gap-4">
        <Field label="LLM Provider">
          <select
            className={inputClass}
            value={form.llm_provider_id}
            onChange={(e) => set('llm_provider_id', Number(e.target.value) || '')}
          >
            <option value="">— pick one —</option>
            {llms.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Embedding Model">
          <select
            className={inputClass}
            value={form.embedding_model_id}
            onChange={(e) =>
              set('embedding_model_id', Number(e.target.value) || '')
            }
          >
            <option value="">— pick one —</option>
            {embeds.map((em) => (
              <option key={em.id} value={em.id}>
                {em.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="External GUID">
          <input
            className={inputClass}
            value={form.external_guid}
            onChange={(e) => set('external_guid', e.target.value)}
          />
        </Field>
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
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button className={buttonClass} onClick={handleSave} disabled={busy}>
          Save
        </button>
        <button
          className={secondaryClass}
          onClick={() => navigate('/owner/ai-providers/pairs')}
        >
          Cancel
        </button>
      </div>
    </div>
  );
};

export default ModelPairEditPage;
