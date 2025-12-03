'use strict';

// Lightweight behaviour tracker for Nexelin Chrome extension.
// Goal: capture generic patterns (time on page, scroll depth, form focus, price clicks)
// and send them to background for future proactive suggestions.

const NEXELIN_BT_NAMESPACE = '__nexelin_bt__';

function postBehaviourEvent(event, payload) {
  try {
    chrome.runtime.sendMessage(
      {
        type: 'BEHAVIOUR_EVENT',
        event,
        payload,
        namespace: NEXELIN_BT_NAMESPACE,
      },
      () => {
        // Ignore errors from closed background, etc.
      },
    );
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn('Nexelin behaviour tracker: failed to send event', e);
  }
}

function trackTimeOnPage() {
  const start = Date.now();
  let timerId;

  function sendTick() {
    const now = Date.now();
    const seconds = Math.round((now - start) / 1000);
    postBehaviourEvent('time_on_page', { seconds });
  }

  timerId = window.setInterval(sendTick, 60_000); // every 60s

  window.addEventListener(
    'beforeunload',
    () => {
      window.clearInterval(timerId);
      const now = Date.now();
      const seconds = Math.round((now - start) / 1000);
      postBehaviourEvent('time_on_page_final', { seconds });
    },
    { passive: true },
  );
}

function trackScrollDepth() {
  let maxScroll = 0;
  let timeoutId;

  function onScroll() {
    const doc = document.documentElement || document.body;
    const scrollTop = window.scrollY || doc.scrollTop || 0;
    const scrollHeight = doc.scrollHeight || 1;
    const viewport = window.innerHeight || doc.clientHeight || 1;
    const depth = Math.min(100, Math.round(((scrollTop + viewport) / scrollHeight) * 100));
    if (depth > maxScroll) {
      maxScroll = depth;
    }

    if (timeoutId) window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => {
      postBehaviourEvent('scroll_depth', { percent: maxScroll });
    }, 2000);
  }

  window.addEventListener('scroll', onScroll, { passive: true });
}

function looksLikePriceElement(el) {
  if (!el || !el.textContent) return false;
  const text = el.textContent.trim();
  if (!text) return false;
  // Basic heuristics: currency symbols or numbers with decimals
  const pricePattern = /(\$|€|£|₴|zl|zł|PLN|UAH|USD|EUR)\s*\d|^\d+([.,]\d{2})?\s*(\$|€|£|₴|zl|zł|PLN|UAH|USD|EUR)?/i;
  return pricePattern.test(text);
}

function trackPriceClicks() {
  const priceClickCounts = new Map();

  function onClick(e) {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;

    let el = target;
    for (let i = 0; i < 3 && el; i += 1) {
      if (looksLikePriceElement(el)) {
        const key = el.textContent.trim().slice(0, 50);
        const prev = priceClickCounts.get(key) || 0;
        const next = prev + 1;
        priceClickCounts.set(key, next);
        postBehaviourEvent('price_click', { label: key, count: next });
        break;
      }
      el = el.parentElement;
    }
  }

  window.addEventListener('click', onClick, { capture: true, passive: true });
}

function trackFormFocus() {
  let focusedSince = null;
  let formSelector = null;

  function onFocusIn(e) {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    const form = target.closest('form');
    if (!form) return;
    focusedSince = Date.now();
    formSelector = form.getAttribute('id') || form.getAttribute('name') || form.tagName.toLowerCase();
  }

  function onFocusOut(e) {
    if (!focusedSince) return;
    const durationMs = Date.now() - focusedSince;
    focusedSince = null;
    if (durationMs < 5_000) return; // ignore very short focus
    postBehaviourEvent('form_focus', {
      selector: formSelector,
      seconds: Math.round(durationMs / 1000),
    });
  }

  window.addEventListener('focusin', onFocusIn, { passive: true });
  window.addEventListener('focusout', onFocusOut, { passive: true });
}

// Initialize trackers once DOM is ready enough
try {
  trackTimeOnPage();
  trackScrollDepth();
  trackPriceClicks();
  trackFormFocus();
} catch (e) {
  // eslint-disable-next-line no-console
  console.warn('Nexelin behaviour tracker init failed:', e);
}


