import { FileText, Trash2, Loader2, CheckCircle, Clock } from 'lucide-react';
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
        <h3 className="text-lg font-semibold mb-4">{t('training.uploadedFiles')}</h3>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="animate-spin text-primary-500" size={32} />
        </div>
      </div>
    );
  }

  if (files.length === 0) {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">{t('training.uploadedFiles')}</h3>
        <p className="text-gray-500 text-center py-8">{t('training.noFiles')}</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">{t('training.uploadedFiles')} ({files.length})</h3>
      <div className="space-y-2">
        {files.map((file) => (
          <div
            key={file.id}
            className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <div className="flex items-center gap-3 flex-1">
              <FileText className="text-primary-500 flex-shrink-0" size={20} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="font-medium text-sm truncate">{file.name}</p>
                  {file.is_processed ? (
                    <CheckCircle size={16} className="text-green-500 flex-shrink-0" title="Processed" />
                  ) : (
                    <Clock size={16} className="text-yellow-500 flex-shrink-0" title="Pending processing" />
                  )}
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-500">
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
              className="text-red-500 hover:text-red-700 p-2 flex-shrink-0"
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
