(function() {
  'use strict';
  
  // Перевірка на повторне завантаження
  if (window.NexelinWidgetLoaded) {
    console.warn('Nexelin Widget already loaded');
    return;
  }
  window.NexelinWidgetLoaded = true;
  
  // Отримуємо параметри з URL скрипта
  const currentScript = document.currentScript || (function() {
    const scripts = document.getElementsByTagName('script');
    return scripts[scripts.length - 1];
  })();
  
  const scriptSrc = currentScript ? currentScript.src : '';
  const urlParams = new URLSearchParams(scriptSrc.split('?')[1] || '');
  const tag = urlParams.get('tag');
  
  if (!tag) {
    console.error('Nexelin Widget: Missing tag parameter');
    return;
  }
  
  // Конфігурація віджета
  const config = {
    tag: tag,
    // Визначаємо базовий URL (продакшн або локальний)
    baseUrl: scriptSrc.includes('localhost') || scriptSrc.includes('127.0.0.1') 
      ? 'http://localhost:5173'  // Для розробки
      : 'https://app.nexelin.com', // Для продакшна
    position: 'bottom-right',
    primaryColor: '#3b82f6',
    buttonIcon: '💬',
    closeIcon: '✕',
    buttonSize: '60px',
    zIndex: 999999
  };
  
  // Формуємо URL чату
  const chatUrl = `${config.baseUrl}/client?tag=${tag}`;
  
  // Створюємо стилі
  const style = document.createElement('style');
  style.id = 'nexelin-widget-styles';
  style.textContent = `
    /* Контейнер віджета */
    .nexelin-widget-container {
      position: fixed;
      bottom: 20px;
      right: 20px;
      z-index: ${config.zIndex};
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    
    /* Кнопка відкриття чату */
    .nexelin-widget-button {
      width: ${config.buttonSize};
      height: ${config.buttonSize};
      border-radius: 50%;
      background: linear-gradient(135deg, ${config.primaryColor} 0%, #2563eb 100%);
      color: white;
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 28px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
      overflow: hidden;
    }
    
    .nexelin-widget-button::before {
      content: '';
      position: absolute;
      inset: 0;
      border-radius: 50%;
      padding: 2px;
      background: linear-gradient(135deg, rgba(255,255,255,0.2), rgba(255,255,255,0));
      -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
      -webkit-mask-composite: xor;
      mask-composite: exclude;
    }
    
    .nexelin-widget-button:hover {
      transform: scale(1.05);
      box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5);
    }
    
    .nexelin-widget-button:active {
      transform: scale(0.95);
    }
    
    /* Анімація пульсації для кнопки (опціонально) */
    @keyframes pulse {
      0%, 100% {
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
      }
      50% {
        box-shadow: 0 4px 20px rgba(59, 130, 246, 0.7);
      }
    }
    
    .nexelin-widget-button.pulse {
      animation: pulse 2s infinite;
    }
    
    /* Вікно чату */
    .nexelin-widget-chat {
      position: fixed;
      bottom: 100px;
      right: 20px;
      width: 400px;
      height: 650px;
      max-width: calc(100vw - 40px);
      max-height: calc(100vh - 120px);
      border-radius: 16px;
      box-shadow: 0 12px 48px rgba(0, 0, 0, 0.25);
      background: white;
      display: none;
      overflow: hidden;
      z-index: ${config.zIndex + 1};
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      opacity: 0;
      transform: translateY(20px) scale(0.95);
    }
    
    .nexelin-widget-chat.active {
      display: block;
      animation: chatAppear 0.3s forwards;
    }
    
    @keyframes chatAppear {
      to {
        opacity: 1;
        transform: translateY(0) scale(1);
      }
    }
    
    .nexelin-widget-chat.closing {
      animation: chatDisappear 0.2s forwards;
    }
    
    @keyframes chatDisappear {
      to {
        opacity: 0;
        transform: translateY(20px) scale(0.95);
      }
    }
    
    .nexelin-widget-chat iframe {
      width: 100%;
      height: 100%;
      border: none;
      border-radius: 16px;
    }
    
    /* Overlay для затемнення фону (опціонально на мобільних) */
    .nexelin-widget-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.3);
      z-index: ${config.zIndex - 1};
      opacity: 0;
      transition: opacity 0.3s;
    }
    
    .nexelin-widget-overlay.active {
      display: block;
      opacity: 1;
    }
    
    /* Badge з непрочитаними повідомленнями (опціонально) */
    .nexelin-widget-badge {
      position: absolute;
      top: -4px;
      right: -4px;
      background: #ef4444;
      color: white;
      border-radius: 10px;
      min-width: 20px;
      height: 20px;
      display: none;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 600;
      padding: 0 6px;
      border: 2px solid white;
    }
    
    .nexelin-widget-badge.visible {
      display: flex;
    }
    
    /* Адаптивність для мобільних */
    @media (max-width: 768px) {
      .nexelin-widget-container {
        bottom: 16px;
        right: 16px;
      }
      
      .nexelin-widget-button {
        width: 56px;
        height: 56px;
        font-size: 24px;
      }
      
      .nexelin-widget-chat {
        width: 100%;
        height: 100%;
        max-width: 100%;
        max-height: 100%;
        bottom: 0;
        right: 0;
        left: 0;
        top: 0;
        border-radius: 0;
      }
      
      .nexelin-widget-chat iframe {
        border-radius: 0;
      }
      
      .nexelin-widget-overlay.active {
        display: none;
      }
    }
    
    /* Анімація для завантаження */
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    
    .nexelin-widget-loading {
      position: absolute;
      inset: 0;
      background: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
      color: #666;
    }
    
    .nexelin-widget-loading::after {
      content: '';
      width: 24px;
      height: 24px;
      border: 3px solid #e5e7eb;
      border-top-color: ${config.primaryColor};
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin-left: 8px;
    }
  `;
  document.head.appendChild(style);
  
  // Створюємо HTML структуру
  const container = document.createElement('div');
  container.className = 'nexelin-widget-container';
  container.setAttribute('data-nexelin-widget', 'true');
  
  // Кнопка відкриття
  const button = document.createElement('button');
  button.className = 'nexelin-widget-button';
  button.innerHTML = config.buttonIcon;
  button.setAttribute('aria-label', 'Open chat');
  button.setAttribute('title', 'Chat with us');
  
  // Badge (непрочитані повідомлення)
  const badge = document.createElement('span');
  badge.className = 'nexelin-widget-badge';
  badge.textContent = '1';
  button.appendChild(badge);
  
  // Overlay
  const overlay = document.createElement('div');
  overlay.className = 'nexelin-widget-overlay';
  
  // Вікно чату
  const chatContainer = document.createElement('div');
  chatContainer.className = 'nexelin-widget-chat';
  
  // Iframe з чатом
  const iframe = document.createElement('iframe');
  iframe.src = chatUrl;
  iframe.setAttribute('allow', 'microphone; camera');
  iframe.setAttribute('title', 'Nexelin AI Chat');
  iframe.setAttribute('loading', 'lazy');
  
  chatContainer.appendChild(iframe);
  
  // Стан віджета
  let isOpen = false;
  let isClosing = false;
  
  // Функція відкриття чату
  function openChat() {
    if (isOpen || isClosing) return;
    
    isOpen = true;
    chatContainer.classList.add('active');
    overlay.classList.add('active');
    button.innerHTML = config.closeIcon;
    button.setAttribute('aria-label', 'Close chat');
    button.setAttribute('title', 'Close chat');
    
    // Ховаємо badge при відкритті
    badge.classList.remove('visible');
    
    // Фокус на iframe для доступності
    setTimeout(() => {
      iframe.focus();
    }, 300);
  }
  
  // Функція закриття чату
  function closeChat() {
    if (!isOpen || isClosing) return;
    
    isClosing = true;
    chatContainer.classList.add('closing');
    overlay.classList.remove('active');
    button.innerHTML = config.buttonIcon;
    button.setAttribute('aria-label', 'Open chat');
    button.setAttribute('title', 'Chat with us');
    
    setTimeout(() => {
      chatContainer.classList.remove('active', 'closing');
      isOpen = false;
      isClosing = false;
    }, 200);
  }
  
  // Обробка кліку на кнопку
  button.addEventListener('click', function(e) {
    e.stopPropagation();
    if (isOpen) {
      closeChat();
    } else {
      openChat();
    }
  });
  
  // Закриваємо при кліку на overlay
  overlay.addEventListener('click', function() {
    closeChat();
  });
  
  // Закриваємо при натисканні ESC
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && isOpen) {
      closeChat();
    }
  });
  
  // API для керування віджетом ззовні
  window.NexelinWidget = {
    open: openChat,
    close: closeChat,
    toggle: function() {
      if (isOpen) {
        closeChat();
      } else {
        openChat();
      }
    },
    isOpen: function() {
      return isOpen;
    },
    showBadge: function(count) {
      if (count && count > 0) {
        badge.textContent = count > 99 ? '99+' : count;
        badge.classList.add('visible');
      } else {
        badge.classList.remove('visible');
      }
    },
    hideBadge: function() {
      badge.classList.remove('visible');
    }
  };
  
  // Додаємо елементи до DOM
  container.appendChild(button);
  document.body.appendChild(overlay);
  document.body.appendChild(chatContainer);
  document.body.appendChild(container);
  
  // Повідомлення про успішне завантаження
  console.log('✅ Nexelin AI Chat Widget loaded successfully');
  console.log('📦 Widget API available: window.NexelinWidget');
  console.log('🏷️  Client tag:', tag);
  
  // Опціонально: показуємо badge через 3 секунди після завантаження
  // (щоб привернути увагу користувача)
  setTimeout(function() {
    if (!isOpen) {
      // Розкоментуйте наступний рядок, якщо хочете показувати badge автоматично
      // badge.classList.add('visible');
      
      // Або додайте пульсацію
      button.classList.add('pulse');
      setTimeout(() => button.classList.remove('pulse'), 4000);
    }
  }, 3000);
  
})();

