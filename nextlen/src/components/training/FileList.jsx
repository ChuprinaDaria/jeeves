import { FileText, Trash2, Loader2, CheckCircle, Clock, Type } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const FileList = ({ files, onDelete, loading }) => {
  const { t } = useTranslation();
  
  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (loading) {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">{t('training.uploadedFiles')}</h3>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="animate-spin text-primary-500 dark:text-primary-400" size={32} />
        </div>
      </div>
    );
  }

  if (files.length === 0) {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">{t('training.uploadedFiles')}</h3>
        <p className="text-gray-500 dark:text-gray-400 text-center py-8">{t('training.noFiles')}</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">{t('training.uploadedFiles')} ({files.length})</h3>
      <div className="space-y-2">
        {files.map((file) => (
          <div
            key={file.id}
            className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <div className="flex items-center gap-3 flex-1">
              {file.type === 'text' || (file.name && file.name.endsWith('.txt') && !file.url) ? (
                <Type className="text-blue-500 dark:text-blue-400 flex-shrink-0" size={20} />
              ) : (
                <FileText className="text-primary-500 dark:text-primary-400 flex-shrink-0" size={20} />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="font-medium text-sm truncate text-gray-900 dark:text-gray-100">{file.name}</p>
                  {(file.type === 'text' || (file.name && file.name.endsWith('.txt') && !file.url)) && (
                    <span className="text-xs px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded">
                      {t('training.text') || 'Text'}
                    </span>
                  )}
                  {file.is_processed ? (
                    <CheckCircle
                      size={16}
                      className="text-green-500 dark:text-green-400 flex-shrink-0"
                      title={t('training.fileProcessed') || 'Processed'}
                    />
                  ) : (
                    <Loader2
                      size={16}
                      className="text-yellow-500 dark:text-yellow-400 flex-shrink-0 animate-spin"
                      title={t('training.fileProcessing') || 'Processing'}
                    />
                  )}
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                  <span>{formatFileSize(file.size)}</span>
                  {file.uploadedAt && (
                    <>
                      <span>•</span>
                      <span>{formatDate(file.uploadedAt)}</span>
                    </>
                  )}
                </div>
              </div>
            </div>
            <button
              onClick={() => onDelete(file.id)}
              className="text-red-500 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 p-2 flex-shrink-0"
              title="Delete file"
            >
              <Trash2 size={18} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

export default FileList;
