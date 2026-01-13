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

  // Публічний чат з RAG системою (підтримка тексту, зображень та контексту діалогу)
  chat: (message, imageFile = null, context = null) => {
    if (imageFile) {
      // Якщо є зображення, відправляємо як multipart/form-data
      const formData = new FormData();
      formData.append('message', message || '');
      formData.append('image', imageFile);
      if (context) {
        // Контекст передаємо як JSON-рядок
        formData.append('context', JSON.stringify(context));
      }
      return api.post('/rag/chat/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    }
    // Якщо тільки текст, відправляємо як JSON
    const payload = { message };
    if (context) {
      payload.context = context;
    }
    return api.post('/rag/chat/', payload);
  },

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

  // Зберегти Q&A пару в базу знань
  saveSandboxQA: (question, answer) => api.post('/rag/sandbox/save-qa/', { question, answer }),

  // Зберегти фото з описом в базу знань
  saveSandboxPhoto: (photoFile, description, isClean = false) => {
    const formData = new FormData();
    formData.append('photo', photoFile);
    formData.append('description', description);
    formData.append('is_clean', isClean ? 'true' : 'false');
    return api.post('/rag/sandbox/save-photo/', formData, {
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
