import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Send, Mic, Volume2, Trash2, Image, X, BookmarkPlus } from 'lucide-react';
import { ragAPI, mcpAPI } from '../../api/agent';

const BotAvatar = () => (
  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center shrink-0 shadow-md shadow-orange-500/20">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="4" y="8" width="16" height="12" rx="3" fill="white" fillOpacity="0.9"/>
      <circle cx="9" cy="14" r="1.5" fill="#D97757"/>
      <circle cx="15" cy="14" r="1.5" fill="#D97757"/>
      <rect x="10" y="4" width="4" height="5" rx="2" fill="white" fillOpacity="0.9"/>
      <rect x="11" y="2" width="2" height="3" rx="1" fill="white" fillOpacity="0.7"/>
      <circle cx="12" cy="1.5" r="1.5" fill="#D97757" fillOpacity="0.8"/>
    </svg>
  </div>
);

const ToolCallBadge = ({ step }) => {
  const labels = {
    thinking: 'Thinking...',
    searching: 'Searching knowledge base...',
    generating: 'Generating response...',
  };
  const label = labels[step] || step;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-500/10 dark:bg-orange-500/15 border border-orange-500/20 text-orange-600 dark:text-orange-400 text-xs font-medium animate-in">
      <div className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse" />
      {label}
    </div>
  );
};

