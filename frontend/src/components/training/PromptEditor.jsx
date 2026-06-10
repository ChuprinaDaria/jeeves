import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Sparkles, Loader2, X, BookOpen, Check, User } from 'lucide-react';
import { clientAPI } from '../../api/client';

const PromptEditor = () => {
  const { t } = useTranslation();
  const [prompt, setPrompt] = useState('');
  const [originalPrompt, setOriginalPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  
  // Ref для доступу до актуального значення prompt
  const promptRef = useRef('');
  const originalPromptRef = useRef('');
  
  // Система табів для промптів
  const [savedPrompts, setSavedPrompts] = useState(() => {
    const saved = localStorage.getItem('concierge_saved_prompts');
    return saved ? JSON.parse(saved) : [];
  });
  const [activeTab, setActiveTab] = useState('current');
  const [pendingPromptData, setPendingPromptData] = useState(null);

  // Оновлюємо ref при зміні prompt
  useEffect(() => {
    promptRef.current = prompt;
  }, [prompt]);

  useEffect(() => {
    originalPromptRef.current = originalPrompt;
  }, [originalPrompt]);

  // Завантажити поточний промт з API
  useEffect(() => {
    loadPrompt();
    
    // Перевіряємо чи є pending prompt з Prompt Book
    const pendingPrompt = localStorage.getItem('concierge_pending_prompt');
    if (pendingPrompt) {
      try {
        const data = JSON.parse(pendingPrompt);
        localStorage.removeItem('concierge_pending_prompt');
        setPendingPromptData(data);
      } catch (e) {
        console.error('Error parsing pending prompt:', e);
        localStorage.removeItem('concierge_pending_prompt');
      }
    }
  }, []);

  // Обробляємо pending prompt після завантаження поточного промпту
  useEffect(() => {
    if (pendingPromptData && !loading && originalPrompt !== undefined) {
      const { title, template, id } = pendingPromptData;
      addPromptFromBook(title, template, id);
      setPendingPromptData(null);
    }
  }, [pendingPromptData, loading, originalPrompt]);

  // Зберігаємо промпти в localStorage
  useEffect(() => {
    localStorage.setItem('concierge_saved_prompts', JSON.stringify(savedPrompts));
  }, [savedPrompts]);

  // Слухаємо подію додавання промпту з Prompt Book
  useEffect(() => {
    const handlePromptAdded = (event) => {
      const { title, template, id } = event.detail;
      addPromptFromBook(title, template, id);
    };

    window.addEventListener('promptbook:add', handlePromptAdded);
    return () => window.removeEventListener('promptbook:add', handlePromptAdded);
  }, [savedPrompts, originalPrompt]);

  const loadPrompt = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await clientAPI.getMe();
      const currentPrompt = response.data?.custom_system_prompt || '';
      setPrompt(currentPrompt);
      setOriginalPrompt(currentPrompt);
      promptRef.current = currentPrompt;
      originalPromptRef.current = currentPrompt;
    } catch (err) {
      console.error('Failed to load prompt:', err);
      setError(t('training.loadPromptError') || 'Failed to load prompt');
      const defaultPrompt = `You are a friendly AI assistant. Your role is to:
- Answer questions professionally
- Help users with their inquiries
- Be polite and helpful

Always use a warm and welcoming tone.`;
      setPrompt(defaultPrompt);
      setOriginalPrompt(defaultPrompt);
      promptRef.current = defaultPrompt;
      originalPromptRef.current = defaultPrompt;
    } finally {
      setLoading(false);
    }
  };

  const addPromptFromBook = (title, template, bookId) => {
    // Використовуємо ref для отримання актуального значення
    const currentUserPrompt = promptRef.current || originalPromptRef.current;
    
    // Перевіряємо чи вже є такий промпт з Prompt Book
    const existsInSaved = savedPrompts.find(p => p.bookId === bookId);
    if (existsInSaved) {
      setActiveTab(existsInSaved.id);
      return;
    }

    // ЗАВЖДИ зберігаємо поточний промпт користувача в "My Prompt"
    const myPromptExists = savedPrompts.find(p => p.id === 'user_current');
    
    let newSavedPrompts = [...savedPrompts];
    
    if (!myPromptExists) {
      // Створюємо "My Prompt" таб з поточним промптом користувача
      const myPromptTab = {
        id: 'user_current',
        bookId: null,
        title: t('training.myPrompt') || 'My Prompt',
        template: currentUserPrompt,
        createdAt: new Date().toISOString(),
        isUserPrompt: true,
      };
      newSavedPrompts = [myPromptTab, ...newSavedPrompts];
    } else {
      // Оновлюємо існуючий "My Prompt" з поточним значенням
      newSavedPrompts = newSavedPrompts.map(p => 
        p.id === 'user_current' ? { ...p, template: currentUserPrompt } : p
      );
    }

    // Додаємо новий промпт з Prompt Book
    const newPrompt = {
      id: `prompt_${Date.now()}`,
      bookId,
      title,
      template,
      createdAt: new Date().toISOString(),
    };

    newSavedPrompts = [...newSavedPrompts, newPrompt];
    
    setSavedPrompts(newSavedPrompts);
    setActiveTab(newPrompt.id);
  };

  const removePrompt = (promptId) => {
    // Не дозволяємо видаляти "My Prompt"
    if (promptId === 'user_current') {
      return;
    }
    setSavedPrompts(prev => prev.filter(p => p.id !== promptId));
    if (activeTab === promptId) {
      setActiveTab('current');
    }
  };

  const applyPromptToActive = (template) => {
    setPrompt(template);
    setActiveTab('current');
    setError(null);
    setSuccess(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    
    try {
      await clientAPI.updateMe({ custom_system_prompt: prompt });
      setOriginalPrompt(prompt);
      
      // Оновлюємо "My Prompt" таб якщо він існує
      const myPromptExists = savedPrompts.find(p => p.id === 'user_current');
      if (myPromptExists) {
        setSavedPrompts(prev => prev.map(p => 
          p.id === 'user_current' ? { ...p, template: prompt } : p
        ));
      }
      
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

  // Отримуємо поточний контент для відображення
  const getCurrentContent = () => {
    if (activeTab === 'current') {
      return { content: prompt, isEditable: true };
    }
    const savedPrompt = savedPrompts.find(p => p.id === activeTab);
    return savedPrompt ? { content: savedPrompt.template, isEditable: false, prompt: savedPrompt } : { content: '', isEditable: true };
  };

  const { content, prompt: activePrompt } = getCurrentContent();

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <Sparkles className="text-primary-500 dark:text-primary-400" size={20} />
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('training.aiBehavior')}</h3>
      </div>

      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
        {t('training.customizePrompt')}
      </p>

      {/* Tabs */}
      {savedPrompts.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4 pb-4 border-b border-gray-200 dark:border-gray-700">
          {/* Current/Active Tab */}
          <button
            onClick={() => setActiveTab('current')}
            className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
              activeTab === 'current'
                ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 ring-2 ring-primary-500'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            <Sparkles size={14} />
            {t('training.currentPrompt') || 'Current'}
            {hasChanges && <span className="w-2 h-2 bg-yellow-500 rounded-full" />}
          </button>

          {/* Saved Prompts Tabs */}
          {savedPrompts.map(savedPrompt => (
            <div
              key={savedPrompt.id}
              className={`flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                activeTab === savedPrompt.id
                  ? savedPrompt.isUserPrompt 
                    ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 ring-2 ring-green-500'
                    : 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 ring-2 ring-purple-500'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              <button
                onClick={() => setActiveTab(savedPrompt.id)}
                className="flex items-center gap-1.5"
              >
                {savedPrompt.isUserPrompt ? <User size={14} /> : <BookOpen size={14} />}
                <span className="max-w-[120px] truncate">{savedPrompt.title}</span>
              </button>
              {!savedPrompt.isUserPrompt && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removePrompt(savedPrompt.id);
                  }}
                  className="ml-1 p-0.5 hover:bg-gray-300 dark:hover:bg-gray-600 rounded transition-colors"
                  title={t('training.removePrompt') || 'Remove'}
                >
                  <X size={12} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={24} />
          <span className="ml-2 text-gray-600 dark:text-gray-400">{t('training.loading') || 'Loading...'}</span>
        </div>
      ) : (
        <>
          {/* Показуємо превью збереженого промпту або редактор поточного */}
          {activeTab === 'current' ? (
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
          ) : (
            <div className="space-y-4">
              {/* Preview of saved prompt */}
              <div className={`border rounded-lg p-4 ${
                activePrompt?.isUserPrompt 
                  ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                  : 'bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800'
              }`}>
                <div className="flex items-center justify-between mb-2">
                  <h4 className={`font-medium flex items-center gap-2 ${
                    activePrompt?.isUserPrompt 
                      ? 'text-green-900 dark:text-green-100'
                      : 'text-purple-900 dark:text-purple-100'
                  }`}>
                    {activePrompt?.isUserPrompt ? <User size={16} /> : <BookOpen size={16} />}
                    {activePrompt?.title}
                  </h4>
                  <span className={`text-xs ${
                    activePrompt?.isUserPrompt 
                      ? 'text-green-600 dark:text-green-400'
                      : 'text-purple-600 dark:text-purple-400'
                  }`}>
                    {activePrompt?.isUserPrompt 
                      ? (t('training.yourSavedPrompt') || 'Your saved prompt')
                      : (t('training.fromPromptBook') || 'From Prompt Book')
                    }
                  </span>
                </div>
                <pre className={`text-sm whitespace-pre-wrap font-mono bg-white/50 dark:bg-gray-800/50 p-3 rounded max-h-48 overflow-y-auto ${
                  activePrompt?.isUserPrompt 
                    ? 'text-green-800 dark:text-green-200'
                    : 'text-purple-800 dark:text-purple-200'
                }`}>
                  {content || (t('training.emptyPrompt') || '(empty prompt)')}
                </pre>
              </div>

              {/* Apply Button */}
              <button
                onClick={() => applyPromptToActive(content)}
                className={`w-full py-3 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2 ${
                  activePrompt?.isUserPrompt 
                    ? 'bg-green-600 dark:bg-green-500 hover:bg-green-700 dark:hover:bg-green-600'
                    : 'bg-purple-600 dark:bg-purple-500 hover:bg-purple-700 dark:hover:bg-purple-600'
                }`}
              >
                <Check size={18} />
                {t('training.applyThisPrompt') || 'Apply This Prompt'}
              </button>

              <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
                {t('training.applyPromptHint') || 'This will copy the prompt to your active prompt. You can then edit and save it.'}
              </p>
            </div>
          )}

          {activeTab === 'current' && (
            <>
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
        </>
      )}
    </div>
  );
};

export default PromptEditor;
