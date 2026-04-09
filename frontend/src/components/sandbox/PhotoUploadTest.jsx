import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Camera, X, BookPlus, Sparkles } from 'lucide-react';
import { ragAPI } from '../../api/agent';

const PhotoUploadTest = () => {
  const { t } = useTranslation();
  const [photo, setPhoto] = useState(null);
  const [response, setResponse] = useState('');
  const [cleanDescription, setCleanDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingClean, setLoadingClean] = useState(false);
  const [error, setError] = useState('');
  const [uploadedFile, setUploadedFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveWithPrompt, setSaveWithPrompt] = useState(false);

  const handlePhotoUpload = async (e) => {
    const file = e.target.files[0];
    if (file) {
      setLoading(true);
      setError('');
      setResponse('');
      setCleanDescription('');
      setUploadedFile(file);
      setSaved(false);
      setSaveWithPrompt(false);
      
      const reader = new FileReader();
      reader.onloadend = async () => {
        setPhoto(reader.result);
        
        try {
          // Відправляємо зображення на аналіз через RAG API (з контекстом)
          const result = await ragAPI.chat('', file);
          setResponse(result.data?.response || result.data?.image_analysis || t('sandbox.imageAnalysis'));
        } catch (err) {
          console.error('Image analysis error:', err);
          setError(t('sandbox.imageAnalysisError') || 'Failed to analyze image');
          setResponse('');
        } finally {
          setLoading(false);
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const handleGenerateCleanDescription = async () => {
    if (!uploadedFile) return;
    
    setLoadingClean(true);
    setError('');
    
    try {
      // Генеруємо чистий опис без контексту гри
      const result = await ragAPI.chat('Describe what you see in this image in detail. Focus only on the visual content, objects, people, text, and any other relevant information. Do not add any game-related context or references.', uploadedFile);
      setCleanDescription(result.data?.response || result.data?.image_analysis || '');
    } catch (err) {
      console.error('Clean description error:', err);
      setError(t('sandbox.cleanDescriptionError') || 'Failed to generate clean description');
    } finally {
      setLoadingClean(false);
    }
  };

  const handleClear = () => {
    setPhoto(null);
    setResponse('');
    setCleanDescription('');
    setError('');
    setUploadedFile(null);
    setSaved(false);
    setSaveWithPrompt(false);
  };

  const handleAddToKnowledge = async (useClean = false) => {
    if (!uploadedFile) return;
    
    const descriptionToSave = useClean ? cleanDescription : response;
    if (!descriptionToSave) {
      setError(t('sandbox.noDescriptionError') || 'No description available. Please analyze the image first.');
      return;
    }
    
    setSaving(true);
    setError('');
    
    try {
      await ragAPI.saveSandboxPhoto(uploadedFile, descriptionToSave, useClean);
      setSaved(true);
      setSaveWithPrompt(!useClean);
    } catch (err) {
      console.error('Failed to save photo:', err);
      setError(t('history.addToKnowledgeError') || 'Failed to add photo to knowledge base');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">{t('sandbox.photoUpload')}</h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
        {t('sandbox.photoSubtitle')}
      </p>

      <div className="space-y-4">
        {!photo ? (
          <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 text-center">
            <Camera className="mx-auto mb-4 text-gray-400 dark:text-gray-500" size={48} />
            <input
              type="file"
              accept="image/*"
              onChange={handlePhotoUpload}
              className="hidden"
              id="photo-input"
            />
            <label htmlFor="photo-input" className="btn-primary cursor-pointer">
              {t('sandbox.uploadPhoto')}
            </label>
          </div>
        ) : (
        <div className="space-y-4">
          <div className="relative group">
            <img src={photo} alt="Uploaded" className="w-full rounded-lg" />
            <button
              onClick={handleClear}
              className="absolute top-3 right-3 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm text-gray-700 dark:text-gray-300 p-2 rounded-full hover:bg-red-500 hover:text-white dark:hover:bg-red-600 dark:hover:text-white shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-110 opacity-0 group-hover:opacity-100"
              title={t('common.delete')}
            >
              <X size={20} />
            </button>
          </div>

          {loading && (
            <div className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce delay-100"></div>
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce delay-200"></div>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">{t('sandbox.analyzingImage') || 'Analyzing image...'}</p>
            </div>
          )}
          
          {error && (
            <div className="bg-red-100 dark:bg-red-900 p-4 rounded-lg">
              <p className="font-medium text-sm mb-2 text-red-900 dark:text-red-100">{t('sandbox.error') || 'Error'}</p>
              <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
            </div>
          )}
          
          {response && !loading && (
            <>
              <div className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <p className="font-medium text-sm text-gray-900 dark:text-gray-100">{t('sandbox.aiResponse')}</p>
                  {!saved && (
                    <button
                      onClick={handleClear}
                      className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                      title={t('sandbox.uploadNewImage') || 'Upload new image'}
                    >
                      {t('sandbox.uploadNew') || 'New Image'}
                    </button>
                  )}
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300">{response}</p>
              </div>

              {/* Кнопка для генерації чистого опису */}
              {!cleanDescription && !loadingClean && (
                <button
                  onClick={handleGenerateCleanDescription}
                  disabled={loadingClean}
                  className="w-full btn-secondary flex items-center justify-center gap-2"
                >
                  <Sparkles size={18} />
                  {t('sandbox.generateCleanDescription') || 'Generate Clean Description (without game context)'}
                </button>
              )}

              {loadingClean && (
                <div className="bg-blue-100 dark:bg-blue-900 p-4 rounded-lg">
                  <p className="text-sm text-blue-700 dark:text-blue-300">{t('sandbox.generatingClean') || 'Generating clean description...'}</p>
                </div>
              )}

              {cleanDescription && (
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 p-4 rounded-lg">
                  <p className="font-medium text-sm mb-2 text-green-900 dark:text-green-100">{t('sandbox.cleanDescription') || 'Clean Description (without game context)'}</p>
                  <p className="text-sm text-green-700 dark:text-green-300">{cleanDescription}</p>
                </div>
              )}
              
              {!saved ? (
                <div className="flex gap-2">
                  {cleanDescription && (
                    <button
                      onClick={() => handleAddToKnowledge(true)}
                      disabled={saving}
                      className="flex-1 btn-primary flex items-center justify-center gap-2"
                    >
                      <BookPlus size={18} />
                      {saving ? (t('history.adding') || 'Adding...') : (t('sandbox.addClean') || 'Add Clean to Knowledge')}
                    </button>
                  )}
                  <button
                    onClick={() => handleAddToKnowledge(false)}
                    disabled={saving}
                    className={`${cleanDescription ? 'flex-1' : 'w-full'} btn-secondary flex items-center justify-center gap-2`}
                  >
                    <BookPlus size={18} />
                    {saving ? (t('history.adding') || 'Adding...') : (t('sandbox.addWithPrompt') || 'Add with Prompt')}
                  </button>
                </div>
              ) : (
                <div className="bg-green-100 dark:bg-green-900 p-4 rounded-lg text-center">
                  <p className="text-sm font-medium text-green-900 dark:text-green-100">
                    ✓ {t('history.addedToKnowledge') || 'Photo added to knowledge base and indexing started!'}
                    {saveWithPrompt && <span className="block mt-1 text-xs">({t('sandbox.savedWithPrompt') || 'Saved with game context'})</span>}
                  </p>
                </div>
              )}
            </>
          )}
          
          {/* Кнопка для завантаження наступного фото (завжди видима коли є фото) */}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
            <input
              type="file"
              accept="image/*"
              onChange={handlePhotoUpload}
              className="hidden"
              id="photo-input-new"
            />
            <label htmlFor="photo-input-new" className="w-full btn-secondary flex items-center justify-center gap-2 cursor-pointer">
              <Camera size={18} />
              {t('sandbox.uploadNextImage') || 'Upload Next Image'}
            </label>
          </div>
        </div>
        )}
      </div>
    </div>
  );
};

export default PhotoUploadTest;
