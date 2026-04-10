import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { ragAPI } from "../../api/agent";
import { clientAPI } from "../../api/client";
import { CheckCircle, AlertTriangle, Cpu, Database, Loader2 } from "lucide-react";

const LLMProviderCard = () => {
  const { t } = useTranslation();
  const [pairs, setPairs] = useState([]);
  const [selectedPair, setSelectedPair] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showPairSelect, setShowPairSelect] = useState(false);
  const [modelStatuses, setModelStatuses] = useState({
    llm: null, // null = checking, true = OK, false = error
    embedding: null,
  });
  const [checkingStatus, setCheckingStatus] = useState(false);

  useEffect(() => {
    loadPairs();
  }, []);

  useEffect(() => {
    if (selectedPair) {
      checkModelStatuses();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPair?.id]);

  const loadPairs = async () => {
    setLoading(true);
    try {
      const response = await ragAPI.getModelPairs();
      const pairsData = response.data?.pairs || [];
      
      console.log('📦 Model Pairs from API:', pairsData);
      
      setPairs(pairsData);
      
      // Першочергово беремо пару, позначену бекендом (is_selected)
      // Бекенд тепер завжди повертає правильний is_selected на основі збережених даних
      let currentPair = pairsData.find(p => p.is_selected);
      
      // Якщо бекенд не відмітив is_selected (тільки якщо немає client у запиті) —
      //    пробуємо відновити вибір з localStorage як fallback
      if (!currentPair) {
        // Спочатку пробуємо знайти за ID
        const savedId = localStorage.getItem('concierge_selected_model_pair_id');
        if (savedId) {
          currentPair = pairsData.find(p => String(p.id) === savedId) || null;
        }
        
        // Якщо не знайшли за ID, пробуємо знайти за llm_id + embedding_id
        if (!currentPair) {
          const savedLLMId = localStorage.getItem('concierge_selected_llm_id');
          const savedEmbeddingId = localStorage.getItem('concierge_selected_embedding_id');
          if (savedLLMId && savedEmbeddingId) {
            currentPair = pairsData.find(
              p => String(p.llm_id) === savedLLMId && String(p.embedding_id) === savedEmbeddingId
            ) || null;
          }
        }
      }
      
      setSelectedPair(currentPair || null);
      
      // Кешуємо вибір в localStorage тільки для fallback (якщо бекенд не повернув is_selected)
      // Але основним джерелом завжди є бекенд
      if (currentPair) {
        localStorage.setItem('concierge_selected_model_pair_id', String(currentPair.id));
        localStorage.setItem('concierge_selected_llm_id', String(currentPair.llm_id));
        localStorage.setItem('concierge_selected_embedding_id', String(currentPair.embedding_id));
      }
      
      console.log('✅ Selected pair:', currentPair);
    } catch (error) {
      console.error("Failed to load model pairs:", error);
    } finally {
      setLoading(false);
    }
  };

  const checkModelStatuses = async () => {
    if (!selectedPair) return;
    
    setCheckingStatus(true);
    setModelStatuses({ llm: null, embedding: null });
    
    try {
      // Перевіряємо статус моделей через API
      const response = await clientAPI.getModelStatus();
      const data = response.data;
      
      // Якщо статус "Active", обидві моделі працюють
      if (data?.status === "Active") {
        setModelStatuses({ llm: true, embedding: true });
      } else {
        // Якщо статус не "Active", моделі не працюють
        setModelStatuses({ llm: false, embedding: false });
      }
    } catch (err) {
      console.error("Failed to check model statuses:", err);
      // При помилці вважаємо, що моделі не працюють
      setModelStatuses({ llm: false, embedding: false });
    } finally {
      setCheckingStatus(false);
    }
  };

  const handleSelectPair = async (pair) => {
    setLoading(true);
    try {
      // Встановлюємо LLM провайдера
      await ragAPI.setLLMProvider(pair.llm_id);
      
      // Встановлюємо Embedding модель
      const embResponse = await ragAPI.setEmbeddingModel(pair.embedding_id, 'embedding');
      
      // Перевіряємо чи потрібна реіндексація
      if (embResponse.data?.reindex_required) {
        const reindexConfirm = confirm(
          t('modelStatus.reindexRequired') || 
          'This embedding model requires reindexing your documents. Documents will be reindexed automatically. Continue?'
        );
        if (!reindexConfirm) {
          setLoading(false);
          return;
        }
        // Тут можна додати автоматичну реіндексацію або показати прогрес
        // await ragAPI.reindexDocuments();
      }
      
      setShowPairSelect(false);
      
      // Перезавантажуємо пари щоб оновити is_selected з бекенду
      const response = await ragAPI.getModelPairs();
      const pairsData = response.data?.pairs || [];
      setPairs(pairsData);
      
      // Знаходимо поточно обрану пару з оновлених даних (бекенд тепер завжди повертає правильний is_selected)
      let currentPair = pairsData.find(p => p.is_selected);
      
      // Якщо бекенд не відмітив is_selected (малоймовірно, але для безпеки), використовуємо обрану пару
      if (!currentPair) {
        currentPair = pair;
      }
      
      setSelectedPair(currentPair);
      
      // Зберігаємо вибір в localStorage тільки як fallback
      if (currentPair) {
        localStorage.setItem('concierge_selected_model_pair_id', String(currentPair.id));
        localStorage.setItem('concierge_selected_llm_id', String(currentPair.llm_id));
        localStorage.setItem('concierge_selected_embedding_id', String(currentPair.embedding_id));
      }
      
      // Перевіряємо статус нових моделей
      await checkModelStatuses();
      
      console.log(`✅ Successfully switched to: ${pair.display_name}`);
      console.log(`✅ Selected pair after reload:`, currentPair);
    } catch (error) {
      console.error("Failed to switch model pair:", error);
      alert(t('modelStatus.switchError') || 'Failed to switch models');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    if (status === null) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
          <Loader2 size={12} className="animate-spin" />
          {t('modelStatus.checking') || 'Checking...'}
        </span>
      );
    }
    if (status === true) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 font-medium">
          <CheckCircle size={12} />
          {t('modelStatus.active') || t('modelStatus.ok') || 'Active'}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 font-medium">
        <AlertTriangle size={12} />
        {t('modelStatus.inactive') || 'Inactive'}
      </span>
    );
  };

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
        {t("modelStatus.llmAndEmbedding") || "LLM & Embedding Models"}
      </h3>

      {/* Поточна пара */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {t("modelStatus.currentPair") || "Current Model Pair"}:
          </label>
          <button
            onClick={() => setShowPairSelect(!showPairSelect)}
            className="text-xs text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 font-medium"
            disabled={loading}
          >
            {showPairSelect ? 
              (t("modelStatus.cancel") || "Cancel") : 
              (t("modelStatus.changePair") || "Change Pair")}
          </button>
        </div>

        {!showPairSelect ? (
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 bg-gray-50 dark:bg-gray-700/50">
            {selectedPair ? (
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2 flex-1">
                    <Cpu size={18} className="text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {selectedPair.llm_name}
                      </p>
                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        {selectedPair.llm_provider_type} • {selectedPair.llm_model_name}
                      </p>
                    </div>
                  </div>
                  {getStatusBadge(modelStatuses.llm)}
                </div>
                
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2 flex-1">
                    <Database size={18} className="text-purple-600 dark:text-purple-400 mt-0.5 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {selectedPair.embedding_name}
                      </p>
                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        {selectedPair.embedding_provider} • {selectedPair.embedding_dimensions}D
                        {selectedPair.embedding_server_type && ` • ${selectedPair.embedding_server_type}`}
                      </p>
                    </div>
                  </div>
                  {getStatusBadge(modelStatuses.embedding)}
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {t("modelStatus.noPairSelected") || "No model pair selected"}
              </p>
            )}
          </div>
        ) : (
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 bg-white dark:bg-gray-800 max-h-96 overflow-y-auto">
            {loading ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">{t("modelStatus.loading") || "Loading..."}</p>
            ) : pairs.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-3 flex items-center gap-1">
                  <CheckCircle size={14} className="text-green-500 dark:text-green-400" />
                  {t("modelStatus.compatiblePairsOnly") || "Showing only compatible pairs"}
                </p>
                
                {pairs.map((pair) => {
                  const isCurrent = selectedPair?.id === pair.id;
                  
                  return (
                    <button
                      key={pair.id}
                      onClick={() => handleSelectPair(pair)}
                      disabled={loading || isCurrent}
                      className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition border ${
                        isCurrent
                          ? "bg-primary-50 dark:bg-primary-900/30 border-primary-300 dark:border-primary-700 text-primary-700 dark:text-primary-300"
                          : "bg-gray-50 dark:bg-gray-700/50 border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 hover:border-gray-300 dark:hover:border-gray-500 text-gray-700 dark:text-gray-300"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 space-y-2">
                          <div className="font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2">
                            {pair.display_name}
                            {isCurrent && <CheckCircle size={16} className="text-primary-600 dark:text-primary-400" />}
                          </div>
                          
                          <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
                            <Cpu size={14} className="text-blue-600 dark:text-blue-400 flex-shrink-0" />
                            <span>{pair.llm_provider_type} • {pair.llm_model_name}</span>
                          </div>
                          
                          <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
                            <Database size={14} className="text-purple-600 dark:text-purple-400 flex-shrink-0" />
                            <span>
                              {pair.embedding_provider} • {pair.embedding_dimensions}D
                              {pair.embedding_server_type && ` • ${pair.embedding_server_type}`}
                            </span>
                          </div>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {t("modelStatus.noCompatiblePairs") || "No compatible pairs found"}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Додаткова інформація */}
      <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg">
        <p className="text-xs text-blue-800 dark:text-blue-300 flex items-start gap-2">
          <span className="text-base">💡</span>
          <span>{t("modelStatus.pairInfo") || "LLM generates responses, Embedding converts text to vectors for search"}</span>
        </p>
      </div>
    </div>
  );
};

export default LLMProviderCard;
