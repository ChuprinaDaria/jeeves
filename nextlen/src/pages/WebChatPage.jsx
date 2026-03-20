import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Send, Loader2, Image, Moon, Sun, Download, Trash2, Mic, Menu, X, Sparkles, Volume2, VolumeX, Square } from 'lucide-react';
import api from '../api/axios';
import { ragAPI } from '../api/agent';
import { clientAPI } from '../api/client';
import { updateBrandingFromClient } from '../utils/helpers';

const WebChatPage = () => {
  const { t, i18n } = useTranslation();
  const [searchParams] = useSearchParams();
  const tag = searchParams.get('tag');
  const sessionParam = searchParams.get('session');
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [conversationDbId, setConversationDbId] = useState(null);
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
  const [autoVoiceReply, setAutoVoiceReply] = useState(() => {
    const saved = localStorage.getItem('web_chat_auto_voice');
    return saved !== 'false'; // default ON
  });
  const [lastInputWasVoice, setLastInputWasVoice] = useState(false);
  const [playingMessageId, setPlayingMessageId] = useState(null);
  const [ttsLoading, setTtsLoading] = useState(null);
  const [ttsVoice, setTtsVoice] = useState(() => {
    return localStorage.getItem('web_chat_tts_voice') || 'alloy';
  });
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const inputRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioRef = useRef(null);
  const lastInputWasVoiceRef = useRef(false);
  const autoVoiceReplyRef = useRef(localStorage.getItem('web_chat_auto_voice') !== 'false');
  const ttsVoiceRef = useRef(localStorage.getItem('web_chat_tts_voice') || 'alloy');
  const lastCountRef = useRef(0);

  useEffect(() => {
    if (!tag) {
      return;
    }
    
    const setupWebChatManifest = () => {
      const existingManifest = document.querySelector('link[rel="manifest"]');
      if (existingManifest) {
        existingManifest.remove();
      }
      
      const manifestLink = document.createElement('link');
      manifestLink.rel = 'manifest';
      manifestLink.href = `${api.defaults.baseURL || ''}/rag/webchat/manifest.json?tag=${tag}`;
      document.head.appendChild(manifestLink);
    };
    
    setupWebChatManifest();
    
    const applyBranding = async () => {
      try {
        const { data } = await clientAPI.getMe();
        updateBrandingFromClient(data, { context: 'webchat' });
        if (data.logo_url || data.logo) {
          setClientLogo(data.logo_url || data.logo);
        }
        if (data.company_name || data.user) {
          setClientName(data.company_name || data.user);
        }
        // Show greeting message as first assistant message
        if (data.greeting_message) {
          setMessages([{
            id: 'greeting',
            role: 'assistant',
            content: data.greeting_message,
            timestamp: new Date().toISOString(),
          }]);
        }
      } catch (e) {
        document.title = 'AI Chat Assistant';
      }
    };

    applyBranding();
    initializeConversation();
    
    const handleBeforeInstallPrompt = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
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
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!loading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [messages, loading]);

  useEffect(() => {
    if (!conversationId || !tag) return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await api.get('/clients/web-conversations/', {
          params: {
            session_id: conversationId,
            last_count: lastCountRef.current,
          },
        });

        // Update lastCount from server response to keep it synchronized
        if (response.data?.total !== undefined) {
          lastCountRef.current = response.data.total;
        }

        if (response.data?.has_new && response.data?.messages?.length > 0) {
          const newMessages = response.data.messages.map((msg, idx) => ({
            id: `hitl_${Date.now()}_${idx}`,
            role: msg.role,
            content: msg.content,
            timestamp: msg.timestamp,
          }));
          
          setMessages(prev => [...prev, ...newMessages]);
          
          if (response.data.conversation_id && !conversationDbId) {
            setConversationDbId(response.data.conversation_id);
          }
        }
      } catch (error) {
        console.debug('Polling error:', error);
      }
    }, 5000);

    return () => clearInterval(pollInterval);
  }, [conversationId, tag, conversationDbId]);

  useEffect(() => {
    let resizeTimer;
    const handleResize = () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (window.visualViewport) {
          document.documentElement.style.setProperty('--viewport-height', `${window.visualViewport.height}px`);
        } else {
          document.documentElement.style.setProperty('--viewport-height', `${window.innerHeight}px`);
        }
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 50);
    };

    handleResize();

    window.addEventListener('resize', handleResize);
    window.addEventListener('orientationchange', handleResize);
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
      // Якщо є session в URL — відкриваємо конкретну розмову з сервера
      if (sessionParam) {
        const sessionId = sessionParam;
        localStorage.setItem(`web_chat_session_${tag}`, sessionId);
        localStorage.setItem('web_chat_session_id', sessionId);
        setConversationId(sessionId);

        try {
          const response = await api.get('/clients/web-conversations/', {
            params: { session_id: sessionId, last_count: 0 },
          });
          if (response.data?.messages?.length > 0) {
            const serverMessages = response.data.messages.map((msg, idx) => ({
              id: `server_${idx}`,
              role: msg.role,
              content: msg.content,
              timestamp: msg.timestamp,
            }));
            setMessages(serverMessages);
            lastCountRef.current = response.data.total || serverMessages.length;
          } else {
            setMessages([{
              id: 'welcome',
              role: 'assistant',
              content: (t('webChat.welcomeMessage') || 'Hello! How can I help you today?'),
              timestamp: new Date().toISOString(),
              isWelcome: true,
            }]);
          }
          if (response.data?.conversation_id) {
            setConversationDbId(response.data.conversation_id);
          }
        } catch (e) {
          console.error('Failed to load session from server:', e);
          setMessages([{
            id: 'welcome',
            role: 'assistant',
            content: (t('webChat.welcomeMessage') || 'Hello! How can I help you today?'),
            timestamp: new Date().toISOString(),
            isWelcome: true,
          }]);
        }
        return;
      }

      const storageKey = `web_chat_session_${tag}`;
      let sessionId = localStorage.getItem(storageKey);

      if (!sessionId) {
        sessionId = `web_${tag}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        localStorage.setItem(storageKey, sessionId);
        localStorage.setItem('web_chat_session_id', sessionId);

        setMessages([{
          id: 'welcome',
          role: 'assistant',
          content: (t('webChat.welcomeMessage') || 'Hello! How can I help you today?'),
          timestamp: new Date().toISOString(),
          isWelcome: true,
        }]);
      } else {
        localStorage.setItem('web_chat_session_id', sessionId);

        const historyKey = `web_chat_history_${sessionId}`;
        const savedHistory = localStorage.getItem(historyKey);

        if (savedHistory) {
          try {
            const parsedHistory = JSON.parse(savedHistory);
            setMessages(parsedHistory);
          } catch (e) {
            console.error('Failed to parse saved history:', e);
            setMessages([{
              id: 'welcome',
              role: 'assistant',
              content: (t('webChat.welcomeMessage') || 'Hello! How can I help you today?'),
              timestamp: new Date().toISOString(),
              isWelcome: true,
            }]);
          }
        } else {
          setMessages([{
            id: 'welcome',
            role: 'assistant',
            content: (t('webChat.welcomeMessage') || 'Hello! How can I help you today?'),
            timestamp: new Date().toISOString(),
            isWelcome: true,
          }]);
        }
      }

      setConversationId(sessionId);

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

  const unlockAudio = () => {
    // Створюємо і граємо тихий звук щоб розблокувати autoplay на iOS
    if (!audioRef.current) {
      const audio = new Audio();
      audio.src = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=';
      audio.volume = 0.01;
      audio.play().then(() => { audio.pause(); }).catch(() => {});
      audioRef.current = null;
    }
  };

  const startRecording = async () => {
    try {
      unlockAudio();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      let options = { mimeType: 'audio/webm;codecs=opus' };
      
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
        setLastInputWasVoice(true);
        lastInputWasVoiceRef.current = true;
        setInputMessage(transcribedText);
        setLoading(false);
        // Автоматично відправляємо голосове повідомлення
        setTimeout(() => {
          sendMessageWithText(transcribedText);
        }, 100);
        return;
      }
      setLoading(false);
    } catch (error) {
      console.error('STT error:', error);
      setLoading(false);
    }
  };

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setPlayingMessageId(null);
  };

  const playTTS = async (text, messageId) => {
    if (playingMessageId === messageId) {
      stopAudio();
      return;
    }
    stopAudio();

    try {
      setTtsLoading(messageId);
      const response = await ragAPI.textToSpeech(text, ttsVoiceRef.current);
      const audioUrl = URL.createObjectURL(response.data);
      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      audio.onplay = () => {
        setPlayingMessageId(messageId);
        setTtsLoading(null);
      };
      audio.onended = () => {
        setPlayingMessageId(null);
        audioRef.current = null;
        URL.revokeObjectURL(audioUrl);
      };
      audio.onerror = (e) => {
        console.error('Audio playback error:', e);
        setPlayingMessageId(null);
        setTtsLoading(null);
        audioRef.current = null;
        URL.revokeObjectURL(audioUrl);
      };

      await audio.play();
    } catch (error) {
      console.error('TTS error:', error);
      setTtsLoading(null);
      setPlayingMessageId(null);
    }
  };

  const toggleAutoVoice = () => {
    const newVal = !autoVoiceReply;
    setAutoVoiceReply(newVal);
    autoVoiceReplyRef.current = newVal;
    localStorage.setItem('web_chat_auto_voice', String(newVal));
    if (!newVal) {
      stopAudio();
    }
  };

  const sendMessageWithText = (text) => {
    setInputMessage(text);
    sendMessageCore(text, true);
  };

  const sendMessage = () => {
    // Текстовий ввід — скидаємо voice flag
    lastInputWasVoiceRef.current = false;
    setLastInputWasVoice(false);
    sendMessageCore(inputMessage.trim());
  };

  const sendMessageCore = async (messageText, skipLoadingCheck = false) => {
    if ((!messageText && !selectedImage) || (!skipLoadingCheck && loading) || !conversationId) return;

    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: messageText || '',
      image: selectedImage?.preview || null,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => {
      const updatedMessages = [...prev, userMessage];
      const historyKey = `web_chat_history_${conversationId}`;
      const messagesToSave = updatedMessages.map(msg => {
        const { image, ...msgWithoutImage } = msg;
        return {
          ...msgWithoutImage,
          hasImage: !!image
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
      
      const recentMessages = messages.slice(-30).map(msg => ({
        role: msg.role,
        content: msg.content + (msg.hasImage && !msg.image ? ' [with image]' : '')
      }));
      
      if (selectedImage) {
        const formData = new FormData();
        formData.append('message', messageText || 'Analyze this image');
        formData.append('image', selectedImage.file);
        formData.append('context', JSON.stringify(recentMessages));
        formData.append('session_id', conversationId);
        response = await api.post('/rag/chat/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      } else {
        response = await api.post('/rag/chat/', {
          message: messageText,
          session_id: conversationId,
          context: recentMessages,
        });
      }

      if (response.data?.response) {
        const responseText = response.data.response || '';
        const waitingNotice = response.data?.pending_escalation?.waiting_message;
        const fullContent = waitingNotice
          ? `${responseText}\n\n_${waitingNotice}_`
          : responseText;

        const assistantMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: fullContent,
          timestamp: new Date().toISOString(),
        };
        
        setMessages(prev => {
          const updatedMessages = [...prev, assistantMessage];
          const historyKey = `web_chat_history_${conversationId}`;
          const messagesToSave = updatedMessages.map(msg => {
            const { image, ...msgWithoutImage } = msg;
            return {
              ...msgWithoutImage,
              hasImage: !!image
            };
          });
          localStorage.setItem(historyKey, JSON.stringify(messagesToSave));
          return updatedMessages;
        });

        // Auto-TTS якщо ввід був голосовим і auto-voice ввімкнено
        if (lastInputWasVoiceRef.current && autoVoiceReplyRef.current && responseText) {
          playTTS(responseText, assistantMessage.id);
        }
        lastInputWasVoiceRef.current = false;
        setLastInputWasVoice(false);

        try {
          const isInIframe = window.self !== window.top;
          const isWidget = window.location.pathname.includes('/widget') || isInIframe;
          const platform = isWidget ? 'web_widget' : 'web';
          
          const saveResponse = await api.post('/clients/web-conversations/', {
            session_id: conversationId,
            message: messageText || 'Image analysis',
            response: response.data.response,
            platform: platform,
          });
          
          if (saveResponse.data?.conversation_id) {
            setConversationDbId(saveResponse.data.conversation_id);
            localStorage.setItem(`web_chat_conversation_db_id_${conversationId}`, saveResponse.data.conversation_id.toString());
          }
          // Update lastCount after saving message to server
          // POST returns total_messages, GET returns total - support both
          if (saveResponse.data?.total_messages !== undefined) {
            lastCountRef.current = saveResponse.data.total_messages;
          } else if (saveResponse.data?.total !== undefined) {
            lastCountRef.current = saveResponse.data.total;
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
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 300);
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
      const storageKey = `web_chat_session_${tag}`;
      const historyKey = `web_chat_history_${conversationId}`;
      localStorage.removeItem(storageKey);
      localStorage.removeItem(historyKey);
      
      initializeConversation();
      setSidebarOpen(false);
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
    <div className={`flex flex-col transition-colors overflow-hidden ${
      darkMode
        ? 'bg-gray-900 text-gray-100'
        : 'bg-gray-50 text-gray-900'
    }`} style={{
      paddingTop: 'env(safe-area-inset-top)',
      height: 'var(--viewport-height, 100dvh)',
      position: 'fixed',
      inset: 0,
    }}>
      {/* Header */}
      <div className={`relative border-b px-4 py-3 flex items-center justify-between flex-shrink-0 z-20 ${
        darkMode 
          ? 'bg-gradient-to-r from-gray-800 via-gray-800 to-gray-800 border-gray-700' 
          : clientLogo
            ? 'bg-gradient-to-r from-white via-white to-gray-50 border-gray-200'
            : 'bg-white border-gray-200'
      }`} style={{
        position: 'sticky',
        top: 0,
      }}>
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
        <div className="relative z-10 flex items-center gap-3 flex-1 min-w-0">
          {clientLogo && (
            <img 
              src={clientLogo} 
              alt={clientName || 'Logo'} 
              className="h-9 w-9 rounded-full object-cover flex-shrink-0 ring-2 ring-white/50 dark:ring-gray-700/50 shadow-sm"
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
          )}
          <h1 className={`font-semibold truncate flex-1 ${
            fontSize === 'sm'
              ? 'text-base'
              : fontSize === 'lg'
                ? 'text-xl'
                : 'text-lg'
          }`}>
            {clientName || t('webChat.title') || 'Chat with Consultant'}
          </h1>
        </div>
        <div className="relative z-10 flex items-center gap-2">
          <button
            onClick={toggleAutoVoice}
            className={`inline-flex items-center justify-center w-10 h-10 rounded-lg transition-all ${
              autoVoiceReply
                ? darkMode
                  ? 'bg-purple-600/80 text-white backdrop-blur-sm'
                  : 'bg-primary-500/90 text-white shadow-sm'
                : darkMode
                  ? 'bg-gray-700/80 hover:bg-gray-600 text-gray-400 backdrop-blur-sm'
                  : 'bg-white/80 hover:bg-gray-100 text-gray-400 backdrop-blur-sm shadow-sm'
            }`}
            title={autoVoiceReply ? 'Auto voice reply ON' : 'Auto voice reply OFF'}
          >
            {autoVoiceReply ? <Volume2 size={20} /> : <VolumeX size={20} />}
          </button>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className={`inline-flex items-center justify-center w-10 h-10 rounded-lg transition-all ${
              darkMode
                ? 'bg-gray-700/80 hover:bg-gray-600 text-gray-200 backdrop-blur-sm'
                : 'bg-white/80 hover:bg-gray-100 text-gray-700 backdrop-blur-sm shadow-sm'
            }`}
            title="Menu"
          >
            <Menu size={20} />
          </button>
        </div>
      </div>

      {/* Sidebar */}
      <div className={`fixed inset-y-0 right-0 z-50 w-80 bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 shadow-2xl transform transition-transform duration-300 ease-in-out ${
        sidebarOpen ? 'translate-x-0' : 'translate-x-full'
      }`} style={{
        paddingTop: 'env(safe-area-inset-top)',
        paddingBottom: 'env(safe-area-inset-bottom)'
      }}>
        <div className="flex flex-col h-full">
          {/* Sidebar Header */}
          <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <Sparkles size={22} className="text-primary-500" />
              {t('webChat.settings') || 'Settings'}
            </h2>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
            >
              <X size={22} />
            </button>
          </div>
          
          {/* Sidebar Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            
            {/* Dark Mode Toggle */}
            <div className={`p-5 rounded-xl transition-all ${
              darkMode ? 'bg-gray-700/50' : 'bg-gradient-to-br from-gray-50 to-gray-100'
            }`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {darkMode ? (
                    <Moon size={22} className="text-blue-400" />
                  ) : (
                    <Sun size={22} className="text-yellow-500" />
                  )}
                  <span className="font-semibold text-gray-900 dark:text-gray-100">
                    {darkMode ? (t('webChat.darkMode') || 'Dark Mode') : (t('webChat.lightMode') || 'Light Mode')}
                  </span>
                </div>
                <button
                  onClick={() => setDarkMode(!darkMode)}
                  className={`relative inline-flex h-8 w-16 items-center rounded-full transition-all duration-300 ${
                    darkMode ? 'bg-blue-600' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-6 w-6 transform rounded-full bg-white transition-transform duration-300 shadow-lg ${
                      darkMode ? 'translate-x-9' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </div>
            
            {/* Font Size Controls */}
            <div className={`p-5 rounded-xl transition-all ${
              darkMode ? 'bg-gray-700/50' : 'bg-gradient-to-br from-gray-50 to-gray-100'
            }`}>
              <div className="mb-4">
                <span className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                  <span className="text-xl">Aa</span>
                  {t('webChat.fontSize') || 'Font Size'}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <button
                  type="button"
                  onClick={() => handleFontSizeChange('sm')}
                  className={`py-3.5 px-4 rounded-xl transition-all flex items-center justify-center ${
                    fontSize === 'sm'
                      ? darkMode
                        ? 'bg-blue-600 text-white shadow-lg ring-2 ring-blue-400'
                        : 'bg-primary-600 text-white shadow-lg ring-2 ring-primary-300'
                      : darkMode
                        ? 'bg-gray-600/50 text-gray-300 hover:bg-gray-600'
                        : 'bg-white text-gray-600 hover:bg-gray-50 shadow-sm'
                  }`}
                >
                  <span className="text-sm font-bold">A</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleFontSizeChange('md')}
                  className={`py-3.5 px-4 rounded-xl transition-all flex items-center justify-center ${
                    fontSize === 'md'
                      ? darkMode
                        ? 'bg-blue-600 text-white shadow-lg ring-2 ring-blue-400'
                        : 'bg-primary-600 text-white shadow-lg ring-2 ring-primary-300'
                      : darkMode
                        ? 'bg-gray-600/50 text-gray-300 hover:bg-gray-600'
                        : 'bg-white text-gray-600 hover:bg-gray-50 shadow-sm'
                  }`}
                >
                  <span className="text-base font-bold">A</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleFontSizeChange('lg')}
                  className={`py-3.5 px-4 rounded-xl transition-all flex items-center justify-center ${
                    fontSize === 'lg'
                      ? darkMode
                        ? 'bg-blue-600 text-white shadow-lg ring-2 ring-blue-400'
                        : 'bg-primary-600 text-white shadow-lg ring-2 ring-primary-300'
                      : darkMode
                        ? 'bg-gray-600/50 text-gray-300 hover:bg-gray-600'
                        : 'bg-white text-gray-600 hover:bg-gray-50 shadow-sm'
                  }`}
                >
                  <span className="text-lg font-bold">A</span>
                </button>
              </div>
            </div>
            
            {/* Voice Selection */}
            <div className={`p-5 rounded-xl transition-all ${
              darkMode ? 'bg-gray-700/50' : 'bg-gradient-to-br from-gray-50 to-gray-100'
            }`}>
              <div className="mb-4">
                <span className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                  <Volume2 size={20} className="text-primary-500" />
                  {t('webChat.voiceSelect') || 'AI Voice'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: 'alloy', label: 'Alloy' },
                  { id: 'echo', label: 'Echo' },
                  { id: 'fable', label: 'Fable' },
                  { id: 'onyx', label: 'Onyx' },
                  { id: 'nova', label: 'Nova' },
                  { id: 'shimmer', label: 'Shimmer' },
                ].map((voice) => (
                  <button
                    key={voice.id}
                    onClick={() => {
                      setTtsVoice(voice.id);
                      ttsVoiceRef.current = voice.id;
                      localStorage.setItem('web_chat_tts_voice', voice.id);
                    }}
                    className={`py-2.5 px-3 rounded-xl text-sm font-medium transition-all ${
                      ttsVoice === voice.id
                        ? darkMode
                          ? 'bg-purple-600 text-white shadow-lg ring-2 ring-purple-400'
                          : 'bg-primary-600 text-white shadow-lg ring-2 ring-primary-300'
                        : darkMode
                          ? 'bg-gray-600/50 text-gray-300 hover:bg-gray-600'
                          : 'bg-white text-gray-600 hover:bg-gray-50 shadow-sm'
                    }`}
                  >
                    {voice.label}
                  </button>
                ))}
              </div>
              <div className="mt-3 flex items-center justify-between">
                <span className={`text-xs ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                  {t('webChat.autoVoiceReply') || 'Auto voice reply'}
                </span>
                <button
                  onClick={toggleAutoVoice}
                  className={`relative inline-flex h-7 w-12 items-center rounded-full transition-all duration-300 ${
                    autoVoiceReply
                      ? darkMode ? 'bg-purple-600' : 'bg-primary-600'
                      : 'bg-gray-300 dark:bg-gray-600'
                  }`}
                >
                  <span className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform duration-300 shadow ${
                    autoVoiceReply ? 'translate-x-6' : 'translate-x-1'
                  }`} />
                </button>
              </div>
            </div>

            {/* Install PWA */}
            {showInstallPrompt && deferredPrompt && (
              <button
                onClick={() => {
                  handleInstall();
                  setSidebarOpen(false);
                }}
                className={`w-full flex items-center gap-4 px-5 py-4 rounded-xl transition-all shadow-sm ${
                  darkMode
                    ? 'bg-green-600/20 hover:bg-green-600/30 text-green-400 border border-green-600/30'
                    : 'bg-green-50 hover:bg-green-100 text-green-700 border border-green-200'
                }`}
              >
                <Download size={22} />
                <span className="font-semibold">{t('webChat.installApp') || 'Install App'}</span>
              </button>
            )}
          </div>
          
          {/* Clear History */}
          <div className="p-6 border-t border-gray-200 dark:border-gray-700">
            <button
              onClick={handleClearHistory}
              className={`w-full flex items-center gap-4 px-5 py-4 rounded-xl transition-all ${
                darkMode
                  ? 'bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-600/30'
                  : 'bg-red-50 hover:bg-red-100 text-red-600 border border-red-200'
              }`}
            >
              <Trash2 size={22} />
              <span className="font-semibold">{t('webChat.clearHistory') || 'Clear History'}</span>
            </button>
          </div>
        </div>
      </div>
      
      {/* Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 transition-opacity"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 smooth-scroll pb-4" style={{
        paddingLeft: 'max(1rem, env(safe-area-inset-left))',
        paddingRight: 'max(1rem, env(safe-area-inset-right))',
        WebkitOverflowScrolling: 'touch'
      }}>
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-sm ${
                message.role === 'user'
                  ? darkMode
                    ? 'bg-blue-600 text-white'
                    : 'bg-primary-600 text-white'
                  : message.isWelcome
                    ? darkMode
                      ? 'bg-gradient-to-r from-blue-600/20 to-purple-600/20 text-gray-100 border border-blue-500/30'
                      : 'bg-gradient-to-r from-primary-50 to-purple-50 text-gray-800 border border-primary-200'
                    : darkMode
                      ? 'bg-gray-800 text-gray-100 border border-gray-700'
                      : 'bg-white text-gray-800 border border-gray-200'
              }`}
            >
              {message.image && (
                <img 
                  src={message.image} 
                  alt="Uploaded" 
                  className="max-w-full h-auto rounded-lg mb-2"
                />
              )}
              {!message.image && message.hasImage && (
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-2 italic flex items-center gap-2">
                  <Image size={14} />
                  {t('webChat.imageUploaded') || '[Image was uploaded]'}
                </div>
              )}
              {message.content && (
                <p className={`${messageFontClass} whitespace-pre-wrap ${message.isWelcome ? 'text-center font-medium' : ''}`}>
                  {message.content}
                </p>
              )}
              {message.role === 'assistant' && message.content && !message.isWelcome && (
                <button
                  onClick={() => playTTS(message.content, message.id)}
                  disabled={ttsLoading === message.id}
                  className={`mt-2 inline-flex items-center gap-1 text-xs transition-all ${
                    playingMessageId === message.id
                      ? 'text-green-500'
                      : darkMode
                        ? 'text-gray-400 hover:text-gray-200'
                        : 'text-gray-400 hover:text-gray-600'
                  }`}
                >
                  {ttsLoading === message.id ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : playingMessageId === message.id ? (
                    <Square size={14} />
                  ) : (
                    <Volume2 size={14} />
                  )}
                  {playingMessageId === message.id ? 'Stop' : 'Play'}
                </button>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className={`rounded-2xl px-4 py-3 ${
              darkMode
                ? 'bg-gray-800 border border-gray-700'
                : 'bg-white border border-gray-200'
            }`}>
              <Loader2 size={18} className={`animate-spin ${
                darkMode ? 'text-blue-400' : 'text-primary-600'
              }`} />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className={`flex-shrink-0 border-t p-4 ${
        darkMode
          ? 'bg-gray-800 border-gray-700'
          : 'bg-white border-gray-200'
      }`} style={{
        paddingLeft: 'max(1rem, env(safe-area-inset-left))',
        paddingRight: 'max(1rem, env(safe-area-inset-right))',
        paddingBottom: 'max(1rem, env(safe-area-inset-bottom))',
      }}>
        {/* Selected Image Preview */}
        {selectedImage && (
          <div className="mb-3 relative inline-block">
            <img 
              src={selectedImage.preview} 
              alt="Preview" 
              className="max-w-[180px] max-h-[180px] rounded-xl object-cover shadow-lg"
            />
            <button
              onClick={removeImage}
              className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-2 hover:bg-red-600 shadow-lg"
            >
              <X size={16} />
            </button>
          </div>
        )}
        
        <div className="flex gap-2">
          <button
            onClick={isRecording ? stopRecording : startRecording}
            disabled={loading}
            className={`flex items-center justify-center h-11 w-11 rounded-xl transition-all flex-shrink-0 shadow-sm ${
              isRecording
                ? 'bg-red-500 text-white hover:bg-red-600 animate-pulse'
                : darkMode
                  ? 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                  : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
            }`}
            title={isRecording ? (t('webChat.stopRecording') || 'Stop recording') : (t('webChat.startRecording') || 'Start voice recording')}
          >
            <Mic size={20} />
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
            className={`inline-flex items-center justify-center h-11 w-11 rounded-xl cursor-pointer transition-all flex-shrink-0 shadow-sm ${
              darkMode
                ? 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
            }`}
            title={t('webChat.uploadImage') || 'Upload Image'}
          >
            <Image size={20} />
          </label>
          
          <input
            ref={inputRef}
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            onFocus={handleInputFocus}
            placeholder={t('webChat.placeholder') || 'Ask me anything...'}
            className={`flex-1 min-w-0 px-4 py-3 rounded-xl focus:outline-none focus:ring-2 shadow-sm ${
              darkMode
                ? 'bg-gray-700 border border-gray-600 text-gray-100 placeholder-gray-400 focus:ring-blue-500'
                : 'bg-white border border-gray-300 text-gray-900 placeholder-gray-500 focus:ring-primary-500'
            }`}
            style={{
              fontSize: 'max(16px, 1rem)',
            }}
            disabled={loading || isRecording || !conversationId}
          />
          <button
            onClick={sendMessage}
            disabled={loading || isRecording || (!inputMessage.trim() && !selectedImage) || !conversationId}
            className={`h-11 w-11 rounded-xl transition-all flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0 shadow-sm ${
              darkMode
                ? 'bg-blue-600 hover:bg-blue-700 text-white'
                : 'bg-primary-600 hover:bg-primary-700 text-white'
            }`}
          >
            {loading ? (
              <Loader2 size={20} className="animate-spin" />
            ) : (
              <Send size={20} />
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default WebChatPage;