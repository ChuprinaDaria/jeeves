import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowClockwise, Sparkle } from '@phosphor-icons/react';
import CanvasCopilot from '../components/tools/CanvasCopilot';
import { toolsAPI } from '../api/tools';
import ToolCatalogStrip from '../components/tools/ToolCatalogStrip';
import FlowCanvas from '../components/tools/FlowCanvas';
import ToolPopover from '../components/tools/ToolPopover';
import FlowToast, { useFlowToast } from '../components/tools/FlowToast';
import { getToolTargets } from '../components/tools/toolTargets';
import { useAuth } from '../context/AuthContext';

const ToolsPage = () => {
  const { t } = useTranslation();
  const { user, isOwner } = useAuth();
  const multiConn = user?.feature_flags?.mcp_tools_multi_connection;
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [highlightedTool, setHighlightedTool] = useState(null);
  const [popover, setPopover] = useState(null); // { tool, rect }
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [channels, setChannels] = useState([]);
  const [skillsByTarget, setSkillsByTarget] = useState({});
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

  useEffect(() => {
    loadTools();
    toolsAPI.getFlowChannels()
      .then(res => setChannels(res.data?.channels || []))
      .catch(() => {});
    toolsAPI.getSkills()
      .then(res => {
        const map = {};
        (res.data?.skills || []).forEach(sk => {
          sk.attached_to.forEach(target => {
            (map[target] = map[target] || []).push(sk.name);
          });
        });
        setSkillsByTarget(map);
      })
      .catch(() => {});
  }, []);

  const handleConnected = useCallback((slug) => {
    const tool = tools.find(t => t.slug === slug);
    const targets = getToolTargets(slug);
    const targetName = targets.includes('assistant')
      ? t('tools.flow.connectedToAssistant')
      : t('tools.flow.connectedToManager');
    showToast('🔗', `${tool?.name || slug} ${targetName}`);
    loadTools();
  }, [tools, showToast, t]);

  const handleDisconnect = useCallback(async (slug, target) => {
    try {
      const tool = tools.find(t => t.slug === slug);
      // Find the flow connection ID to delete (detach edge only, keep credentials)
      let connId;
      if (multiConn && tool?.connections) {
        const conn = tool.connections.find(c => c.target === target && c.status === 'connected');
        connId = conn?.id;
      } else {
        connId = tool?.connection?.id;
      }

      if (connId) {
        // Detach edge: disable connection but keep credentials intact
        await toolsAPI.updateFlowConnection(connId, { enabled: false });
      }
      showToast('🔌', `${tool?.name || slug} ${t('tools.flow.disconnected')}`);
      loadTools();
    } catch (err) {
      console.error('Disconnect error:', err);
      showToast('⚠️', t('tools.flow.disconnectError'));
    }
  }, [tools, showToast, t, multiConn]);

  const handleMiddlewareRemove = useCallback(async (conn, middlewareId) => {
    try {
      const tool = tools.find(t => t.slug === conn.toolSlug);
      let connId;
      if (multiConn && tool?.connections) {
        const toolConn = tool.connections.find(c => c.target === conn.target && c.status === 'connected');
        connId = toolConn?.id;
      } else {
        connId = tool?.connection?.id;
      }
      if (!connId) return;
      await toolsAPI.detachMiddleware(connId, middlewareId);
      showToast('🔧', t('tools.flow.middlewareRemoved'));
      loadTools();
    } catch (err) {
      console.error('Remove middleware error:', err);
      showToast('⚠️', t('tools.flow.connectError'));
    }
  }, [tools, showToast, t, multiConn]);

  const handleMiddlewareAttach = useCallback(async (conn, skillSlug) => {
    try {
      const tool = tools.find(t => t.slug === conn.toolSlug);
      let connId;
      if (multiConn && tool?.connections) {
        const toolConn = tool.connections.find(c => c.target === conn.target && c.status === 'connected');
        connId = toolConn?.id;
      } else {
        connId = tool?.connection?.id;
      }
      if (!connId) return;
      await toolsAPI.attachMiddleware(connId, skillSlug);
      const skill = tools.find(t => t.slug === skillSlug);
      showToast('🧩', `${skill?.name || skillSlug} ${t('tools.flow.middlewareAttached')}`);
      loadTools();
    } catch (err) {
      console.error('Attach middleware error:', err);
      showToast('⚠️', err.response?.data?.error || t('tools.flow.attachFailed'));
    }
  }, [tools, showToast, t, multiConn]);

  const handleConnect = useCallback(async (slug, target) => {
    const tool = tools.find(t => t.slug === slug);
    if (!tool) return;

    try {
      if (multiConn && tool.connections) {
        const existing = tool.connections.find(
          c => c.target === target && c.status === 'connected' && c.enabled
        );
        if (existing) {
          showToast('✓', t('tools.flow.alreadyConnected'));
          return;
        }
        const anyConn = tool.connections.find(c => c.status === 'connected');
        if (tool.auth_type === 'none' || anyConn) {
          await toolsAPI.createFlowConnection(slug, target);
        } else {
          showToast('💡', t('tools.flow.clickToConnect'));
          return;
        }
      } else {
        const isConnected = tool.connection?.status === 'connected' && tool.connection?.enabled;
        if (isConnected && tool.connection?.id) {
          await toolsAPI.updateFlowConnection(tool.connection.id, { target });
        } else if (tool.auth_type === 'none') {
          await toolsAPI.createFlowConnection(slug, target);
        } else {
          showToast('💡', t('tools.flow.clickToConnect'));
          return;
        }
      }
      showToast('🔗', `${tool?.name || slug} → ${target}`);
      loadTools();
    } catch (err) {
      console.error('Connect error:', err);
      showToast('⚠️', t('tools.flow.connectError'));
    }
  }, [tools, showToast, t, multiConn]);

  const handleToolDrop = useCallback(async (slug) => {
    const tool = tools.find(t => t.slug === slug);
    if (!tool) return;
    const isConnected = multiConn && tool.connections
      ? tool.connections.some(c => c.status === 'connected' && c.enabled)
      : tool.connection?.status === 'connected' && tool.connection?.enabled;
    if (isConnected) return;
    if (tool.auth_type === 'none') {
      try {
        await toolsAPI.connect(slug, {});
        handleConnected(slug);
      } catch (err) {
        console.error('Drop-connect error:', err);
        showToast('⚠️', t('tools.flow.connectError'));
      }
    } else {
      showToast('💡', t('tools.flow.clickToConnect'));
    }
  }, [tools, handleConnected, showToast, t, multiConn]);

  const handlePositionSave = useCallback(async (slug, pos) => {
    const tool = tools.find(t => t.slug === slug);
    if (!tool) return;
    const conns = (tool.connections?.length ? tool.connections : (tool.connection ? [tool.connection] : []))
      .filter(c => c.id && c.status === 'connected');
    try {
      await Promise.all(conns.map(c =>
        toolsAPI.updateFlowConnection(c.id, { position_x: pos.x, position_y: pos.y })
      ));
    } catch (err) {
      console.error('Position save error:', err); // non-blocking — localStorage still has it
    }
  }, [tools]);

  const handleCanvasToolClick = useCallback((tool, e) => {
    const el = e?.currentTarget || document.getElementById(`canvas-tool-${tool.slug}`);
    if (el) {
      setPopover({ tool, rect: el.getBoundingClientRect() });
    }
  }, []);

  const connectedCount = tools.filter(t => {
    if (multiConn && t.connections) {
      return t.connections.some(c => c.status === 'connected' && c.enabled);
    }
    return t.connection?.status === 'connected' && t.connection?.enabled;
  }).length;
  const availableCount = tools.length - connectedCount;

  if (loading) {
    return (
      <div className="space-y-6 max-w-[1200px] mx-auto">
        {/* Skeleton strip */}
        <div className="flex gap-3 overflow-hidden">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="w-[160px] h-[100px] rounded-lg bg-linen border-[1.5px] border-rule animate-pulse shrink-0" />
          ))}
        </div>
        {/* Skeleton canvas */}
        <div className="relative w-full rounded-lg bg-stage border-[1.5px] border-stage-line overflow-hidden"
             style={{ minHeight: 'max(60vh, 400px)' }}>
          <div className="absolute top-1/2 left-[35%] -translate-x-1/2 -translate-y-1/2 w-[200px] h-[140px] rounded-xl bg-stage-deep border-[1.5px] border-stage-line animate-pulse" />
          <div className="absolute top-1/2 left-[65%] -translate-x-1/2 -translate-y-1/2 w-[200px] h-[140px] rounded-xl bg-stage-deep border-[1.5px] border-stage-line animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-[1200px] mx-auto overflow-x-hidden">
      {/* Header */}
      <div className="flex items-end justify-between animate-fade-up">
        <div>
          <h1 className="text-[28px] font-bold tracking-tightest text-ink">
            {t('tools.flow.title')}{' '}
            <span className="text-iris">{t('tools.flow.titleAccent')}</span>
          </h1>
          <div className="font-mono text-[13px] text-fog mt-1">
            {t('tools.flow.headerHint')}
          </div>
        </div>
        <div className="flex items-center gap-5">
          <div className="flex gap-5 font-mono text-[11px] uppercase tracking-wider text-fog">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-sage shadow-[0_0_4px_rgba(123,200,159,0.55)]" />
              <span className="text-sage">{connectedCount}</span> {t('tools.flow.statsConnected')}
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-fog" />
              {availableCount} {t('tools.flow.statsAvailable')}
            </span>
          </div>
          <button
            onClick={() => setCopilotOpen(o => !o)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border-[1.5px] text-[12px] font-medium
                        transition-all ${copilotOpen
                          ? 'border-iris bg-iris text-paper'
                          : 'border-iris text-iris bg-transparent hover:bg-iris-soft/30'}`}
          >
            <Sparkle size={14} weight="light" />
            {t('tools.copilot.open')}
          </button>
        </div>
      </div>

      {/* Tool Catalog Strip */}
      {error ? (
        <div className="flex items-center gap-3 p-4 bg-paper border-[1.5px] border-rose rounded-lg">
          <span className="text-[13px] text-rose">{error}</span>
          <button
            onClick={() => { setLoading(true); loadTools(); }}
            className="flex items-center gap-1.5 font-mono text-[12px] uppercase tracking-wider text-rose
                       hover:text-ink transition-colors bg-transparent min-h-0"
          >
            <ArrowClockwise size={14} weight="light" /> {t('tools.retry')}
          </button>
        </div>
      ) : (
        <ToolCatalogStrip
          tools={tools}
          onConnected={handleConnected}
          onToolHover={setHighlightedTool}
          onToolHoverEnd={() => setHighlightedTool(null)}
          canInstall={isOwner}
        />
      )}

      {/* Flow Canvas */}
      <FlowCanvas
        tools={tools}
        channels={channels}
        skillsByTarget={skillsByTarget}
        onToolClick={handleCanvasToolClick}
        highlightedTool={highlightedTool}
        onToolDrop={handleToolDrop}
        onDisconnect={handleDisconnect}
        onConnect={handleConnect}
        onMiddlewareRemove={handleMiddlewareRemove}
        onMiddlewareAttach={handleMiddlewareAttach}
        onRefresh={loadTools}
        onPositionSave={handlePositionSave}
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

      {/* Jeeves canvas copilot */}
      <CanvasCopilot
        open={copilotOpen}
        onClose={() => setCopilotOpen(false)}
        onCanvasChanged={loadTools}
      />

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
