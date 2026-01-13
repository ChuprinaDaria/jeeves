import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Send, Mic, Volume2, Trash2, Image, X, BookmarkPlus } from 'lucide-react';
import { ragAPI } from '../../api/agent';

const ChatWindow = () => {
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
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioPlayerRef = useRef(null);
  const inputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const isInitializedRef = useRef(false);

  // Отримуємо унікальний ключ для історії на базі tag клієнта
  const getStorageKey = () => {
    // Спочатку перевіряємо URL
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const tag = urlParams.get('tag');
      if (tag) return `sandbox_chat_history_${tag}`;
    } catch (_) {}
    
    // Потім перевіряємо localStorage
    const storedTag = localStorage.getItem('client_tag');
    if (storedTag) return `sandbox_chat_history_${storedTag}`;
    
    // Fallback на глобальний ключ (не повинно статися, але для безпеки)
    return 'sandbox_chat_history_default';
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
    <div className="card h-[600px] flex flex-col">
      {/* Header with Clear History Button */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('sandbox.chatTest')}</h3>
        <button
          onClick={handleClearHistory}
          className="flex items-center justify-center w-8 h-8 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-red-100 dark:hover:bg-red-900 hover:text-red-600 dark:hover:text-red-400 transition"
          title={t('sandbox.clearHistory') || 'Clear History'}
        >
          <Trash2 size={18} />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[70%] p-3 rounded-lg ${
                msg.sender === 'user'
                  ? 'bg-primary-500 dark:bg-primary-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200'
              }`}
            >
              {msg.image && (
                <img src={msg.image} alt="User upload" className="w-full rounded-lg mb-2 max-h-48 object-cover" />
              )}
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm flex-1">{msg.text}</p>
                {msg.sender === 'ai' && (
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => handleTextToSpeech(msg.text)}
                      disabled={isPlaying}
                      className="flex items-center justify-center w-6 h-6 rounded hover:bg-gray-600 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 transition"
                      title={t('sandbox.playVoice') || 'Play voice'}
                    >
                      <Volume2 size={16} />
                    </button>
                    <button
                      onClick={() => handleSaveQA(msg.id)}
                      disabled={savingQA === msg.id || msg.savedToKnowledge}
                      className={`flex items-center justify-center w-6 h-6 rounded transition ${
                        msg.savedToKnowledge
                          ? 'text-green-600 dark:text-green-400'
                          : 'text-gray-700 dark:text-gray-300 hover:bg-gray-600 dark:hover:bg-gray-700'
                      }`}
                      title={msg.savedToKnowledge ? (t('sandbox.savedToKnowledge') || 'Saved to knowledge base') : (t('sandbox.saveToKnowledge') || 'Save to knowledge base')}
                    >
                      <BookmarkPlus size={16} />
                    </button>
                  </div>
                )}
              </div>
              <p
                className={`text-xs mt-1 ${
                  msg.sender === 'user' ? 'text-primary-100' : 'text-gray-500 dark:text-gray-400'
                }`}
              >
                {msg.timestamp.toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 dark:bg-gray-800 p-3 rounded-lg">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce delay-100"></div>
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce delay-200"></div>
              </div>
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
        >
          <Image size={18} />
        </label>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          placeholder={t('sandbox.typeMessage')}
          className="flex-1 input"
          disabled={isRecording}
        />
        <button 
          onClick={handleSend} 
          disabled={loading || isRecording || (!input.trim() && !selectedImage)} 
          className="flex items-center justify-center w-10 h-10 btn-primary rounded-lg"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
};

export default ChatWindow;
