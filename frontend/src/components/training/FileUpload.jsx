import { Upload, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

const FileUpload = ({ onUpload, uploading }) => {
  const { t } = useTranslation();
  const [dragging, setDragging] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
  };

  const handleFiles = (fileList) => {
    // Передаємо File об'єкти з метаданими для відображення прогресу
    const newFiles = fileList.map((file) => ({
      id: Date.now() + Math.random(),
      name: file.name,
      size: file.size,
      type: file.type,
      uploadedAt: new Date().toISOString(),
      file: file, // Зберігаємо сам File об'єкт для завантаження
    }));
    onUpload(newFiles);
  };

  const handleFileInput = (e) => {
    const files = Array.from(e.target.files);
    handleFiles(files);
  };

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">{t('training.uploadFiles')}</h3>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          dragging
            ? 'border-primary-500 dark:border-primary-400 bg-primary-50 dark:bg-primary-900/30'
            : 'border-gray-300 dark:border-gray-600 hover:border-primary-400 dark:hover:border-primary-500'
        } ${uploading ? 'opacity-50 pointer-events-none' : ''}`}
      >
        {uploading ? (
          <Loader2 className="mx-auto mb-4 text-primary-500 dark:text-primary-400 animate-spin" size={48} />
        ) : (
          <Upload className="mx-auto mb-4 text-gray-400 dark:text-gray-500" size={48} />
        )}
        <p className="text-gray-700 dark:text-gray-300 font-medium mb-2">
          {uploading ? t('training.uploading') || 'Uploading...' : t('training.dragDrop')}
        </p>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
          {t('training.supportedFormats')}
        </p>
        <input
          type="file"
          multiple
          onChange={handleFileInput}
          className="hidden"
          id="file-input"
          accept=".pdf,.doc,.docx,.txt,.xls,.xlsx,.json"
          disabled={uploading}
        />
        <label 
          htmlFor="file-input" 
          className={`btn-primary cursor-pointer ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {t('training.chooseFiles')}
        </label>
      </div>
    </div>
  );
};

export default FileUpload;
