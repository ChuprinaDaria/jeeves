import { Image, Trash2, Edit2 } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

const PhotoList = ({ photos, onDelete, onUpdate }) => {
  const { t } = useTranslation();
  const [editingId, setEditingId] = useState(null);
  const [editDescription, setEditDescription] = useState('');

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const handleEdit = (photo) => {
    setEditingId(photo.id);
    setEditDescription(photo.description || '');
  };

  const handleSave = (photoId) => {
    onUpdate(photoId, editDescription);
    setEditingId(null);
    setEditDescription('');
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditDescription('');
  };

  if (photos.length === 0) {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">{t('training.uploadedPhotos')}</h3>
        <p className="text-gray-500 dark:text-gray-400 text-center py-8">{t('training.noPhotos')}</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">{t('training.uploadedPhotos')} ({photos.length})</h3>
      <div className="space-y-4">
        {photos.map((photo) => (
          <div
            key={photo.id}
            className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0">
                {photo.file && (
                  <img
                    src={URL.createObjectURL(photo.file)}
                    alt={photo.name}
                    className="w-20 h-20 object-cover rounded-lg"
                  />
                )}
                {!photo.file && (
                  <div className="w-20 h-20 bg-gray-200 dark:bg-gray-600 rounded-lg flex items-center justify-center">
                    <Image className="text-gray-400 dark:text-gray-500" size={24} />
                  </div>
                )}
              </div>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-2">
                  <p className="font-medium text-sm truncate text-gray-900 dark:text-gray-100">{photo.name}</p>
                  <div className="flex items-center gap-2 ml-2">
                    <button
                      onClick={() => handleEdit(photo)}
                      className="text-primary-500 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 p-1"
                      title={t('training.editDescription')}
                    >
                      <Edit2 size={16} />
                    </button>
                    <button
                      onClick={() => onDelete(photo.id)}
                      className="text-red-500 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 p-1"
                      title={t('common.delete')}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">{formatFileSize(photo.size)}</p>
                
                {editingId === photo.id ? (
                  <div className="space-y-2">
                    <textarea
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      placeholder={t('training.photoDescriptionPlaceholder')}
                      className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 dark:focus:ring-primary-400 focus:border-transparent outline-none resize-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                      rows={3}
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleSave(photo.id)}
                        className="btn-primary text-sm px-3 py-1"
                      >
                        {t('common.save')}
                      </button>
                      <button
                        onClick={handleCancel}
                        className="btn-secondary text-sm px-3 py-1"
                      >
                        {t('common.cancel')}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    {photo.description ? (
                      <p className="text-sm text-gray-700 dark:text-gray-300">{photo.description}</p>
                    ) : (
                      <p className="text-sm text-gray-400 dark:text-gray-500 italic">{t('training.noDescription')}</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PhotoList;

