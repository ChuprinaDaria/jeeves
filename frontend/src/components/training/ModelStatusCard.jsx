import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { ragAPI } from "../../api/agent";
import { clientAPI } from "../../api/client";

const ModelStatusCard = () => {
  const { t } = useTranslation();
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showModelSelect, setShowModelSelect] = useState(false);
  const [modelStatus, setModelStatus] = useState({
    status: "Unknown",
    lastUpdated: "Unknown",
    dataSources: 0,
    knowledgeBlocks: 0,
    error: null,
  });
  const [statusLoading, setStatusLoading] = useState(false);

  useEffect(() => {
    loadModels();
    loadModelStatus();
  }, []);

  const loadModels = async () => {
    try {
      // Отримуємо AI моделі з API
      const aiResponse = await ragAPI.getAIModels();
      const aiModels = aiResponse.data?.models || [];
      
      // Отримуємо embedding моделі та інформацію про клієнта
      const embeddingResponse = await ragAPI.getEmbeddingModels();
      const embeddingModels = embeddingResponse.data?.models || [];
      
      // Отримуємо поточну AI модель з клієнта (якщо є)
      const clientResponse = await clientAPI.getMe().catch(() => null);
      const clientAiModel = clientResponse?.data?.features?.ai_model;
      
      // Об'єднуємо моделі
      const allModels = [
        ...aiModels.map(m => ({
          id: m.id,
          name: m.name,
          description: m.description,
          pl: parseFloat(m.pl) || 0,
          pc: parseFloat(m.pc) || 0,
          ph: parseFloat(m.ph) || 0,
          active: m.active,
          type: 'ai',
          updated_at: m.updated_at
        })),
        ...embeddingModels.map(m => ({
          id: m.id,
          name: m.name || m.model_name,
          description: m.description || `${m.provider} - ${m.dimensions} dimensions`,
          dimensions: m.dimensions,
          type: 'embedding',
          is_selected: m.is_selected
        }))
      ];
      
      setModels(allModels);
      
      // Встановити поточну модель (перевага клієнтській AI моделі, потім embedding, потім активна AI)
      if (clientAiModel) {
        const selectedAIModel = allModels.find(m => m.type === 'ai' && m.id === clientAiModel.id);
        if (selectedAIModel) {
          setSelectedModel({
            id: selectedAIModel.id,
            name: selectedAIModel.name,
            type: 'ai',
            pl: selectedAIModel.pl,
            pc: selectedAIModel.pc,
            ph: selectedAIModel.ph
          });
          return;
        }
      }
      
      const selectedEmbedding = embeddingModels.find(m => m.is_selected);
      if (selectedEmbedding) {
        setSelectedModel({
          id: selectedEmbedding.id,
          name: selectedEmbedding.name || selectedEmbedding.model_name,
          type: 'embedding',
          dimensions: selectedEmbedding.dimensions
        });
        return;
      }
      
      // Якщо немає вибраної моделі, встановлюємо першу доступну embedding модель як fallback
      const firstEmbedding = embeddingModels[0];
      if (firstEmbedding) {
        setSelectedModel({
          id: firstEmbedding.id,
          name: firstEmbedding.name || firstEmbedding.model_name,
          type: 'embedding',
          dimensions: firstEmbedding.dimensions
        });
        return;
      }
      
      const activeAIModel = aiModels.find(m => m.active);
      if (activeAIModel) {
        setSelectedModel({
          id: activeAIModel.id,
          name: activeAIModel.name,
          type: 'ai',
          pl: parseFloat(activeAIModel.pl) || 0,
          pc: parseFloat(activeAIModel.pc) || 0,
          ph: parseFloat(activeAIModel.ph) || 0
        });
      }
    } catch (error) {
      console.error("Failed to load models:", error);
      // Якщо помилка завантаження, залишаємо порожній список
      setModels([]);
      setSelectedModel(null);
    }
  };

  const handleSwitchModel = async (modelId) => {
    setLoading(true);
    try {
      const modelToSwitch = models.find(m => m.id === modelId);
      
      if (!modelToSwitch) {
        console.error("Model not found");
        return;
      }
      
      // Для embedding та AI моделей використовуємо той самий endpoint
      await ragAPI.setEmbeddingModel(modelId, modelToSwitch.type);
      
      setSelectedModel(modelToSwitch);
      setShowModelSelect(false);
      
      // Перезавантажуємо статус моделі після зміни
      loadModelStatus();
      
      // Можна додати повідомлення про успіх
      console.log(`Successfully switched to model: ${modelToSwitch.name}`);
    } catch (error) {
      console.error("Failed to switch model:", error);
      // Можна додати повідомлення про помилку
    } finally {
      setLoading(false);
    }
  };

  const loadModelStatus = async () => {
    setStatusLoading(true);
    try {
      const response = await clientAPI.getModelStatus();
      const data = response.data;
      
      setModelStatus({
        status: data.status || "Unknown",
        lastUpdated: data.last_updated || "Unknown",
        dataSources: data.data_sources || 0,
        knowledgeBlocks: data.knowledge_blocks_count || 0,
        error: data.error || null,
      });
    } catch (err) {
      console.error("Failed to load model status:", err);
      setModelStatus({
        status: "Error",
        lastUpdated: "Unknown",
        dataSources: 0,
        knowledgeBlocks: 0,
        error: err.message || "Failed to check model status",
      });
    } finally {
      setStatusLoading(false);
    }
  };

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-3 text-gray-900 dark:text-gray-100">
        {t("modelStatus.title")}
      </h3>

      {statusLoading ? (
        <div className="bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-700 rounded-lg p-3 mb-4">
          <p className="text-gray-600 dark:text-gray-400 font-medium">
            {t("modelStatus.checking") || "Checking status..."}
          </p>
        </div>
      ) : modelStatus.status === "Active" ? (
        <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 rounded-lg p-3 mb-4">
          <p className="text-green-700 dark:text-green-300 font-medium">
            ✓ {modelStatus.status} — {t("modelStatus.statusMessage") || "Model is live and responding"}
          </p>
        </div>
      ) : (
        <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded-lg p-3 mb-4">
          <p className="text-red-700 dark:text-red-300 font-medium">
            ✗ {modelStatus.status || "Inactive"} — {t("modelStatus.statusInactive") || "Model is not responding"}
          </p>
          {modelStatus.error && (
            <p className="text-red-600 dark:text-red-400 text-xs mt-1">
              {t("modelStatus.error") || "Error"}: {modelStatus.error}
            </p>
          )}
        </div>
      )}

      <div className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
        <p>
          <strong>{t("modelStatus.lastUpdated")}:</strong> {modelStatus.lastUpdated === "Unknown" ? (t("modelStatus.unknown") || "Unknown") : modelStatus.lastUpdated}
        </p>
        <p>
          <strong>{t("modelStatus.dataSources")}:</strong> {modelStatus.dataSources}
        </p>
        <p>
          <strong>{t("modelStatus.knowledgeBlocks")}:</strong> {modelStatus.knowledgeBlocks}
        </p>
      </div>

      {/* Switch Model */}
      <div className="mt-4">
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {t("modelStatus.embeddingModel") || "Embedding Model"}:
          </label>
          <button
            onClick={() => setShowModelSelect(!showModelSelect)}
            className="text-xs text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 font-medium"
          >
            {showModelSelect ? (t("modelStatus.cancel") || "Cancel") : (t("modelStatus.switchModel") || "Switch Model")}
          </button>
        </div>
        
        {!showModelSelect ? (
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-2 bg-gray-50 dark:bg-gray-700/50">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {selectedModel?.name || (t("modelStatus.noModelSelected") || "No model selected")}
            </p>
            {selectedModel && selectedModel.type === 'ai' && (
              <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                <div>
                  {t("modelStatus.local") || "Local"}: {selectedModel.pl} • {t("modelStatus.cloud") || "Cloud"}: {selectedModel.pc} • {t("modelStatus.hybrid") || "Hybrid"}: {selectedModel.ph}
                </div>
              </div>
            )}
            {selectedModel && selectedModel.type === 'embedding' && (
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {selectedModel.dimensions} {t("modelStatus.dimensions") || "dimensions"}
              </p>
            )}
          </div>
        ) : (
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-2 bg-white dark:bg-gray-800">
            {loading ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">{t("modelStatus.switching") || "Switching..."}</p>
            ) : (
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {models.map((m) => {
                  const isUnsupported = m.type === 'embedding' && m.dimensions > 2000;
                  return (
                  <button
                    key={m.id}
                    onClick={() => !isUnsupported && handleSwitchModel(m.id)}
                    disabled={isUnsupported}
                    className={`w-full text-left px-2 py-1.5 rounded text-sm transition ${
                      isUnsupported
                        ? "bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed opacity-60"
                        : m.id === selectedModel?.id
                        ? "bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium"
                        : "hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="font-medium">{m.name}</div>
                        {m.description && (
                          <div className="text-xs text-gray-500 dark:text-gray-400">{m.description}</div>
                        )}
                      </div>
                      {m.id === selectedModel?.id && (
                        <span className="text-xs ml-2">✓</span>
                      )}
                    </div>
                    {m.type === 'ai' && (
                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        <span className="mr-2">Local: {m.pl}</span>
                        <span className="mr-2">Cloud: {m.pc}</span>
                        <span>Hybrid: {m.ph}</span>
                      </div>
                    )}
                    {m.type === 'embedding' && m.dimensions && (
                      <div className="text-xs mt-1">
                        <span className="text-gray-500 dark:text-gray-400">{m.dimensions} {t("modelStatus.dimensions") || "dimensions"}</span>
                        {m.dimensions > 2000 && (
                          <span className="ml-2 text-red-500 dark:text-red-400 font-medium">⚠ {t("modelStatus.unsupported") || "Unsupported (max 2000)"}</span>
                        )}
                      </div>
                    )}
                  </button>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      <button className="mt-4 w-full border border-gray-300 dark:border-gray-600 rounded-lg py-2 hover:bg-gray-100 dark:hover:bg-gray-700 transition text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800">
        {t("modelStatus.viewHistory")}
      </button>
    </div>
  );
};

export default ModelStatusCard;
