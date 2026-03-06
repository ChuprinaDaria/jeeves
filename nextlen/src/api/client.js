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
  
  // Видалити логотип клієнта
  deleteLogo: () => api.delete('/clients/logo/'),

  // Отримати статистику клієнта
  getStats: (clientId) => api.get(`/clients/${clientId}/stats/`),

  // Список документів клієнта
  getDocuments: () => api.get('/clients/documents/'),

  // Завантажити документ клієнта
  uploadDocument: (file, title) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title || file.name);
    
    // Визначаємо тип файлу
    const fileExtension = file.name.split('.').pop().toLowerCase();
    const fileTypeMap = {
      'pdf': 'pdf',
      'txt': 'txt',
      'csv': 'csv',
      'json': 'json',
      'docx': 'docx',
      'doc': 'docx'
    };
    const fileType = fileTypeMap[fileExtension] || 'txt';
    formData.append('file_type', fileType);
    
    return api.post('/clients/documents/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  // Завантажити текст як документ
  uploadTextDocument: (title, text) => {
    // Створюємо Blob з тексту
    const blob = new Blob([text], { type: 'text/plain' });
    const file = new File([blob], `${title || 'text'}.txt`, { type: 'text/plain' });
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title || 'Text Document');
    formData.append('file_type', 'txt');
    
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
  rateConversation: (conversationId, rating) => api.post(`/clients/conversations/${conversationId}/rate/`, { rating }),
  sendConversationEmail: (conversationId) => api.post(`/clients/conversations/${conversationId}/generate-report/`),
  updateConversationNotes: (conversationId, notes) => api.post(`/clients/conversations/${conversationId}/notes/`, { notes }),
  
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

  // Pixel Dashboard Status API
  getPixelStatus: () => api.get('/clients/pixel-status/'),

  // Web Parsing Requests API
  getWebParsingRequests: () => api.get('/clients/web-parsing-requests/'),
  createWebParsingRequest: (data) => api.post('/clients/web-parsing-requests/', data),
  getWebParsingRequest: (id) => api.get(`/clients/web-parsing-requests/${id}/`),
  updateWebParsingRequest: (id, data) => api.patch(`/clients/web-parsing-requests/${id}/`, data),
  deleteWebParsingRequest: (id) => api.delete(`/clients/web-parsing-requests/${id}/`),
};

