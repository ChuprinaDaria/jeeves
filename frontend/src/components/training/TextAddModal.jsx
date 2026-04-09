import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { X, FileText, Loader2 } from 'lucide-react';

const TextAddModal = ({ isOpen, onClose, onSave, saving }) => {
  const { t } = useTranslation();
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!text.trim()) {
      alert(t('training.textRequired') || 'Please enter some text');
      return;
    }
    
    const textTitle = title.trim() || t('training.textDocument') || 'Text Document';
    onSave(textTitle, text.trim());
    
    // Очищаємо форму
    setTitle('');
    setText('');
  };

  const handleClose = () => {
    if (!saving) {
      setTitle('');
      setText('');
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 dark:bg-opacity-70">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col m-4">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <FileText className="text-primary-500 dark:text-primary-400" size={24} />
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
              {t('training.addTextInformation') || 'Add Text Information'}
            </h2>
          </div>
          <button
            onClick={handleClose}
            disabled={saving}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-50"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {/* Title Input */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t('training.documentTitle') || 'Document Title (Optional)'}
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={t('training.titlePlaceholder') || 'Enter a title for this text...'}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 dark:focus:ring-primary-400 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                disabled={saving}
              />
            </div>

            {/* Text Input */}
            <div className="flex-1 flex flex-col min-h-[300px]">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t('training.textContent') || 'Text Content'} <span className="text-red-500">*</span>
              </label>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={t('training.textPlaceholder') || 'Paste or type your text here...'}
                className="flex-1 w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 dark:focus:ring-primary-400 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 resize-none"
                disabled={saving}
                required
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                {t('training.textHint') || 'This text will be processed and added to your knowledge base'}
              </p>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 dark:border-gray-700">
            <button
              type="button"
              onClick={handleClose}
              disabled={saving}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg disabled:opacity-50"
            >
              {t('common.cancel') || 'Cancel'}
            </button>
            <button
              type="submit"
              disabled={saving || !text.trim()}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {saving ? (
                <>
                  <Loader2 className="animate-spin" size={18} />
                  {t('training.saving') || 'Saving...'}
                </>
              ) : (
                t('training.saveText') || 'Save Text'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default TextAddModal;

