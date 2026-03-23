import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageSquare, Camera, FlaskConical, ChevronDown, ChevronUp } from 'lucide-react';
import ChatWindow from '../sandbox/ChatWindow';
import PhotoUploadTest from '../sandbox/PhotoUploadTest';

const SandboxSection = () => {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(true);
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' or 'photo'

  return (
    <div className="space-y-4">
      {/* Header Card */}
      <div className="card">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
              <FlaskConical className="text-white" size={20} />
            </div>
            <div className="text-left">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {t('sandbox.title')}
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {t('training.sandboxDescription') || 'Test your AI assistant before going live'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden sm:inline-block text-xs px-2 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-full font-medium">
              {t('training.sandboxBadge') || 'Test Mode'}
            </span>
            {isExpanded ? (
              <ChevronUp className="text-gray-400 dark:text-gray-500" size={20} />
            ) : (
              <ChevronDown className="text-gray-400 dark:text-gray-500" size={20} />
            )}
          </div>
        </button>
      </div>

      {/* Expandable content */}
      {isExpanded && (
        <div className="space-y-4">
          {/* Tabs */}
          <div className="flex gap-2 p-1 bg-gray-100 dark:bg-gray-800 rounded-lg">
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-md text-sm font-medium transition-all ${
                activeTab === 'chat'
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              <MessageSquare size={18} />
              <span className="hidden sm:inline">{t('sandbox.chatTest')}</span>
              <span className="sm:hidden">Chat</span>
            </button>
            <button
              onClick={() => setActiveTab('photo')}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-md text-sm font-medium transition-all ${
                activeTab === 'photo'
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              <Camera size={18} />
              <span className="hidden sm:inline">{t('sandbox.photoUpload')}</span>
              <span className="sm:hidden">Photo</span>
            </button>
          </div>

          {/* Tab Content */}
          <div>
            {activeTab === 'chat' ? (
              <ChatWindow channel="web" />
            ) : (
              <PhotoUploadTest />
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default SandboxSection;
