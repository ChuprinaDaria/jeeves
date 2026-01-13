import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Sparkles, Loader2 } from 'lucide-react';
import { clientAPI } from '../../api/client';

const PromptEditor = () => {
  const { t } = useTranslation();
  const [prompt, setPrompt] = useState('');
  const [originalPrompt, setOriginalPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  // Завантажити поточний промт з API
  useEffect(() => {
    loadPrompt();
  }, []);

  const loadPrompt = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await clientAPI.getMe();
      const currentPrompt = response.data?.custom_system_prompt || '';
      setPrompt(currentPrompt);
      setOriginalPrompt(currentPrompt);
    } catch (err) {
      console.error('Failed to load prompt:', err);
      setError(t('training.loadPromptError') || 'Failed to load prompt');
      // Fallback на дефолтний промт
      const defaultPrompt = `You are a friendly AI assistant. Your role is to:
- Answer questions professionally
- Help users with their inquiries
- Be polite and helpful

Always use a warm and welcoming tone.`;
      setPrompt(defaultPrompt);
      setOriginalPrompt(defaultPrompt);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    
    try {
      await clientAPI.updateMe({ custom_system_prompt: prompt });
      setOriginalPrompt(prompt);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to save prompt:', err);
      setError(t('training.savePromptError') || 'Failed to save prompt');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setPrompt('');
    setError(null);
  };

  const hasChanges = prompt !== originalPrompt;

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <Sparkles className="text-primary-500 dark:text-primary-400" size={20} />
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('training.aiBehavior')}</h3>
      </div>

      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
        {t('training.customizePrompt')}
      </p>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={24} />
          <span className="ml-2 text-gray-600 dark:text-gray-400">{t('training.loading') || 'Loading...'}</span>
        </div>
      ) : (
        <>
          <textarea
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value);
              setError(null);
              setSuccess(false);
            }}
            className="w-full h-64 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 dark:focus:ring-primary-400 focus:border-transparent outline-none resize-none font-mono text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            placeholder={t('training.promptPlaceholder') || 'Enter your custom AI behavior prompt here...'}
          />

          {error && (
            <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded text-red-700 dark:text-red-400 text-sm">
              {error}
            </div>
          )}

          {success && (
            <div className="mt-2 p-2 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 rounded text-green-700 dark:text-green-400 text-sm">
              {t('training.promptSaved') || 'Prompt saved successfully!'}
            </div>
          )}

          <div className="mt-4 flex gap-3">
            <button
              onClick={handleSave}
              disabled={saving || !hasChanges}
              className={`btn-primary ${!hasChanges ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {saving ? (
                <>
                  <Loader2 className="animate-spin mr-2" size={16} />
                  {t('training.saving') || 'Saving...'}
                </>
              ) : (
                t('training.savePrompt')
              )}
            </button>
            <button
              onClick={handleReset}
              disabled={saving || !hasChanges}
              className={`btn-secondary ${!hasChanges ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {t('training.resetDefault')}
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default PromptEditor;
