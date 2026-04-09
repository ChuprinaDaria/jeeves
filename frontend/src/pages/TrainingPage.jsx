import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import FileUpload from '../components/training/FileUpload';
import FileList from '../components/training/FileList';
import PromptEditor from '../components/training/PromptEditor';
import SyncActions from '../components/training/SyncActions';
import LLMProviderCard from '../components/training/LLMProviderCard';
import KnowledgeBlocks from '../components/training/KnowledgeBlocks';
import WebKnowledgeAdd from '../components/training/WebKnowledgeAdd';
import TextAddModal from '../components/training/TextAddModal';
import SandboxSection from '../components/training/SandboxSection';
import { clientAPI } from '../api/client';
import { FileText, Plus, AlertCircle } from 'lucide-react';

const TrainingPage = () => {
  const { t } = useTranslation();
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showTextModal, setShowTextModal] = useState(false);
  const [savingText, setSavingText] = useState(false);
  const [uploadErrors, setUploadErrors] = useState([]);

  // Завантажити список документів при монтуванні компонента
  useEffect(() => {
    loadDocuments(true);
  }, []);

  const loadDocuments = async (showLoader = true) => {
    try {
      if (showLoader) {
        setLoading(true);
      }
      const response = await clientAPI.getDocuments();
      // Перетворюємо формат документів з бекенду в формат для FileList
      const docs = (response.data || []).map(doc => {
        const fileType = doc.file_type || 'unknown';
        const isTextDocument = fileType === 'txt' && (!doc.file || doc.file === '');
        return {
          id: doc.id,
          name: doc.title || doc.file_name || 'Untitled',
          size: doc.file_size || 0,
          type: isTextDocument ? 'text' : fileType,
          uploadedAt: doc.uploaded_at || new Date().toISOString(),
          url: doc.file,
          is_processed: doc.is_processed,
        };
      });
      setFiles(docs);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      if (showLoader) {
        setLoading(false);
      }
    }
  };

  // Авто-оновлення статусу обробки файлів (is_processed) без F5
  useEffect(() => {
    // Якщо немає жодного файлу в статусі processing – інтервал не запускаємо
    if (!files.some((f) => !f.is_processed)) {
      return;
    }

    const interval = setInterval(() => {
      // Перезавантажуємо список без глобового спінера
      loadDocuments(false);
    }, 5000); // кожні 5 секунд

    return () => clearInterval(interval);
  }, [files]);

  const handleFileUpload = async (newFiles) => {
    // newFiles містить File об'єкти з браузера
    setUploading(true);
    setUploadErrors([]);
    
    for (const fileObj of newFiles) {
      // Визначаємо fileName ДО try/catch щоб мати доступ в обох блоках
      const actualFile = fileObj.file || fileObj;
      const fileName = actualFile.name || fileObj.name || 'Untitled';
      
      try {
        // Відправляємо файл на бекенд
        const response = await clientAPI.uploadDocument(
          actualFile,
          fileName,
          null // clientId не потрібен, backend визначить з JWT
        );
        
        console.log('File uploaded:', response.data);
      } catch (error) {
        const errorMsg = error.response?.data?.error 
          || error.response?.data?.message 
          || error.response?.data?.detail
          || error.message 
          || 'Unknown error';
        console.error('Failed to upload file:', fileName, error);
        setUploadErrors(prev => [
          ...prev,
          {
            id: `${Date.now()}-${Math.random()}`,
            name: fileName,
            message: errorMsg,
          }
        ]);
      }
    }
    
    setUploading(false);
    // Перезавантажуємо список документів після завантаження
    loadDocuments(true);
  };

  const handleDeleteFile = async (fileId) => {
    try {
      await clientAPI.deleteDocument(fileId);
      // Оновлюємо локальний стан
      setFiles(files.filter(f => f.id !== fileId));
    } catch (error) {
      console.error('Failed to delete file:', error);
      alert(`Failed to delete file: ${error.response?.data?.error || error.message}`);
    }
  };

  const handleSaveText = async (title, text) => {
    setSavingText(true);
    try {
      await clientAPI.uploadTextDocument(title, text);
      setShowTextModal(false);
      // Перезавантажуємо список документів після збереження
      loadDocuments(true);
    } catch (error) {
      const errorMsg = error.response?.data?.error 
        || error.response?.data?.message 
        || error.response?.data?.detail
        || error.message 
        || 'Unknown error';
      console.error('Failed to save text:', error);
      alert(`Failed to save text: ${errorMsg}`);
    } finally {
      setSavingText(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('training.title')}</h1>
          <p className="text-gray-600 dark:text-gray-400">{t('training.subtitle')}</p>
        </div>
        <SyncActions onSync={() => loadDocuments(true)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <FileUpload onUpload={handleFileUpload} uploading={uploading} />
          
          {/* Помилки завантаження файлів */}
          {uploadErrors.length > 0 && (
            <div className="space-y-2">
              {uploadErrors.map((err) => (
                <div
                  key={err.id}
                  className="flex items-start gap-3 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700"
                >
                  <AlertCircle className="text-red-600 dark:text-red-400 mt-0.5" size={18} />
                  <div className="text-sm text-red-700 dark:text-red-200">
                    <div className="font-semibold">
                      {t('training.uploadErrorTitle', { fileName: err.name })}
                    </div>
                    <div className="text-xs mt-1">
                      {t('training.uploadErrorSuggestion')}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          
          {/* Add Text Information Button */}
          <div className="card">
            <button
              onClick={() => setShowTextModal(true)}
              disabled={uploading}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg hover:border-primary-400 dark:hover:border-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <FileText className="text-primary-500 dark:text-primary-400" size={20} />
              <span className="text-gray-700 dark:text-gray-300 font-medium">
                {t('training.addTextInformation') || 'Add Text Information'}
              </span>
              <Plus className="text-primary-500 dark:text-primary-400" size={18} />
            </button>
          </div>

          <FileList files={files} onDelete={handleDeleteFile} loading={loading} />
          <PromptEditor />
          <SandboxSection />
        </div>
        <div className="space-y-6">
          <LLMProviderCard />
          <KnowledgeBlocks />
          <WebKnowledgeAdd />
        </div>
      </div>

      {/* Text Add Modal */}
      <TextAddModal
        isOpen={showTextModal}
        onClose={() => setShowTextModal(false)}
        onSave={handleSaveText}
        saving={savingText}
      />
    </div>
  );
};

export default TrainingPage;
