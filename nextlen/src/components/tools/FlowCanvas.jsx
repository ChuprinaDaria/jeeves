import { useRef, useState, useEffect, useCallback, useMemo } from 'react';
import { ZoomIn, ZoomOut, Maximize2, RotateCcw } from 'lucide-react';
import CoreNode from './CoreNode';
import CanvasToolNode from './CanvasToolNode';
import ConnectionsLayer from './ConnectionsLayer';
import OnboardingHint from './OnboardingHint';
import { getToolTargets } from './toolTargets';

/* ── Constants ─────────────────────────────────────── */
const CORE_W = 200, CORE_H = 145;
const TOOL_W = 160, TOOL_H = 104;
const PORT_RADIUS = 6; // half of w-3 h-3 (12px)
const ZOOM_MIN = 0.3, ZOOM_MAX = 2, ZOOM_STEP = 0.1;
const CANVAS_PADDING = 60;
const PORT_GAP = 20;

/* ── Helpers ───────────────────────────────────────── */
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** Cubic bezier path from source-right port to target-left port */
const calcPath = (x1, y1, x2, y2) => {
  const dx = Math.abs(x2 - x1) * 0.55;
  return `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
};

/** Build initial positions for all nodes based on canvas size */
const buildInitialPositions = (canvasW, canvasH, groups) => {
  const pos = {};
  const cx = canvasW / 2;
  const cy = canvasH / 2;

  // Core nodes — three-column layout
  pos['__assistant'] = { x: canvasW * 0.30 - CORE_W / 2, y: cy - CORE_H / 2 };
  pos['__manager']   = { x: canvasW * 0.55 - CORE_W / 2, y: cy - CORE_H / 2 };
  pos['__leads']     = { x: canvasW * 0.80 - CORE_W / 2, y: cy - CORE_H / 2 };

  // Tool nodes — left column
  const layoutColumn = (list, baseX) => {
    const total = list.length;
    const spacing = total > 1 ? Math.min(100, (canvasH - CANVAS_PADDING * 2) / (total - 1)) : 0;
    const yStart = total > 1 ? cy - (spacing * (total - 1)) / 2 : cy - TOOL_H / 2;
    list.forEach((tool, i) => {
      pos[tool.slug] = { x: baseX, y: yStart + i * spacing };
    });
  };

  layoutColumn(groups.left, CANVAS_PADDING);
  layoutColumn(groups.right, canvasW - CANVAS_PADDING - TOOL_W);

  // Both — horizontal row above center
  const bothTotal = groups.both.length;
  groups.both.forEach((tool, i) => {
    const offset = (i - (bothTotal - 1) / 2) * (TOOL_W + 20);
    pos[tool.slug] = { x: cx + offset - TOOL_W / 2, y: CANVAS_PADDING };
  });

  return pos;
};

/* ── Component ─────────────────────────────────────── */
const FlowCanvas = ({ tools, onToolClick, highlightedTool, onToolDrop }) => {
  const containerRef = useRef(null);
  const innerRef = useRef(null);

  /* ── Connected tools & groups ──────────── */
  const connectedTools = useMemo(
    () => tools.filter(t => t.connection?.status === 'connected' && t.connection?.enabled),
    [tools]
  );

  const groups = useMemo(() => {
    const left = [], right = [], both = [], leadsTools = [];
    connectedTools.forEach(tool => {
      const targets = getToolTargets(tool.slug);
      if (targets.includes('leads')) leadsTools.push(tool);
      if (targets.includes('assistant') && targets.includes('manager')) both.push(tool);
      else if (targets.includes('manager')) right.push(tool);
      else left.push(tool);
    });
    return { left, right, both, leads: leadsTools };
  }, [connectedTools]);

  /* ── Canvas dimensions ─────────────────── */
  const maxGroupSize = Math.max(groups.left.length, groups.right.length, 1);
  const canvasH = Math.max(500, maxGroupSize * 100 + 200);
  const canvasW = 1200;

  /* ── Node positions ────────────────────── */
  const [positions, setPositions] = useState(() =>
    buildInitialPositions(canvasW, canvasH, groups)
  );

  // Re-initialize positions when tools change (new connections)
  useEffect(() => {
    setPositions(prev => {
      const fresh = buildInitialPositions(canvasW, canvasH, groups);
      // Keep existing positions for nodes that already have one
      const merged = { ...fresh };
      for (const key in prev) {
        if (key in merged) merged[key] = prev[key];
      }
      return merged;
    });
  }, [connectedTools.length, canvasW, canvasH, groups]);

  /* ── Viewport (pan & zoom) ─────────────── */
  const [viewport, setViewport] = useState({ x: 0, y: 0, zoom: 1 });

  /* ── Drag state ────────────────────────── */
  const dragRef = useRef(null);     // { nodeId, offsetX, offsetY }
  const panRef = useRef(null);      // { startX, startY, vpX, vpY }
  const [isDragging, setIsDragging] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const clickGuardRef = useRef(false); // prevent click after drag

  /* ── Convert screen coords → canvas coords ── */
  const screenToCanvas = useCallback((clientX, clientY) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
      x: (clientX - rect.left - viewport.x) / viewport.zoom,
      y: (clientY - rect.top  - viewport.y) / viewport.zoom,
    };
  }, [viewport]);

  /* ── Per-port Y offset for core nodes ─── */
  const getPortY = (nodePos, portIndex, portCount) => {
    const totalH = (portCount - 1) * PORT_GAP;
    const startY = nodePos.y + CORE_H / 2 - totalH / 2;
    return startY + portIndex * PORT_GAP + PORT_RADIUS;
  };

  /* ── Compute connections from positions ── */
  const connections = useMemo(() => {
    const aPos = positions['__assistant'];
    const mPos = positions['__manager'];
    const lPos = positions['__leads'];
    if (!aPos || !mPos) return [];

    const conns = [];

    // Escalation link: Assistant → Manager
    const aRightX = aPos.x + CORE_W, aRightY = aPos.y + CORE_H / 2;
    const mLeftX  = mPos.x,          mLeftY  = mPos.y + CORE_H / 2;
    conns.push({
      id: 'escalation',
      pathD: calcPath(aRightX, aRightY, mLeftX, mLeftY),
      target: 'escalation',
      toolSlug: null,
    });

    // Collect tools targeting each core node to assign port indices
    const assistantTools = connectedTools.filter(t => getToolTargets(t.slug).includes('assistant'));
    const managerTools = connectedTools.filter(t => getToolTargets(t.slug).includes('manager'));
    const leadsTools = connectedTools.filter(t => getToolTargets(t.slug).includes('leads'));

    // Tool connections — edges go to specific ports
    assistantTools.forEach((tool, portIdx) => {
      const tPos = positions[tool.slug];
      if (!tPos) return;
      const srcX = tPos.x + TOOL_W, srcY = tPos.y + TOOL_H / 2;
      const tgtX = aPos.x;
      const tgtY = getPortY(aPos, portIdx, assistantTools.length);
      conns.push({
        id: `${tool.slug}-assistant`,
        pathD: calcPath(srcX, srcY, tgtX, tgtY),
        target: 'assistant',
        toolSlug: tool.slug,
      });
    });

    managerTools.forEach((tool, portIdx) => {
      const tPos = positions[tool.slug];
      if (!tPos) return;
      const srcX = tPos.x + TOOL_W, srcY = tPos.y + TOOL_H / 2;
      const tgtX = mPos.x;
      const tgtY = getPortY(mPos, portIdx, managerTools.length);
      conns.push({
        id: `${tool.slug}-manager`,
        pathD: calcPath(srcX, srcY, tgtX, tgtY),
        target: 'manager',
        toolSlug: tool.slug,
      });
    });

    // Leads connections
    if (lPos) {
      leadsTools.forEach((tool, portIdx) => {
        const tPos = positions[tool.slug];
        if (!tPos) return;
        const srcX = tPos.x + TOOL_W, srcY = tPos.y + TOOL_H / 2;
        const tgtX = lPos.x;
        const tgtY = getPortY(lPos, portIdx, leadsTools.length);
        conns.push({
          id: `${tool.slug}-leads`,
          pathD: calcPath(srcX, srcY, tgtX, tgtY),
          target: 'leads',
          toolSlug: tool.slug,
        });
      });
    }

    return conns;
  }, [positions, connectedTools]);

  /* ── Node drag handlers ────────────────── */
  const handleNodePointerDown = useCallback((nodeId, e) => {
    // Only primary button
    if (e.button !== 0) return;
    e.stopPropagation();
    // NOT calling preventDefault() — click events must still fire for popover

    const canvas = screenToCanvas(e.clientX, e.clientY);
    const pos = positions[nodeId];
    if (!pos) return;

    dragRef.current = {
      nodeId,
      offsetX: canvas.x - pos.x,
      offsetY: canvas.y - pos.y,
    };
    clickGuardRef.current = false;
    setIsDragging(true);

    const target = e.currentTarget;
    target.setPointerCapture?.(e.pointerId);
  }, [positions, screenToCanvas]);

  const handleNodePointerMove = useCallback((e) => {
    if (!dragRef.current) return;
    e.preventDefault();

    clickGuardRef.current = true; // moved → suppress click

    const canvas = screenToCanvas(e.clientX, e.clientY);
    const { nodeId, offsetX, offsetY } = dragRef.current;
    const newX = canvas.x - offsetX;
    const newY = canvas.y - offsetY;

    setPositions(prev => ({
      ...prev,
      [nodeId]: { x: newX, y: newY },
    }));
  }, [screenToCanvas]);

  const handleNodePointerUp = useCallback(() => {
    dragRef.current = null;
    setIsDragging(false);
  }, []);

  /* ── Canvas pan handlers ───────────────── */
  const handleCanvasPointerDown = useCallback((e) => {
    // Only on canvas background (not nodes) & primary button
    if (e.button !== 0) return;
    if (e.target !== innerRef.current && e.target !== containerRef.current) return;

    panRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      vpX: viewport.x,
      vpY: viewport.y,
    };
    setIsPanning(true);
  }, [viewport]);

  useEffect(() => {
    if (!isPanning) return;

    const handleMove = (e) => {
      if (!panRef.current) return;
      const dx = e.clientX - panRef.current.startX;
      const dy = e.clientY - panRef.current.startY;
      setViewport(prev => ({
        ...prev,
        x: panRef.current.vpX + dx,
        y: panRef.current.vpY + dy,
      }));
    };

    const handleUp = () => {
      panRef.current = null;
      setIsPanning(false);
    };

    document.addEventListener('pointermove', handleMove);
    document.addEventListener('pointerup', handleUp);
    return () => {
      document.removeEventListener('pointermove', handleMove);
      document.removeEventListener('pointerup', handleUp);
    };
  }, [isPanning]);

  /* ── Zoom (wheel) ──────────────────────── */
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const handleWheel = (e) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      setViewport(prev => {
        const direction = e.deltaY > 0 ? -1 : 1;
        const newZoom = clamp(prev.zoom + direction * ZOOM_STEP, ZOOM_MIN, ZOOM_MAX);
        const ratio = newZoom / prev.zoom;

        return {
          x: mouseX - (mouseX - prev.x) * ratio,
          y: mouseY - (mouseY - prev.y) * ratio,
          zoom: newZoom,
        };
      });
    };

    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, []);

  /* ── Zoom controls ─────────────────────── */
  const zoomIn = () => {
    setViewport(prev => ({ ...prev, zoom: clamp(prev.zoom + ZOOM_STEP, ZOOM_MIN, ZOOM_MAX) }));
  };

  const zoomOut = () => {
    setViewport(prev => ({ ...prev, zoom: clamp(prev.zoom - ZOOM_STEP, ZOOM_MIN, ZOOM_MAX) }));
  };

  const fitToView = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();

    // Find bounding box of all nodes
    const allIds = Object.keys(positions);
    if (allIds.length === 0) return;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    allIds.forEach(id => {
      const p = positions[id];
      const w = id.startsWith('__') ? CORE_W : TOOL_W;
      const h = id.startsWith('__') ? CORE_H : TOOL_H;
      minX = Math.min(minX, p.x);
      minY = Math.min(minY, p.y);
      maxX = Math.max(maxX, p.x + w);
      maxY = Math.max(maxY, p.y + h);
    });

    const contentW = maxX - minX + CANVAS_PADDING * 2;
    const contentH = maxY - minY + CANVAS_PADDING * 2;
    const zoom = clamp(Math.min(rect.width / contentW, rect.height / contentH), ZOOM_MIN, ZOOM_MAX);

    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;

    setViewport({
      x: rect.width / 2 - cx * zoom,
      y: rect.height / 2 - cy * zoom,
      zoom,
    });
  }, [positions]);

  const resetView = () => setViewport({ x: 0, y: 0, zoom: 1 });

  // Fit to view on first render
  useEffect(() => {
    const timer = setTimeout(fitToView, 200);
    return () => clearTimeout(timer);
  }, [connectedTools.length]);

  /* ── Drop zone for tool cards from strip ── */
  const [dragOver, setDragOver] = useState(false);

  const handleDragOver = useCallback((e) => {
    if (!e.dataTransfer.types.includes('tool-slug')) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => setDragOver(false), []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const slug = e.dataTransfer.getData('tool-slug');
    if (!slug) return;
    onToolDrop?.(slug);
  }, [onToolDrop]);

  /* ── Tool click guard (don't fire click after drag) ── */
  const handleToolClick = useCallback((tool, e) => {
    if (clickGuardRef.current) {
      clickGuardRef.current = false;
      return;
    }
    onToolClick?.(tool, e);
  }, [onToolClick]);

  /* ── Escalation label position ─────────── */
  const escLabel = useMemo(() => {
    const a = positions['__assistant'];
    const m = positions['__manager'];
    if (!a || !m) return null;
    return {
      x: (a.x + CORE_W + m.x) / 2,
      y: (a.y + CORE_H / 2 + m.y + CORE_H / 2) / 2,
    };
  }, [positions]);

  /* ── Render ────────────────────────────── */
  const zoomPercent = Math.round(viewport.zoom * 100);

  return (
    <section
      ref={containerRef}
      aria-label="Flow diagram"
      className={`flow-canvas relative w-full bg-gray-50 dark:bg-gray-900 rounded-xl overflow-hidden ${isPanning ? 'panning' : ''} ${dragOver ? 'ring-2 ring-primary-400 ring-inset bg-primary-50/30 dark:bg-primary-900/10' : ''}`}
      style={{ minHeight: `max(60vh, 500px)`, cursor: isPanning ? 'grabbing' : 'default' }}
      onPointerDown={handleCanvasPointerDown}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* ── Transform layer (pan & zoom) ── */}
      <div
        ref={innerRef}
        className="absolute inset-0 origin-top-left"
        style={{
          transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`,
          willChange: isDragging || isPanning ? 'transform' : 'auto',
        }}
      >
        {/* Dot grid */}
        <div
          className="absolute dot-grid"
          style={{ inset: -2000, width: canvasW + 4000, height: canvasH + 4000 }}
        />

        {/* Onboarding hint */}
        {connectedTools.length === 0 && <OnboardingHint />}

        {/* SVG connections */}
        <ConnectionsLayer
          connections={connections}
          highlightedTool={highlightedTool}
          canvasW={canvasW}
          canvasH={canvasH}
        />

        {/* Core nodes */}
        {positions['__assistant'] && (
          <div
            className={`flow-draggable absolute ${isDragging && dragRef.current?.nodeId === '__assistant' ? 'dragging' : ''}`}
            style={{ left: positions['__assistant'].x, top: positions['__assistant'].y }}
            onPointerDown={(e) => handleNodePointerDown('__assistant', e)}
            onPointerMove={handleNodePointerMove}
            onPointerUp={handleNodePointerUp}
          >
            <CoreNode
              variant="assistant"
              connectedCount={groups.left.length + groups.both.length}
            />
          </div>
        )}
        {positions['__manager'] && (
          <div
            className={`flow-draggable absolute ${isDragging && dragRef.current?.nodeId === '__manager' ? 'dragging' : ''}`}
            style={{ left: positions['__manager'].x, top: positions['__manager'].y }}
            onPointerDown={(e) => handleNodePointerDown('__manager', e)}
            onPointerMove={handleNodePointerMove}
            onPointerUp={handleNodePointerUp}
          >
            <CoreNode
              variant="manager"
              connectedCount={groups.right.length + groups.both.length}
            />
          </div>
        )}
        {positions['__leads'] && (
          <div
            className={`flow-draggable absolute ${isDragging && dragRef.current?.nodeId === '__leads' ? 'dragging' : ''}`}
            style={{ left: positions['__leads'].x, top: positions['__leads'].y }}
            onPointerDown={(e) => handleNodePointerDown('__leads', e)}
            onPointerMove={handleNodePointerMove}
            onPointerUp={handleNodePointerUp}
          >
            <CoreNode
              variant="leads"
              connectedCount={groups.leads.length}
            />
          </div>
        )}

        {/* Escalation label */}
        {escLabel && (
          <div
            className="absolute text-[10px] text-gray-400 dark:text-gray-500 font-medium tracking-wider uppercase pointer-events-none"
            style={{ left: escLabel.x, top: escLabel.y, transform: 'translate(-50%, -50%)' }}
          >
            escalation
          </div>
        )}

        {/* Connected tool nodes */}
        {connectedTools.map(tool => {
          const pos = positions[tool.slug];
          if (!pos) return null;
          const isBeingDragged = isDragging && dragRef.current?.nodeId === tool.slug;
          return (
            <div
              key={tool.slug}
              className={`flow-draggable absolute ${isBeingDragged ? 'dragging' : ''}`}
              style={{ left: pos.x, top: pos.y }}
              onPointerDown={(e) => handleNodePointerDown(tool.slug, e)}
              onPointerMove={handleNodePointerMove}
              onPointerUp={handleNodePointerUp}
            >
              <CanvasToolNode
                tool={tool}
                onClick={handleToolClick}
                isHighlighted={highlightedTool === null ? null : highlightedTool === tool.slug}
              />
            </div>
          );
        })}
      </div>

      {/* ── Zoom controls (fixed in corner) ── */}
      <div className="flow-zoom-controls absolute bottom-4 right-4 flex items-center gap-1 bg-white/90 dark:bg-gray-800/90 border border-gray-200 dark:border-gray-700 rounded-xl p-1 shadow-sm z-20">
        <button
          onClick={zoomOut}
          disabled={viewport.zoom <= ZOOM_MIN}
          className="p-1.5 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30 transition-colors"
          aria-label="Zoom out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 min-w-[3ch] text-center tabular-nums">
          {zoomPercent}%
        </span>
        <button
          onClick={zoomIn}
          disabled={viewport.zoom >= ZOOM_MAX}
          className="p-1.5 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30 transition-colors"
          aria-label="Zoom in"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <div className="w-px h-4 bg-gray-200 dark:bg-gray-700 mx-0.5" />
        <button
          onClick={fitToView}
          className="p-1.5 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          aria-label="Fit to view"
          title="Fit to view"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
        <button
          onClick={resetView}
          className="p-1.5 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          aria-label="Reset view"
          title="Reset zoom & position"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      {/* ── Keyboard hint ── */}
      {connectedTools.length > 0 && (
        <div className="absolute bottom-4 left-4 text-[10px] text-gray-400 dark:text-gray-500 pointer-events-none select-none z-20">
          Scroll to zoom · Drag background to pan · Drag nodes to move
        </div>
      )}
    </section>
  );
};

export default FlowCanvas;
