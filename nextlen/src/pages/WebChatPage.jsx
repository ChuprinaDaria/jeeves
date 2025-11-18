import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Send, Loader2, Image, Moon, Sun, Download, Trash2 } from 'lucide-react';
import api from '../api/axios';

const WebChatPage = () => {
  const [searchParams] = useSearchParams();
  const tag = searchParams.get('tag');
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [selectedImage, setSelectedImage] = useState(null);
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('web_chat_dark_mode');
    return saved ? saved === 'true' : false;
  });
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [showInstallPrompt, setShowInstallPrompt] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!tag) {
      return;
    }
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
    // Scroll to last message
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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
          content: 'Hello! I am your AI assistant. How can I help you today?',
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
              content: 'Hello! I am your AI assistant. How can I help you today?',
              timestamp: new Date().toISOString(),
            }]);
          }
        } else {
          // No saved history, add welcome message
          setMessages([{
            id: 'welcome',
            role: 'assistant',
            content: 'Hello! I am your AI assistant. How can I help you today?',
            timestamp: new Date().toISOString(),
          }]);
        }
      }
      
      setConversationId(sessionId);
    } catch (error) {
      console.error('Failed to initialize conversation:', error);
      setMessages([{
        id: 'error',
        role: 'assistant',
        content: 'Connection error. Please try again later.',
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
      // Save to localStorage
      const historyKey = `web_chat_history_${conversationId}`;
      localStorage.setItem(historyKey, JSON.stringify(updatedMessages));
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
      
      if (selectedImage) {
        // Send message with image description
        // For now, we'll send a text message indicating an image was uploaded
        // The API can be extended later to support image analysis
        const imageMessage = messageText || 'I uploaded an image. Please analyze it.';
        response = await api.post('/rag/chat/', {
          message: imageMessage,
        });
        
        // Note: In the future, we can add image analysis by sending:
        // const formData = new FormData();
        // formData.append('message', messageText || 'Analyze this image');
        // formData.append('image', selectedImage.file);
        // response = await api.post('/rag/chat/', formData, {
        //   headers: { 'Content-Type': 'multipart/form-data' },
        // });
      } else {
        // Send text message only
        response = await api.post('/rag/chat/', {
          message: messageText,
        });
      }

      if (response.data?.response) {
        const assistantMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response.data.response,
          timestamp: new Date().toISOString(),
        };
        setMessages(prev => {
          const updatedMessages = [...prev, assistantMessage];
          // Save to localStorage
          const historyKey = `web_chat_history_${conversationId}`;
          localStorage.setItem(historyKey, JSON.stringify(updatedMessages));
          return updatedMessages;
        });
        
        // Save conversation to history
        try {
          await api.post('/clients/web-conversations/', {
            session_id: conversationId,
            message: messageText || 'Image analysis',
            response: response.data.response,
            platform: 'web',
          });
        } catch (saveError) {
          console.error('Failed to save conversation:', saveError);
        }
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, an error occurred. Please try again.',
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

  const handleClearHistory = () => {
    if (confirm('Are you sure you want to clear the chat history? This action cannot be undone.')) {
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
          <p className="text-gray-600 dark:text-gray-400">Missing tag parameter in URL</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen flex flex-col transition-colors ${
      darkMode 
        ? 'bg-gray-900 text-gray-100' 
        : 'bg-gray-50 text-gray-900'
    }`}>
      {/* Header */}
      <div className={`border-b px-4 py-3 flex items-center justify-between ${
        darkMode 
          ? 'bg-gray-800 border-gray-700' 
          : 'bg-white border-gray-200'
      }`}>
        <h1 className="text-lg font-semibold">Chat with Consultant</h1>
        <div className="flex items-center gap-2">
          {/* Clear History Button */}
          <button
            onClick={handleClearHistory}
            className={`p-2 rounded-lg transition-colors ${
              darkMode
                ? 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
            }`}
            title="Clear History"
          >
            <Trash2 size={20} />
          </button>
          {/* Install PWA Button */}
          {showInstallPrompt && deferredPrompt && (
            <button
              onClick={handleInstall}
              className={`p-2 rounded-lg transition-colors ${
                darkMode
                  ? 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                  : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
              }`}
              title="Install App"
            >
              <Download size={20} />
            </button>
          )}
          {/* Dark Mode Toggle */}
          <button
            onClick={() => setDarkMode(!darkMode)}
            className={`p-2 rounded-lg transition-colors ${
              darkMode
                ? 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
            }`}
            title={darkMode ? 'Light Mode' : 'Dark Mode'}
          >
            {darkMode ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
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
              {message.content && (
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
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

      {/* Input Area */}
      <div className={`border-t p-4 ${
        darkMode
          ? 'bg-gray-800 border-gray-700'
          : 'bg-white border-gray-200'
      }`}>
        {/* Selected Image Preview */}
        {selectedImage && (
          <div className="mb-3 relative inline-block">
            <img 
              src={selectedImage.preview} 
              alt="Preview" 
              className="max-w-[200px] max-h-[200px] rounded-lg object-cover"
            />
            <button
              onClick={removeImage}
              className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-1 hover:bg-red-600"
            >
              <span className="text-xs">×</span>
            </button>
          </div>
        )}
        
        <div className="flex gap-2">
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
            className={`p-2 rounded-lg cursor-pointer transition-colors ${
              darkMode
                ? 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
            }`}
            title="Upload Image"
          >
            <Image size={20} />
          </label>
          
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            className={`flex-1 px-4 py-2 rounded-lg focus:outline-none focus:ring-2 ${
              darkMode
                ? 'bg-gray-700 border border-gray-600 text-gray-100 placeholder-gray-400 focus:ring-blue-500'
                : 'bg-white border border-gray-300 text-gray-900 placeholder-gray-500 focus:ring-primary-500'
            }`}
            disabled={loading || !conversationId}
          />
          <button
            onClick={sendMessage}
            disabled={loading || (!inputMessage.trim() && !selectedImage) || !conversationId}
            className={`px-6 py-2 rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${
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
