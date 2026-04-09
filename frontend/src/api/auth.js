import api from './axios';

export const authAPI = {
  register: (data) => api.post('/auth/register/', data),
  login: (data) => api.post('/auth/login/', data),
  logout: () => api.post('/auth/logout/'),
  getProfile: () => api.get('/auth/me/'),
  refreshToken: (refreshToken) => api.post('/auth/refresh/', { refresh: refreshToken }),
  
  // Отримати JWT токен через client_token
  getTokenByClientToken: (clientToken) => 
    api.post('/rag/auth/token-by-client-token/', { client_token: clientToken }),
  
  // Bootstrap для створення/отримання клієнта
  bootstrap: (branchSlug, specializationSlug, clientToken, data) => 
    api.post(`/rag/bootstrap/${branchSlug}/${specializationSlug}/${clientToken}/`, data),
};
