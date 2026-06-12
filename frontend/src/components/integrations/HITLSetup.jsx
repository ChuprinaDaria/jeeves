import { X, Loader2, Check, AlertCircle, UserPlus, Trash2, HelpCircle } from 'lucide-react';
import { useState, useEffect } from 'react';
import api from '../../api/axios';
import { useTranslation } from 'react-i18next';

const HITLSetup = ({ onClose }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    hitl_enabled: false,
    manager_telegram_ids: [],
  });
  const [newManagerId, setNewManagerId] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [telegramBotConfigured, setTelegramBotConfigured] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const res = await api.get('/clients/hitl/config/');
      setForm({
        hitl_enabled: res.data.hitl_enabled || false,
        manager_telegram_ids: res.data.manager_telegram_ids || [],
      });
      setTelegramEnabled(res.data.telegram_enabled || false);
      setTelegramBotConfigured(res.data.telegram_bot_configured || false);
    } catch (error) {
      console.error('Failed to load HITL config:', error);
      setError('Failed to load HITL configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, checked } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: checked
    }));
    setError('');
    setSuccess('');
  };

  const handleAddManager = () => {
    const id = newManagerId.trim();
    if (!id) return;
    
    // Validate it's a number
    const numId = parseInt(id, 10);
    if (isNaN(numId) || numId <= 0) {
      setError('Please enter a valid Telegram user ID (positive number)');
      return;
    }
    
    // Check for duplicates
    if (form.manager_telegram_ids.includes(numId)) {
      setError('This manager ID is already added');
      return;
    }
    
    // Check limit
    if (form.manager_telegram_ids.length >= 5) {
      setError('Maximum 5 managers allowed');
      return;
    }
    
    setForm(prev => ({
      ...prev,
      manager_telegram_ids: [...prev.manager_telegram_ids, numId]
    }));
    setNewManagerId('');
    setError('');
  };

  const handleRemoveManager = (idToRemove) => {
    setForm(prev => ({
      ...prev,
      manager_telegram_ids: prev.manager_telegram_ids.filter(id => id !== idToRemove)
    }));
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError('');
      setSuccess('');
      
      const res = await api.patch('/clients/hitl/config/', form);
      
      if (res.data.success) {
        setSuccess('HITL configuration saved successfully');
        setTimeout(() => {
          onClose();
        }, 1500);
      }
    } catch (error) {
      const errorMsg = error.response?.data?.error || 'Failed to save configuration';
      setError(errorMsg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex justify-end bg-ink/30 backdrop-blur-[2px]">
        <div className="settings-drawer bg-white dark:bg-gray-800 h-full overflow-y-auto border-l-[1.5px] border-rule shadow-ink-lg p-6 w-[480px] max-w-[94vw]">
          <div className="flex items-center justify-center py-8">
            <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={32} />
          </div>
        </div>
      </div>
    );
  }

  const canEnableHITL = telegramEnabled && telegramBotConfigured;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink/30 backdrop-blur-[2px]">
      <div className="settings-drawer bg-white dark:bg-gray-800 h-full overflow-y-auto border-l-[1.5px] border-rule shadow-ink-lg p-6 w-[480px] max-w-[94vw]">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Human-in-the-Loop (HITL)
          </h3>
          <button 
            onClick={onClose} 
            className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
          >
            <X size={24} />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded-lg flex items-center gap-2 text-red-700 dark:text-red-300">
            <AlertCircle size={18} />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {success && (
          <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 rounded-lg flex items-center gap-2 text-green-700 dark:text-green-300">
            <Check size={18} />
            <span className="text-sm">{success}</span>
          </div>
        )}

        <div className="space-y-4">
          {/* Info box explaining HITL */}
          <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
            <div className="flex items-start gap-2">
              <HelpCircle size={18} className="text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-blue-800 dark:text-blue-300">
                <p className="font-medium mb-1">What is HITL?</p>
                <p className="text-xs">
                  When the AI cannot confidently answer a customer's question, it will escalate to a human manager via Telegram. 
                  The manager can reply with the answer, and the AI will rephrase it professionally for the customer.
                </p>
              </div>
            </div>
          </div>

          {/* Prerequisite check */}
          {!canEnableHITL && (
            <div className="bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4">
              <div className="flex items-start gap-2">
                <AlertCircle size={18} className="text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
                <div className="text-sm text-yellow-800 dark:text-yellow-300">
                  <p className="font-medium">Prerequisites required</p>
                  <p className="text-xs mt-1">
                    HITL requires a Telegram Bot to be configured and enabled first. 
                    Please set up your Telegram Bot integration before enabling HITL.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Enable toggle */}
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="hitl_enabled"
              name="hitl_enabled"
              checked={form.hitl_enabled}
              onChange={handleChange}
              disabled={!canEnableHITL}
              className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500 disabled:opacity-50"
            />
            <label 
              htmlFor="hitl_enabled" 
              className={`text-sm font-medium ${canEnableHITL ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400 dark:text-gray-500'}`}
            >
              Enable Human-in-the-Loop escalation
            </label>
          </div>

          {form.hitl_enabled && canEnableHITL && (
            <>
              {/* Manager IDs section */}
              <div>
                <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">
                  Manager Telegram IDs
                </label>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                  Add up to 5 manager Telegram user IDs. To find your Telegram ID, message @userinfobot on Telegram.
                </p>

                {/* List of added managers */}
                {form.manager_telegram_ids.length > 0 && (
                  <div className="space-y-2 mb-3">
                    {form.manager_telegram_ids.map((id, index) => (
                      <div key={id} className="flex items-center justify-between bg-gray-50 dark:bg-gray-700 rounded-lg px-3 py-2">
                        <span className="text-sm text-gray-900 dark:text-gray-100 font-mono">
                          Manager {index + 1}: {id}
                        </span>
                        <button
                          onClick={() => handleRemoveManager(id)}
                          className="text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add new manager input */}
                {form.manager_telegram_ids.length < 5 && (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newManagerId}
                      onChange={(e) => setNewManagerId(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleAddManager()}
                      placeholder="e.g., 123456789"
                      className="input flex-1"
                    />
                    <button
                      onClick={handleAddManager}
                      className="btn-secondary flex items-center gap-1"
                    >
                      <UserPlus size={16} />
                      Add
                    </button>
                  </div>
                )}

                {form.manager_telegram_ids.length >= 5 && (
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Maximum 5 managers reached
                  </p>
                )}
              </div>

              {/* How it works */}
              <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-2">How it works:</p>
                <ol className="text-xs text-gray-600 dark:text-gray-400 space-y-1 list-decimal list-inside">
                  <li>Customer asks a question the AI cannot answer confidently</li>
                  <li>AI tells customer: "Let me check with my colleague..."</li>
                  <li>Manager receives notification on Telegram with the question</li>
                  <li>Manager replies with the answer</li>
                  <li>AI rephrases and sends the answer to the customer</li>
                </ol>
              </div>
            </>
          )}

          <div className="flex gap-3 pt-4">
            <button
              onClick={handleSave}
              disabled={saving || (!canEnableHITL && form.hitl_enabled)}
              className="btn-primary flex-1 flex items-center justify-center gap-2"
            >
              {saving ? (
                <>
                  <Loader2 className="animate-spin" size={18} />
                  Saving...
                </>
              ) : (
                'Save'
              )}
            </button>
            <button
              onClick={onClose}
              disabled={saving}
              className="btn-secondary flex-1"
            >
              {t('common.cancel') || 'Cancel'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HITLSetup;

