import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { ragAPI } from "../../api/agent";

const LLMProviderCard = () => {
  const { t } = useTranslation();
  const [providers, setProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showProviderSelect, setShowProviderSelect] = useState(false);

  useEffect(() => {
    loadProviders();
  }, []);

  const loadProviders = async () => {
    try {
      const response = await ragAPI.getLLMProviders();
      const providersList = response.data?.providers || [];
      
      setProviders(providersList);
      
      // Знаходимо обраного провайдера
      const selected = providersList.find(p => p.is_selected);
      if (selected) {
        setSelectedProvider(selected);
      } else {
        // Якщо немає обраного, беремо дефолтного
        const defaultProvider = providersList.find(p => p.is_default);
        if (defaultProvider) {
          setSelectedProvider(defaultProvider);
        }
      }
    } catch (error) {
      console.error("Failed to load LLM providers:", error);
      setProviders([]);
    }
  };

  const handleSwitchProvider = async (providerId) => {
    setLoading(true);
    try {
      const providerToSwitch = providers.find(p => p.id === providerId);
      
      if (!providerToSwitch) {
        console.error("Provider not found");
        return;
      }
      
      await ragAPI.setLLMProvider(providerId);
      
      setSelectedProvider(providerToSwitch);
      setShowProviderSelect(false);
      
      console.log(`Successfully switched to LLM provider: ${providerToSwitch.name}`);
    } catch (error) {
      console.error("Failed to switch LLM provider:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-3">
        {t("llmProvider.title") || "LLM Provider"}
      </h3>

      <p className="text-sm text-gray-600 mb-4">
        {t("llmProvider.description") || "Select the AI model for generating responses"}
      </p>

      {/* Switch Provider */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-gray-700">
            {t("llmProvider.currentProvider") || "Current Provider"}:
          </label>
          <button
            onClick={() => setShowProviderSelect(!showProviderSelect)}
            className="text-xs text-primary-600 hover:text-primary-700 font-medium"
          >
            {showProviderSelect ? (t("llmProvider.cancel") || "Cancel") : (t("llmProvider.switchProvider") || "Switch Provider")}
          </button>
        </div>
        
        {!showProviderSelect ? (
          <div className="border rounded-lg p-3 bg-gray-50">
            <p className="text-sm font-medium">
              {selectedProvider?.name || (t("llmProvider.noProviderSelected") || "No provider selected")}
            </p>
            {selectedProvider && (
              <div className="mt-2 space-y-1">
                <p className="text-xs text-gray-600">
                  <span className="font-medium">{t("llmProvider.model") || "Model"}:</span> {selectedProvider.model_name}
                </p>
                <p className="text-xs text-gray-600">
                  <span className="font-medium">{t("llmProvider.type") || "Type"}:</span> {selectedProvider.provider_type}
                </p>
                {selectedProvider.api_endpoint && (
                  <p className="text-xs text-gray-600">
                    <span className="font-medium">{t("llmProvider.endpoint") || "Endpoint"}:</span> {selectedProvider.api_endpoint}
                  </p>
                )}
                <p className="text-xs text-gray-600">
                  <span className="font-medium">{t("llmProvider.maxTokens") || "Max Tokens"}:</span> {selectedProvider.max_tokens}
                </p>
                <p className="text-xs text-gray-600">
                  <span className="font-medium">{t("llmProvider.temperature") || "Temperature"}:</span> {selectedProvider.temperature}
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="border rounded-lg p-2 bg-white">
            {loading ? (
              <p className="text-sm text-gray-500">{t("llmProvider.switching") || "Switching..."}</p>
            ) : (
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {providers.map((provider) => (
                  <button
                    key={provider.id}
                    onClick={() => handleSwitchProvider(provider.id)}
                    className={`w-full text-left px-2 py-2 rounded text-sm transition ${
                      provider.id === selectedProvider?.id
                        ? "bg-primary-100 text-primary-700 font-medium border border-primary-300"
                        : "hover:bg-gray-100 text-gray-700 border border-transparent"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="font-medium">{provider.name}</div>
                        {provider.description && (
                          <div className="text-xs text-gray-500 mt-0.5">{provider.description}</div>
                        )}
                        <div className="text-xs text-gray-500 mt-1">
                          {provider.model_name} • {provider.provider_type}
                          {provider.api_endpoint && ` • ${provider.api_endpoint.split('//')[1]}`}
                        </div>
                      </div>
                      {provider.id === selectedProvider?.id && (
                        <span className="text-xs ml-2">✓</span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default LLMProviderCard;

