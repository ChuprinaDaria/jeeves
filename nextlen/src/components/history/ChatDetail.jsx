import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { User, Bot, Plus, Loader2, Mail, ThumbsUp, ThumbsDown, FileText, X } from 'lucide-react';
import { ragAPI } from '../../api/agent';
import { clientAPI } from '../../api/client';

const ChatDetail = ({ chat }) => {
  const { t } = useTranslation();
  const [uploading, setUploading] = useState({});
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [chatData, setChatData] = useState(null);
  const [showNotesModal, setShowNotesModal] = useState(false);
  const [notes, setNotes] = useState('');
  const [rating, setRating] = useState(null);
  
  useEffect(() => {
    if (chat && chat.conversation_id) {
      loadConversationDetail();
    } else {
      // Fallback на mock дані якщо немає conversation_id
      setMessages([
        {
          id: 1,
          text: 'Hello! I would like to book an appointment',
          sender: 'customer',
          timestamp: '10:30 AM',
          photo: null,
        },
        {
          id: 2,
          text: 'Hello! I would be happy to help you book an appointment. What service are you interested in?',
          sender: 'ai',
          timestamp: '10:30 AM',
          photo: null,
        },
      ]);
    }
  }, [chat]);
  
  const loadConversationDetail = async () => {
    if (!chat?.conversation_id) return;
    
    setLoading(true);
    try {
      const response = await clientAPI.getConversationDetail(chat.conversation_id);
      const data = response.data;
      setChatData(data);
      
      // Завантажуємо notes та rating
      setNotes(data.notes || '');
      setRating(data.user_rating || null);
      
      // Форматуємо повідомлення
      const formattedMessages = (data.messages || []).map((msg, idx) => ({
        id: idx + 1,
        text: msg.text,
        sender: msg.sender,
        timestamp: msg.timestamp,
        photo: msg.photo || null,
      }));
      
      setMessages(formattedMessages);
    } catch (err) {
      console.error('Failed to load conversation detail:', err);
      // Fallback на mock дані
      setMessages([
        {
          id: 1,
          text: chat.lastMessage || 'No messages',
          sender: 'customer',
          timestamp: chat.timestamp || '',
          photo: null,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };
  
  const handleAddChatToKnowledge = async () => {
    if (!chat || !messages.length) return;

    setUploading(prev => ({ ...prev, chat: true }));

    try {
      // Створюємо окремі документи для кожної пари Q&A (окремі ембедінги)
      const qaPairs = [];
      for (let i = 0; i < messages.length - 1; i++) {
        const userMsg = messages[i];
        const aiMsg = messages[i + 1];
        
        // Шукаємо пари Customer -> AI
        if (userMsg.sender === 'customer' && aiMsg.sender === 'ai') {
          qaPairs.push({
            question: userMsg.text,
            answer: aiMsg.text,
          });
        }
      }

      if (qaPairs.length === 0) {
        alert(t('history.noQAPairs') || 'No Q&A pairs found in this chat');
        return;
      }

      // Зберігаємо кожну пару Q&A як окремий документ
      let savedCount = 0;
      for (const qa of qaPairs) {
        try {
          await ragAPI.saveSandboxQA(qa.question, qa.answer);
          savedCount++;
        } catch (err) {
          console.error('Error saving Q&A pair:', err);
        }
      }

      // Запускаємо індексування нових документів
      await clientAPI.syncData();

      alert(t('history.addedToKnowledge') || `${savedCount} Q&A pairs added to knowledge base and indexing started!`);
    } catch (error) {
      console.error('Error adding chat to knowledge:', error);
      alert(t('history.addToKnowledgeError') || 'Failed to add chat to knowledge base');
    } finally {
      setUploading(prev => ({ ...prev, chat: false }));
    }
  };

  const handleSendEmail = async () => {
    if (!chat?.conversation_id) return;

    setUploading(prev => ({ ...prev, email: true }));

    try {
      const response = await clientAPI.sendConversationEmail(chat.conversation_id);
      if (response.data?.email_sent) {
        alert(t('history.emailSent') || 'Email sent successfully!');
      } else {
        alert(t('history.emailNotSent') || 'Email not sent. Check email settings.');
      }
    } catch (error) {
      console.error('Error sending email:', error);
      alert(t('history.emailError') || 'Failed to send email');
    } finally {
      setUploading(prev => ({ ...prev, email: false }));
    }
  };

  const handleRate = async (newRating) => {
    if (!chat?.conversation_id) return;

    setUploading(prev => ({ ...prev, rating: true }));

    try {
      await clientAPI.rateConversation(chat.conversation_id, newRating);
      setRating(newRating);
      alert(t('history.ratingSaved') || 'Rating saved!');
    } catch (error) {
      console.error('Error saving rating:', error);
      alert(t('history.ratingError') || 'Failed to save rating');
    } finally {
      setUploading(prev => ({ ...prev, rating: false }));
    }
  };

  const handleSaveNotes = async () => {
    if (!chat?.conversation_id) return;

    setUploading(prev => ({ ...prev, notes: true }));

    try {
      await clientAPI.updateConversationNotes(chat.conversation_id, notes);
      setShowNotesModal(false);
      alert(t('history.notesSaved') || 'Notes saved!');
    } catch (error) {
      console.error('Error saving notes:', error);
      alert(t('history.notesError') || 'Failed to save notes');
    } finally {
      setUploading(prev => ({ ...prev, notes: false }));
    }
  };

  return (
    <div className="card h-[600px] flex flex-col">
      <div className="pb-4 border-b border-gray-200 dark:border-gray-700 mb-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{chat.customerName}</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">{t('history.lastActive')} {chat.timestamp}</p>
          </div>
          <button
            onClick={handleAddChatToKnowledge}
            disabled={uploading.chat}
            className="ml-4 px-3 py-1.5 bg-primary-600 dark:bg-primary-500 text-white rounded-lg shadow hover:bg-primary-700 dark:hover:bg-primary-600 transition flex items-center gap-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            title={t('history.addToKnowledge') || 'Add to Knowledge'}
          >
            {uploading.chat ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                <span>{t('history.adding') || 'Adding...'}</span>
              </>
            ) : (
              <>
                <Plus size={14} />
                <span>{t('history.addToKnowledge') || 'Add to Knowledge'}</span>
              </>
            )}
          </button>
        </div>
        
        {/* Action buttons */}
        <div className="flex flex-wrap gap-2 mt-3">
          <button
            onClick={handleSendEmail}
            disabled={uploading.email}
            className="px-3 py-1.5 bg-blue-600 dark:bg-blue-500 text-white rounded-lg shadow hover:bg-blue-700 dark:hover:bg-blue-600 transition flex items-center gap-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            title={t('history.sendEmail') || 'Send summary to email'}
          >
            {uploading.email ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Mail size={14} />
            )}
            <span>{t('history.sendEmail') || 'Send Email'}</span>
          </button>
          
          <div className="flex gap-1">
            <button
              onClick={() => handleRate('positive')}
              disabled={uploading.rating}
              className={`px-3 py-1.5 rounded-lg shadow transition flex items-center gap-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed ${
                rating === 'positive'
                  ? 'bg-green-600 dark:bg-green-500 text-white'
                  : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
              }`}
              title={t('history.ratePositive') || 'Rate positive'}
            >
              {uploading.rating ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <ThumbsUp size={14} />
              )}
            </button>
            <button
              onClick={() => handleRate('negative')}
              disabled={uploading.rating}
              className={`px-3 py-1.5 rounded-lg shadow transition flex items-center gap-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed ${
                rating === 'negative'
                  ? 'bg-red-600 dark:bg-red-500 text-white'
                  : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
              }`}
              title={t('history.rateNegative') || 'Rate negative'}
            >
              {uploading.rating ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <ThumbsDown size={14} />
              )}
            </button>
          </div>
          
          <button
            onClick={() => setShowNotesModal(true)}
            className="px-3 py-1.5 bg-purple-600 dark:bg-purple-500 text-white rounded-lg shadow hover:bg-purple-700 dark:hover:bg-purple-600 transition flex items-center gap-2 text-sm"
            title={t('history.addNotes') || 'Add notes'}
          >
            <FileText size={14} />
            <span>{t('history.notes') || 'Notes'}</span>
          </button>
        </div>
      </div>

      {/* Notes Modal */}
      {showNotesModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-2xl w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {t('history.notes') || 'Notes'}
              </h3>
              <button
                onClick={() => setShowNotesModal(false)}
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                <X size={20} />
              </button>
            </div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t('history.notesPlaceholder') || 'Add your notes about this conversation...'}
              className="w-full h-40 p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 resize-none"
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setShowNotesModal(false)}
                className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition"
              >
                {t('common.cancel') || 'Cancel'}
              </button>
              <button
                onClick={handleSaveNotes}
                disabled={uploading.notes}
                className="px-4 py-2 bg-primary-600 dark:bg-primary-500 text-white rounded-lg hover:bg-primary-700 dark:hover:bg-primary-600 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {uploading.notes ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    <span>{t('common.saving') || 'Saving...'}</span>
                  </>
                ) : (
                  <span>{t('common.save') || 'Save'}</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto space-y-4">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={24} />
            <span className="ml-2 text-gray-600 dark:text-gray-400">{t('history.loading') || 'Loading...'}</span>
          </div>
        ) : messages.length === 0 ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-8">
            <p>{t('history.noMessages') || 'No messages in this conversation'}</p>
          </div>
        ) : (
          messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.sender === 'customer' ? '' : 'flex-row-reverse'}`}
          >
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                msg.sender === 'customer'
                  ? 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
                  : 'bg-primary-100 dark:bg-primary-900/50 text-primary-600 dark:text-primary-400'
              }`}
            >
              {msg.sender === 'customer' ? <User size={16} /> : <Bot size={16} />}
            </div>

            <div className="flex-1">
              <div
                className={`p-3 rounded-lg ${
                  msg.sender === 'customer' 
                    ? 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100' 
                    : 'bg-primary-50 dark:bg-primary-900/30 text-gray-900 dark:text-gray-100'
                }`}
              >
                <p className="text-sm whitespace-pre-line">{msg.text}</p>
                
                {/* Photo display */}
                {msg.photo && (
                  <div className="mt-3">
                    <img 
                      src={msg.photo} 
                      alt="Chat photo" 
                      className="max-w-full h-auto rounded-lg border border-gray-200 dark:border-gray-700"
                    />
                  </div>
                )}
              </div>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{msg.timestamp}</p>
            </div>
          </div>
        ))
        )}
      </div>
    </div>
  );
};

export default ChatDetail;
