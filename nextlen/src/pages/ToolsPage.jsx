import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, Loader2 } from 'lucide-react';
import { toolsAPI } from '../api/tools';
import ToolCard from '../components/tools/ToolCard';
import CategoryFilter from '../components/tools/CategoryFilter';
import ConnectModal from '../components/tools/ConnectModal';

const ToolsPage = () => {
  const { t } = useTranslation();
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [category, setCategory] = useState('all');
  const [search, setSearch] = useState('');
  const [connectTool, setConnectTool] = useState(null);
  const [configureTool, setConfigureTool] = useState(null);

  const loadTools = async () => {
    try {
      const res = await toolsAPI.getCatalog();
      setTools(res.data);
      setError('');
    } catch (err) {
      setError('Failed to load tools');
      console.error('Tools catalog error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTools();
  }, []);

  const handleConnect = (tool) => {
    setConnectTool(tool);
  };

  const handleConfigure = (tool) => {
    setConfigureTool(tool);
  };

  const handleConnected = () => {
    loadTools(); // Refresh catalog
  };

  const handleDisconnect = async (slug) => {
    if (!window.confirm(t('tools.confirmDisconnect'))) return;
    try {
      await toolsAPI.disconnect(slug);
      setConfigureTool(null);
      loadTools();
    } catch (err) {
      console.error('Disconnect error:', err);
    }
  };

  const filtered = tools.filter((tool) => {
    if (category !== 'all' && tool.category !== category) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        tool.name.toLowerCase().includes(q) ||
        tool.tagline.toLowerCase().includes(q)
      );
    }
    return true;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {t('tools.title')}
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            {t('tools.subtitle')}
          </p>
        </div>
        <div className="relative w-full sm:w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
          <input
            type="text"
            placeholder={t('tools.search')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input w-full pl-9"
          />
        </div>
      </div>

      {/* Category Filter */}
      <CategoryFilter active={category} onChange={setCategory} />

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Grid */}
      {filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
          {t('tools.noTools')}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((tool) => (
            <ToolCard
              key={tool.slug}
              tool={tool}
              onConnect={handleConnect}
              onConfigure={handleConfigure}
            />
          ))}
        </div>
      )}

      {/* Connect Modal */}
      {connectTool && (
        <ConnectModal
          tool={connectTool}
          onClose={() => setConnectTool(null)}
          onConnected={handleConnected}
        />
      )}

      {/* Configure Modal (simple disconnect for now) */}
      {configureTool && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl w-full max-w-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
              {configureTool.name}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              {t('tools.connected')} {configureTool.connection?.connected_at
                ? new Date(configureTool.connection.connected_at).toLocaleDateString()
                : ''}
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setConfigureTool(null)}
                className="btn-secondary flex-1"
              >
                {t('common.close')}
              </button>
              <button
                onClick={() => handleDisconnect(configureTool.slug)}
                className="flex-1 py-2 px-4 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"
              >
                {t('tools.disconnect')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ToolsPage;
