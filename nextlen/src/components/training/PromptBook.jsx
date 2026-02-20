import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import api from '../../api/axios';
import { clientAPI } from '../../api/client';
import { 
  BookOpen, Search, Filter, Copy, ExternalLink, Sparkles, TrendingUp,
  Megaphone, Briefcase, Users, Headphones, Scale, DollarSign, Code, PenTool,
  ShoppingBag, Heart, Building2, GraduationCap, ThumbsUp, ThumbsDown, Plus, X,
  Check, Zap
} from 'lucide-react';

const PromptBook = ({ onSelectPrompt, embedded = false, showHeader = true }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedIndustry, setSelectedIndustry] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  const [prompts, setPrompts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [applyingPrompt, setApplyingPrompt] = useState(null);
  const [appliedPrompt, setAppliedPrompt] = useState(null);
  const [newPrompt, setNewPrompt] = useState({
    title: '',
    category: 'marketing',
    industry: 'all',
    description: '',
    prompt_template: '',
    variables: [],
    tags: [],
    model: 'gpt-4',
    temperature: 0.7,
    max_tokens: 1500,
  });
  const [voting, setVoting] = useState({});

  const categories = [
    { id: 'all', name: t('promptBook.allCategories') || 'All Categories', icon: BookOpen, color: 'text-gray-600 dark:text-gray-400' },
    { id: 'marketing', name: t('promptBook.marketing') || 'Marketing', icon: Megaphone, color: 'text-pink-600 dark:text-pink-400' },
    { id: 'sales', name: t('promptBook.sales') || 'Sales', icon: Briefcase, color: 'text-blue-600 dark:text-blue-400' },
    { id: 'hr', name: t('promptBook.hr') || 'HR / Recruitment', icon: Users, color: 'text-purple-600 dark:text-purple-400' },
    { id: 'customer_support', name: t('promptBook.customerSupport') || 'Customer Support', icon: Headphones, color: 'text-green-600 dark:text-green-400' },
    { id: 'legal', name: t('promptBook.legal') || 'Legal / Compliance', icon: Scale, color: 'text-indigo-600 dark:text-indigo-400' },
    { id: 'finance', name: t('promptBook.finance') || 'Finance / Analytics', icon: DollarSign, color: 'text-emerald-600 dark:text-emerald-400' },
    { id: 'tech', name: t('promptBook.tech') || 'Software Development', icon: Code, color: 'text-orange-600 dark:text-orange-400' },
    { id: 'content', name: t('promptBook.content') || 'Content Creation', icon: PenTool, color: 'text-rose-600 dark:text-rose-400' },
  ];

  const industries = [
    { id: 'all', name: t('promptBook.allIndustries') || 'All Industries', icon: Building2 },
    { id: 'retail', name: t('promptBook.retail') || 'Retail', icon: ShoppingBag },
    { id: 'healthcare', name: t('promptBook.healthcare') || 'Healthcare', icon: Heart },
    { id: 'finance', name: t('promptBook.financeIndustry') || 'Finance', icon: DollarSign },
    { id: 'tech', name: t('promptBook.techIndustry') || 'Technology', icon: Code },
    { id: 'education', name: t('promptBook.education') || 'Education', icon: GraduationCap },
  ];

  // Завантаження промптів з API
  useEffect(() => {
    loadPrompts();
  }, [selectedCategory, selectedIndustry, searchQuery]);

  const loadPrompts = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedCategory !== 'all') params.append('category', selectedCategory);
      if (selectedIndustry !== 'all') params.append('industry', selectedIndustry);
      if (searchQuery) params.append('search', searchQuery);

      const response = await api.get(`/clients/prompts/?${params.toString()}`);
      setPrompts(response.data.results || response.data || []);
    } catch (error) {
      console.error('Error loading prompts:', error);
      // Якщо 404, встановлюємо порожній масив
      if (error.response?.status === 404) {
        setPrompts([]);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVote = async (promptId, voteType) => {
    if (voting[promptId]) return; // Запобігаємо подвійним клікам

    setVoting({ ...voting, [promptId]: true });
    try {
      const response = await api.post(`/clients/prompts/${promptId}/vote/`, { vote: voteType });
      
      // Оновлюємо локальний стан
      setPrompts(prompts.map(p => 
        p.id === promptId 
          ? { 
              ...p, 
              likes_count: response.data.likes_count,
              dislikes_count: response.data.dislikes_count,
              like_ratio: response.data.like_ratio,
              user_vote: voteType === p.user_vote ? null : voteType // Якщо той самий голос - знімаємо
            }
          : p
      ));
    } catch (error) {
      console.error('Error voting:', error);
    } finally {
      setVoting({ ...voting, [promptId]: false });
    }
  };

  const handleAddPrompt = async () => {
    try {
      const response = await api.post('/clients/prompts/', newPrompt);
      setShowAddModal(false);
      setNewPrompt({
        title: '',
        category: 'marketing',
        industry: 'all',
        description: '',
        prompt_template: '',
        variables: [],
        tags: [],
        model: 'gpt-4',
        temperature: 0.7,
        max_tokens: 1500,
      });
      loadPrompts();
    } catch (error) {
      console.error('Error adding prompt:', error);
      const errorMessage = error.response?.data?.error || 
                          error.response?.data?.message || 
                          error.message || 
                          'Failed to add prompt';
      alert(errorMessage);
    }
  };

  const handleCopyPrompt = (prompt) => {
    navigator.clipboard.writeText(prompt.prompt_template);
    // Можна додати toast notification
  };

  const handleApplyPrompt = async (prompt) => {
    if (onSelectPrompt) {
      // Якщо є callback (embedded mode), використовуємо його
      onSelectPrompt(prompt);
      return;
    }

    // Зберігаємо pending prompt в localStorage для PromptEditor
    const pendingPrompt = {
      id: prompt.id,
      title: prompt.title,
      template: prompt.prompt_template,
    };
    localStorage.setItem('nexelin_pending_prompt', JSON.stringify(pendingPrompt));

    // Також відправляємо подію (для випадку коли вже на сторінці Train AI)
    const event = new CustomEvent('promptbook:add', {
      detail: pendingPrompt
    });
    window.dispatchEvent(event);

    // Показуємо успіх
    setAppliedPrompt(prompt.id);
    
    // Перенаправляємо на Train AI через 800ms
    setTimeout(() => {
      setAppliedPrompt(null);
      
      // Перевіряємо чи ми в режимі /l?tag=... (ClientLoginPage)
      // Якщо так - відправляємо подію для зміни view
      // Якщо ні - використовуємо React Router navigate
      const isClientMode = window.location.pathname === '/l' && window.location.search.includes('tag=');
      
      if (isClientMode) {
        // Відправляємо подію для ClientLoginPage щоб змінити view на training
        window.dispatchEvent(new CustomEvent('nexelin:navigate', { detail: { view: 'training' } }));
      } else {
        navigate('/training');
      }
    }, 800);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      {showHeader && (
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <BookOpen size={28} className="text-primary-600 dark:text-primary-400" />
              {t('promptBook.title') || 'Prompt Book'}
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mt-2">
              {t('promptBook.subtitle') || 'Prompt Engineering Resources by Industry'}
            </p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="btn-primary flex items-center gap-2"
          >
            <Plus size={18} />
            {t('promptBook.addPrompt') || 'Add Prompt'}
          </button>
        </div>
      )}

      {/* Add Prompt Button - показуємо окремо якщо заголовок приховано */}
      {!showHeader && (
        <div className="flex justify-end">
          <button
            onClick={() => setShowAddModal(true)}
            className="btn-primary flex items-center gap-2"
          >
            <Plus size={18} />
            {t('promptBook.addPrompt') || 'Add Prompt'}
          </button>
        </div>
      )}

      {/* Search and Filters */}
      <div className="card">
        <div className="space-y-4">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
            <input
              type="text"
              placeholder={t('promptBook.searchPlaceholder') || 'Search prompts...'}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 dark:focus:ring-primary-400 focus:border-transparent bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
            />
          </div>

          {/* Category Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              <Filter size={16} className="inline mr-1" />
              {t('promptBook.category') || 'Category'}
            </label>
            <div className="flex flex-wrap gap-2">
              {categories.map(cat => {
                const IconComponent = cat.icon;
                return (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCategory(cat.id)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
                      selectedCategory === cat.id
                        ? 'bg-primary-600 dark:bg-primary-500 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                  >
                    <IconComponent size={16} className={selectedCategory === cat.id ? 'text-white' : cat.color} />
                    {cat.name}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Industry Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              {t('promptBook.industry') || 'Industry'}
            </label>
            <div className="flex flex-wrap gap-2">
              {industries.map(ind => {
                const IconComponent = ind.icon;
                return (
                  <button
                    key={ind.id}
                    onClick={() => setSelectedIndustry(ind.id)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
                      selectedIndustry === ind.id
                        ? 'bg-primary-600 dark:bg-primary-500 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                  >
                    <IconComponent size={16} className={selectedIndustry === ind.id ? 'text-white' : 'text-gray-500 dark:text-gray-400'} />
                    {ind.name}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Prompts Grid */}
      {loading ? (
        <div className="card text-center py-12">
          <p className="text-gray-500 dark:text-gray-400">{t('promptBook.loading') || 'Loading...'}</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {prompts.map(prompt => (
              <div
                key={prompt.id}
                className="card hover:shadow-lg transition-shadow cursor-pointer"
                onClick={() => setSelectedPrompt(prompt)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">
                      {prompt.title}
                    </h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                      {prompt.description}
                    </p>
                  </div>
                </div>

                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs px-2 py-1 bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded">
                    {categories.find(c => c.id === prompt.category)?.name || prompt.category}
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
                    <TrendingUp size={14} />
                    {prompt.usage_count || 0} {t('promptBook.uses') || 'uses'}
                  </span>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-gray-200 dark:border-gray-700">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleVote(prompt.id, 'like');
                      }}
                      className={`flex items-center gap-1 text-sm ${
                        prompt.user_vote === 'like'
                          ? 'text-green-600 dark:text-green-400'
                          : 'text-gray-500 dark:text-gray-400 hover:text-green-600 dark:hover:text-green-400'
                      }`}
                      disabled={voting[prompt.id]}
                    >
                      <ThumbsUp size={16} />
                      {prompt.likes_count || 0}
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleVote(prompt.id, 'dislike');
                      }}
                      className={`flex items-center gap-1 text-sm ${
                        prompt.user_vote === 'dislike'
                          ? 'text-red-600 dark:text-red-400'
                          : 'text-gray-500 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400'
                      }`}
                      disabled={voting[prompt.id]}
                    >
                      <ThumbsDown size={16} />
                      {prompt.dislikes_count || 0}
                    </button>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCopyPrompt(prompt);
                      }}
                      className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 flex items-center gap-1"
                      title={t('promptBook.copyPrompt') || 'Copy prompt'}
                    >
                      <Copy size={16} />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleApplyPrompt(prompt);
                      }}
                      disabled={applyingPrompt === prompt.id}
                      className={`text-sm font-medium flex items-center gap-1 px-2 py-1 rounded transition-colors ${
                        appliedPrompt === prompt.id
                          ? 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400'
                          : 'bg-primary-100 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 hover:bg-primary-200 dark:hover:bg-primary-900/50'
                      }`}
                      title={t('promptBook.usePrompt') || 'Use this prompt'}
                    >
                      {appliedPrompt === prompt.id ? (
                        <>
                          <Check size={14} />
                          {t('promptBook.applied') || 'Applied!'}
                        </>
                      ) : applyingPrompt === prompt.id ? (
                        <>
                          <Zap size={14} className="animate-pulse" />
                          ...
                        </>
                      ) : (
                        <>
                          <Zap size={14} />
                          {t('promptBook.use') || 'Use'}
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {prompts.length === 0 && (
            <div className="card text-center py-12">
              <p className="text-gray-500 dark:text-gray-400">
                {t('promptBook.noPrompts') || 'No prompts found. Try adjusting your filters.'}
              </p>
            </div>
          )}
        </>
      )}

      {/* Prompt Detail Modal */}
      {selectedPrompt && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setSelectedPrompt(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">
                    {selectedPrompt.title}
                  </h3>
                  <div className="flex items-center gap-2">
                    <span className="text-sm px-2 py-1 bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded">
                      {categories.find(c => c.id === selectedPrompt.category)?.name}
                    </span>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {industries.find(i => i.id === selectedPrompt.industry)?.name}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedPrompt(null)}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <X size={24} />
                </button>
              </div>

              <p className="text-gray-700 dark:text-gray-300 mb-6">
                {selectedPrompt.description}
              </p>

              <div className="bg-gray-50 dark:bg-gray-900/50 p-4 rounded-lg mb-6">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {t('promptBook.promptTemplate') || 'Prompt Template'}
                  </label>
                  <button
                    onClick={() => handleCopyPrompt(selectedPrompt)}
                    className="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 flex items-center gap-1"
                  >
                    <Copy size={14} />
                    {t('promptBook.copy') || 'Copy'}
                  </button>
                </div>
                <code className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
                  {selectedPrompt.prompt_template}
                </code>
              </div>

              {selectedPrompt.variables && selectedPrompt.variables.length > 0 && (
                <div className="mb-6">
                  <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-3">
                    {t('promptBook.variables') || 'Variables'}
                  </h4>
                  <div className="space-y-2">
                    {selectedPrompt.variables.map((variable, idx) => (
                      <div key={idx} className="bg-gray-50 dark:bg-gray-900/50 p-3 rounded-lg">
                        <div className="flex items-center gap-2 mb-1">
                          <code className="text-sm font-mono text-primary-600 dark:text-primary-400">
                            {`{{${variable.name}}}`}
                          </code>
                          {variable.required && (
                            <span className="text-xs text-red-600 dark:text-red-400">*</span>
                          )}
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            ({variable.type})
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          {variable.description}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex flex-col gap-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-2">
                      <TrendingUp size={16} />
                      {selectedPrompt.usage_count || 0} {t('promptBook.uses') || 'uses'}
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleVote(selectedPrompt.id, 'like')}
                        className={`flex items-center gap-1 text-sm ${
                          selectedPrompt.user_vote === 'like'
                            ? 'text-green-600 dark:text-green-400'
                            : 'text-gray-500 dark:text-gray-400 hover:text-green-600 dark:hover:text-green-400'
                        }`}
                        disabled={voting[selectedPrompt.id]}
                      >
                        <ThumbsUp size={16} />
                        {selectedPrompt.likes_count || 0}
                      </button>
                      <button
                        onClick={() => handleVote(selectedPrompt.id, 'dislike')}
                        className={`flex items-center gap-1 text-sm ${
                          selectedPrompt.user_vote === 'dislike'
                            ? 'text-red-600 dark:text-red-400'
                            : 'text-gray-500 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400'
                        }`}
                        disabled={voting[selectedPrompt.id]}
                      >
                        <ThumbsDown size={16} />
                        {selectedPrompt.dislikes_count || 0}
                      </button>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {selectedPrompt.tags && selectedPrompt.tags.map(tag => (
                      <span key={tag} className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded">
                        #{tag}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Use Prompt Button */}
                <button
                  onClick={() => handleApplyPrompt(selectedPrompt)}
                  disabled={applyingPrompt === selectedPrompt.id}
                  className={`w-full py-3 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors ${
                    appliedPrompt === selectedPrompt.id
                      ? 'bg-green-500 text-white'
                      : 'bg-primary-600 dark:bg-primary-500 text-white hover:bg-primary-700 dark:hover:bg-primary-600'
                  }`}
                >
                  {appliedPrompt === selectedPrompt.id ? (
                    <>
                      <Check size={20} />
                      {t('promptBook.appliedRedirecting') || 'Applied! Redirecting to Train AI...'}
                    </>
                  ) : applyingPrompt === selectedPrompt.id ? (
                    <>
                      <Zap size={20} className="animate-pulse" />
                      {t('promptBook.applying') || 'Applying...'}
                    </>
                  ) : (
                    <>
                      <Zap size={20} />
                      {t('promptBook.useThisPrompt') || 'Use This Prompt in Train AI'}
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add Prompt Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setShowAddModal(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                  {t('promptBook.addNewPrompt') || 'Add New Prompt'}
                </h3>
                <button
                  onClick={() => setShowAddModal(false)}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <X size={24} />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    {t('promptBook.title') || 'Title'} *
                  </label>
                  <input
                    type="text"
                    value={newPrompt.title}
                    onChange={(e) => setNewPrompt({ ...newPrompt, title: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      {t('promptBook.category') || 'Category'} *
                    </label>
                    <select
                      value={newPrompt.category}
                      onChange={(e) => setNewPrompt({ ...newPrompt, category: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    >
                      {categories.filter(c => c.id !== 'all').map(cat => (
                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      {t('promptBook.industry') || 'Industry'} *
                    </label>
                    <select
                      value={newPrompt.industry}
                      onChange={(e) => setNewPrompt({ ...newPrompt, industry: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    >
                      {industries.map(ind => (
                        <option key={ind.id} value={ind.id}>{ind.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    {t('promptBook.description') || 'Description'} *
                  </label>
                  <textarea
                    value={newPrompt.description}
                    onChange={(e) => setNewPrompt({ ...newPrompt, description: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    {t('promptBook.promptTemplate') || 'Prompt Template'} *
                  </label>
                  <textarea
                    value={newPrompt.prompt_template}
                    onChange={(e) => setNewPrompt({ ...newPrompt, prompt_template: e.target.value })}
                    rows={5}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 font-mono text-sm"
                    placeholder="Use {{variable_name}} for variables"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    {t('promptBook.tags') || 'Tags'} (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={newPrompt.tags.join(', ')}
                    onChange={(e) => setNewPrompt({ 
                      ...newPrompt, 
                      tags: e.target.value.split(',').map(t => t.trim()).filter(t => t) 
                    })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    placeholder="tag1, tag2, tag3"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-4">
                  <button
                    onClick={() => setShowAddModal(false)}
                    className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                  >
                    {t('promptBook.cancel') || 'Cancel'}
                  </button>
                  <button
                    onClick={handleAddPrompt}
                    className="btn-primary"
                    disabled={!newPrompt.title || !newPrompt.description || !newPrompt.prompt_template}
                  >
                    {t('promptBook.add') || 'Add Prompt'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Resources Section */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
          <Sparkles size={20} className="text-primary-600 dark:text-primary-400" />
          {t('promptBook.resources') || 'Top Prompt Engineering Resources'}
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <a
            href="https://docs.anthropic.com/claude/prompt-library"
            target="_blank"
            rel="noopener noreferrer"
            className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-primary-500 dark:hover:border-primary-400 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-medium text-gray-900 dark:text-gray-100">Anthropic Prompt Library</h4>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Official Claude prompts</p>
              </div>
              <ExternalLink size={18} className="text-gray-400" />
            </div>
          </a>
          <a
            href="https://platform.openai.com/docs/guides/prompt-engineering"
            target="_blank"
            rel="noopener noreferrer"
            className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-primary-500 dark:hover:border-primary-400 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-medium text-gray-900 dark:text-gray-100">OpenAI Prompt Guide</h4>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Best practices & examples</p>
              </div>
              <ExternalLink size={18} className="text-gray-400" />
            </div>
          </a>
          <a
            href="https://github.com/promptslab/Awesome-Prompt-Engineering"
            target="_blank"
            rel="noopener noreferrer"
            className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-primary-500 dark:hover:border-primary-400 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-medium text-gray-900 dark:text-gray-100">Awesome Prompt Engineering</h4>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Community-driven library</p>
              </div>
              <ExternalLink size={18} className="text-gray-400" />
            </div>
          </a>
          <a
            href="https://learnprompting.org"
            target="_blank"
            rel="noopener noreferrer"
            className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-primary-500 dark:hover:border-primary-400 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-medium text-gray-900 dark:text-gray-100">Learn Prompting</h4>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Free comprehensive guide</p>
              </div>
              <ExternalLink size={18} className="text-gray-400" />
            </div>
          </a>
        </div>
      </div>
    </div>
  );
};

export default PromptBook;
