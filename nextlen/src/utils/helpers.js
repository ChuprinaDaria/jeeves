// Date formatting
export const formatDate = (dateString) => {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

export const formatTime = (dateString) => {
  const date = new Date(dateString);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const formatDateTime = (dateString) => {
  return `${formatDate(dateString)} ${formatTime(dateString)}`;
};

// File size formatting
export const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
};

// String truncation
export const truncateText = (text, maxLength = 50) => {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
};

// Validation
export const isValidEmail = (email) => {
  const re = /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i;
  return re.test(email);
};

export const isValidPhoneNumber = (phone) => {
  const re = /^[\d\s\-\+\(\)]+$/;
  return re.test(phone) && phone.replace(/\D/g, '').length >= 10;
};

// Error handling
export const getErrorMessage = (error) => {
  if (error.response?.data?.message) {
    return error.response.data.message;
  }
  if (error.response?.data?.error) {
    return error.response.data.error;
  }
  if (error.message) {
    return error.message;
  }
  return 'An unexpected error occurred';
};

// Local storage helpers
export const storage = {
  get: (key, defaultValue = null) => {
    try {
      const item = localStorage.getItem(key);
      return item ? JSON.parse(item) : defaultValue;
    } catch (error) {
      console.error('Error reading from localStorage:', error);
      return defaultValue;
    }
  },
  set: (key, value) => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error('Error writing to localStorage:', error);
    }
  },
  remove: (key) => {
    try {
      localStorage.removeItem(key);
    } catch (error) {
      console.error('Error removing from localStorage:', error);
    }
  },
};

// Browser branding helpers (tab title + favicon) based on client data
export const updateBrandingFromClient = (client, options = {}) => {
  if (typeof document === 'undefined') return;

  const { context = 'portal' } = options;

  // Для white label (якщо є company_name) - показуємо company_name
  // Для звичайних клієнтів - показуємо просто "NEXELIN"
  const name = client?.company_name || 'NEXELIN';

  if (context === 'webchat') {
    document.title = `${name} – AI Chat`;
  } else {
    // Для portal не додаємо " – Nexelin Client Portal"
    document.title = name;
  }

  const logoUrl = client?.logo_url || client?.logo;
  if (!logoUrl) return;

  const ensureLink = (rel, extraAttrs = {}) => {
    let link = document.querySelector(`link[rel="${rel}"]`);
    if (!link) {
      link = document.createElement('link');
      link.rel = rel;
      document.head.appendChild(link);
    }
    Object.entries(extraAttrs).forEach(([key, value]) => {
      if (value) {
        link.setAttribute(key, value);
      }
    });
    return link;
  };

  // Basic favicon
  ensureLink('icon', { href: logoUrl, type: 'image/png' });
  // Apple touch icon for iOS / PWA
  ensureLink('apple-touch-icon', { href: logoUrl });
};
