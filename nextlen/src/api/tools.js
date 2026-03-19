import api from './axios';

export const toolsAPI = {
  getCatalog: () => api.get('/tools/catalog/'),
  connect: (slug, credentials, config) => api.post(`/tools/${slug}/connect/`, { credentials }, config),
  disconnect: (slug) => api.post(`/tools/${slug}/disconnect/`),
  getStatus: (slug) => api.get(`/tools/${slug}/status/`),
  getMyTools: () => api.get('/tools/my/'),
};
