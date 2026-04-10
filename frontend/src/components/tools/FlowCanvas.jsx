import { useRef, useState, useEffect, useCallback, useMemo } from 'react';
import {
  MagnifyingGlassPlus as ZoomIn,
  MagnifyingGlassMinus as ZoomOut,
  ArrowsOut as Maximize2,
  ArrowCounterClockwise as RotateCcw,
  Trash as Trash2,
} from '@phosphor-icons/react';
import CoreNode from './CoreNode';
import CanvasToolNode from './CanvasToolNode';
import ConnectionsLayer from './ConnectionsLayer';
import OnboardingHint from './OnboardingHint';
import EdgeSkillBadge from './EdgeSkillBadge';
import { getToolTargets } from './toolTargets';
import { hasRichCard } from './richcards/RichCardWrapper';
import ContextPanel from './ContextPanel';

/* ── Constants ─────────────────────────────────────── */
const CORE_W = 200, CORE_H = 145;
const TOOL_W = 160, TOOL_H = 104;
const PORT_RADIUS = 6;
const ZOOM_MIN = 0.3, ZOOM_MAX = 2, ZOOM_STEP = 0.1;
const CANVAS_PADDING = 60;
const PORT_GAP = 20;
const LS_POSITIONS_KEY = 'flow-canvas-positions';
const LS_VIEWPORT_KEY = 'flow-canvas-viewport';

/* ── Helpers ───────────────────────────────────────── */
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const getToolWidth = (slug) => hasRichCard(slug) ? 220 : TOOL_W;

