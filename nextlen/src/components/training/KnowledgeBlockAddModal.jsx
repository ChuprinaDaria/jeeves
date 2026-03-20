import { useState } from "react";
import { useTranslation } from "react-i18next";
import { X } from "lucide-react";
import { useAuth } from '../../context/AuthContext';

const KnowledgeBlockAddModal = ({ isOpen, onClose, onSave }) => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const knowledgeSplitEnabled = user?.feature_flags?.mcp_knowledge_split;
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [targetScope, setTargetScope] = useState('all');

  const handleSave = () => {
    if (!name.trim()) {
      alert(t("knowledgeBlocks.nameRequired") || "Block name is required");
      return;
    }
    onSave(name, description, knowledgeSplitEnabled ? targetScope : 'all');
    setName("");
    setDescription("");
    setTargetScope('all');
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {t("knowledgeBlocks.addBlock")}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
          >
            <X size={20} />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t("knowledgeBlocks.blockName")} *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 dark:focus:ring-primary-400 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              placeholder={t("knowledgeBlocks.blockNamePlaceholder")}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t("knowledgeBlocks.description")}
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 dark:focus:ring-primary-400 focus:border-transparent h-24 resize-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              placeholder={t("knowledgeBlocks.descriptionPlaceholder")}
            />
          </div>

          {knowledgeSplitEnabled && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('training.scopeFilter') || 'Scope'}
              </label>
              <select
                value={targetScope}
                onChange={(e) => setTargetScope(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 dark:focus:ring-primary-400 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              >
                <option value="all">{t('training.scopeAll') || 'Shared (Assistant + Manager)'}</option>
                <option value="assistant">{t('training.scopeAssistant') || 'Assistant only'}</option>
                <option value="manager">{t('training.scopeManager') || 'Manager only'}</option>
              </select>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800"
          >
            {t("common.cancel")}
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-primary-600 dark:bg-primary-500 text-white rounded-lg hover:bg-primary-700 dark:hover:bg-primary-600 transition"
          >
            {t("knowledgeBlocks.create")}
          </button>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBlockAddModal;

