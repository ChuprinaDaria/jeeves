'use strict';

// Lightweight wrapper around Web Speech APIs for popup UI.
// No backend dependency; all voice features are optional and feature-detected.

function getSpeechRecognitionCtor() {
  if (typeof window === 'undefined') return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function isSpeechRecognitionSupported() {
  return !!getSpeechRecognitionCtor();
}

export function isSpeechSynthesisSupported() {
  if (typeof window === 'undefined') return false;
  return typeof window.speechSynthesis !== 'undefined' && typeof window.SpeechSynthesisUtterance !== 'undefined';
}

/**
 * Start one-shot speech recognition.
 * Returns a controller with stop() method.
 */
export function startSpeechRecognition({ onResult, onError, onEnd, lang } = {}) {
  const Ctor = getSpeechRecognitionCtor();
  if (!Ctor) {
    if (onError) onError(new Error('Speech recognition is not supported in this browser.'));
    return { stop() {} };
  }

  const recognition = new Ctor();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = lang || 'en-US';

  recognition.onresult = (event) => {
    try {
      const transcript = Array.from(event.results)
        .map((res) => res[0] && res[0].transcript)
        .join(' ')
        .trim();
      if (transcript && onResult) onResult(transcript);
    } catch (e) {
      if (onError) onError(e);
    }
  };

  recognition.onerror = (event) => {
    if (onError) onError(new Error(event.error || 'Speech recognition error'));
  };

  recognition.onend = () => {
    if (onEnd) onEnd();
  };

  try {
    recognition.start();
  } catch (e) {
    if (onError) onError(e);
    if (onEnd) onEnd();
  }

  return {
    stop() {
      try {
        recognition.stop();
      } catch (e) {
        console.debug('Speech recognition stop failed:', e);
      }
    },
  };
}

export function speakText(text, { lang, rate, pitch } = {}) {
  if (!isSpeechSynthesisSupported()) return;
  if (!text) return;

  const utterance = new window.SpeechSynthesisUtterance(text);
  utterance.lang = lang || 'en-US';
  if (rate && typeof rate === 'number') utterance.rate = rate;
  if (pitch && typeof pitch === 'number') utterance.pitch = pitch;

  window.speechSynthesis.speak(utterance);
}


