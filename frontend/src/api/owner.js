import api from './axios';

// GET /api/platform/bootstrap — called on React boot, drives routing
export const platformAPI = {
  getBootstrap: () => api.get('/platform/bootstrap/'),
};

// POST /api/setup/* — used by the two-step SetupWizard
export const setupAPI = {
  createOwner: (data) => api.post('/setup/owner/', data),
  saveLicense: (license_key) => api.post('/setup/license/', { license_key }),
  complete: () => api.post('/setup/complete/'),
};

// GET /api/owner/* — used after login in the admin panel
export const ownerAPI = {
  getDashboardStats: () => api.get('/owner/dashboard/stats/'),
  reverifyLicense: () => api.post('/owner/license/reverify/'),
};
