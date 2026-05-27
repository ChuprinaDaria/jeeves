import api from './axios';

// GET /api/platform/bootstrap — called on React boot, drives routing
export const platformAPI = {
  getBootstrap: () => api.get('/platform/bootstrap/'),
};

// POST /api/setup/* — used by the SetupWizard
export const setupAPI = {
  createOwner: (data) => api.post('/setup/owner/', data),
  complete: () => api.post('/setup/complete/'),
};

// GET /api/owner/* — used after login in the admin panel
export const ownerAPI = {
  getDashboardStats: () => api.get('/owner/dashboard/stats/'),
};

// AI Providers — LLM
export const llmProvidersAPI = {
  list: () => api.get('/owner/ai-providers/llm/'),
  detail: (id) => api.get(`/owner/ai-providers/llm/${id}/`),
  create: (data) => api.post('/owner/ai-providers/llm/', data),
  update: (id, data) => api.put(`/owner/ai-providers/llm/${id}/`, data),
  delete: (id) => api.delete(`/owner/ai-providers/llm/${id}/`),
  test: (id, apiKeyOverride) =>
    api.post(
      `/owner/ai-providers/llm/${id}/test/`,
      apiKeyOverride ? { api_key: apiKeyOverride } : {},
    ),
  testUnsaved: (payload) =>
    api.post('/owner/ai-providers/llm/test-unsaved/', payload),
};

// AI Providers — Embedding
export const embeddingModelsAPI = {
  list: () => api.get('/owner/ai-providers/embeddings/'),
  detail: (id) => api.get(`/owner/ai-providers/embeddings/${id}/`),
  create: (data) => api.post('/owner/ai-providers/embeddings/', data),
  update: (id, data) => api.put(`/owner/ai-providers/embeddings/${id}/`, data),
  delete: (id) => api.delete(`/owner/ai-providers/embeddings/${id}/`),
  test: (id, apiKeyOverride) =>
    api.post(
      `/owner/ai-providers/embeddings/${id}/test/`,
      apiKeyOverride ? { api_key: apiKeyOverride } : {},
    ),
  testUnsaved: (payload) =>
    api.post('/owner/ai-providers/embeddings/test-unsaved/', payload),
};

// AI Providers — Model Pairs
export const modelPairsAPI = {
  list: () => api.get('/owner/ai-providers/pairs/'),
  detail: (id) => api.get(`/owner/ai-providers/pairs/${id}/`),
  create: (data) => api.post('/owner/ai-providers/pairs/', data),
  update: (id, data) => api.put(`/owner/ai-providers/pairs/${id}/`, data),
  delete: (id) => api.delete(`/owner/ai-providers/pairs/${id}/`),
};

// Platform Defaults — singleton
export const platformDefaultsAPI = {
  get: () => api.get('/owner/settings/defaults/'),
  update: (data) => api.put('/owner/settings/defaults/', data),
};

// Clients
export const clientsAPI = {
  list: () => api.get('/owner/clients/'),
  detail: (id) => api.get(`/owner/clients/${id}/`),
  choices: () => api.get('/owner/clients/choices/'),
  create: (data) => api.post('/owner/clients/', data),
  update: (id, data) => api.put(`/owner/clients/${id}/`, data),
  delete: (id) => api.delete(`/owner/clients/${id}/`),
};

// MCP Servers (ToolCards)
export const mcpServersAPI = {
  list: () => api.get('/owner/tools/'),
  detail: (id) => api.get(`/owner/tools/${id}/`),
  create: (data) => api.post('/owner/tools/', data),
  update: (id, data) => api.put(`/owner/tools/${id}/`, data),
  delete: (id) => api.delete(`/owner/tools/${id}/`),
  discover: (url) => api.post('/owner/tools/discover/', { url }),
  createFromUrl: (data) => api.post('/owner/tools/from-url/', data),
  refresh: (id) => api.post(`/owner/tools/${id}/refresh/`),
};

// Branches
export const branchesAPI = {
  list: () => api.get('/owner/branches/'),
  detail: (id) => api.get(`/owner/branches/${id}/`),
  create: (data) => api.post('/owner/branches/', data),
  update: (id, data) => api.put(`/owner/branches/${id}/`, data),
  delete: (id) => api.delete(`/owner/branches/${id}/`),
  choices: () => api.get('/owner/branches/choices/'),
};

// Specializations
export const specializationsAPI = {
  list: () => api.get('/owner/specializations/'),
  detail: (id) => api.get(`/owner/specializations/${id}/`),
  create: (data) => api.post('/owner/specializations/', data),
  update: (id, data) => api.put(`/owner/specializations/${id}/`, data),
  delete: (id) => api.delete(`/owner/specializations/${id}/`),
  choices: () => api.get('/owner/specializations/choices/'),
};

// Feature Flags
export const featureFlagsAPI = {
  list: () => api.get('/owner/feature-flags/'),
  detail: (id) => api.get(`/owner/feature-flags/${id}/`),
  create: (data) => api.post('/owner/feature-flags/', data),
  update: (id, data) => api.put(`/owner/feature-flags/${id}/`, data),
  delete: (id) => api.delete(`/owner/feature-flags/${id}/`),
  choices: () => api.get('/owner/feature-flags/choices/'),
};

// System Messages
export const systemMessagesAPI = {
  list: () => api.get('/owner/system-messages/'),
  detail: (id) => api.get(`/owner/system-messages/${id}/`),
  create: (data) => api.post('/owner/system-messages/', data),
  update: (id, data) => api.put(`/owner/system-messages/${id}/`, data),
  delete: (id) => api.delete(`/owner/system-messages/${id}/`),
};
