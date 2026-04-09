import api from './axios';

export const embeddingModelAPI = {
  // Отримати список embedding моделей (новий ендпоінт)
  getModels: () => api.get('/rag/embedding-models/'),

  // Вибрати embedding модель для клієнта (новий ендпоінт)
  selectModel: (modelId) => 
    api.post('/rag/client/embedding-model/', { model_id: modelId, model_type: 'embedding' }),

  // Переіндексувати документи клієнта (новий ендпоінт)
  reindex: () => api.post('/rag/client/reindex/'),
};