const ChatWindow = ({ fullHeight = false, channel = 'sandbox' }) => {
  const { t, i18n } = useTranslation();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [selectedImage, setSelectedImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [savingQA, setSavingQA] = useState(null); // ID повідомлення, яке зараз зберігається
  const [clientTag, setClientTag] = useState(null); // Зберігаємо tag клієнта
  const [mcpEnabled, setMcpEnabled] = useState(false);
  const [mcpStatus, setMcpStatus] = useState(null); // { step: 'thinking' | 'searching' | 'generating' }
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioPlayerRef = useRef(null);
  const inputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const isInitializedRef = useRef(false);

  // Отримуємо унікальний ключ для історії на базі tag клієнта
  const getStorageKey = () => {
    const prefix = channel === 'sandbox' ? 'sandbox' : 'consultant';
    // Спочатку перевіряємо URL
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const tag = urlParams.get('tag');
      if (tag) return `${prefix}_chat_history_${tag}`;
    } catch (_) {}

    // Потім перевіряємо localStorage
    const storedTag = localStorage.getItem('client_tag');
    if (storedTag) return `${prefix}_chat_history_${storedTag}`;

    // Fallback
    return `${prefix}_chat_history_default`;
  };

  // Ініціалізація: визначаємо tag та завантажуємо історію
  useEffect(() => {
    if (!isInitializedRef.current) {
      isInitializedRef.current = true;
      
      // Визначаємо tag клієнта
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const tag = urlParams.get('tag') || localStorage.getItem('client_tag');
        setClientTag(tag);
      } catch (_) {
        const tag = localStorage.getItem('client_tag');
        setClientTag(tag);
      }
      
      initializeChat();
    }
  }, []);

  // Check MCP flag
  useEffect(() => {
    const flag = localStorage.getItem('mcp_real_agent');
    if (flag === 'true') setMcpEnabled(true);
  }, []);

  const initializeChat = () => {
    // Завантажуємо історію з унікального ключа для цього клієнта
    const storageKey = getStorageKey();
    const savedHistory = localStorage.getItem(storageKey);
    if (savedHistory) {
      try {
        const parsedHistory = JSON.parse(savedHistory);
        // Конвертуємо timestamp з рядка в Date
        const historyWithDates = parsedHistory.map(msg => ({
          ...msg,
          timestamp: new Date(msg.timestamp)
        }));
        setMessages(historyWithDates);
      } catch (error) {
        console.error('Failed to parse saved history:', error);
        setDefaultMessage();
      }
    } else {
      setDefaultMessage();
    }
  };

  const setDefaultMessage = () => {
    setMessages([
      { id: 1, text: t('sandbox.helloMessage'), sender: 'ai', timestamp: new Date() },
    ]);
  };

  // Оновлення привітального повідомлення при зміні мови (якщо тільки воно одне)
  useEffect(() => {
    if (messages.length === 1 && messages[0].id === 1) {
      setMessages([
        { id: 1, text: t('sandbox.helloMessage'), sender: 'ai', timestamp: new Date() },
      ]);
    }
  }, [i18n.language, t]);

  // Збереження історії при зміні messages (без зображень для економії місця)
  useEffect(() => {
    if (messages.length > 0 && isInitializedRef.current) {
      // Виключаємо image з збереження, бо base64 може бути дуже великим
      const messagesToSave = messages.map(msg => {
        const { image, ...msgWithoutImage } = msg;
        return msgWithoutImage;
      });
      const storageKey = getStorageKey();
      localStorage.setItem(storageKey, JSON.stringify(messagesToSave));
    }
  }, [messages]);

  // Прокрутка до кінця повідомлень
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Автоматичний фокус на поле введення після відповіді AI
  useEffect(() => {
    if (!loading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [messages, loading]);

  const handleImageSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedImage(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleRemoveImage = () => {
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSend = async () => {
    if (!input.trim() && !selectedImage) return;

    if (mcpEnabled) {
      setLoading(true);
      const userMsg = {
        id: Date.now(),
        text: input,
        sender: 'user',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, userMsg]);
      const userMessage = input;
      setInput('');

      mcpAPI.chatSSE(
        userMessage,
        channel,
        (text) => {
          setMcpStatus(null); // got first token, hide status
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last?.sender === 'ai' && last?.streaming) {
              return [...prev.slice(0, -1), { ...last, text: last.text + text }];
            }
            return [...prev, { id: Date.now(), sender: 'ai', text, streaming: true, timestamp: new Date() }];
          });
        },
        () => {
          setMessages(prev => prev.map(m => ({ ...m, streaming: false })));
          setMcpStatus(null);
          setLoading(false);
        },
        (error) => {
          setMessages(prev => [...prev, {
            id: Date.now(),
            sender: 'ai',
            text: `Error: ${error}`,
            timestamp: new Date(),
          }]);
          setMcpStatus(null);
          setLoading(false);
        },
        (statusData) => {
          setMcpStatus(statusData);
        },
      );
      return;
    }

    const userMessage = {
      id: Date.now(),
      text: input || (selectedImage ? '[Image]' : ''),
      sender: 'user',
      timestamp: new Date(),
      image: imagePreview,
    };

    // Формуємо локальну історію включно з поточним повідомленням
    const updatedHistory = [...messages, userMessage];
    setMessages(updatedHistory);
    const messageText = input;
    const imageFile = selectedImage;
    setInput('');
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    setLoading(true);

    try {
      // Формуємо контекст для AI (останні 30 повідомлень)
      const recentMessages = updatedHistory.slice(-30).map((msg) => ({
        role: msg.sender === 'user' ? 'user' : 'assistant',
        content: msg.text,
      }));

      // Використовуємо RAG API для чату (з підтримкою зображень + контексту)
      const response = await ragAPI.chat(messageText, imageFile, recentMessages);
      const aiMessage = {
        id: Date.now() + 1,
        text: response.data?.response || t('sandbox.testResponse'),
        sender: 'ai',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      // Fallback на мок відповідь
      const aiMessage = {
        id: Date.now() + 1,
        text: t('sandbox.testResponse'),
        sender: 'ai',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);
    } finally {
      setLoading(false);
    }
  };

  // Запис голосу (STT)
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await handleSpeechToText(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error('Error starting recording:', error);
      alert(t('sandbox.micPermissionError') || 'Microphone permission denied');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleSpeechToText = async (audioBlob) => {
    try {
      setLoading(true);
      // Конвертуємо Blob в File для відправки
      const audioFile = new File([audioBlob], 'recording.webm', { type: 'audio/webm' });
      const response = await ragAPI.speechToText(audioFile);
      const transcribedText = response.data?.text || '';
      
      if (transcribedText) {
        // Автоматично відправляємо розпізнаний текст
        const userMessage = {
          id: Date.now(),
          text: transcribedText,
          sender: 'user',
          timestamp: new Date(),
        };

        setMessages((prev) => [...prev, userMessage]);
        setLoading(true);

        try {
          // Формуємо контекст для AI (останні 30 повідомлень)
          const recentMessages = [...messages, userMessage].slice(-30).map((msg) => ({
            role: msg.sender === 'user' ? 'user' : 'assistant',
            content: msg.text,
          }));

          // Використовуємо RAG API для чату з контекстом
          const chatResponse = await ragAPI.chat(transcribedText, null, recentMessages);
          const aiMessage = {
            id: Date.now() + 1,
            text: chatResponse.data?.response || t('sandbox.testResponse'),
            sender: 'ai',
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, aiMessage]);
        } catch (error) {
          console.error('Chat error:', error);
          // Fallback на мок відповідь
          const aiMessage = {
            id: Date.now() + 1,
            text: t('sandbox.testResponse'),
            sender: 'ai',
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, aiMessage]);
        } finally {
          setLoading(false);
        }
      }
    } catch (error) {
      console.error('STT error:', error);
      alert(t('sandbox.sttError') || 'Failed to transcribe audio');
      setLoading(false);
    }
  };

  // Відтворення голосу (TTS)
  const handleTextToSpeech = async (text) => {
    if (!text || isPlaying) return;

    try {
      setIsPlaying(true);
      const response = await ragAPI.textToSpeech(text, 'alloy');
      
      // Створюємо audio URL з blob
      const audioUrl = URL.createObjectURL(response.data);
      const audio = new Audio(audioUrl);
      audioPlayerRef.current = audio;

      audio.onended = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl);
      };

      audio.onerror = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl);
        console.error('Audio playback error');
      };

      await audio.play();
    } catch (error) {
      console.error('TTS error:', error);
      setIsPlaying(false);
      alert(t('sandbox.ttsError') || 'Failed to generate speech');
    }
  };

  // Збереження Q&A в базу знань
  const handleSaveQA = async (aiMessageId) => {
    // Знайти AI повідомлення та попереднє user повідомлення
    const messageIndex = messages.findIndex(msg => msg.id === aiMessageId);
    if (messageIndex <= 0) return; // Немає попереднього повідомлення
    
    const aiMessage = messages[messageIndex];
    const userMessage = messages[messageIndex - 1];
    
    if (aiMessage.sender !== 'ai' || userMessage.sender !== 'user') return;
    
    setSavingQA(aiMessageId);
    
    try {
      await ragAPI.saveSandboxQA(userMessage.text, aiMessage.text);
      
      // Оновлюємо повідомлення, щоб показати, що воно збережено
      setMessages(prev => prev.map(msg => 
        msg.id === aiMessageId ? { ...msg, savedToKnowledge: true } : msg
      ));
      
      // Показуємо успішне повідомлення
      alert(t('sandbox.qaSaved') || 'Q&A saved to knowledge base!');
    } catch (error) {
      console.error('Error saving Q&A:', error);
      alert(t('sandbox.qaSaveError') || 'Failed to save Q&A to knowledge base');
    } finally {
      setSavingQA(null);
    }
  };

  // Очистка історії
  const handleClearHistory = () => {
    if (confirm(t('sandbox.clearHistoryConfirm') || 'Are you sure you want to clear the chat history? This action cannot be undone.')) {
      // Очищаємо localStorage для цього конкретного клієнта
      const storageKey = getStorageKey();
      localStorage.removeItem(storageKey);
      
      // Відновлюємо привітальне повідомлення
      setDefaultMessage();
    }
  };

  return (
    <div className={`card flex flex-col ${fullHeight ? 'h-full' : 'h-[600px]'}`}>
      {/* Header with Clear History Button */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('sandbox.chatTest')}</h3>
        <button
          onClick={handleClearHistory}
          className="flex items-center justify-center w-8 h-8 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-red-100 dark:hover:bg-red-900 hover:text-red-600 dark:hover:text-red-400 transition"
          title={t('sandbox.clearHistory') || 'Clear History'}
          aria-label={t('sandbox.clearHistory') || 'Clear History'}
        >
          <Trash2 size={18} />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-2 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'} animate-in`}
          >
            {msg.sender === 'ai' && <BotAvatar />}
            <div
              className={`max-w-[75%] p-3 rounded-2xl group ${
                msg.sender === 'user'
                  ? 'bg-indigo-500 dark:bg-indigo-600 text-white rounded-br-md'
                  : 'bg-gray-100 dark:bg-gray-700/50 text-gray-800 dark:text-gray-200 rounded-bl-md'
              }`}
            >
              {msg.image && (
                <img src={msg.image} alt="User upload" className="w-full rounded-lg mb-2 max-h-48 object-cover" />
              )}
              <div className="flex items-start justify-between gap-2">
                {msg.sender === 'ai' ? (
                  <div className="text-sm flex-1 prose prose-sm dark:prose-invert max-w-none
                    prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5
                    prose-headings:my-2 prose-headings:font-semibold
                    prose-code:bg-gray-200 prose-code:dark:bg-gray-600 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs
                    prose-pre:bg-gray-900 prose-pre:dark:bg-gray-950 prose-pre:rounded-lg prose-pre:p-3
                    prose-a:text-indigo-400 prose-a:no-underline prose-a:hover:underline
                    prose-table:text-xs prose-th:px-2 prose-th:py-1 prose-td:px-2 prose-td:py-1
                    prose-img:rounded-lg prose-img:max-h-64">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="text-sm flex-1">{msg.text}</p>
                )}
                {msg.sender === 'ai' && !msg.streaming && (
                  <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => handleTextToSpeech(msg.text)}
                      disabled={isPlaying}
                      className="flex items-center justify-center w-6 h-6 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500 dark:text-gray-400 transition cursor-pointer"
                      title={t('sandbox.playVoice') || 'Play voice'}
                      aria-label={t('sandbox.playVoice') || 'Play voice'}
                    >
                      <Volume2 size={14} />
                    </button>
                    <button
                      onClick={() => handleSaveQA(msg.id)}
                      disabled={savingQA === msg.id || msg.savedToKnowledge}
                      className={`flex items-center justify-center w-6 h-6 rounded transition cursor-pointer ${
                        msg.savedToKnowledge
                          ? 'text-green-500'
                          : 'text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
                      }`}
                      title={msg.savedToKnowledge ? (t('sandbox.savedToKnowledge') || 'Saved') : (t('sandbox.saveToKnowledge') || 'Save to knowledge base')}
                      aria-label={msg.savedToKnowledge ? (t('sandbox.savedToKnowledge') || 'Saved') : (t('sandbox.saveToKnowledge') || 'Save to knowledge base')}
                    >
                      <BookmarkPlus size={14} />
                    </button>
                  </div>
                )}
              </div>
              <p className={`text-[10px] mt-1.5 ${
                msg.sender === 'user' ? 'text-indigo-200' : 'text-gray-400 dark:text-gray-500'
              }`}>
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-2 justify-start animate-in">
            <BotAvatar />
            <div className="bg-gray-100 dark:bg-gray-700/50 p-3 rounded-2xl rounded-bl-md">
              {mcpStatus ? (
                <ToolCallBadge step={mcpStatus.step} />
              ) : (
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    <div className="w-1.5 h-1.5 bg-orange-400 rounded-full animate-bounce" style={{animationDelay: '0ms'}} />
                    <div className="w-1.5 h-1.5 bg-orange-400 rounded-full animate-bounce" style={{animationDelay: '150ms'}} />
                    <div className="w-1.5 h-1.5 bg-orange-400 rounded-full animate-bounce" style={{animationDelay: '300ms'}} />
                  </div>
                  <span className="text-xs text-gray-400">Thinking...</span>
                </div>
              )}
            </div>
          </div>
        )}
        {messages.length <= 1 && !loading && channel === 'sandbox' && (
          <div className="flex flex-col items-center gap-4 py-6 animate-in">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-500/20">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
                <rect x="4" y="8" width="16" height="12" rx="3" fill="white" fillOpacity="0.9"/>
                <circle cx="9" cy="14" r="1.5" fill="#D97757"/>
                <circle cx="15" cy="14" r="1.5" fill="#D97757"/>
                <rect x="10" y="4" width="4" height="5" rx="2" fill="white" fillOpacity="0.9"/>
                <rect x="11" y="2" width="2" height="3" rx="1" fill="white" fillOpacity="0.7"/>
                <circle cx="12" cy="1.5" r="1.5" fill="#D97757" fillOpacity="0.8"/>
              </svg>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center">Try asking me something:</p>
            <div className="flex flex-wrap gap-2 justify-center max-w-md">
              {[
                'Show my leads from this week',
                'Research techstack of stripe.com',
                'What are my lead conversion stats?',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => { setInput(suggestion); }}
                  className="px-3 py-1.5 text-xs rounded-full border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 hover:border-gray-300 dark:hover:border-gray-500 transition-all cursor-pointer"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Image Preview */}
      {imagePreview && (
        <div className="mb-2 relative inline-block">
          <img src={imagePreview} alt="Preview" className="max-h-32 rounded-lg" />
          <button
            onClick={handleRemoveImage}
            className="absolute top-2 right-2 bg-red-500 dark:bg-red-600 text-white p-1.5 rounded-full hover:bg-red-600 dark:hover:bg-red-700 shadow-lg transition-all flex items-center justify-center w-6 h-6"
            title={t('sandbox.removeImage') || 'Remove image'}
            aria-label={t('sandbox.removeImage') || 'Remove image'}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2 items-center">
        <button
          onClick={isRecording ? stopRecording : startRecording}
          className={`flex items-center justify-center w-10 h-10 rounded-lg transition ${
            isRecording
              ? 'bg-red-500 dark:bg-red-600 text-white hover:bg-red-600 dark:hover:bg-red-700'
              : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
          }`}
          title={isRecording ? (t('sandbox.stopRecording') || 'Stop recording') : (t('sandbox.startRecording') || 'Start recording')}
          aria-label={isRecording ? (t('sandbox.stopRecording') || 'Stop recording') : (t('sandbox.startRecording') || 'Start recording')}
          disabled={loading}
        >
          <Mic size={18} />
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
          className={`flex items-center justify-center w-10 h-10 rounded-lg cursor-pointer transition bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 ${loading || isRecording ? 'opacity-50 cursor-not-allowed' : ''}`}
          title={t('sandbox.uploadImage') || 'Upload image'}
          aria-label={t('sandbox.uploadImage') || 'Upload image'}
        >
          <Image size={18} />
        </label>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            e.target.style.height = '44px';
            e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder={t('sandbox.inputPlaceholder') || 'Type your message...'}
          rows={1}
          className="flex-1 resize-none overflow-hidden bg-gray-100 dark:bg-gray-600 border border-gray-300 dark:border-gray-500 rounded-xl px-4 py-3 text-base focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-gray-900 dark:text-gray-100"
          style={{ minHeight: '44px', maxHeight: '120px' }}
          disabled={isRecording}
        />
        <button
          onClick={handleSend}
          disabled={loading || isRecording || (!input.trim() && !selectedImage)}
          title={t('sandbox.sendMessage') || 'Send message'}
          aria-label={t('sandbox.sendMessage') || 'Send message'}
          className={`flex items-center justify-center w-10 h-10 btn-primary rounded-lg ${(!input.trim() && !selectedImage) ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
};

export default ChatWindow;
