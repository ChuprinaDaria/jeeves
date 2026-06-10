import { useState, useEffect, useMemo } from 'react';
import { FileText, Trash2, Loader2, CheckCircle, Type, Search, ArrowUpDown, X, ChevronRight, Filter, FolderOpen } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const FileList = ({ files, onDelete, loading }) => {
  const { t } = useTranslation();
  const [showModal, setShowModal] = useState(false);
  
  // Стан для модалки
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [sortBy, setSortBy] = useState(() => {
    const saved = localStorage.getItem('fileList_sortBy');
    return saved || 'date_desc';
  });
  const [filterType, setFilterType] = useState('all');

  // Дебаунс для пошуку (400ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 400);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Зберігаємо сортування в localStorage
  useEffect(() => {
    localStorage.setItem('fileList_sortBy', sortBy);
  }, [sortBy]);

  // Закриття модалки по Escape
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') setShowModal(false);
    };
    if (showModal) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [showModal]);

  // Функція для обрізання назви файлу
  const truncateFileName = (fileName, maxLength = 40) => {
    if (!fileName || fileName.length <= maxLength) return fileName;
    
    const lastDot = fileName.lastIndexOf('.');
    if (lastDot === -1) return fileName.slice(0, maxLength - 3) + '...';
    
    const extension = fileName.slice(lastDot);
    const nameWithoutExt = fileName.slice(0, lastDot);
    const truncated = nameWithoutExt.slice(0, maxLength - extension.length - 3);
    
    return `${truncated}...${extension}`;
  };

  // Функція для отримання розширення файлу
  const getFileExtension = (fileName) => {
    if (!fileName) return 'OTHER';
    const parts = fileName.split('.');
    return parts.length > 1 ? parts.pop().toUpperCase() : 'OTHER';
  };
  
  const formatFileSize = (bytes) => {
    if (!bytes || bytes < 1024) return (bytes || 0) + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  // Отримуємо унікальні типи файлів для фільтра
  const fileTypes = useMemo(() => {
    const types = {};
    files.forEach(file => {
      const ext = getFileExtension(file.name);
      types[ext] = (types[ext] || 0) + 1;
    });
    return Object.entries(types)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5); // Топ 5 типів
  }, [files]);

  // Останні 3 файли (сортовані по даті)
  const recentFiles = useMemo(() => {
    return [...files]
      .sort((a, b) => {
        const dateA = a.uploadedAt ? new Date(a.uploadedAt).getTime() : 0;
        const dateB = b.uploadedAt ? new Date(b.uploadedAt).getTime() : 0;
        return dateB - dateA;
      })
      .slice(0, 3);
  }, [files]);

  // Фільтрація та сортування файлів для модалки
  const filteredAndSortedFiles = useMemo(() => {
    let result = [...files];

    // Фільтрація по типу
    if (filterType !== 'all') {
      result = result.filter(file => getFileExtension(file.name) === filterType);
    }

    // Фільтрація по пошуку
    if (debouncedSearch.trim()) {
      const query = debouncedSearch.toLowerCase().trim();
      result = result.filter(file => 
        file.name.toLowerCase().includes(query)
      );
    }

    // Сортування
    result.sort((a, b) => {
      switch (sortBy) {
        case 'date_desc': {
          const dateA = a.uploadedAt ? new Date(a.uploadedAt).getTime() : 0;
          const dateB = b.uploadedAt ? new Date(b.uploadedAt).getTime() : 0;
          return dateB - dateA;
        }

        case 'date_asc': {
          const dateA2 = a.uploadedAt ? new Date(a.uploadedAt).getTime() : 0;
          const dateB2 = b.uploadedAt ? new Date(b.uploadedAt).getTime() : 0;
          return dateA2 - dateB2;
        }
        
        case 'name_asc':
          return (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' });
        
        case 'name_desc':
          return (b.name || '').localeCompare(a.name || '', undefined, { sensitivity: 'base' });
        
        case 'size_desc':
          return (b.size || 0) - (a.size || 0);
        
        case 'size_asc':
          return (a.size || 0) - (b.size || 0);
        
        default:
          return 0;
      }
    });

    return result;
  }, [files, debouncedSearch, sortBy, filterType]);

  const sortOptions = [
    { value: 'date_desc', label: t('training.sort.newestFirst') || 'Newest first' },
    { value: 'date_asc', label: t('training.sort.oldestFirst') || 'Oldest first' },
    { value: 'name_asc', label: t('training.sort.nameAZ') || 'Name (A → Z)' },
    { value: 'name_desc', label: t('training.sort.nameZA') || 'Name (Z → A)' },
    { value: 'size_desc', label: t('training.sort.sizeDesc') || 'Size (largest)' },
    { value: 'size_asc', label: t('training.sort.sizeAsc') || 'Size (smallest)' },
  ];

  // Компонент для рендеру одного файлу
  const FileItem = ({ file, compact = false }) => {
    const truncatedName = truncateFileName(file.name, compact ? 35 : 45);
    const isTruncated = file.name && file.name.length > (compact ? 35 : 45);
    const isText = file.type === 'text' || (file.name && file.name.endsWith('.txt') && !file.url);
    
    return (
      <div className={`flex items-center justify-between ${compact ? 'p-2.5' : 'p-3'} bg-gray-50 dark:bg-gray-700/50 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-all group`}>
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {isText ? (
            <Type className="text-blue-500 dark:text-blue-400 flex-shrink-0" size={compact ? 18 : 20} />
          ) : (
            <FileText className="text-primary-500 dark:text-primary-400 flex-shrink-0" size={compact ? 18 : 20} />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p 
                className={`font-medium ${compact ? 'text-xs' : 'text-sm'} text-gray-900 dark:text-gray-100 truncate`}
                title={isTruncated ? file.name : undefined}
              >
                {truncatedName}
              </p>
              {file.is_processed ? (
                <CheckCircle
                  size={14}
                  className="text-green-500 dark:text-green-400 flex-shrink-0"
                  title={t('training.fileProcessed') || 'Processed'}
                />
              ) : (
                <Loader2
                  size={14}
                  className="text-yellow-500 dark:text-yellow-400 flex-shrink-0 animate-spin"
                  title={t('training.fileProcessing') || 'Processing'}
                />
              )}
            </div>
            <div className={`flex items-center gap-2 ${compact ? 'text-[10px]' : 'text-xs'} text-gray-500 dark:text-gray-400 mt-0.5`}>
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
          onClick={(e) => {
            e.stopPropagation();
            onDelete(file.id);
          }}
          className="text-red-500 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 p-1.5 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
          title={t('training.deleteFile') || 'Delete file'}
        >
          <Trash2 size={16} />
        </button>
      </div>
    );
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
    <>
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {t('training.uploadedFiles')} ({files.length})
          </h3>
        </div>

        {/* Останні 3 файли */}
        <div className="space-y-2">
          {recentFiles.map((file) => (
            <FileItem key={file.id} file={file} compact />
          ))}
        </div>

        {/* Кнопка See More */}
        {files.length > 3 && (
          <button
            onClick={() => setShowModal(true)}
            className="w-full mt-4 py-2.5 px-4 flex items-center justify-center gap-2 text-sm font-medium text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 bg-primary-50 dark:bg-primary-900/20 hover:bg-primary-100 dark:hover:bg-primary-900/30 rounded-lg transition-colors"
          >
            <FolderOpen size={18} />
            {t('training.seeAllFiles') || 'See all files'} ({files.length})
            <ChevronRight size={16} />
          </button>
        )}
      </div>

      {/* Модалка з усіма файлами */}
      {showModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => setShowModal(false)}
        >
          <div 
            className="relative w-full max-w-3xl max-h-[85vh] bg-white dark:bg-gray-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="sticky top-0 z-10 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                  {t('training.allFiles') || 'All Files'} 
                  <span className="ml-2 text-sm font-normal text-gray-500 dark:text-gray-400">
                    ({filteredAndSortedFiles.length} {t('training.of') || 'of'} {files.length})
                  </span>
                </h2>
                <button
                  onClick={() => setShowModal(false)}
                  className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  <X size={20} />
                </button>
              </div>

              {/* Пошук */}
              <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-500" size={18} />
                <input
                  type="text"
                  placeholder={t('training.searchFiles') || 'Search files...'}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="input pl-10 w-full"
                  autoFocus
                />
              </div>

              {/* Фільтри та сортування */}
              <div className="flex flex-col sm:flex-row gap-3">
                {/* Фільтр по типу */}
                <div className="flex items-center gap-2 flex-wrap flex-1">
                  <Filter size={16} className="text-gray-400 dark:text-gray-500 flex-shrink-0" />
                  <button
                    onClick={() => setFilterType('all')}
                    className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                      filterType === 'all'
                        ? 'bg-primary-500 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                  >
                    {t('training.filter.all') || 'All'} ({files.length})
                  </button>
                  {fileTypes.map(([type, count]) => (
                    <button
                      key={type}
                      onClick={() => setFilterType(type)}
                      className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                        filterType === type
                          ? 'bg-primary-500 text-white'
                          : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                      }`}
                    >
                      {type} ({count})
                    </button>
                  ))}
                </div>

                {/* Сортування */}
                <div className="flex items-center gap-2">
                  <ArrowUpDown size={16} className="text-gray-400 dark:text-gray-500 flex-shrink-0" />
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    className="input text-sm py-1.5 pr-8 min-w-[150px]"
                  >
                    {sortOptions.map(option => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* Список файлів */}
            <div className="overflow-y-auto p-6 pt-4" style={{ maxHeight: 'calc(85vh - 220px)' }}>
              {filteredAndSortedFiles.length === 0 ? (
                <div className="text-center py-12">
                  <FolderOpen className="mx-auto text-gray-300 dark:text-gray-600 mb-4" size={48} />
                  <p className="text-gray-500 dark:text-gray-400">
                    {t('training.noFilesFound') || 'No files found'}
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredAndSortedFiles.map((file) => (
                    <FileItem key={file.id} file={file} />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default FileList;