const calcPath = (x1, y1, x2, y2) => {
  const dx = Math.abs(x2 - x1) * 0.55;
  return `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
};

const buildInitialPositions = (canvasW, canvasH, groups) => {
  const pos = {};
  const cx = canvasW / 2;
  const cy = canvasH / 2;

  pos['__assistant'] = { x: canvasW * 0.30 - CORE_W / 2, y: cy - CORE_H / 2 };
  pos['__manager']   = { x: canvasW * 0.55 - CORE_W / 2, y: cy - CORE_H / 2 };
  pos['__leads']     = { x: canvasW * 0.80 - CORE_W / 2, y: cy - CORE_H / 2 };

  const layoutColumn = (list, baseX) => {
    const total = list.length;
    const spacing = total > 1 ? Math.min(100, (canvasH - CANVAS_PADDING * 2) / (total - 1)) : 0;
    const yStart = total > 1 ? cy - (spacing * (total - 1)) / 2 : cy - TOOL_H / 2;
    list.forEach((tool, i) => {
      pos[tool.slug] = { x: baseX, y: yStart + i * spacing };
    });
  };

  layoutColumn(groups.left, CANVAS_PADDING);
  const rightMaxW = groups.right.length ? Math.max(...groups.right.map(t => getToolWidth(t.slug))) : TOOL_W;
  layoutColumn(groups.right, canvasW - CANVAS_PADDING - rightMaxW);

  const bothTotal = groups.both.length;
  groups.both.forEach((tool, i) => {
    const tw = getToolWidth(tool.slug);
    const offset = (i - (bothTotal - 1) / 2) * (tw + 20);
    pos[tool.slug] = { x: cx + offset - tw / 2, y: CANVAS_PADDING };
  });

  return pos;
};

/* ── Component ─────────────────────────────────────── */
const FlowCanvas = ({ tools, onToolClick, highlightedTool, onToolDrop, onDisconnect, onConnect, onMiddlewareRemove, onMiddlewareAttach, onRefresh }) => {
  const containerRef = useRef(null);
  const innerRef = useRef(null);

  /* ── Connected tools & groups ──────────── */
  const connectedTools = useMemo(
    () => tools.filter(t => {
      if (t.connections) {
        return t.connections.some(c => c.status === 'connected' && c.enabled);
      }
      return t.connection?.status === 'connected' && t.connection?.enabled;
    }),
    [tools]
  );

  /* ── Effective targets: use connection.target from API, fallback to static map ── */
  const getEffectiveTargets = useCallback((tool) => {
    if (tool.connections?.length) {
      const targets = tool.connections
        .filter(c => c.status === 'connected' && c.enabled)
        .map(c => c.target);
      return targets.length ? targets : getToolTargets(tool.slug);
    }
    const connTarget = tool.connection?.target;
    if (connTarget) return [connTarget];
    return getToolTargets(tool.slug);
  }, []);

  const groups = useMemo(() => {
    const left = [], right = [], both = [], leadsTools = [];
    connectedTools.forEach(tool => {
      const targets = getEffectiveTargets(tool);
      if (targets.includes('leads')) leadsTools.push(tool);
      if (targets.includes('assistant') && targets.includes('manager')) both.push(tool);
      else if (targets.includes('manager')) right.push(tool);
      else left.push(tool);
    });
    return { left, right, both, leads: leadsTools };
  }, [connectedTools, getEffectiveTargets]);

  /* ── Canvas dimensions ─────────────────── */
  const maxGroupSize = Math.max(groups.left.length, groups.right.length, 1);
  const canvasH = Math.max(500, maxGroupSize * 100 + 200);
  const canvasW = 1200;

  /* ── Node positions (persisted to localStorage) ── */
  const [positions, setPositions] = useState(() => {
    const fresh = buildInitialPositions(canvasW, canvasH, groups);
    try {
      const saved = JSON.parse(localStorage.getItem(LS_POSITIONS_KEY));
      if (saved && typeof saved === 'object') {
        const merged = { ...fresh };
        for (const key in saved) {
          if (key in merged) merged[key] = saved[key];
        }
        return merged;
      }
    } catch { /* ignore */ }
    return fresh;
  });

  useEffect(() => {
    setPositions(prev => {
      const fresh = buildInitialPositions(canvasW, canvasH, groups);
      const merged = { ...fresh };
      for (const key in prev) {
        if (key in merged) merged[key] = prev[key];
      }
      return merged;
    });
  }, [connectedTools.length, canvasW, canvasH, groups]);

  /* ── Viewport (pan & zoom, persisted) ──── */
  const [viewport, setViewport] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(LS_VIEWPORT_KEY));
      if (saved && typeof saved.zoom === 'number') return saved;
    } catch { /* ignore */ }
    return { x: 0, y: 0, zoom: 1 };
  });

  /* ── Drag state ────────────────────────── */
  const dragRef = useRef(null);
  const panRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const clickGuardRef = useRef(false);

  /* ── Edge interaction state ─────────────── */
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [edgeDrag, setEdgeDrag] = useState(null); // { sourceNode, sourcePort, mouseX, mouseY }
  const [ghostEdge, setGhostEdge] = useState(null);

  /* ── Context menu state ─────────────────── */
  const [contextMenu, setContextMenu] = useState(null); // { x, y, edgeId }

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

  /* ── Get port position in canvas coords ── */
  const getPortPosition = useCallback((nodeId, portIndex) => {
    const pos = positions[nodeId];
    if (!pos) return null;

    if (nodeId.startsWith('__')) {
      // Core node — left side ports
      const variant = nodeId.slice(2);
      const toolsForNode = connectedTools.filter(t => getEffectiveTargets(t).includes(variant));
      const portCount = Math.max(toolsForNode.length, 1);
      return {
        x: pos.x,
        y: getPortY(pos, portIndex, portCount),
      };
    } else {
      // Tool node — right side port
      return {
        x: pos.x + getToolWidth(nodeId),
        y: pos.y + TOOL_H / 2,
      };
    }
  }, [positions, connectedTools]);

  /* ── Compute connections from positions ── */
  const connections = useMemo(() => {
    const aPos = positions['__assistant'];
    const mPos = positions['__manager'];
    const lPos = positions['__leads'];
    if (!aPos || !mPos) return [];

    const conns = [];

    // Escalation: Assistant → Manager
    const aRightX = aPos.x + CORE_W, aRightY = aPos.y + CORE_H / 2;
    const mLeftX  = mPos.x,          mLeftY  = mPos.y + CORE_H / 2;
    conns.push({
      id: 'escalation',
      pathD: calcPath(aRightX, aRightY, mLeftX, mLeftY),
      target: 'escalation',
      toolSlug: '__escalation',
      source: '__assistant',
      targetNode: '__manager',
    });

    const assistantTools = connectedTools.filter(t => getEffectiveTargets(t).includes('assistant'));
    const managerTools = connectedTools.filter(t => getEffectiveTargets(t).includes('manager'));
    const leadsTools = connectedTools.filter(t => getEffectiveTargets(t).includes('leads'));

    assistantTools.forEach((tool, portIdx) => {
      const tPos = positions[tool.slug];
      if (!tPos) return;
      const srcX = tPos.x + getToolWidth(tool.slug), srcY = tPos.y + TOOL_H / 2;
      const tgtX = aPos.x;
      const tgtY = getPortY(aPos, portIdx, assistantTools.length);
      conns.push({
        id: `${tool.slug}-assistant`,
        pathD: calcPath(srcX, srcY, tgtX, tgtY),
        target: 'assistant',
        toolSlug: tool.slug,
        source: tool.slug,
        targetNode: '__assistant',
        sourcePort: 0,
        targetPort: portIdx,
      });
    });

    managerTools.forEach((tool, portIdx) => {
      const tPos = positions[tool.slug];
      if (!tPos) return;
      const srcX = tPos.x + getToolWidth(tool.slug), srcY = tPos.y + TOOL_H / 2;
      const tgtX = mPos.x;
      const tgtY = getPortY(mPos, portIdx, managerTools.length);
      conns.push({
        id: `${tool.slug}-manager`,
        pathD: calcPath(srcX, srcY, tgtX, tgtY),
        target: 'manager',
        toolSlug: tool.slug,
        source: tool.slug,
        targetNode: '__manager',
        sourcePort: 0,
        targetPort: portIdx,
      });
    });

    if (lPos) {
      leadsTools.forEach((tool, portIdx) => {
        const tPos = positions[tool.slug];
        if (!tPos) return;
        const srcX = tPos.x + getToolWidth(tool.slug), srcY = tPos.y + TOOL_H / 2;
        const tgtX = lPos.x;
        const tgtY = getPortY(lPos, portIdx, leadsTools.length);
        conns.push({
          id: `${tool.slug}-leads`,
          pathD: calcPath(srcX, srcY, tgtX, tgtY),
          target: 'leads',
          toolSlug: tool.slug,
          source: tool.slug,
          targetNode: '__leads',
          sourcePort: 0,
          targetPort: portIdx,
        });
      });
    }

    return conns;
  }, [positions, connectedTools]);

  /* -- Middleware on edges -- */
  const middlewareByEdge = useMemo(() => {
    const map = {};
    connectedTools.forEach(tool => {
      if (tool.connections?.length) {
        // Multi-connection: each connection has its own middlewares
        tool.connections
          .filter(c => c.status === 'connected' && c.enabled && c.middlewares?.length)
          .forEach(c => {
            const edgeId = `${tool.slug}-${c.target}`;
            map[edgeId] = c.middlewares;
          });
      } else {
        // Legacy single connection
        const mws = tool.connection?.middlewares;
        if (!mws?.length) return;
        const targets = getEffectiveTargets(tool);
        targets.forEach(target => {
          const edgeId = `${tool.slug}-${target}`;
          map[edgeId] = mws;
        });
      }
    });
    return map;
  }, [connectedTools]);

  /* ── Valid drop ports for edge dragging ── */
  const validDropPorts = useMemo(() => {
    if (!edgeDrag) return null;
    const ports = [];
    // Tool ports (right side) can connect to core node ports (left side) and vice versa
    const sourceIsCore = edgeDrag.sourceNode.startsWith('__');
    if (sourceIsCore) {
      // Dragging from core → valid targets are tool ports
      connectedTools.forEach(tool => {
        ports.push(`${tool.slug}:0`);
      });
    } else {
      // Dragging from tool → valid targets are core ports
      ['__assistant', '__manager', '__leads'].forEach(coreId => {
        const variant = coreId.slice(2);
        const toolsForNode = connectedTools.filter(t => getEffectiveTargets(t).includes(variant));
        const portCount = Math.max(toolsForNode.length, 1);
        for (let i = 0; i < portCount; i++) {
          ports.push(`${coreId}:${i}`);
        }
      });
    }
    return ports;
  }, [edgeDrag, connectedTools]);

  /* ── Port event handlers ────────────────── */
  const handlePortPointerDown = useCallback((nodeId, portIndex, e) => {
    e.preventDefault();
    const canvasPos = screenToCanvas(e.clientX, e.clientY);
    setEdgeDrag({
      sourceNode: nodeId,
      sourcePort: portIndex,
      mouseX: canvasPos.x,
      mouseY: canvasPos.y,
    });
    setSelectedEdge(null);
    setContextMenu(null);
  }, [screenToCanvas]);

  const handlePortPointerUp = useCallback((nodeId, portIndex) => {
    if (!edgeDrag) return;

    const { sourceNode } = edgeDrag;
    setEdgeDrag(null);
    setGhostEdge(null);

    // Determine tool slug and target core node
    const sourceIsCore = sourceNode.startsWith('__');
    const targetIsCore = nodeId.startsWith('__');

    // Only allow tool-to-core or core-to-tool connections
    if (sourceIsCore === targetIsCore) return;

    const toolSlug = sourceIsCore ? nodeId : sourceNode;
    const coreNodeId = sourceIsCore ? sourceNode : nodeId;

    // Don't create edges for core-only nodes
    if (toolSlug.startsWith('__')) return;

    const target = coreNodeId.slice(2); // '__assistant' -> 'assistant'
    onConnect?.(toolSlug, target);
  }, [edgeDrag, onConnect]);

  /* ── Ghost edge during port drag ──────── */
  useEffect(() => {
    if (!edgeDrag) return;

    const handleMove = (e) => {
      const canvasPos = screenToCanvas(e.clientX, e.clientY);
      setEdgeDrag(prev => prev ? { ...prev, mouseX: canvasPos.x, mouseY: canvasPos.y } : null);

      // Calculate ghost edge path
      const portPos = getPortPosition(edgeDrag.sourceNode, edgeDrag.sourcePort);
      if (!portPos) return;

      const sourceIsCore = edgeDrag.sourceNode.startsWith('__');
      if (sourceIsCore) {
        // Core port is on left side, ghost goes right-to-left (reversed)
        setGhostEdge({ pathD: calcPath(canvasPos.x, canvasPos.y, portPos.x, portPos.y) });
      } else {
        // Tool port is on right side
        setGhostEdge({ pathD: calcPath(portPos.x, portPos.y, canvasPos.x, canvasPos.y) });
      }
    };

    const handleUp = () => {
      setEdgeDrag(null);
      setGhostEdge(null);
    };

    document.addEventListener('pointermove', handleMove);
    document.addEventListener('pointerup', handleUp);
    return () => {
      document.removeEventListener('pointermove', handleMove);
      document.removeEventListener('pointerup', handleUp);
    };
  }, [edgeDrag?.sourceNode, edgeDrag?.sourcePort, screenToCanvas, getPortPosition]);

  /* ── Edge click & context menu ──────────── */
  const handleEdgeClick = useCallback((edgeId, e) => {
    e.stopPropagation();
    setSelectedEdge(prev => prev === edgeId ? null : edgeId);
    setContextMenu(null);
  }, []);

  const handleEdgePointerDown = useCallback((edgeId, e) => {
    // Right click → context menu
    if (e.button === 2) {
      e.preventDefault();
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      setContextMenu({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        edgeId,
      });
      setSelectedEdge(edgeId);
    }
  }, []);

  const handleDeleteEdge = useCallback((edgeId) => {
    const conn = connections.find(c => c.id === edgeId);
    if (!conn || conn.target === 'escalation' || !conn.toolSlug) return;

    if (window.confirm('Detach this edge?')) {
      onDisconnect?.(conn.toolSlug, conn.target);
    }
    setSelectedEdge(null);
    setContextMenu(null);
  }, [connections, onDisconnect]);

  /* ── Node drag handlers ────────────────── */
  const handleNodePointerDown = useCallback((nodeId, e) => {
    if (e.button !== 0) return;
    e.stopPropagation();

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
    setSelectedEdge(null);
    setContextMenu(null);
  }, [positions, screenToCanvas]);

  /* Node drag move/up — on document so pointer never "escapes" the node */
  useEffect(() => {
    if (!isDragging || !dragRef.current) return;

    const handleMove = (e) => {
      if (!dragRef.current) return;
      e.preventDefault();
      clickGuardRef.current = true;

      const canvas = screenToCanvas(e.clientX, e.clientY);
      const { nodeId, offsetX, offsetY } = dragRef.current;
      setPositions(prev => ({
        ...prev,
        [nodeId]: { x: canvas.x - offsetX, y: canvas.y - offsetY },
      }));
    };

    const handleUp = () => {
      const dragInfo = dragRef.current;
      dragRef.current = null;
      setIsDragging(false);

      // Persist positions after drag
      if (clickGuardRef.current) {
        setPositions(cur => {
          try { localStorage.setItem(LS_POSITIONS_KEY, JSON.stringify(cur)); } catch { /* ignore */ }
          return cur;
        });
      }

      // If no movement happened, treat as click → open popover
      if (!clickGuardRef.current && dragInfo && !dragInfo.nodeId.startsWith('__')) {
        const tool = connectedTools.find(t => t.slug === dragInfo.nodeId);
        if (tool) {
          const el = document.getElementById(`canvas-tool-${dragInfo.nodeId}`);
          if (el) onToolClick?.(tool, { currentTarget: el });
        }
      }
    };

    document.addEventListener('pointermove', handleMove);
    document.addEventListener('pointerup', handleUp);
    return () => {
      document.removeEventListener('pointermove', handleMove);
      document.removeEventListener('pointerup', handleUp);
    };
  }, [isDragging, screenToCanvas, connectedTools, onToolClick]);

  /* ── Canvas pan handlers ───────────────── */
  const handleCanvasPointerDown = useCallback((e) => {
    if (e.button !== 0) return;
    if (e.target !== innerRef.current && e.target !== containerRef.current) return;

    // Click on empty space → deselect edge
    setSelectedEdge(null);
    setContextMenu(null);

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

    const allIds = Object.keys(positions);
    if (allIds.length === 0) return;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    allIds.forEach(id => {
      const p = positions[id];
      const w = id.startsWith('__') ? CORE_W : getToolWidth(id);
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

  /* ── Persist viewport to localStorage (debounced) ── */
  useEffect(() => {
    const timer = setTimeout(() => {
      try { localStorage.setItem(LS_VIEWPORT_KEY, JSON.stringify(viewport)); } catch { /* ignore */ }
    }, 300);
    return () => clearTimeout(timer);
  }, [viewport]);

  const hasRestoredRef = useRef(false);
  useEffect(() => {
    // Skip auto-fit if we restored saved viewport
    if (!hasRestoredRef.current) {
      hasRestoredRef.current = true;
      const hasSaved = localStorage.getItem(LS_VIEWPORT_KEY);
      if (hasSaved) return;
    }
    const timer = setTimeout(fitToView, 200);
    return () => clearTimeout(timer);
  }, [connectedTools.length]);

  /* ── Periodic refresh for canvas updates from Jeevs's bridge tools ── */
  useEffect(() => {
    if (!onRefresh) return;
    const interval = setInterval(onRefresh, 10000); // poll every 10s
    return () => clearInterval(interval);
  }, [onRefresh]);

  /* ── Drop zone for tool cards from strip ── */
  const [dragOver, setDragOver] = useState(false);
  const [dragOverEdgeId, setDragOverEdgeId] = useState(null);
  const [isSkillDrag, setIsSkillDrag] = useState(false);
  const [skillDropPreview, setSkillDropPreview] = useState(null); // { x, y, edgeId }

  /** Pre-sampled points for each edge (computed once per connections change) */
  const edgeSamples = useMemo(() => {
    const SAMPLES = 16;
    return connections
      .filter(c => c.target !== 'escalation')
      .map(conn => {
        const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        pathEl.setAttribute('d', conn.pathD);
        const totalLen = pathEl.getTotalLength();
        const points = [];
        for (let i = 0; i <= SAMPLES; i++) {
          const pt = pathEl.getPointAtLength((i / SAMPLES) * totalLen);
          points.push({ x: pt.x, y: pt.y });
        }
        return { id: conn.id, points };
      });
  }, [connections]);

  /** Find nearest edge to a point on canvas, returns { id, point, dist } */
  const findNearestEdge = useCallback((canvasX, canvasY, threshold = 40) => {
    let nearest = null;
    let minDist = threshold;
    let nearestPoint = null;

    for (const edge of edgeSamples) {
      for (const pt of edge.points) {
        const dist = Math.hypot(pt.x - canvasX, pt.y - canvasY);
        if (dist < minDist) {
          minDist = dist;
          nearest = edge.id;
          nearestPoint = pt;
        }
      }
    }
    return nearest ? { id: nearest, point: nearestPoint, dist: minDist } : null;
  }, [edgeSamples]);

  /** Throttled drag-over handler */
  const dragOverThrottleRef = useRef(0);

  const handleDragOver = useCallback((e) => {
    if (!e.dataTransfer.types.includes('tool-slug')) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    setDragOver(true);

    // Throttle edge detection to ~30fps
    const now = Date.now();
    if (now - dragOverThrottleRef.current < 33) return;
    dragOverThrottleRef.current = now;

    const skillDrag = e.dataTransfer.types.includes('is-skill');
    setIsSkillDrag(skillDrag);

    const canvasPos = screenToCanvas(e.clientX, e.clientY);
    const skillThreshold = skillDrag ? 80 : 20;
    const nearEdge = findNearestEdge(canvasPos.x, canvasPos.y, skillThreshold);

    if (nearEdge) {
      setDragOverEdgeId(nearEdge.id);
      if (skillDrag) {
        setSkillDropPreview({ x: nearEdge.point.x, y: nearEdge.point.y, edgeId: nearEdge.id });
      }
    } else {
      setDragOverEdgeId(null);
      setSkillDropPreview(null);
    }
  }, [screenToCanvas, findNearestEdge]);

  const handleDragLeave = useCallback(() => {
    setDragOver(false);
    setDragOverEdgeId(null);
    setIsSkillDrag(false);
    setSkillDropPreview(null);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    setSkillDropPreview(null);
    setIsSkillDrag(false);

    const slug = e.dataTransfer.getData('tool-slug');
    const group = e.dataTransfer.getData('tool-group');
    if (!slug) return;

    // Skills — ONLY drop onto edges
    if (group === 'skills') {
      if (dragOverEdgeId) {
        const conn = connections.find(c => c.id === dragOverEdgeId);
        console.log('[SkillDrop]', { slug, dragOverEdgeId, conn: conn ? { id: conn.id, toolSlug: conn.toolSlug, target: conn.target } : null });
        if (conn && conn.toolSlug) {
          onMiddlewareAttach?.(conn, slug);
        }
      }
      setDragOverEdgeId(null);
      return;
    }

    // Tools/servers — existing behavior
    if (dragOverEdgeId) {
      const conn = connections.find(c => c.id === dragOverEdgeId);
      if (conn && conn.toolSlug) {
        onMiddlewareAttach?.(conn, slug);
      }
      setDragOverEdgeId(null);
      return;
    }

    setDragOverEdgeId(null);
    onToolDrop?.(slug);
  }, [onToolDrop, dragOverEdgeId, connections, onMiddlewareAttach]);

  /* ── Prevent default context menu on canvas ── */
  const handleContextMenu = useCallback((e) => {
    e.preventDefault();
  }, []);

  /* ── Tool click guard ───────────────────── */
  const handleToolClick = useCallback((tool, e) => {
    if (clickGuardRef.current) {
      clickGuardRef.current = false;
      return;
    }
    onToolClick?.(tool, e);
  }, [onToolClick]);

  /* ── Keyboard: Delete selected edge ──────── */
  useEffect(() => {
    if (!selectedEdge) return;
    const handleKey = (e) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        handleDeleteEdge(selectedEdge);
      } else if (e.key === 'Escape') {
        setSelectedEdge(null);
        setContextMenu(null);
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [selectedEdge, handleDeleteEdge]);

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
      className={`flow-canvas relative w-full bg-linen border-[1.5px] border-rule rounded-lg overflow-hidden
        ${isPanning ? 'panning' : ''}
        ${dragOver && !isSkillDrag ? 'ring-2 ring-iris ring-inset bg-mist' : ''}
        ${isSkillDrag && dragOverEdgeId ? 'ring-2 ring-iris ring-inset' : ''}
        ${isSkillDrag && !dragOverEdgeId ? 'ring-2 ring-rule ring-inset opacity-90' : ''}`}
      style={{ minHeight: `max(60vh, 500px)`, cursor: isPanning ? 'grabbing' : edgeDrag ? 'crosshair' : 'default' }}
      onPointerDown={handleCanvasPointerDown}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onContextMenu={handleContextMenu}
    >
      <ContextPanel tools={tools} />

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
          selectedEdge={selectedEdge}
          onEdgeClick={handleEdgeClick}
          onEdgePointerDown={handleEdgePointerDown}
          ghostEdge={ghostEdge}
          dragOverEdgeId={dragOverEdgeId}
          isSkillDrag={isSkillDrag}
        />

        {/* Core nodes */}
        {['assistant', 'manager', 'leads'].map(variant => {
          const nodeId = `__${variant}`;
          const pos = positions[nodeId];
          if (!pos) return null;
          const count = variant === 'assistant' ? groups.left.length + groups.both.length
            : variant === 'manager' ? groups.right.length + groups.both.length
            : groups.leads.length;

          return (
            <div
              key={nodeId}
              className={`flow-draggable absolute ${isDragging && dragRef.current?.nodeId === nodeId ? 'dragging' : ''}`}
              style={{ left: pos.x, top: pos.y }}
              onPointerDown={(e) => handleNodePointerDown(nodeId, e)}
            >
              <CoreNode
                variant={variant}
                connectedCount={count}
                onPortPointerDown={handlePortPointerDown}
                onPortPointerUp={handlePortPointerUp}
                edgeDragging={!!edgeDrag}
                validDropPorts={validDropPorts}
              />
            </div>
          );
        })}

        {/* Escalation label */}
        {escLabel && (
          <div
            className="absolute font-mono text-[10px] text-fog tracking-wider uppercase pointer-events-none"
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
            >
              <CanvasToolNode
                tool={tool}
                onClick={handleToolClick}
                isHighlighted={highlightedTool === null ? null : highlightedTool === tool.slug}
                onPortPointerDown={handlePortPointerDown}
                onPortPointerUp={handlePortPointerUp}
                edgeDragging={!!edgeDrag}
                validDropPorts={validDropPorts}
              />
            </div>
          );
        })}

        {/* Middleware badges on edges */}
        {connections.map(conn => {
          const mws = middlewareByEdge[conn.id];
          if (!mws?.length || conn.target === 'escalation') return null;
          return mws.map((mw, i) => {
            const count = mws.length;
            const position = count === 1 ? 0.5 : (i + 1) / (count + 1);
            return (
              <EdgeSkillBadge
                key={`${conn.id}-${mw.id}`}
                middleware={mw}
                pathD={conn.pathD}
                position={position}
                onRemove={(mwId) => onMiddlewareRemove?.(conn, mwId)}
              />
            );
          });
        })}

        {/* Ghost skill drop preview circle */}
        {skillDropPreview && (
          <div
            className="absolute pointer-events-none"
            style={{
              left: skillDropPreview.x,
              top: skillDropPreview.y,
              transform: 'translate(-50%, -50%)',
              zIndex: 10,
            }}
          >
            <div className="w-9 h-9 rounded-full border-2 border-dashed border-iris bg-iris-soft/40
              flex items-center justify-center animate-pulse shadow-[0_0_16px_rgba(155,126,216,0.35)]">
              <div className="w-2 h-2 rounded-full bg-iris" />
            </div>
          </div>
        )}
      </div>

      {/* ── Edge context menu ── */}
      {contextMenu && (
        <div
          className="absolute z-30 bg-paper border-[1.5px] border-rule rounded-lg shadow-ink py-1 min-w-[160px]"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          {contextMenu.edgeId !== 'escalation' && (
            <button
              onClick={() => handleDeleteEdge(contextMenu.edgeId)}
              className="flex items-center gap-2 w-full px-3 py-2 text-[13px] text-rose
                         hover:bg-rose-soft/40 transition-colors cursor-pointer bg-transparent"
            >
              <Trash2 size={14} weight="light" />
              Remove connection
            </button>
          )}
          <button
            onClick={() => { setSelectedEdge(null); setContextMenu(null); }}
            className="flex items-center gap-2 w-full px-3 py-2 text-[13px] text-slate
                       hover:bg-mist hover:text-ink transition-colors cursor-pointer bg-transparent"
          >
            Cancel
          </button>
        </div>
      )}

      {/* ── Delete button for selected edge ── */}
      {selectedEdge && selectedEdge !== 'escalation' && !contextMenu && (() => {
        const conn = connections.find(c => c.id === selectedEdge);
        if (!conn) return null;
        // Find midpoint of bezier for button placement
        const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        pathEl.setAttribute('d', conn.pathD);
        const mid = pathEl.getPointAtLength(pathEl.getTotalLength() / 2);
        const btnX = mid.x * viewport.zoom + viewport.x;
        const btnY = mid.y * viewport.zoom + viewport.y;
        return (
          <button
            className="absolute z-20 w-7 h-7 rounded-full border-[1.5px] border-rose bg-paper
                       hover:bg-rose-soft text-rose flex items-center justify-center
                       shadow-ink-sm transition-all cursor-pointer"
            style={{ left: btnX, top: btnY, transform: 'translate(-50%, -50%)' }}
            onClick={() => handleDeleteEdge(selectedEdge)}
            title="Delete connection"
          >
            <Trash2 size={13} weight="light" />
          </button>
        );
      })()}

      {/* ── Zoom controls (fixed in corner) ── */}
      <div className="flow-zoom-controls absolute bottom-4 right-4 flex items-center gap-1
                      bg-paper/95 border-[1.5px] border-rule rounded-lg p-1 shadow-ink-sm z-20">
        <button
          onClick={zoomOut}
          disabled={viewport.zoom <= ZOOM_MIN}
          className="p-1.5 rounded-sm text-slate hover:bg-mist hover:text-ink disabled:opacity-30 transition-colors bg-transparent"
          aria-label="Zoom out"
        >
          <ZoomOut size={16} weight="light" />
        </button>
        <span className="font-mono text-[11px] text-slate min-w-[4ch] text-center tabular-nums">
          {zoomPercent}%
        </span>
        <button
          onClick={zoomIn}
          disabled={viewport.zoom >= ZOOM_MAX}
          className="p-1.5 rounded-sm text-slate hover:bg-mist hover:text-ink disabled:opacity-30 transition-colors bg-transparent"
          aria-label="Zoom in"
        >
          <ZoomIn size={16} weight="light" />
        </button>
        <div className="w-px h-4 bg-rule mx-0.5" />
        <button
          onClick={fitToView}
          className="p-1.5 rounded-sm text-slate hover:bg-mist hover:text-ink transition-colors bg-transparent"
          aria-label="Fit to view"
          title="Fit to view"
        >
          <Maximize2 size={16} weight="light" />
        </button>
        <button
          onClick={resetView}
          className="p-1.5 rounded-sm text-slate hover:bg-mist hover:text-ink transition-colors bg-transparent"
          aria-label="Reset view"
          title="Reset zoom & position"
        >
          <RotateCcw size={16} weight="light" />
        </button>
      </div>

      {/* ── Keyboard hint ── */}
      {connectedTools.length > 0 && (
        <div className="absolute bottom-4 left-4 font-mono text-[10px] text-fog tracking-wide uppercase pointer-events-none select-none z-20">
          scroll · drag bg to pan · drag node to move · click edge · del to remove
        </div>
      )}
    </section>
  );
};

export default FlowCanvas;
