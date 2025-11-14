import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Camera, X, QrCode, Loader2 } from 'lucide-react';
import { clientAPI } from '../../api/client';

const PhotoUploadTest = () => {
  const { t } = useTranslation();
  const [photo, setPhoto] = useState(null);
  const [response, setResponse] = useState('');
  const [generatingQR, setGeneratingQR] = useState(false);
  const [loadingQR, setLoadingQR] = useState(true);
  const [qrCodeUrl, setQrCodeUrl] = useState(null);

  // Завантажити існуючий QR-код при монтуванні компонента
  useEffect(() => {
    const loadExistingQRCode = async () => {
      try {
        const response = await clientAPI.getQRCodes();
        const qrCodes = response.data || [];
        
        // Знайти QR-код з назвою "Photo Upload Test"
        const photoQRCode = qrCodes.find(qr => qr.name === 'Photo Upload Test');
        
        if (photoQRCode && photoQRCode.qr_code_url_display) {
          setQrCodeUrl(photoQRCode.qr_code_url_display);
        }
      } catch (error) {
        console.error('Failed to load existing QR code:', error);
      } finally {
        setLoadingQR(false);
      }
    };

    loadExistingQRCode();
  }, []);

  const handlePhotoUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setPhoto(reader.result);
        // Simulate AI analysis
        setTimeout(() => {
          setResponse(t('sandbox.imageAnalysis'));
        }, 1000);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleClear = () => {
    setPhoto(null);
    setResponse('');
    // QR-код залишається навіть після очищення фото
  };

  const handleGenerateQR = async () => {
    setGeneratingQR(true);
    try {
      // Перевіряємо чи є вже QR коди
      const existingQRCodes = await clientAPI.getQRCodes();
      const qrCodes = existingQRCodes.data || [];
      
      // Перевіряємо чи вже існує QR-код з назвою "Photo Upload Test"
      const existingPhotoQR = qrCodes.find(qr => qr.name === 'Photo Upload Test');
      
      if (existingPhotoQR) {
        // Якщо QR-код вже існує, просто показуємо його
        if (existingPhotoQR.qr_code_url_display) {
          setQrCodeUrl(existingPhotoQR.qr_code_url_display);
        }
        alert(t('sandbox.qrCodeAlreadyExists') || 'QR code already exists!');
        return;
      }
      
      if (qrCodes.length >= 10) {
        alert(t('sandbox.maxQRCodesReached') || 'Maximum 10 QR codes allowed per client');
        return;
      }
      
      // Створюємо новий QR код з назвою "Photo Upload Test"
      const qrData = {
        name: 'Photo Upload Test',
        description: t('sandbox.qrCodeDescription') || 'QR code generated from Photo Upload Test',
        location: 'Sandbox',
        is_active: true,
      };
      
      const response = await clientAPI.createQRCode(qrData);
      const qrCode = response.data;
      
      // Отримуємо URL зображення QR коду
      if (qrCode.qr_code_url_display) {
        setQrCodeUrl(qrCode.qr_code_url_display);
      } else if (qrCode.qr_code_url) {
        setQrCodeUrl(qrCode.qr_code_url);
      } else {
        alert(t('sandbox.qrCodeGenerated') || 'QR code generated successfully!');
      }
    } catch (error) {
      console.error('Failed to generate QR code:', error);
      alert(t('sandbox.qrCodeError') || 'Failed to generate QR code');
    } finally {
      setGeneratingQR(false);
    }
  };

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">{t('sandbox.photoUpload')}</h3>
      <p className="text-sm text-gray-600 mb-4">
        {t('sandbox.photoSubtitle')}
      </p>

      {!photo ? (
        <div className="space-y-4">
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
            <Camera className="mx-auto mb-4 text-gray-400" size={48} />
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
          
          {/* Generate QR Button */}
          <div className="border-t pt-4">
            <button
              onClick={handleGenerateQR}
              disabled={generatingQR || loadingQR || qrCodeUrl}
              className="w-full btn-secondary flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loadingQR ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>{t('sandbox.loadingQR') || 'Loading...'}</span>
                </>
              ) : generatingQR ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>{t('sandbox.generatingQR') || 'Generating...'}</span>
                </>
              ) : qrCodeUrl ? (
                <>
                  <QrCode size={16} />
                  <span>{t('sandbox.qrCodeExists') || 'QR Code Already Generated'}</span>
                </>
              ) : (
                <>
                  <QrCode size={16} />
                  <span>{t('sandbox.generateQR') || 'Generate QR'}</span>
                </>
              )}
            </button>
          </div>
          
          {qrCodeUrl && (
            <div className="border rounded-lg p-4 bg-gray-50">
              <p className="text-sm font-medium mb-2">{t('sandbox.qrCodeGenerated') || 'QR Code Generated:'}</p>
              <div className="flex items-center justify-center">
                <img src={qrCodeUrl} alt="QR Code" className="max-w-full h-auto rounded" />
              </div>
              <p className="text-xs text-gray-500 mt-2 text-center break-all">{qrCodeUrl}</p>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="relative">
            <img src={photo} alt="Uploaded" className="w-full rounded-lg" />
            <button
              onClick={handleClear}
              className="absolute top-2 right-2 bg-red-500 text-white p-2 rounded-full hover:bg-red-600"
            >
              <X size={18} />
            </button>
          </div>

          {response && (
            <div className="bg-gray-100 p-4 rounded-lg">
              <p className="font-medium text-sm mb-2">{t('sandbox.aiResponse')}</p>
              <p className="text-sm text-gray-700">{response}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PhotoUploadTest;
