import api from './axios';

export const clientAPI = {
  // Отримати інформацію про поточного клієнта
  getMe: () => api.get('/clients/me/'),

  // Оновити інформацію про клієнта (включаючи custom_system_prompt)
  updateMe: (data) => api.patch('/clients/me/', data),

  // Завантажити логотип клієнта
  uploadLogo: (logoFile) => {
    const formData = new FormData();
    formData.append('logo', logoFile);
    return api.post('/clients/logo/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  // Отримати статистику клієнта
  getStats: (clientId) => api.get(`/clients/${clientId}/stats/`),

  // Список документів клієнта
  getDocuments: () => api.get('/clients/documents/'),

  // Завантажити документ клієнта
  uploadDocument: (file, title, clientId) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    if (clientId) {
      formData.append('client', clientId);
    }
    return api.post('/clients/documents/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  // Видалити документ клієнта
  deleteDocument: (documentId) => api.delete(`/clients/documents/${documentId}/`),

  // Knowledge Blocks API
  getKnowledgeBlocks: () => api.get('/clients/knowledge-blocks/'),
  createKnowledgeBlock: (data) => api.post('/clients/knowledge-blocks/', data),
  updateKnowledgeBlock: (id, data) => api.patch(`/clients/knowledge-blocks/${id}/`, data),
  deleteKnowledgeBlock: (id) => api.delete(`/clients/knowledge-blocks/${id}/`),
  addDocumentToBlock: (blockId, file, title) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    return api.post(`/clients/knowledge-blocks/${blockId}/documents/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  // Sync New Data - індексування тільки нових документів (is_processed=False)
  syncData: () => api.post('/rag/client/index-new/'),
  
  // Retrain Now - переіндексація всіх документів (при виборі нової моделі або повна переіндексація)
  reindexData: () => api.post('/rag/client/reindex/'),
  
  // WhatsApp Conversations API
  getConversations: () => api.get('/clients/conversations/'),
  getConversationDetail: (conversationId) => api.get(`/clients/conversations/${conversationId}/`),
  
  // QR Codes API
  getQRCodes: () => api.get('/clients/qr-codes/'),
  createQRCode: (data) => api.post('/clients/qr-codes/', data),
  updateQRCode: (id, data) => api.patch(`/clients/qr-codes/${id}/`, data),
  deleteQRCode: (id) => api.delete(`/clients/qr-codes/${id}/`),
  
  // Top Questions API
  getTopQuestions: () => api.get('/clients/top-questions/'),
  
  // Recent Activity API
  getRecentActivity: () => api.get('/clients/recent-activity/'),
  
  // Stats API
  getStats: () => api.get('/clients/stats/'),
  
  // Model Status API
  getModelStatus: () => api.get('/clients/model-status/'),
};

