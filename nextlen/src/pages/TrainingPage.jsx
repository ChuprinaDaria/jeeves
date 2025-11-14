import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import FileUpload from '../components/training/FileUpload';
import FileList from '../components/training/FileList';
import PromptEditor from '../components/training/PromptEditor';
import SyncActions from '../components/training/SyncActions';
import LLMProviderCard from '../components/training/LLMProviderCard';
import ModelStatusCard from '../components/training/ModelStatusCard';
import LLMProviderCard from '../components/training/LLMProviderCard';
import KnowledgeBlocks from '../components/training/KnowledgeBlocks';
import { clientAPI } from '../api/client';

const TrainingPage = () => {
  const { t } = useTranslation();
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  // Завантажити список документів при монтуванні компонента
  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      const response = await clientAPI.getDocuments();
      // Перетворюємо формат документів з бекенду в формат для FileList
      const docs = (response.data || []).map(doc => ({
        id: doc.id,
        name: doc.title || doc.file_name || 'Untitled',
        size: doc.file_size || 0,
        type: doc.file_type || 'unknown',
        uploadedAt: doc.uploaded_at || new Date().toISOString(),
        url: doc.file,
        is_processed: doc.is_processed,
      }));
      setFiles(docs);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (newFiles) => {
    // newFiles містить File об'єкти з браузера
    setUploading(true);
    
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
        alert(`Failed to upload ${fileName}: ${errorMsg}`);
      }
    }
    
    setUploading(false);
    // Перезавантажуємо список документів після завантаження
    loadDocuments();
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

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('training.title')}</h1>
          <p className="text-gray-600">{t('training.subtitle')}</p>
        </div>
        <SyncActions onSync={loadDocuments} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <FileUpload onUpload={handleFileUpload} uploading={uploading} />
          <FileList files={files} onDelete={handleDeleteFile} loading={loading} />
          <PromptEditor />
        </div>
        <div className="space-y-6">
          <LLMProviderCard />
          <ModelStatusCard />
          <LLMProviderCard />
          <KnowledgeBlocks />
        </div>
      </div>
    </div>
  );
};

export default TrainingPage;
