import api from './axios';

// RAG API
export const ragAPI = {
  // Завантажити документ для RAG
  uploadDocument: (file, title) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    return api.post('/rag/upload/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  // Публічний чат з RAG системою
  chat: (message) => api.post('/rag/chat/', { message }),

  // Отримати список embedding моделей
  getEmbeddingModels: () => api.get('/rag/embedding-models/'),

  // Отримати список AI моделей з mg.nexelin.com
  getAIModels: () => api.get('/rag/ai-models/'),

  // Отримати список LLM провайдерів
  getLLMProviders: () => api.get('/rag/llm-providers/'),

  // Отримати готові пари LLM + Embedding
  getModelPairs: () => api.get('/rag/model-pairs/'),

  // Встановити LLM провайдера для клієнта
  setLLMProvider: (providerId) => 
    api.post('/rag/client/llm-provider/', { provider_id: providerId }),

  // Встановити embedding або AI модель для клієнта
  setEmbeddingModel: (modelId, modelType = 'embedding') => 
    api.post('/rag/client/embedding-model/', { model_id: modelId, model_type: modelType }),

  // Переіндексувати документи клієнта
  reindexDocuments: () => api.post('/rag/client/reindex/'),

  // Text-to-Speech (TTS)
  textToSpeech: (text, voice = 'alloy') => 
    api.post('/restaurant/tts/', { text, voice }, {
      responseType: 'blob', // Для отримання audio файлу
    }),

  // Speech-to-Text (STT)
  speechToText: (audioFile) => {
    const formData = new FormData();
    formData.append('file', audioFile);
    return api.post('/restaurant/stt/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

// Legacy agentAPI для сумісності - перенаправляємо на нові RAG ендпоінти
export const agentAPI = {
  uploadFile: (file, title) => ragAPI.uploadDocument(file, title),
  testChat: (message) => ragAPI.chat(message),
  reindexDocuments: () => ragAPI.reindexDocuments(),
};
