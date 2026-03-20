import api from './axios';

export const toolsAPI = {
  getCatalog: () => api.get('/tools/catalog/'),
  connect: (slug, credentials, config) => api.post(`/tools/${slug}/connect/`, { credentials }, config),
  disconnect: (slug) => api.post(`/tools/${slug}/disconnect/`),
  getStatus: (slug) => api.get(`/tools/${slug}/status/`),
  getMyTools: () => api.get('/tools/my/'),

  // Flow canvas
  getFlowConnections: () => api.get('/tools/flow/connections/'),
  createFlowConnection: (slug, target) => api.post('/tools/flow/connections/', { slug, target }),
  updateFlowConnection: (id, data) => api.patch(`/tools/flow/connections/${id}/`, data),
  deleteFlowConnection: (id) => api.delete(`/tools/flow/connections/${id}/`),

  // Edge middleware
  getEdgeMiddleware: (connectionId) => api.get(`/tools/flow/edges/${connectionId}/middleware/`),
  attachMiddleware: (connectionId, skillSlug) => api.post(`/tools/flow/edges/${connectionId}/middleware/`, { skill_slug: skillSlug }),
  detachMiddleware: (connectionId, middlewareId) => api.delete(`/tools/flow/edges/${connectionId}/middleware/${middlewareId}/`),
};
