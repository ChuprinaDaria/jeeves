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

// MCP SSE Chat (used when mcp_real_agent flag is enabled)
export const mcpAPI = {
  chatSSE: (message, channel = 'sandbox', onToken, onDone, onError, onStatus, onToolEvent) => {
    const tag = localStorage.getItem('client_tag');
    const baseURL = api.defaults.baseURL || '';
    const url = `${baseURL}/mcp/chat/`;

    const body = JSON.stringify({ message, channel });

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(tag ? { 'X-Client-Tag': tag } : {}),
        ...api.defaults.headers.common,
      },
      body,
    }).then(response => {
      if (!response.ok) {
        onError?.(`HTTP ${response.status}`);
        return;
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      function read() {
        reader.read().then(({ done, value }) => {
          if (done) {
            onDone?.();
            return;
          }
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          let eventType = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ') && eventType) {
              try {
                const data = JSON.parse(line.slice(6));
                if (eventType === 'token') onToken?.(data.text);
                else if (eventType === 'status') onStatus?.(data);
                else if (eventType === 'done') onDone?.(data);
                else if (eventType === 'error') onError?.(data.message);
                else if (eventType === 'tool_start' || eventType === 'tool_result' || eventType === 'tool_error') {
                  console.log('[SSE]', eventType, data?.tool_name, data?.result?.substring?.(0, 80));
                  onToolEvent?.(eventType, data);
                }
              } catch (_) {}
              eventType = '';
            }
          }
          read();
        });
      }
      read();
    }).catch(err => onError?.(err.message));
  },
};

// Legacy agentAPI для сумісності - перенаправляємо на нові RAG ендпоінти
export const agentAPI = {
  uploadFile: (file, title) => ragAPI.uploadDocument(file, title),
  testChat: (message) => ragAPI.chat(message),
  reindexDocuments: () => ragAPI.reindexDocuments(),
};
