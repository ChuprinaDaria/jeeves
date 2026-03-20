import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw } from 'lucide-react';
import { toolsAPI } from '../api/tools';
import ToolCatalogStrip from '../components/tools/ToolCatalogStrip';
import FlowCanvas from '../components/tools/FlowCanvas';
import ToolPopover from '../components/tools/ToolPopover';
import FlowToast, { useFlowToast } from '../components/tools/FlowToast';
import { getToolTargets } from '../components/tools/toolTargets';

const ToolsPage = () => {
  const { t } = useTranslation();
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [highlightedTool, setHighlightedTool] = useState(null);
  const [popover, setPopover] = useState(null); // { tool, rect }
  const { toast, showToast, hideToast } = useFlowToast();

  const loadTools = async () => {
    try {
      const res = await toolsAPI.getCatalog();
      setTools(res.data);
      setError('');
    } catch {
      setError(t('tools.flow.loadError'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTools(); }, []);

  const handleConnected = useCallback((slug) => {
    const tool = tools.find(t => t.slug === slug);
    const targets = getToolTargets(slug);
    const targetName = targets.includes('assistant')
      ? t('tools.flow.connectedToAssistant')
      : t('tools.flow.connectedToManager');
    showToast('🔗', `${tool?.name || slug} ${targetName}`);
    loadTools();
  }, [tools, showToast, t]);

  const handleDisconnect = useCallback(async (slug) => {
    try {
      await toolsAPI.disconnect(slug);
      const tool = tools.find(t => t.slug === slug);
      showToast('🔌', `${tool?.name || slug} ${t('tools.flow.disconnected')}`);
      loadTools();
    } catch (err) {
      console.error('Disconnect error:', err);
    }
  }, [tools, showToast, t]);

  const handleConnect = useCallback(async (slug, target) => {
    const tool = tools.find(t => t.slug === slug);
    if (!tool) return;

    const isConnected = tool.connection?.status === 'connected' && tool.connection?.enabled;

    try {
      if (isConnected && tool.connection?.id) {
        await toolsAPI.updateFlowConnection(tool.connection.id, { target });
      } else if (tool.auth_type === 'none') {
        await toolsAPI.createFlowConnection(slug, target);
      } else {
        showToast('💡', t('tools.flow.clickToConnect'));
        return;
      }
      showToast('🔗', `${tool?.name || slug} → ${target}`);
      loadTools();
    } catch (err) {
      console.error('Connect error:', err);
    }
  }, [tools, showToast, t]);

  const handleToolDrop = useCallback(async (slug) => {
    const tool = tools.find(t => t.slug === slug);
    if (!tool) return;
    const isConnected = tool.connection?.status === 'connected' && tool.connection?.enabled;
    if (isConnected) return;
    if (tool.auth_type === 'none') {
      try {
        await toolsAPI.connect(slug, {});
        handleConnected(slug);
      } catch (err) {
        console.error('Drop-connect error:', err);
      }
    } else {
      showToast('💡', t('tools.flow.clickToConnect'));
    }
  }, [tools, handleConnected, showToast, t]);

  const handleCanvasToolClick = useCallback((tool, e) => {
    const el = e?.currentTarget || document.getElementById(`canvas-tool-${tool.slug}`);
    if (el) {
      setPopover({ tool, rect: el.getBoundingClientRect() });
    }
  }, []);

  const connectedCount = tools.filter(t => t.connection?.status === 'connected' && t.connection?.enabled).length;
  const availableCount = tools.length - connectedCount;

  if (loading) {
    return (
      <div className="space-y-6">
        {/* Skeleton strip */}
        <div className="flex gap-3 overflow-hidden">
          {[1,2,3,4,5].map(i => (
            <div key={i} className="w-[160px] h-[100px] rounded-xl bg-gray-200 dark:bg-gray-700 animate-pulse shrink-0" />
          ))}
        </div>
        {/* Skeleton canvas with blurred core node placeholders */}
        <div className="relative w-full rounded-xl bg-gray-100 dark:bg-gray-800 overflow-hidden" style={{ minHeight: 'max(60vh, 400px)' }}>
          <div className="absolute top-1/2 left-[35%] -translate-x-1/2 -translate-y-1/2 w-[200px] h-[140px] rounded-2xl bg-gray-200 dark:bg-gray-700 animate-pulse blur-[2px]" />
          <div className="absolute top-1/2 left-[65%] -translate-x-1/2 -translate-y-1/2 w-[200px] h-[140px] rounded-2xl bg-gray-200 dark:bg-gray-700 animate-pulse blur-[2px]" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-full overflow-x-hidden">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {t('tools.flow.title')} <span className="text-primary-500">{t('tools.flow.titleAccent')}</span>
          </h1>
        </div>
        <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_4px_rgba(34,197,94,0.6)]" />
            {connectedCount} {t('tools.flow.statsConnected')}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
            {availableCount} {t('tools.flow.statsAvailable')}
          </span>
        </div>
      </div>

      {/* Tool Catalog Strip */}
      {error ? (
        <div className="flex items-center gap-3 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
          <span className="text-sm text-red-700 dark:text-red-400">{error}</span>
          <button onClick={() => { setLoading(true); loadTools(); }}
            className="flex items-center gap-1 text-sm font-medium text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 min-h-0">
            <RefreshCw className="w-3.5 h-3.5" /> {t('tools.retry')}
          </button>
        </div>
      ) : (
        <ToolCatalogStrip
          tools={tools}
          onConnected={handleConnected}
          onToolHover={setHighlightedTool}
          onToolHoverEnd={() => setHighlightedTool(null)}
        />
      )}

      {/* Flow Canvas */}
      <FlowCanvas
        tools={tools}
        onToolClick={handleCanvasToolClick}
        highlightedTool={highlightedTool}
        onToolDrop={handleToolDrop}
        onDisconnect={handleDisconnect}
        onConnect={handleConnect}
      />

      {/* Popover */}
      {popover && (
        <ToolPopover
          tool={popover.tool}
          anchorRect={popover.rect}
          onDisconnect={handleDisconnect}
          onClose={() => setPopover(null)}
        />
      )}

      {/* Toast */}
      <FlowToast
        message={toast.message}
        icon={toast.icon}
        visible={toast.visible}
        onHide={hideToast}
      />
    </div>
  );
};

export default ToolsPage;
