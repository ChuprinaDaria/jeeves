import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Edit3, Loader2, Trash2, Power } from "lucide-react";
import { clientAPI } from "../../api/client";
import KnowledgeBlockEditModal from "./KnowledgeBlockEditModal";
import KnowledgeBlockAddModal from "./KnowledgeBlockAddModal";

const KnowledgeBlocks = () => {
  const [blocks, setBlocks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editingBlock, setEditingBlock] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const { t } = useTranslation();

  useEffect(() => {
    loadBlocks();
  }, []);

  const loadBlocks = async () => {
    setLoading(true);
    try {
      const response = await clientAPI.getKnowledgeBlocks();
      const blocksData = response.data || [];
      
      // Перетворюємо дані з API
      const formattedBlocks = blocksData.map((block) => ({
        id: block.id,
        name: block.name,
        description: block.description || "",
        entries: block.entries_count || 0,
        active: block.is_active,
        permanent: block.is_permanent,
        ...block, // Зберігаємо всі дані для редагування
      }));
      
      setBlocks(formattedBlocks);
    } catch (error) {
      console.error("Failed to load knowledge blocks:", error);
      // Fallback на мок дані тільки "Clients Chats"
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
      const response = await clientAPI.createKnowledgeBlock({
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

  return (
    <>
      <div className="card">
        {/* Header */}
        <div className="flex justify-between items-center mb-5">
          <h3 className="text-lg font-semibold text-accent-900 dark:text-accent-400">
            {t("knowledgeBlocks.title")}
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
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {blocks.map((block) => (
              <div
                key={block.id}
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
                        <p className="font-semibold text-accent-900 dark:text-accent-100 truncate">{block.name}</p>
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
            ))}
          </div>
        )}
      </div>

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
