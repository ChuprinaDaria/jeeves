import api from './axios';

export const autoReplyAPI = {
  /** GET /api/clients/channel-auto-reply/ */
  list() {
    return api.get('/clients/channel-auto-reply/');
  },

  /** GET /api/clients/channel-auto-reply/<channel>/ */
  get(channel) {
    return api.get(`/clients/channel-auto-reply/${channel}/`);
  },

  /** PUT /api/clients/channel-auto-reply/<channel>/ */
  save(channel, data) {
    return api.put(`/clients/channel-auto-reply/${channel}/`, data);
  },

  /** GET /api/clients/channel-auto-reply/<channel>/contacts/ */
  getContacts(channel) {
    return api.get(`/clients/channel-auto-reply/${channel}/contacts/`);
  },
};
