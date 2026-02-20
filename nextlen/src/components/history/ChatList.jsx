import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageSquare, Loader2, Globe, Send, Monitor } from 'lucide-react';
import { clientAPI } from '../../api/client';

const ChatList = ({ onSelectChat, selectedChatId }) => {
  const { t } = useTranslation();
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const isInitialLoad = useRef(true); // flag for first load
  
  useEffect(() => {
    loadConversations();
  }, []);
  
  const loadConversations = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await clientAPI.getConversations();
      console.log('📊 Conversations API response:', response.data);
      console.log('📊 Number of conversations:', response.data?.conversations?.length || 0);
      const conversations = response.data?.conversations || [];
      console.log('📊 Conversations by source:', conversations.reduce((acc, conv) => {
        acc[conv.source || 'unknown'] = (acc[conv.source || 'unknown'] || 0) + 1;
        return acc;
      }, {}));
      setChats(conversations);
      
      // choose first chat for first load
      if (isInitialLoad.current && conversations.length > 0) {
        onSelectChat(conversations[0]);
        isInitialLoad.current = false;
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
      setError(t('history.loadError') || 'Failed to load conversations');
      // Fallback to empty 
      setChats([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card h-[600px] flex flex-col">
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('history.allConversations')}</h3>
        <button
          onClick={loadConversations}
          className="w-8 h-8 flex items-center justify-center text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          title={t('history.refresh') || 'Refresh'}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto custom-scrollbar -mr-2 pr-2">

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={24} />
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded text-sm">
          {error}
        </div>
      ) : chats.length === 0 ? (
        <div className="text-center text-gray-500 dark:text-gray-400 py-8">
          <p>{t('history.noChats') || 'No conversations yet'}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {chats.map((chat) => (
          <div
            key={chat.id}
            onClick={() => onSelectChat(chat)}
            className={`p-3 rounded-lg cursor-pointer transition-colors ${
              selectedChatId === chat.id
                ? 'bg-primary-50 dark:bg-primary-900/30 border-2 border-primary-200 dark:border-primary-700'
                : 'hover:bg-gray-50 dark:hover:bg-gray-700 border-2 border-transparent'
            }`}
          >
            <div className="flex items-start justify-between mb-1">
              <div className="flex items-center gap-2 flex-1 min-w-0">
                {chat.source === 'web' ? (
                  <Globe size={16} className="text-blue-500 dark:text-blue-400 flex-shrink-0" />
                ) : chat.source === 'telegram' ? (
                  <Send size={16} className="text-cyan-500 dark:text-cyan-400 flex-shrink-0" />
                ) : chat.source === 'web_widget' ? (
                  <Monitor size={16} className="text-purple-500 dark:text-purple-400 flex-shrink-0" />
                ) : (
                  <MessageSquare size={16} className="text-green-500 dark:text-green-400 flex-shrink-0" />
                )}
                <span className="font-medium text-sm text-gray-900 dark:text-gray-100 truncate">{chat.customerName}</span>
                {chat.source === 'web' && (
                  <span className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded flex-shrink-0">Web</span>
                )}
                {chat.source === 'telegram' && (
                  <span className="text-xs bg-cyan-100 dark:bg-cyan-900 text-cyan-700 dark:text-cyan-300 px-1.5 py-0.5 rounded flex-shrink-0">Telegram</span>
                )}
                {chat.source === 'web_widget' && (
                  <span className="text-xs bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300 px-1.5 py-0.5 rounded flex-shrink-0">Widget</span>
                )}
              </div>
              {chat.unread > 0 && (
                <span className="bg-primary-500 dark:bg-primary-600 text-white text-xs px-2 py-0.5 rounded-full flex-shrink-0">
                  {chat.unread}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 truncate">{chat.lastMessage}</p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{chat.timestamp}</p>
          </div>
        ))}
        </div>
      )}
      </div>
    </div>
  );
};

export default ChatList;