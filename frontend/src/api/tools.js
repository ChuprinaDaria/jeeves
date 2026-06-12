import api from './axios';

export const toolsAPI = {
  getCatalog: () => api.get('/tools/catalog/'),
  connect: (slug, credentials, axiosConfig) =>
    api.post(`/tools/${slug}/connect/`, { credentials }, axiosConfig),
  connectWithConfig: (slug, credentials, config) =>
    api.post(`/tools/${slug}/connect/`, { credentials, config }),
  startBridgeLogin: (network, stepData) =>
    api.post(`/tools/matrix/bridges/${network}/login/start/`, stepData ? { step_data: stepData } : {}),
  bridgeLoginStatus: (network, loginId) =>
    api.get(`/tools/matrix/bridges/${network}/login/status/`, { params: { login_id: loginId } }),
  bridgeLoginCookies: (network, cookies) =>
    api.post(`/tools/matrix/bridges/${network}/login/cookies/`, { cookies }),
  disconnect: (slug, target) => api.post(`/tools/${slug}/disconnect/`, target ? { target } : {}),
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

  // Living canvas: recent tool calls + 7-day usage aggregates
  getFlowActivity: (since) =>
    api.get('/tools/flow/activity/', { params: since ? { since } : {} }),

  getWordCloud: () => api.get('/tools/word-cloud/'),
};
