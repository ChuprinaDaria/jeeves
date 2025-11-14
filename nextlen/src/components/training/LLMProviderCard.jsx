import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { ragAPI } from "../../api/agent";
import { CheckCircle, AlertTriangle, Cpu, Database } from "lucide-react";

const LLMProviderCard = () => {
  const { t } = useTranslation();
  const [pairs, setPairs] = useState([]);
  const [selectedPair, setSelectedPair] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showPairSelect, setShowPairSelect] = useState(false);

  useEffect(() => {
    loadPairs();
  }, []);

  const loadPairs = async () => {
    setLoading(true);
    try {
      const response = await ragAPI.getModelPairs();
      const pairsData = response.data?.pairs || [];
      
      console.log('📦 Model Pairs from API:', pairsData);
      
      setPairs(pairsData);
      
      // Знаходимо поточно обрану пару
      const currentPair = pairsData.find(p => p.is_selected);
      setSelectedPair(currentPair || null);
      
      console.log('✅ Selected pair:', currentPair);
    } catch (error) {
      console.error("Failed to load model pairs:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPair = async (pair) => {
    setLoading(true);
    try {
      // Встановлюємо LLM провайдера
      await ragAPI.setLLMProvider(pair.llm_id);
      
      // Встановлюємо Embedding модель
      await ragAPI.setEmbeddingModel(pair.embedding_id, 'embedding');
      
      setSelectedPair(pair);
      setShowPairSelect(false);
      
      // Перезавантажуємо пари щоб оновити is_selected
      loadPairs();
      
      console.log(`✅ Successfully switched to: ${pair.display_name}`);
    } catch (error) {
      console.error("Failed to switch model pair:", error);
      alert(t('modelStatus.switchError') || 'Failed to switch models');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">
        {t("modelStatus.llmAndEmbedding") || "LLM & Embedding Models"}
      </h3>

      {/* Поточна пара */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-gray-700">
            {t("modelStatus.currentPair") || "Current Model Pair"}:
          </label>
          <button
            onClick={() => setShowPairSelect(!showPairSelect)}
            className="text-xs text-primary-600 hover:text-primary-700 font-medium"
            disabled={loading}
          >
            {showPairSelect ? 
              (t("modelStatus.cancel") || "Cancel") : 
              (t("modelStatus.changePair") || "Change Pair")}
          </button>
        </div>

        {!showPairSelect ? (
          <div className="border rounded-lg p-3 bg-gray-50">
            {selectedPair ? (
              <div className="space-y-3">
                <div className="flex items-start gap-2">
                  <Cpu size={18} className="text-blue-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {selectedPair.llm_name}
                    </p>
                    <p className="text-xs text-gray-600">
                      {selectedPair.llm_provider_type} • {selectedPair.llm_model_name}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-start gap-2">
                  <Database size={18} className="text-purple-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {selectedPair.embedding_name}
                    </p>
                    <p className="text-xs text-gray-600">
                      {selectedPair.embedding_provider} • {selectedPair.embedding_dimensions}D
                      {selectedPair.embedding_server_type && ` • ${selectedPair.embedding_server_type}`}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                {t("modelStatus.noPairSelected") || "No model pair selected"}
              </p>
            )}
          </div>
        ) : (
          <div className="border rounded-lg p-3 bg-white max-h-96 overflow-y-auto">
            {loading ? (
              <p className="text-sm text-gray-500">{t("modelStatus.loading") || "Loading..."}</p>
            ) : pairs.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs text-gray-600 mb-3 flex items-center gap-1">
                  <CheckCircle size={14} className="text-green-500" />
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
                          ? "bg-primary-50 border-primary-300 text-primary-700"
                          : "bg-gray-50 border-gray-200 hover:bg-gray-100 hover:border-gray-300 text-gray-700"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 space-y-2">
                          <div className="font-medium text-gray-900 flex items-center gap-2">
                            {pair.display_name}
                            {isCurrent && <CheckCircle size={16} className="text-primary-600" />}
                          </div>
                          
                          <div className="flex items-center gap-2 text-xs text-gray-600">
                            <Cpu size={14} className="text-blue-600 flex-shrink-0" />
                            <span>{pair.llm_provider_type} • {pair.llm_model_name}</span>
                          </div>
                          
                          <div className="flex items-center gap-2 text-xs text-gray-600">
                            <Database size={14} className="text-purple-600 flex-shrink-0" />
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
              <p className="text-sm text-gray-500">
                {t("modelStatus.noCompatiblePairs") || "No compatible pairs found"}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Додаткова інформація */}
      <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-xs text-blue-800 flex items-start gap-2">
          <span className="text-base">💡</span>
          <span>{t("modelStatus.pairInfo") || "LLM generates responses, Embedding converts text to vectors for search"}</span>
        </p>
      </div>
    </div>
  );
};

export default LLMProviderCard;
