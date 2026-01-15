import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Send, Loader2, Image, Moon, Sun, Download, Trash2, Mic, Menu, X } from 'lucide-react';
import api from '../api/axios';
import { ragAPI } from '../api/agent';
import { clientAPI } from '../api/client';
import { updateBrandingFromClient } from '../utils/helpers';

const WebChatPage = () => {
  const { t, i18n } = useTranslation();
  const [searchParams] = useSearchParams();
  const tag = searchParams.get('tag');
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [conversationDbId, setConversationDbId] = useState(null); // ID з бази даних для оцінки
  const [selectedImage, setSelectedImage] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('web_chat_dark_mode');
    return saved ? saved === 'true' : false;
  });
  const [fontSize, setFontSize] = useState(() => {
    const saved = localStorage.getItem('web_chat_font_size');
    return saved === 'sm' || saved === 'lg' ? saved : 'md';
  });
  const [clientLogo, setClientLogo] = useState(null);
  const [clientName, setClientName] = useState(null);
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [showInstallPrompt, setShowInstallPrompt] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const inputRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  useEffect(() => {
    if (!tag) {
      return;
    }
    
    // НЕ зберігаємо tag глобально, щоб уникнути конфліктів між різними тегами
    // Tag буде зчитуватись безпосередньо з URL в axios interceptor
    
    // Встановлюємо серверний динамічний manifest для webchat
    const setupWebChatManifest = () => {
      // Видаляємо старий manifest link якщо є
      const existingManifest = document.querySelector('link[rel="manifest"]');
      if (existingManifest) {
        existingManifest.remove();
      }
      
      // Додаємо новий manifest link з серверним endpoint
      const manifestLink = document.createElement('link');
      manifestLink.rel = 'manifest';
      manifestLink.href = `${api.defaults.baseURL || ''}/rag/webchat/manifest.json?tag=${tag}`;
      document.head.appendChild(manifestLink);
    };
    
    setupWebChatManifest();
    
    // Завантажуємо дані клієнта, щоб оновити заголовок вкладки, favicon та логотип
    const applyBranding = async () => {
      try {
        const { data } = await clientAPI.getMe();
        updateBrandingFromClient(data, { context: 'webchat' });
        // Зберігаємо логотип та назву для використання в хедері
        if (data.logo_url || data.logo) {
          setClientLogo(data.logo_url || data.logo);
        }
        if (data.company_name || data.user) {
          setClientName(data.company_name || data.user);
        }
      } catch (e) {
        // Fallback заголовок, якщо бекенд недоступний
        document.title = 'AI Chat Assistant';
      }
    };

    applyBranding();
    
    initializeConversation();
    
    // PWA install prompt
    const handleBeforeInstallPrompt = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
      // Show install prompt after 3 seconds
      setTimeout(() => {
        setShowInstallPrompt(true);
      }, 3000);
    };
    
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    
    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    };
  }, [tag]);

  useEffect(() => {
    // Apply dark mode
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('web_chat_dark_mode', darkMode.toString());
  }, [darkMode]);

  useEffect(() => {
    localStorage.setItem('web_chat_font_size', fontSize);
  }, [fontSize]);

  useEffect(() => {
    // Scroll to last message
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Автоматичний фокус на поле введення після відповіді AI
  useEffect(() => {
    if (!loading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [messages, loading]);

  // Polling for HITL responses (manager responses)
  useEffect(() => {
    if (!conversationId || !tag) return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await api.get('/clients/web-conversations/', {
          params: {
            session_id: conversationId,
            last_count: messages.length,
          },
        });

        if (response.data?.has_new && response.data?.messages?.length > 0) {
          // Add new messages (HITL responses) to the chat
          const newMessages = response.data.messages.map((msg, idx) => ({
            id: `hitl_${Date.now()}_${idx}`,
            role: msg.role,
            content: msg.content,
            timestamp: msg.timestamp,
          }));
          
          setMessages(prev => [...prev, ...newMessages]);
          
          // Update conversationDbId if available
          if (response.data.conversation_id && !conversationDbId) {
            setConversationDbId(response.data.conversation_id);
          }
        }
      } catch (error) {
        // Silent fail - polling errors shouldn't disrupt the user
        console.debug('Polling error:', error);
      }
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(pollInterval);
  }, [conversationId, tag, messages.length, conversationDbId]);

  // Обробка resize для мобільної клавіатури
  useEffect(() => {
    let resizeTimer;
    const handleResize = () => {
      // Очищуємо попередній таймер
      clearTimeout(resizeTimer);
      // Додаємо невелику затримку для уникнення частих перерахунків
      resizeTimer = setTimeout(() => {
        // Змушуємо браузер перерахувати висоту viewport
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
        // Прокручуємо до останнього повідомлення після зміни розміру
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    };

    // Встановлюємо початкове значення
    handleResize();

    // Додаємо слухачі подій
    window.addEventListener('resize', handleResize);
    window.addEventListener('orientationchange', handleResize);
    // Для iOS - додаємо обробку visualViewport
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', handleResize);
      window.visualViewport.addEventListener('scroll', handleResize);
    }

    return () => {
      clearTimeout(resizeTimer);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('orientationchange', handleResize);
      if (window.visualViewport) {
        window.visualViewport.removeEventListener('resize', handleResize);
        window.visualViewport.removeEventListener('scroll', handleResize);
      }
    };
  }, []);

  const initializeConversation = async () => {
    try {
      // Check if we have existing session_id for this tag
      const storageKey = `web_chat_session_${tag}`;
      let sessionId = localStorage.getItem(storageKey);
      
      if (!sessionId) {
        // Generate new unique session_id for this client tag
        sessionId = `web_${tag}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        localStorage.setItem(storageKey, sessionId);
        localStorage.setItem('web_chat_session_id', sessionId);
        
        // Add welcome message for new conversation
        setMessages([{
          id: 'welcome',
          role: 'assistant',
          content: 'Bonjour! Hello! Hallo! Hola! Ciao! 你好!',
          timestamp: new Date().toISOString(),
        }]);
      } else {
        // Load existing conversation history
        localStorage.setItem('web_chat_session_id', sessionId);
        
        // Try to load history from localStorage
        const historyKey = `web_chat_history_${sessionId}`;
        const savedHistory = localStorage.getItem(historyKey);
        
        if (savedHistory) {
          try {
            const parsedHistory = JSON.parse(savedHistory);
            setMessages(parsedHistory);
          } catch (e) {
            console.error('Failed to parse saved history:', e);
            // Add welcome message if history parse failed
            setMessages([{
              id: 'welcome',
              role: 'assistant',
              content: 'Bonjour! Hello! Hallo! Hola! Ciao! 你好!',
              timestamp: new Date().toISOString(),
            }]);
          }
        } else {
          // No saved history, add welcome message
          setMessages([{
            id: 'welcome',
            role: 'assistant',
            content: 'Bonjour! Hello! Hallo! Hola! Ciao! 你好!',
            timestamp: new Date().toISOString(),
          }]);
        }
      }
      
      setConversationId(sessionId);
      
      // Відновлюємо conversation_id з бази даних з localStorage якщо є
      const savedDbId = localStorage.getItem(`web_chat_conversation_db_id_${sessionId}`);
      if (savedDbId) {
        setConversationDbId(parseInt(savedDbId));
      }
    } catch (error) {
      console.error('Failed to initialize conversation:', error);
      setMessages([{
        id: 'error',
        role: 'assistant',
        content: t('webChat.connectionError') || 'Connection error. Please try again later.',
        timestamp: new Date().toISOString(),
      }]);
    }
  };

  const handleImageSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        alert('Please select an image file');
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        alert('Image size must be less than 10MB');
        return;
      }
      const reader = new FileReader();
      reader.onloadend = () => {
        setSelectedImage({
          file: file,
          preview: reader.result,
        });
      };
      reader.readAsDataURL(file);
    }
  };

  const removeImage = () => {
    setSelectedImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Speech-to-Text функції
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Використовуємо audio/mp4 або audio/webm;codecs=opus для кращої сумісності
      let options = { mimeType: 'audio/webm;codecs=opus' };
      
      // Спробуємо знайти підтримуваний формат
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options = { mimeType: 'audio/webm' };
      }
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options = { mimeType: 'audio/mp4' };
      }
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options = {};
      }
      
      const mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const mimeType = mediaRecorder.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        await handleSpeechToText(audioBlob, mimeType);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error('Error starting recording:', error);
      alert('Microphone permission denied');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleSpeechToText = async (audioBlob, mimeType) => {
    try {
      setLoading(true);
      
      // Визначаємо розширення файлу на основі MIME типу
      let extension = 'webm';
      if (mimeType.includes('mp4')) {
        extension = 'mp4';
      } else if (mimeType.includes('ogg')) {
        extension = 'ogg';
      } else if (mimeType.includes('opus')) {
        extension = 'opus';
      }
      
      const audioFile = new File([audioBlob], `recording.${extension}`, { type: mimeType });
      const response = await ragAPI.speechToText(audioFile);
      const transcribedText = response.data?.text || '';
      
      if (transcribedText) {
        // Встановлюємо розпізнаний текст в поле введення
        setInputMessage(transcribedText);
      }
      setLoading(false);
    } catch (error) {
      console.error('STT error:', error);
      alert('Failed to transcribe audio. Please try again.');
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    const messageText = inputMessage.trim();
    if ((!messageText && !selectedImage) || loading || !conversationId) return;

    // Add user message
    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: messageText || '',
      image: selectedImage?.preview || null,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => {
      const updatedMessages = [...prev, userMessage];
      // Save to localStorage (without images to save space)
      const historyKey = `web_chat_history_${conversationId}`;
      const messagesToSave = updatedMessages.map(msg => {
        // Виключаємо base64 зображення для економії місця
        const { image, ...msgWithoutImage } = msg;
        return {
          ...msgWithoutImage,
          hasImage: !!image // Зберігаємо тільки прапорець, що було зображення
        };
      });
      localStorage.setItem(historyKey, JSON.stringify(messagesToSave));
      return updatedMessages;
    });
    setInputMessage('');
    setSelectedImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    setLoading(true);

    try {
      let response;
      
      // Підготовка контексту для AI (останні 30 повідомлень)
      const recentMessages = messages.slice(-30).map(msg => ({
        role: msg.role,
        content: msg.content + (msg.hasImage && !msg.image ? ' [with image]' : '')
      }));
      
      if (selectedImage) {
        // Send message with image - використовуємо FormData для відправки файлу
        const formData = new FormData();
        formData.append('message', messageText || 'Analyze this image');
        formData.append('image', selectedImage.file);
        // Додаємо контекст як JSON string
        formData.append('context', JSON.stringify(recentMessages));
        // Додаємо session_id для бекендового контексту
        formData.append('session_id', conversationId);
        // X-Client-Token додається автоматично через axios interceptor
        response = await api.post('/rag/chat/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      } else {
        // Send text message only with context
        // X-Client-Token додається автоматично через axios interceptor
        response = await api.post('/rag/chat/', {
          message: messageText,
          session_id: conversationId,
          context: recentMessages,
        });
      }

      if (response.data?.response) {
        const responseText = response.data.response || '';
        
        const assistantMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: responseText,
          timestamp: new Date().toISOString(),
        };
        
        setMessages(prev => {
          const updatedMessages = [...prev, assistantMessage];
          // Save to localStorage (without images to save space)
          const historyKey = `web_chat_history_${conversationId}`;
          const messagesToSave = updatedMessages.map(msg => {
            // Виключаємо base64 зображення для економії місця
            const { image, ...msgWithoutImage } = msg;
            return {
              ...msgWithoutImage,
              hasImage: !!image // Зберігаємо тільки прапорець, що було зображення
            };
          });
          localStorage.setItem(historyKey, JSON.stringify(messagesToSave));
          return updatedMessages;
        });
        
        // Save conversation to history
        try {
          // Визначаємо platform: якщо відкрито в iframe або через widget - це web_widget
          const isInIframe = window.self !== window.top;
          const isWidget = window.location.pathname.includes('/widget') || isInIframe;
          const platform = isWidget ? 'web_widget' : 'web';
          
          const saveResponse = await api.post('/clients/web-conversations/', {
            session_id: conversationId,
            message: messageText || 'Image analysis',
            response: response.data.response,
            platform: platform,
          });
          
          // Зберігаємо conversation_id з бази даних для оцінки
          if (saveResponse.data?.conversation_id) {
            setConversationDbId(saveResponse.data.conversation_id);
            // Зберігаємо в localStorage для відновлення при перезавантаженні
            localStorage.setItem(`web_chat_conversation_db_id_${conversationId}`, saveResponse.data.conversation_id.toString());
          }
        } catch (saveError) {
          console.error('Failed to save conversation:', saveError);
        }
      }
    } catch (error) {
      console.error('Failed to send message:', error);
        const errorMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: t('webChat.errorOccurred') || 'Sorry, an error occurred. Please try again.',
          timestamp: new Date().toISOString(),
        };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleInputFocus = () => {
    // Прокручуємо до низу при фокусі на input (коли з'являється клавіатура)
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 300); // Затримка для очікування анімації клавіатури
  };

  const handleInstall = async () => {
    if (!deferredPrompt) {
      return;
    }
    
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    
    if (outcome === 'accepted') {
      console.log('User accepted the install prompt');
    }
    
    setDeferredPrompt(null);
    setShowInstallPrompt(false);
  };

  const handleFontSizeChange = (size) => {
    if (size === 'sm' || size === 'md' || size === 'lg') {
      setFontSize(size);
    }
  };

  const messageFontClass =
    fontSize === 'sm'
      ? 'text-xs sm:text-sm'
      : fontSize === 'lg'
        ? 'text-base sm:text-lg'
        : 'text-sm sm:text-base';

  const handleClearHistory = () => {
    if (confirm(t('webChat.clearHistoryConfirm') || 'Are you sure you want to clear the chat history? This action cannot be undone.')) {
      // Clear localStorage
      const storageKey = `web_chat_session_${tag}`;
      const historyKey = `web_chat_history_${conversationId}`;
      localStorage.removeItem(storageKey);
      localStorage.removeItem(historyKey);
      
      // Reinitialize conversation
      initializeConversation();
    }
  };

  if (!tag) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-200 mb-2">Error</h1>
          <p className="text-gray-600 dark:text-gray-400">{t('webChat.missingTag') || 'Missing tag parameter in URL'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-[100dvh] max-h-[100dvh] flex flex-col transition-colors overflow-hidden ${
      darkMode 
        ? 'bg-gray-900 text-gray-100' 
        : 'bg-gray-50 text-gray-900'
    }`} style={{
      paddingTop: 'env(safe-area-inset-top)',
      height: '100dvh',
      position: 'fixed',
      inset: 0,
    }}>
      {/* Header - мобільно-адаптований з брендованим градієнтом */}
      <div className={`relative border-b px-3 sm:px-4 py-2 sm:py-3 flex items-center justify-between flex-shrink-0 z-20 ${
        darkMode 
          ? 'bg-gradient-to-r from-gray-800 via-gray-800 to-gray-800 border-gray-700' 
          : clientLogo
            ? 'bg-gradient-to-r from-white via-white to-gray-50 border-gray-200'
            : 'bg-white border-gray-200'
      }`} style={{
        position: 'sticky',
        top: 0,
      }}>
        {/* Логотип клієнта як тонкий фон (опціонально) */}
        {clientLogo && (
          <div 
            className="absolute inset-0 opacity-[0.03] dark:opacity-[0.05] pointer-events-none overflow-hidden"
            style={{
              backgroundImage: `url(${clientLogo})`,
              backgroundSize: '200%',
              backgroundPosition: 'center',
              backgroundRepeat: 'no-repeat',
              filter: 'blur(20px)',
            }}
          />
        )}
        <div className="relative z-10 flex items-center gap-2 flex-1 min-w-0">
          {clientLogo && (
            <img 
              src={clientLogo} 
              alt={clientName || 'Logo'} 
              className="h-7 sm:h-8 w-7 sm:w-8 rounded-full object-cover flex-shrink-0 ring-2 ring-white/50 dark:ring-gray-700/50 shadow-sm"
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
          )}
          <h1 className={`font-semibold truncate flex-1 ${
            fontSize === 'sm'
              ? 'text-sm sm:text-base'
              : fontSize === 'lg'
                ? 'text-lg sm:text-xl'
                : 'text-base sm:text-lg'
          }`}>
            {clientName || t('webChat.title') || 'Chat with Consultant'}
          </h1>
        </div>
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className={`relative z-10 inline-flex items-center justify-center w-8 h-8 sm:w-9 sm:h-9 rounded-lg transition-colors ${
            darkMode
              ? 'bg-gray-700/80 hover:bg-gray-600 text-gray-200 backdrop-blur-sm'
              : 'bg-white/80 hover:bg-gray-100 text-gray-700 backdrop-blur-sm shadow-sm'
          }`}
          title="Menu"
        >
          <Menu size={18} className="sm:w-5 sm:h-5" />
        </button>
      </div>

      {/* Sidebar з налаштуваннями */}
      <div className={`fixed inset-y-0 right-0 z-50 w-64 bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 shadow-xl transform transition-transform duration-300 ease-in-out ${
        sidebarOpen ? 'translate-x-0' : 'translate-x-full'
      }`} style={{
        paddingTop: 'env(safe-area-inset-top)',
        paddingBottom: 'env(safe-area-inset-bottom)'
      }}>
        <div className="flex flex-col h-full">
          {/* Sidebar Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {t('webChat.settings') || 'Settings'}
            </h2>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400"
            >
              <X size={20} />
            </button>
          </div>
          
          {/* Sidebar Content */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Clear History */}
            <button
              onClick={() => {
                handleClearHistory();
                setSidebarOpen(false);
              }}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                darkMode
                  ? 'bg-gray-700/50 hover:bg-gray-600 text-gray-200'
                  : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
              }`}
            >
              <Trash2 size={20} />
              <span className="font-medium">{t('webChat.clearHistory') || 'Clear History'}</span>
            </button>
            
            {/* Install PWA */}
            {showInstallPrompt && deferredPrompt && (
              <button
                onClick={() => {
                  handleInstall();
                  setSidebarOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  darkMode
                    ? 'bg-gray-700/50 hover:bg-gray-600 text-gray-200'
                    : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                }`}
              >
                <Download size={20} />
                <span className="font-medium">{t('webChat.installApp') || 'Install App'}</span>
              </button>
            )}
            
            {/* Dark Mode Toggle */}
            <div className={`p-4 rounded-lg ${
              darkMode ? 'bg-gray-700/50' : 'bg-gray-100'
            }`}>
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {darkMode ? (t('webChat.lightMode') || 'Light Mode') : (t('webChat.darkMode') || 'Dark Mode')}
                </span>
                <button
                  onClick={() => setDarkMode(!darkMode)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    darkMode ? 'bg-blue-600' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      darkMode ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </div>
            
            {/* Font Size Controls */}
            <div className={`p-4 rounded-lg ${
              darkMode ? 'bg-gray-700/50' : 'bg-gray-100'
            }`}>
              <div className="mb-3">
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {t('webChat.fontSize') || 'Font Size'}
                </span>
              </div>
              <div className="flex items-center justify-center gap-2">
                <button
                  type="button"
                  onClick={() => handleFontSizeChange('sm')}
                  className={`flex-1 py-2 rounded-lg transition-colors flex items-center justify-center ${
                    fontSize === 'sm'
                      ? darkMode
                        ? 'bg-gray-700 text-white'
                        : 'bg-gray-200 text-gray-900'
                      : darkMode
                        ? 'bg-gray-600/50 text-gray-300 hover:bg-gray-600'
                        : 'bg-white text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <span className="text-[10px] leading-none">A</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleFontSizeChange('md')}
                  className={`flex-1 py-2 rounded-lg transition-colors flex items-center justify-center ${
                    fontSize === 'md'
                      ? darkMode
                        ? 'bg-gray-700 text-white'
                        : 'bg-gray-200 text-gray-900'
                      : darkMode
                        ? 'bg-gray-600/50 text-gray-300 hover:bg-gray-600'
                        : 'bg-white text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <span className="text-xs leading-none">A</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleFontSizeChange('lg')}
                  className={`flex-1 py-2 rounded-lg transition-colors flex items-center justify-center ${
                    fontSize === 'lg'
                      ? darkMode
                        ? 'bg-gray-700 text-white'
                        : 'bg-gray-200 text-gray-900'
                      : darkMode
                        ? 'bg-gray-600/50 text-gray-300 hover:bg-gray-600'
                        : 'bg-white text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <span className="text-sm leading-none">A</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Overlay для закриття сайдбара */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Messages Area - мобільно-адаптований з safe-area */}
      <div className="flex-1 overflow-y-auto p-2 sm:p-4 space-y-3 sm:space-y-4 smooth-scroll pb-20 sm:pb-24" style={{
        paddingLeft: 'max(0.5rem, env(safe-area-inset-left))',
        paddingRight: 'max(0.5rem, env(safe-area-inset-right))',
        WebkitOverflowScrolling: 'touch'
      }}>
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] sm:max-w-[80%] rounded-lg px-3 py-2 sm:px-4 sm:py-2 ${
                message.role === 'user'
                  ? darkMode
                    ? 'bg-blue-600 text-white'
                    : 'bg-primary-600 text-white'
                  : darkMode
                    ? 'bg-gray-800 text-gray-100 border border-gray-700'
                    : 'bg-white text-gray-800 border border-gray-200'
              }`}
            >
              {message.image && (
                <img 
                  src={message.image} 
                  alt="Uploaded" 
                  className="max-w-full h-auto rounded mb-2"
                />
              )}
              {!message.image && message.hasImage && (
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-2 italic flex items-center gap-1">
                  <Image size={14} />
                  {t('webChat.imageUploaded') || '[Image was uploaded]'}
                </div>
              )}
              {message.content && (
                <p className={`${messageFontClass} whitespace-pre-wrap`}>{message.content}</p>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className={`rounded-lg px-4 py-2 ${
              darkMode
                ? 'bg-gray-800 border border-gray-700'
                : 'bg-white border border-gray-200'
            }`}>
              <Loader2 size={16} className={`animate-spin ${
                darkMode ? 'text-blue-400' : 'text-primary-600'
              }`} />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area - мобільно-адаптований з safe-area */}
      <div className={`fixed bottom-0 left-0 right-0 border-t p-2 sm:p-4 z-30 ${
        darkMode
          ? 'bg-gray-800/98 border-gray-700 backdrop-blur-md'
          : 'bg-white/98 border-gray-200 backdrop-blur-md'
      }`} style={{
        paddingLeft: 'max(0.5rem, env(safe-area-inset-left))',
        paddingRight: 'max(0.5rem, env(safe-area-inset-right))',
        paddingBottom: 'max(0.5rem, env(safe-area-inset-bottom))',
      }}>
        {/* Selected Image Preview */}
        {selectedImage && (
          <div className="mb-2 sm:mb-3 relative inline-block">
            <img 
              src={selectedImage.preview} 
              alt="Preview" 
              className="max-w-[150px] sm:max-w-[200px] max-h-[150px] sm:max-h-[200px] rounded-lg object-cover"
            />
            <button
              onClick={removeImage}
              className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-1.5 hover:bg-red-600 shadow-lg"
            >
              <span className="text-sm">×</span>
            </button>
          </div>
        )}
        
        <div className="flex gap-1.5 sm:gap-2">
          <button
            onClick={isRecording ? stopRecording : startRecording}
            disabled={loading}
            className={`flex items-center justify-center h-10 w-10 sm:h-11 sm:w-11 rounded-lg transition-colors flex-shrink-0 ${
              isRecording
                ? 'bg-red-500 text-white hover:bg-red-600'
                : darkMode
                  ? 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                  : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
            }`}
            title={isRecording ? (t('webChat.stopRecording') || 'Stop recording') : (t('webChat.startRecording') || 'Start voice recording')}
          >
            <Mic size={18} className="sm:w-5 sm:h-5" />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleImageSelect}
            className="hidden"
            id="image-input"
          />
          <label
            htmlFor="image-input"
            className={`inline-flex items-center justify-center h-10 w-10 sm:h-11 sm:w-11 rounded-lg cursor-pointer transition-colors flex-shrink-0 ${
              darkMode
                ? 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
            }`}
            title={t('webChat.uploadImage') || 'Upload Image'}
          >
            <Image size={18} className="sm:w-5 sm:h-5" />
          </label>
          
          <input
            ref={inputRef}
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            onFocus={handleInputFocus}
            placeholder={t('webChat.placeholder') || 'Type message...'}
            className={`flex-1 min-w-0 px-3 py-2 sm:px-4 sm:py-2 rounded-lg focus:outline-none focus:ring-2 ${
              darkMode
                ? 'bg-gray-700 border border-gray-600 text-gray-100 placeholder-gray-400 focus:ring-blue-500'
                : 'bg-white border border-gray-300 text-gray-900 placeholder-gray-500 focus:ring-primary-500'
            }`}
            style={{
              fontSize: 'max(16px, 1rem)', // Prevent iOS zoom on focus
            }}
            disabled={loading || isRecording || !conversationId}
          />
          <button
            onClick={sendMessage}
            disabled={loading || isRecording || (!inputMessage.trim() && !selectedImage) || !conversationId}
            className={`h-10 w-10 sm:h-11 sm:w-11 rounded-lg transition-colors flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0 ${
              darkMode
                ? 'bg-blue-600 hover:bg-blue-700 text-white'
                : 'bg-primary-600 hover:bg-primary-700 text-white'
            }`}
          >
            {loading ? (
              <Loader2 size={18} className="sm:w-5 sm:h-5 animate-spin" />
            ) : (
              <Send size={18} className="sm:w-5 sm:h-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default WebChatPage;
