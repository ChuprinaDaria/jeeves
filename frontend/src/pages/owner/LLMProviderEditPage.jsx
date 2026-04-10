import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { llmProvidersAPI } from '../../api/owner';
import MaskedPasswordInput from '../../components/owner/forms/MaskedPasswordInput';

const PROVIDER_TYPES = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'cohere', label: 'Cohere' },
  { value: 'kimi', label: 'Kimi (Moonshot)' },
  { value: 'ollama_main', label: 'Ollama — Main' },
  { value: 'ollama_light', label: 'Ollama — Light' },
  { value: 'custom', label: 'Custom' },
];

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';
const secondaryClass =
  'px-4 py-2 border border-ink/20 rounded-sm hover:bg-ink/5 text-sm';
const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-cream text-ink text-sm';

const emptyForm = {
  name: '',
  provider_type: 'openai',
  model_name: '',
  api_key: '',
  api_endpoint: '',
  max_tokens: 4096,
  temperature: 0.7,
  cost_per_1k_input_tokens: '0',
  cost_per_1k_output_tokens: '0',
  is_active: true,
  is_default: false,
  description: '',
};

const Field = ({ label, children, error }) => (
  <label className="block space-y-1">
    <span className="text-xs label-mono text-ink/60">{label}</span>
    {children}
    {error && <p className="text-xs text-red-600">{String(error)}</p>}
  </label>
);

const LLMProviderEditPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = id && id !== 'new';
  const [form, setForm] = useState(emptyForm);
  const [existing, setExisting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [testOutcome, setTestOutcome] = useState(null);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!isEdit) return;
    llmProvidersAPI.detail(id).then(({ data }) => {
      setExisting(data);
      setForm({
        name: data.name || '',
        provider_type: data.provider_type || 'openai',
        model_name: data.model_name || '',
        api_key: '',
        api_endpoint: data.api_endpoint || '',
        max_tokens: data.max_tokens ?? 4096,
        temperature: data.temperature ?? 0.7,
        cost_per_1k_input_tokens: String(data.cost_per_1k_input_tokens ?? '0'),
        cost_per_1k_output_tokens: String(data.cost_per_1k_output_tokens ?? '0'),
        is_active: !!data.is_active,
        is_default: !!data.is_default,
        description: data.description || '',
      });
    });
  }, [id, isEdit]);

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  const buildPayload = () => {
    const payload = { ...form };
    if (isEdit && payload.api_key === '') {
      delete payload.api_key;
    }
    return payload;
  };

  const handleSave = async () => {
    setBusy(true);
    setErrors({});
    try {
      if (isEdit) {
        await llmProvidersAPI.update(id, buildPayload());
      } else {
        await llmProvidersAPI.create(buildPayload());
      }
      navigate('/owner/ai-providers/llm');
    } catch (e) {
      setErrors(e?.response?.data || { detail: 'Save failed' });
    } finally {
      setBusy(false);
    }
  };

  const handleTest = async () => {
    setBusy(true);
    setTestOutcome(null);
    try {
      let data;
      if (isEdit) {
        const resp = await llmProvidersAPI.test(id, form.api_key || undefined);
        data = resp.data;
      } else {
        const resp = await llmProvidersAPI.testUnsaved({
          provider_type: form.provider_type,
          api_key: form.api_key,
          api_endpoint: form.api_endpoint,
          model_name: form.model_name,
        });
        data = resp.data;
      }
      setTestOutcome(data);
    } catch (e) {
      setTestOutcome({ outcome: 'network_error', message: 'Test failed' });
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete "${form.name}"?`)) return;
    try {
      await llmProvidersAPI.delete(id);
      navigate('/owner/ai-providers/llm');
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
        {isEdit ? `Edit ${existing?.name || ''}` : 'New LLM Provider'}
      </h1>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Name" error={errors.name}>
          <input
            className={inputClass}
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
          />
        </Field>
        <Field label="Provider type">
          <select
            className={inputClass}
            value={form.provider_type}
            onChange={(e) => set('provider_type', e.target.value)}
          >
            {PROVIDER_TYPES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Model name">
          <input
            className={inputClass}
            value={form.model_name}
            onChange={(e) => set('model_name', e.target.value)}
          />
        </Field>
        <Field label="API endpoint (Ollama/custom)">
          <input
            className={inputClass}
            value={form.api_endpoint}
            onChange={(e) => set('api_endpoint', e.target.value)}
          />
        </Field>
        <div className="col-span-2">
          <Field
            label={`API key${
              isEdit && existing?.api_key_set
                ? ` (stored: ${existing.api_key_masked || 'set'})`
                : ''
            }`}
          >
            <MaskedPasswordInput
              value={form.api_key}
              onChange={(v) => set('api_key', v)}
              placeholder={
                isEdit && existing?.api_key_set
                  ? 'leave empty to keep stored key'
                  : 'sk-...'
              }
              onClear={isEdit ? () => set('api_key', '') : undefined}
            />
          </Field>
        </div>
        <Field label="Max tokens">
          <input
            className={inputClass}
            type="number"
            value={form.max_tokens}
            onChange={(e) => set('max_tokens', Number(e.target.value))}
          />
        </Field>
        <Field label="Temperature">
          <input
            className={inputClass}
            type="number"
            step="0.1"
            value={form.temperature}
            onChange={(e) => set('temperature', Number(e.target.value))}
          />
        </Field>
        <Field label="Cost per 1k input tokens (USD)">
          <input
            className={inputClass}
            value={form.cost_per_1k_input_tokens}
            onChange={(e) => set('cost_per_1k_input_tokens', e.target.value)}
          />
        </Field>
        <Field label="Cost per 1k output tokens (USD)">
          <input
            className={inputClass}
            value={form.cost_per_1k_output_tokens}
            onChange={(e) => set('cost_per_1k_output_tokens', e.target.value)}
          />
        </Field>
        <div className="col-span-2 flex gap-6">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => set('is_active', e.target.checked)}
            />
            Active
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={(e) => set('is_default', e.target.checked)}
            />
            Default for platform
          </label>
        </div>
      </div>

      {testOutcome && (
        <div
          className={`text-sm p-3 rounded-sm border ${
            testOutcome.outcome === 'success'
              ? 'border-green-600 text-green-700'
              : testOutcome.outcome === 'invalid_key'
              ? 'border-red-600 text-red-700'
              : 'border-yellow-600 text-yellow-700'
          }`}
        >
          <strong>{testOutcome.outcome}:</strong> {testOutcome.message}
        </div>
      )}

      {errors.detail && (
        <p className="text-sm text-red-600">{String(errors.detail)}</p>
      )}

      <div className="flex gap-2">
        <button className={buttonClass} onClick={handleSave} disabled={busy}>
          Save
        </button>
        <button className={secondaryClass} onClick={handleTest} disabled={busy}>
          Test connection
        </button>
        <button
          className={secondaryClass}
          onClick={() => navigate('/owner/ai-providers/llm')}
        >
          Cancel
        </button>
        {isEdit && existing?.can_delete !== false && (
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

export default LLMProviderEditPage;
