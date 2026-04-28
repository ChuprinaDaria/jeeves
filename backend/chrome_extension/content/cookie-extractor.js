/**
 * Cookie extraction module for mautrix bridge authentication.
 * Extracts httpOnly cookies via chrome.cookies API for Meta and LinkedIn bridges.
 */

const BRIDGE_COOKIE_CONFIG = {
  'meta-facebook': {
    domains: ['.facebook.com', '.messenger.com'],
    required: ['c_user', 'xs', 'datr', 'sb'],
    loginUrl: 'https://www.messenger.com/',
  },
  'meta-instagram': {
    domains: ['.instagram.com'],
    required: ['sessionid', 'csrftoken', 'mid', 'ig_did', 'ds_user_id'],
    loginUrl: 'https://www.instagram.com/',
  },
  'linkedin': {
    domains: ['.linkedin.com'],
    required: ['li_at', 'JSESSIONID', 'lidc'],
    loginUrl: 'https://www.linkedin.com/',
  },
};

async function extractCookies(bridgeType) {
  const config = BRIDGE_COOKIE_CONFIG[bridgeType];
  if (!config) {
    return { error: `Unknown bridge type: ${bridgeType}` };
  }

  const allCookies = {};
  for (const domain of config.domains) {
    const cookies = await chrome.cookies.getAll({ domain });
    for (const cookie of cookies) {
      allCookies[cookie.name] = cookie.value;
    }
  }

  const result = {};
  const missing = [];
  for (const name of config.required) {
    if (allCookies[name]) {
      result[name] = allCookies[name];
    } else {
      missing.push(name);
    }
  }

  if (missing.length > 0) {
    return { cookies: result, missing, complete: false };
  }

  return { cookies: result, missing: [], complete: true };
}

async function openLoginPopup(bridgeType) {
  const config = BRIDGE_COOKIE_CONFIG[bridgeType];
  if (!config) return null;

  const tab = await chrome.tabs.create({
    url: config.loginUrl,
    active: true,
  });
  return tab.id;
}

async function pollForCookies(bridgeType, tabId) {
  const maxAttempts = 40;
  const interval = 3000;

  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(resolve => setTimeout(resolve, interval));

    const result = await extractCookies(bridgeType);
    if (result.complete) {
      try {
        await chrome.tabs.remove(tabId);
      } catch (e) {
        console.debug('Tab may already be closed:', e);
      }
      return result;
    }
  }

  return { error: 'Timeout waiting for login', complete: false };
}

export { extractCookies, openLoginPopup, pollForCookies, BRIDGE_COOKIE_CONFIG };
