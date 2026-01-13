(function() {
  'use strict';
  
  // Перевірка на повторне завантаження
  if (window.ChatWidgetLoaded) return;
  window.ChatWidgetLoaded = true;
  
  // Отримуємо параметри з URL скрипта
  const currentScript = document.currentScript || (function() {
    const scripts = document.getElementsByTagName('script');
    return scripts[scripts.length - 1];
  })();
  
  const scriptSrc = currentScript ? currentScript.src : '';
  const urlParams = new URLSearchParams(scriptSrc.split('?')[1] || '');
  const tag = urlParams.get('tag');
  // Для white label можна передати власний домен через параметр domain
  const customDomain = urlParams.get('domain');
  
  if (!tag) {
    console.error('Widget: Missing tag parameter');
    return;
  }
  
  // URL чату - власний домен або app.nexelin.com
  const baseUrl = customDomain ? ('https://' + customDomain) : 'https://app.nexelin.com';
  const chatUrl = baseUrl + '/client?tag=' + tag;
  
  // Стилі
  const style = document.createElement('style');
  style.textContent = `
    .chat-widget-btn {
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: #1f2937;
      color: white;
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 16px rgba(0,0,0,0.3);
      font-size: 24px;
      z-index: 99999;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s, background 0.2s;
    }
    .chat-widget-btn:hover {
      transform: scale(1.08);
      background: #374151;
    }
    .chat-widget-popup {
      display: none;
      position: fixed;
      bottom: 96px;
      right: 24px;
      width: 400px;
      height: 600px;
      max-width: calc(100vw - 48px);
      max-height: calc(100vh - 120px);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 8px 32px rgba(0,0,0,0.25);
      z-index: 99998;
      background: white;
    }
    .chat-widget-popup.open { display: block; }
    .chat-widget-popup iframe {
      width: 100%;
      height: 100%;
      border: none;
    }
    /* Кнопка закриття для мобільного */
    .chat-widget-close {
      display: none;
      position: absolute;
      top: 12px;
      right: 12px;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: rgba(0,0,0,0.6);
      color: white;
      border: none;
      cursor: pointer;
      font-size: 20px;
      z-index: 10;
      align-items: center;
      justify-content: center;
    }
    @media (max-width: 480px) {
      .chat-widget-btn.hidden { display: none; }
      .chat-widget-popup {
        width: 100%;
        height: 100%;
        max-width: 100%;
        max-height: 100%;
        bottom: 0;
        right: 0;
        top: 0;
        left: 0;
        border-radius: 0;
      }
      .chat-widget-close {
        display: flex;
      }
    }
  `;
  document.head.appendChild(style);
  
  // Кнопка відкриття
  const btn = document.createElement('button');
  btn.className = 'chat-widget-btn';
  btn.innerHTML = '💬';
  btn.title = 'Chat';
  
  // Popup з iframe
  const popup = document.createElement('div');
  popup.className = 'chat-widget-popup';
  
  // Кнопка закриття (для мобільного)
  const closeBtn = document.createElement('button');
  closeBtn.className = 'chat-widget-close';
  closeBtn.innerHTML = '✕';
  closeBtn.title = 'Close';
  
  // Iframe з готовим Client Portal
  const iframe = document.createElement('iframe');
  iframe.src = chatUrl;
  iframe.allow = 'microphone; camera';
  
  popup.appendChild(closeBtn);
  popup.appendChild(iframe);
  
  // Логіка відкриття/закриття
  let isOpen = false;
  const isMobile = window.innerWidth <= 480;
  
  function openChat() {
    isOpen = true;
    popup.classList.add('open');
    btn.innerHTML = '✕';
    if (isMobile) btn.classList.add('hidden');
  }
  
  function closeChat() {
    isOpen = false;
    popup.classList.remove('open');
    btn.innerHTML = '💬';
    btn.classList.remove('hidden');
  }
  
  btn.onclick = function() {
    if (isOpen) closeChat();
    else openChat();
  };
  
  closeBtn.onclick = closeChat;
  
  // Додаємо до сторінки
  document.body.appendChild(popup);
  document.body.appendChild(btn);
  
  // API для зовнішнього керування
  window.ChatWidget = {
    open: openChat,
    close: closeChat,
    toggle: function() { if (isOpen) closeChat(); else openChat(); }
  };
  
  console.log('✅ Chat Widget loaded, tag:', tag);
})();
