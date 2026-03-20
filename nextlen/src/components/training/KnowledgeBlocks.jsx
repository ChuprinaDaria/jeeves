import { useState, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Edit3, Loader2, Trash2, Power, Search, ArrowUpDown, X, ChevronRight, Filter, Database, Boxes } from "lucide-react";
import { clientAPI } from "../../api/client";
import { useAuth } from '../../context/AuthContext';
import KnowledgeBlockEditModal from "./KnowledgeBlockEditModal";
import KnowledgeBlockAddModal from "./KnowledgeBlockAddModal";

const KnowledgeBlocks = () => {
  const [blocks, setBlocks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editingBlock, setEditingBlock] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showAllModal, setShowAllModal] = useState(false);
  const { t } = useTranslation();
  const { user } = useAuth();
  const knowledgeSplitEnabled = user?.feature_flags?.mcp_knowledge_split;

  // Стан для модалки
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [sortBy, setSortBy] = useState(() => {
    const saved = localStorage.getItem('knowledgeBlocks_sortBy');
    return saved || 'entries_desc';
  });
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterScope, setFilterScope] = useState('all_scopes');

  // Дебаунс для пошуку (400ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 400);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Зберігаємо сортування в localStorage
  useEffect(() => {
    localStorage.setItem('knowledgeBlocks_sortBy', sortBy);
  }, [sortBy]);

  // Закриття модалки по Escape
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') setShowAllModal(false);
    };
    if (showAllModal) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [showAllModal]);

  useEffect(() => {
    loadBlocks();
  }, []);

  const loadBlocks = async () => {
    setLoading(true);
    try {
      const response = await clientAPI.getKnowledgeBlocks();
      const blocksData = response.data || [];
      
      const formattedBlocks = blocksData.map((block) => ({
        id: block.id,
        name: block.name,
        description: block.description || "",
        entries: block.entries_count || 0,
        active: block.is_active,
        permanent: block.is_permanent,
        ...block,
      }));
      
      setBlocks(formattedBlocks);
    } catch (error) {
      console.error("Failed to load knowledge blocks:", error);
      setBlocks([
        { id: 0, name: "Clients Chats", entries: 0, active: true, permanent: true, is_permanent: true },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const toggleBlock = async (id) => {
    const block = blocks.find((b) => b.id === id);
    if (!block || block.permanent) return;

    try {
      await clientAPI.updateKnowledgeBlock(id, {
        is_active: !block.active,
      });
      setBlocks(
        blocks.map((b) => (b.id === id ? { ...b, active: !b.active } : b))
      );
    } catch (error) {
      console.error("Failed to toggle block:", error);
    }
  };

  const handleCreateBlock = async (name, description) => {
    try {
      await clientAPI.createKnowledgeBlock({
        name,
        description,
        is_active: true,
      });
      await loadBlocks();
      setShowAddModal(false);
    } catch (error) {
      console.error("Failed to create block:", error);
      alert(t("knowledgeBlocks.createError") || "Failed to create knowledge block");
    }
  };

  const handleEditBlock = (block) => {
    setEditingBlock(block);
  };

  const handleSaveBlock = () => {
    loadBlocks();
    setEditingBlock(null);
  };

  const handleDeleteBlock = async (id) => {
    if (!confirm(t("knowledgeBlocks.deleteConfirm") || "Are you sure you want to delete this block?")) {
      return;
    }

    try {
      await clientAPI.deleteKnowledgeBlock(id);
      await loadBlocks();
    } catch (error) {
      console.error("Failed to delete block:", error);
      alert(t("knowledgeBlocks.deleteError") || "Failed to delete knowledge block");
    }
  };

  // Функція для обрізання назви блоку
  const truncateName = (name, maxLength = 20) => {
    if (!name || name.length <= maxLength) return name;
    return name.slice(0, maxLength - 3) + '...';
  };

  // Топ 4 блоки для превью (сортовані по entries)
  const previewBlocks = useMemo(() => {
    return [...blocks]
      .sort((a, b) => (b.entries || 0) - (a.entries || 0))
      .slice(0, 4);
  }, [blocks]);

  // Фільтрація та сортування блоків для модалки
  const filteredAndSortedBlocks = useMemo(() => {
    let result = [...blocks];

    // Фільтрація по статусу
    if (filterStatus === 'active') {
      result = result.filter(block => block.active);
    } else if (filterStatus === 'inactive') {
      result = result.filter(block => !block.active);
    } else if (filterStatus === 'permanent') {
      result = result.filter(block => block.permanent);
    }

    // Фільтрація по scope
    if (knowledgeSplitEnabled && filterScope !== 'all_scopes') {
      result = result.filter(b => b.target_scope === filterScope);
    }

    // Фільтрація по пошуку
    if (debouncedSearch.trim()) {
      const query = debouncedSearch.toLowerCase().trim();
      result = result.filter(block => 
        block.name.toLowerCase().includes(query) ||
        (block.description && block.description.toLowerCase().includes(query))
      );
    }

    // Сортування
    result.sort((a, b) => {
      switch (sortBy) {
        case 'entries_desc':
          return (b.entries || 0) - (a.entries || 0);
        case 'entries_asc':
          return (a.entries || 0) - (b.entries || 0);
        case 'name_asc':
          return (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' });
        case 'name_desc':
          return (b.name || '').localeCompare(a.name || '', undefined, { sensitivity: 'base' });
        default:
          return 0;
      }
    });

    return result;
  }, [blocks, debouncedSearch, sortBy, filterStatus, filterScope, knowledgeSplitEnabled]);

  const sortOptions = [
    { value: 'entries_desc', label: t('knowledgeBlocks.sort.entriesDesc') || 'Most entries' },
    { value: 'entries_asc', label: t('knowledgeBlocks.sort.entriesAsc') || 'Least entries' },
    { value: 'name_asc', label: t('knowledgeBlocks.sort.nameAZ') || 'Name (A → Z)' },
    { value: 'name_desc', label: t('knowledgeBlocks.sort.nameZA') || 'Name (Z → A)' },
  ];

  // Статистика для фільтрів
  const stats = useMemo(() => ({
    all: blocks.length,
    active: blocks.filter(b => b.active).length,
    inactive: blocks.filter(b => !b.active).length,
    permanent: blocks.filter(b => b.permanent).length,
  }), [blocks]);

  // Компонент для рендеру одного блоку (компактний)
  const BlockItemCompact = ({ block }) => {
    const truncatedName = truncateName(block.name, 18);
    const isTruncated = block.name && block.name.length > 18;
    
    return (
      <div
        className={`border rounded-xl p-3 ${
          block.permanent
            ? "bg-accent-100 dark:bg-accent-900/30 border-accent-300 dark:border-accent-700"
            : "bg-accent-50 dark:bg-accent-900/20 hover:bg-accent-100 dark:hover:bg-accent-900/40 border-accent-200 dark:border-accent-800"
        } transition`}
      >
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <p 
            className="font-semibold text-sm text-accent-900 dark:text-accent-100 truncate"
            title={isTruncated ? block.name : undefined}
          >
            {truncatedName}
          </p>
          <span className="text-xs text-accent-500 dark:text-accent-500 flex-shrink-0 font-medium">
            {block.entries} {t('knowledgeBlocks.entriesShort') || 'entries'}
          </span>
        </div>
        {block.description && (
          <p className="text-xs text-accent-600 dark:text-accent-400 line-clamp-1">
            {block.description}
          </p>
        )}
        <div className="flex items-center justify-between mt-2 pt-2 border-t border-accent-200 dark:border-accent-800">
          <div className="flex items-center gap-1.5">
            {block.permanent ? (
              <span className="text-[10px] bg-accent-200 dark:bg-accent-800 text-accent-700 dark:text-accent-300 px-1.5 py-0.5 rounded">
                {t("knowledgeBlocks.permanent") || "Permanent"}
              </span>
            ) : (
              <>
                <button
                  onClick={() => handleEditBlock(block)}
                  className="p-1 text-accent-700 dark:text-accent-300 hover:bg-accent-100 dark:hover:bg-accent-800 rounded transition-colors"
                  title={t("knowledgeBlocks.edit")}
                >
                  <Edit3 size={12} />
                </button>
                <button
                  onClick={() => handleDeleteBlock(block.id)}
                  className="p-1 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                  title={t("knowledgeBlocks.delete") || "Delete"}
                >
                  <Trash2 size={12} />
                </button>
              </>
            )}
          </div>
          <div className={`w-2 h-2 rounded-full ${block.active ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600'}`} />
        </div>
      </div>
    );
  };

  // Компонент для рендеру одного блоку (повний)
  const BlockItemFull = ({ block }) => {
    return (
      <div
        className={`border rounded-xl p-4 ${
          block.permanent
            ? "bg-accent-100 dark:bg-accent-900/30 border-accent-300 dark:border-accent-700"
            : "bg-accent-50 dark:bg-accent-900/20 hover:bg-accent-100 dark:hover:bg-accent-900/40 border-accent-200 dark:border-accent-800"
        } transition`}
      >
        <div className="flex flex-col justify-between h-full">
          <div>
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <p className="font-semibold text-accent-900 dark:text-accent-100 truncate" title={block.name}>{block.name}</p>
                {knowledgeSplitEnabled && block.target_scope && block.target_scope !== 'all' && (
                  <span className={`ml-2 px-2 py-0.5 text-xs rounded-full font-medium ${
                    block.target_scope === 'assistant'
                      ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300'
                      : 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
                  }`}>
                    {block.target_scope === 'assistant'
                      ? (t('training.scopeBadgeAssistant') || 'Oleg')
                      : (t('training.scopeBadgeManager') || 'Vasya')}
                  </span>
                )}
                {block.permanent && (
                  <span className="text-xs bg-accent-200 dark:bg-accent-800 text-accent-700 dark:text-accent-300 px-2 py-0.5 rounded flex-shrink-0">
                    {t("knowledgeBlocks.permanent") || "Permanent"}
                  </span>
                )}
              </div>
              <span className="text-xs text-accent-500 dark:text-accent-500 flex-shrink-0 font-medium">
                {t('knowledgeBlocks.entries', { count: block.entries })}
              </span>
            </div>
            {block.description && (
              <p className="text-sm text-accent-600 dark:text-accent-400 line-clamp-2">
                {block.description}
              </p>
            )}
          </div>

          <div className="flex items-center justify-between mt-4 pt-3 border-t border-accent-200 dark:border-accent-800">
            {!block.permanent ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleEditBlock(block)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-accent-700 dark:text-accent-300 hover:bg-accent-100 dark:hover:bg-accent-800 rounded-lg transition-colors"
                  title={t("knowledgeBlocks.edit")}
                >
                  <Edit3 size={14} />
                  <span>{t("knowledgeBlocks.edit")}</span>
                </button>
                <button
                  onClick={() => handleDeleteBlock(block.id)}
                  className="p-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                  title={t("knowledgeBlocks.delete") || "Delete"}
                >
                  <Trash2 size={18} />
                </button>
              </div>
            ) : (
              <div className="text-xs text-accent-500 dark:text-accent-500">
                {t("knowledgeBlocks.permanentNote") || "Permanent blocks cannot be edited"}
              </div>
            )}

            {/* Toggle switch */}
            <div className="flex items-center gap-2">
              <Power size={14} className={`${block.active ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'}`} />
              <label
                className={`relative inline-flex items-center ${
                  block.permanent
                    ? "cursor-not-allowed opacity-60"
                    : "cursor-pointer"
                }`}
                title={block.active ? (t("knowledgeBlocks.active") || "Active") : (t("knowledgeBlocks.inactive") || "Inactive")}
              >
                <input
                  type="checkbox"
                  checked={block.active}
                  onChange={() => toggleBlock(block.id)}
                  disabled={block.permanent}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-300 dark:bg-gray-600 rounded-full peer peer-checked:bg-green-500 dark:peer-checked:bg-green-600 transition-colors"></div>
                <div className="absolute left-[2px] top-[2px] bg-white dark:bg-gray-200 w-5 h-5 rounded-full shadow-md transition-transform peer-checked:translate-x-5"></div>
              </label>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <>
      <div className="card">
        {/* Header */}
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-accent-900 dark:text-accent-400">
            {t("knowledgeBlocks.title")} ({blocks.length})
          </h3>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-3 py-2 bg-accent-900 dark:bg-accent-700 text-white rounded-lg hover:bg-accent-800 dark:hover:bg-accent-600 transition text-sm font-medium"
          >
            {t("knowledgeBlocks.add")}
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center items-center py-8">
            <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={24} />
          </div>
        ) : blocks.length === 0 ? (
          <div className="text-center py-8">
            <Database className="mx-auto text-gray-300 dark:text-gray-600 mb-3" size={40} />
            <p className="text-gray-500 dark:text-gray-400">
              {t("knowledgeBlocks.noBlocks") || "No knowledge blocks yet"}
            </p>
          </div>
        ) : (
          <>
            {/* Топ 4 блоки */}
            <div className="grid grid-cols-2 gap-3">
              {previewBlocks.map((block) => (
                <BlockItemCompact key={block.id} block={block} />
              ))}
            </div>

            {/* Кнопка See More */}
            {blocks.length > 4 && (
              <button
                onClick={() => setShowAllModal(true)}
                className="w-full mt-4 py-2.5 px-4 flex items-center justify-center gap-2 text-sm font-medium text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 bg-primary-50 dark:bg-primary-900/20 hover:bg-primary-100 dark:hover:bg-primary-900/30 rounded-lg transition-colors"
              >
                <Boxes size={18} />
                {t('knowledgeBlocks.seeAll') || 'See all blocks'} ({blocks.length})
                <ChevronRight size={16} />
              </button>
            )}
          </>
        )}
      </div>

      {/* Модалка з усіма блоками */}
      {showAllModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => setShowAllModal(false)}
        >
          <div 
            className="relative w-full max-w-3xl max-h-[85vh] bg-white dark:bg-gray-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="sticky top-0 z-10 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                  {t('knowledgeBlocks.allBlocks') || 'All Knowledge Blocks'} 
                  <span className="ml-2 text-sm font-normal text-gray-500 dark:text-gray-400">
                    ({filteredAndSortedBlocks.length} {t('training.of') || 'of'} {blocks.length})
                  </span>
                </h2>
                <button
                  onClick={() => setShowAllModal(false)}
                  className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  <X size={20} />
                </button>
              </div>

              {/* Пошук */}
              <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-500" size={18} />
                <input
                  type="text"
                  placeholder={t('knowledgeBlocks.searchBlocks') || 'Search blocks...'}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="input pl-10 w-full"
                  autoFocus
                />
              </div>

              {/* Фільтри та сортування */}
              <div className="flex flex-col sm:flex-row gap-3">
                {/* Фільтр по статусу */}
                <div className="flex items-center gap-2 flex-wrap flex-1">
                  <Filter size={16} className="text-gray-400 dark:text-gray-500 flex-shrink-0" />
                  <button
                    onClick={() => setFilterStatus('all')}
                    className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                      filterStatus === 'all'
                        ? 'bg-primary-500 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                  >
                    {t('knowledgeBlocks.filter.all') || 'All'} ({stats.all})
                  </button>
                  <button
                    onClick={() => setFilterStatus('active')}
                    className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                      filterStatus === 'active'
                        ? 'bg-green-500 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                  >
                    {t('knowledgeBlocks.filter.active') || 'Active'} ({stats.active})
                  </button>
                  <button
                    onClick={() => setFilterStatus('inactive')}
                    className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                      filterStatus === 'inactive'
                        ? 'bg-gray-500 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                  >
                    {t('knowledgeBlocks.filter.inactive') || 'Inactive'} ({stats.inactive})
                  </button>
                </div>

                {/* Фільтр по scope */}
                {knowledgeSplitEnabled && (
                  <select
                    value={filterScope}
                    onChange={(e) => setFilterScope(e.target.value)}
                    className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  >
                    <option value="all_scopes">{t('training.scopeFilter') || 'All scopes'}</option>
                    <option value="all">{t('training.scopeAll') || 'Shared'}</option>
                    <option value="assistant">{t('training.scopeAssistant') || 'Oleg only'}</option>
                    <option value="manager">{t('training.scopeManager') || 'Vasya only'}</option>
                  </select>
                )}

                {/* Сортування */}
                <div className="flex items-center gap-2">
                  <ArrowUpDown size={16} className="text-gray-400 dark:text-gray-500 flex-shrink-0" />
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    className="input text-sm py-1.5 pr-8 min-w-[150px]"
                  >
                    {sortOptions.map(option => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* Список блоків */}
            <div className="overflow-y-auto p-6 pt-4" style={{ maxHeight: 'calc(85vh - 220px)' }}>
              {filteredAndSortedBlocks.length === 0 ? (
                <div className="text-center py-12">
                  <Database className="mx-auto text-gray-300 dark:text-gray-600 mb-4" size={48} />
                  <p className="text-gray-500 dark:text-gray-400">
                    {t('knowledgeBlocks.noBlocksFound') || 'No blocks found'}
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {filteredAndSortedBlocks.map((block) => (
                    <BlockItemFull key={block.id} block={block} />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editingBlock && (
        <KnowledgeBlockEditModal
          block={editingBlock}
          isOpen={!!editingBlock}
          onClose={() => setEditingBlock(null)}
          onSave={handleSaveBlock}
        />
      )}

      {/* Add Modal */}
      {showAddModal && (
        <KnowledgeBlockAddModal
          isOpen={showAddModal}
          onClose={() => setShowAddModal(false)}
          onSave={handleCreateBlock}
        />
      )}
    </>
  );
};

export default KnowledgeBlocks;
