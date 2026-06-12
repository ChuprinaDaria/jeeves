import { useRef, useState, useEffect, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  MagnifyingGlassPlus as ZoomIn,
  MagnifyingGlassMinus as ZoomOut,
  ArrowsOut as Maximize2,
  ArrowCounterClockwise as RotateCcw,
  Trash as Trash2,
  Pulse,
  Fire,
} from '@phosphor-icons/react';
import { toolsAPI } from '../../api/tools';
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
const ZOOM_MIN = 0.3, ZOOM_MAX = 2, ZOOM_STEP = 0.1;
const CANVAS_PADDING = 60;
const PORT_GAP = 20;
const LS_POSITIONS_KEY = 'flow-canvas-positions';
const LS_VIEWPORT_KEY = 'flow-canvas-viewport';

/* ── Helpers ───────────────────────────────────────── */
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const getToolWidth = (slug) => hasRichCard(slug) ? 220 : TOOL_W;

/* dir = +1 when the edge leaves/enters through a node's RIGHT side, -1 for LEFT */
const calcPath = (x1, y1, x2, y2, dir1 = 1, dir2 = -1) => {
  const dx = Math.max(40, Math.abs(x2 - x1) * 0.55);
  return `M${x1},${y1} C${x1 + dir1 * dx},${y1} ${x2 + dir2 * dx},${y2} ${x2},${y2}`;
};

/* Vertical distance between core-node ports, clamped so the column never
   overflows the node */
const portPitch = (count, nodeH) =>
  count > 1 ? Math.min(PORT_GAP, (nodeH - 36) / (count - 1)) : 0;

/* Vertical pitch between stacked tool nodes — real node heights run up to
   ~150px (tagline + chips + status), so anything tighter overlaps */
const NODE_V = 160;

const buildInitialPositions = (canvasW, canvasH, groups) => {
  const pos = {};
  const cx = canvasW / 2;
  const hasLeadsLane = groups.leadsOnly.length > 0;
  // Main lane (assistant ↔ manager) sits higher when the leads funnel
  // occupies its own lane at the bottom
  const laneCy = hasLeadsLane ? canvasH * 0.38 : canvasH / 2;
  const leadsCy = hasLeadsLane ? canvasH * 0.80 : canvasH / 2;

  pos['__assistant'] = { x: canvasW * 0.34 - CORE_W / 2, y: laneCy - CORE_H / 2 };
  pos['__manager']   = { x: canvasW * 0.62 - CORE_W / 2, y: laneCy - CORE_H / 2 };
  pos['__leads']     = hasLeadsLane
    ? { x: canvasW * 0.55 - CORE_W / 2, y: leadsCy - CORE_H / 2 }
    : { x: canvasW * 0.88 - CORE_W / 2, y: laneCy - CORE_H / 2 };

  const layoutColumn = (list, baseX, centerY) => {
    const total = list.length;
    const spacing = total > 1 ? Math.min(NODE_V, (canvasH - CANVAS_PADDING * 2) / (total - 1)) : 0;
    const yStart = total > 1 ? centerY - (spacing * (total - 1)) / 2 : centerY - TOOL_H / 2;
    list.forEach((tool, i) => {
      pos[tool.slug] = { x: baseX, y: yStart + i * spacing };
    });
  };

  layoutColumn(groups.left, CANVAS_PADDING, laneCy);
  const rightMaxW = groups.right.length ? Math.max(...groups.right.map(t => getToolWidth(t.slug))) : TOOL_W;
  layoutColumn(groups.right, canvasW - CANVAS_PADDING - rightMaxW, laneCy);
  // Pure-leads tools live in the bottom lane, left of the Leads node
  layoutColumn(groups.leadsOnly, CANVAS_PADDING + 40, leadsCy);

  const bothTotal = groups.both.length;
  groups.both.forEach((tool, i) => {
    const tw = getToolWidth(tool.slug);
    const offset = (i - (bothTotal - 1) / 2) * (tw + 20);
    pos[tool.slug] = { x: cx + offset - tw / 2, y: CANVAS_PADDING };
  });

  return pos;
};

/* ── Component ─────────────────────────────────────── */
const FlowCanvas = ({ tools, channels, skillsByTarget, onToolClick, highlightedTool, onToolDrop, onDisconnect, onConnect, onMiddlewareRemove, onMiddlewareAttach, onRefresh, onPositionSave }) => {
  const { t } = useTranslation();
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
    const left = [], right = [], both = [], leadsTools = [], leadsOnly = [];
    connectedTools.forEach(tool => {
      const targets = getEffectiveTargets(tool);
      if (targets.includes('leads')) leadsTools.push(tool);
      const onlyLeads = targets.length > 0 && targets.every(t => t === 'leads');
      if (onlyLeads) { leadsOnly.push(tool); return; }
      if (targets.includes('assistant') && targets.includes('manager')) both.push(tool);
      else if (targets.includes('manager')) right.push(tool);
      else left.push(tool);
    });
    return { left, right, both, leads: leadsTools, leadsOnly };
  }, [connectedTools, getEffectiveTargets]);

  /* ── Canvas dimensions ─────────────────── */
  const maxGroupSize = Math.max(groups.left.length, groups.right.length, 1);
  const canvasH = Math.max(640, maxGroupSize * NODE_V + 260)
    + (groups.leadsOnly.length > 0 ? 280 : 0);
  const canvasW = 1200;

  /* ── Node positions: layout < backend (ToolConnection.position_x/y) < localStorage ── */
  const backendPositions = useMemo(() => {
    const map = {};
    connectedTools.forEach(tool => {
      const conns = tool.connections?.length ? tool.connections : (tool.connection ? [tool.connection] : []);
      const withPos = conns.find(c => c.position_x != null && c.position_y != null);
      if (withPos) map[tool.slug] = { x: withPos.position_x, y: withPos.position_y };
    });
    return map;
  }, [connectedTools]);

  const [positions, setPositions] = useState(() => {
    const merged = { ...buildInitialPositions(canvasW, canvasH, groups), ...backendPositions };
    try {
      const saved = JSON.parse(localStorage.getItem(LS_POSITIONS_KEY));
      if (saved && typeof saved === 'object') {
        for (const key in saved) {
          if (key in merged) merged[key] = saved[key];
        }
      }
    } catch { /* ignore */ }
    return merged;
  });

  useEffect(() => {
    setPositions(prev => {
      const merged = { ...buildInitialPositions(canvasW, canvasH, groups), ...backendPositions };
      for (const key in prev) {
        if (key in merged) merged[key] = prev[key];
      }
      return merged;
    });
  }, [connectedTools.length, canvasW, canvasH, groups, backendPositions]);

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

  /* ── Measured node sizes (real DOM height/width) ───────────────
     Edge endpoints must use the rendered size, not the design constants:
     rich cards and long taglines make nodes taller than TOOL_H/CORE_H,
     which used to detach the port circles from the edges. */
  const [nodeSizes, setNodeSizes] = useState({});

  useEffect(() => {
    const el = innerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(entries => {
      setNodeSizes(prev => {
        let changed = false;
        const next = { ...prev };
        for (const entry of entries) {
          const id = entry.target.dataset.nodeId;
          if (!id) continue;
          const w = entry.target.offsetWidth;
          const h = entry.target.offsetHeight;
          if (!prev[id] || prev[id].w !== w || prev[id].h !== h) {
            next[id] = { w, h };
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    });
    el.querySelectorAll('.flow-draggable[data-node-id]').forEach(box => observer.observe(box));
    return () => observer.disconnect();
  }, [connectedTools]);

  const getNodeSize = useCallback((id) => (
    nodeSizes[id] || (id.startsWith('__')
      ? { w: CORE_W, h: CORE_H }
      : { w: getToolWidth(id), h: TOOL_H })
  ), [nodeSizes]);

  /* ── Port layout: each edge attaches to the side FACING the other node.
     Tools left of a core land on its left port column, tools to the right
     on its right column; within a column ports are sorted by the tool's Y
     so edges don't cross. ── */
  const portLayout = useMemo(() => {
    const layout = {};
    ['assistant', 'manager', 'leads'].forEach(variant => {
      const coreId = `__${variant}`;
      const corePos = positions[coreId];
      layout[coreId] = { left: [], right: [] };
      if (!corePos) return;
      const coreCx = corePos.x + getNodeSize(coreId).w / 2;
      connectedTools
        .filter(t => getEffectiveTargets(t).includes(variant))
        .forEach(tool => {
          const tPos = positions[tool.slug];
          if (!tPos) return;
          const toolCx = tPos.x + getNodeSize(tool.slug).w / 2;
          layout[coreId][toolCx <= coreCx ? 'left' : 'right'].push(tool.slug);
        });
      ['left', 'right'].forEach(side =>
        layout[coreId][side].sort((a, b) => (positions[a]?.y ?? 0) - (positions[b]?.y ?? 0)));
    });
    return layout;
  }, [positions, connectedTools, getEffectiveTargets, getNodeSize]);

  /* Core port position (canvas coords) for a given side + column index */
  const getCorePortPos = useCallback((coreId, side, index) => {
    const pos = positions[coreId];
    if (!pos) return null;
    const size = getNodeSize(coreId);
    const count = Math.max(portLayout[coreId]?.[side]?.length || 0, 1);
    const pitch = portPitch(count, size.h);
    const cy = pos.y + size.h / 2;
    return {
      x: side === 'left' ? pos.x : pos.x + size.w,
      y: cy + (index - (count - 1) / 2) * pitch,
    };
  }, [positions, portLayout, getNodeSize]);

  /* Sides on which each tool node currently has edges */
  const toolPortSides = useMemo(() => {
    const map = {};
    Object.values(portLayout).forEach(sides => {
      sides.left.forEach(slug => { (map[slug] = map[slug] || new Set()).add('right'); });
      sides.right.forEach(slug => { (map[slug] = map[slug] || new Set()).add('left'); });
    });
    return map;
  }, [portLayout]);

  /* ── Get port position in canvas coords (used for the ghost edge) ── */
  const getPortPosition = useCallback((nodeId, portIndex) => {
    const pos = positions[nodeId];
    if (!pos) return null;

    if (nodeId.startsWith('__')) {
      const [side, idx] = String(portIndex).split(':');
      return getCorePortPos(nodeId, side === 'right' ? 'right' : 'left', Number(idx) || 0);
    }
    const size = getNodeSize(nodeId);
    const side = portIndex === 'left' ? 'left' : 'right';
    return {
      x: side === 'left' ? pos.x : pos.x + size.w,
      y: pos.y + size.h / 2,
    };
  }, [positions, getCorePortPos, getNodeSize]);

  /* ── Customer channel pills — consultant outputs ─────────────── */
  const CHANNEL_W = 132, CHANNEL_H = 38, CHANNEL_V = 84;
  const channelNodes = useMemo(() => {
    const mPos = positions['__manager'];
    if (!mPos) return [];
    const active = (channels || []).filter(c => c.active);
    if (!active.length) return [];
    const mSize = getNodeSize('__manager');
    let rightmost = mPos.x + mSize.w;
    (portLayout['__manager']?.right || []).forEach(slug => {
      const tp = positions[slug];
      if (tp) rightmost = Math.max(rightmost, tp.x + getNodeSize(slug).w);
    });
    const x = rightmost + 90;
    const cy = mPos.y + mSize.h / 2;
    return active.map((ch, i) => ({
      ...ch,
      x,
      y: cy + (i - (active.length - 1) / 2) * CHANNEL_V - CHANNEL_H / 2,
    }));
  }, [channels, positions, portLayout, getNodeSize]);

  /* ── Compute connections from positions ── */
  const connections = useMemo(() => {
    const aPos = positions['__assistant'];
    const mPos = positions['__manager'];
    if (!aPos || !mPos) return [];

    const conns = [];

    // Escalation: Assistant → Manager, sides face each other
    const aSize = getNodeSize('__assistant');
    const mSize = getNodeSize('__manager');
    const aFirst = aPos.x + aSize.w / 2 <= mPos.x + mSize.w / 2;
    const escSrc = {
      x: aFirst ? aPos.x + aSize.w : aPos.x,
      y: aPos.y + aSize.h / 2,
    };
    const escTgt = {
      x: aFirst ? mPos.x : mPos.x + mSize.w,
      y: mPos.y + mSize.h / 2,
    };
    conns.push({
      id: 'escalation',
      pathD: calcPath(escSrc.x, escSrc.y, escTgt.x, escTgt.y, aFirst ? 1 : -1, aFirst ? -1 : 1),
      target: 'escalation',
      toolSlug: '__escalation',
      source: '__assistant',
      targetNode: '__manager',
    });

    ['assistant', 'manager', 'leads'].forEach(variant => {
      const coreId = `__${variant}`;
      if (!positions[coreId]) return;
      ['left', 'right'].forEach(side => {
        (portLayout[coreId]?.[side] || []).forEach((slug, portIdx) => {
          const tPos = positions[slug];
          const corePt = getCorePortPos(coreId, side, portIdx);
          if (!tPos || !corePt) return;
          const tSize = getNodeSize(slug);
          // The tool attaches on the side facing the core node
          const toolSide = side === 'left' ? 'right' : 'left';
          const srcX = toolSide === 'right' ? tPos.x + tSize.w : tPos.x;
          const srcY = tPos.y + tSize.h / 2;
          conns.push({
            id: `${slug}-${variant}`,
            pathD: calcPath(
              srcX, srcY, corePt.x, corePt.y,
              toolSide === 'right' ? 1 : -1,
              side === 'left' ? -1 : 1,
            ),
            target: variant,
            toolSlug: slug,
            source: slug,
            targetNode: coreId,
            sourcePort: toolSide,
            targetPort: `${side}:${portIdx}`,
          });
        });
      });
    });

    // Consultant → customer channels (read-only edges)
    const mSizeForCh = getNodeSize('__manager');
    channelNodes.forEach(ch => {
      conns.push({
        id: `channel-${ch.id}`,
        pathD: calcPath(
          mPos.x + mSizeForCh.w, mPos.y + mSizeForCh.h / 2,
          ch.x, ch.y + 19, 1, -1,
        ),
        target: 'channel',
        toolSlug: '',
        source: '__manager',
        targetNode: `channel-${ch.id}`,
      });
    });

    return conns;
  }, [positions, portLayout, getCorePortPos, getNodeSize, channelNodes]);

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
    const sourceIsCore = edgeDrag.sourceNode.startsWith('__');
    if (sourceIsCore) {
      // Dragging from core → valid targets are tool ports (either side)
      connectedTools.forEach(tool => {
        ports.push(`${tool.slug}:left`, `${tool.slug}:right`);
      });
    } else {
      // Dragging from tool → valid targets are core ports on both sides
      ['__assistant', '__manager', '__leads'].forEach(coreId => {
        ['left', 'right'].forEach(side => {
          const count = Math.max(portLayout[coreId]?.[side]?.length || 0, 1);
          for (let i = 0; i < count; i++) {
            ports.push(`${coreId}:${side}:${i}`);
          }
        });
      });
    }
    return ports;
  }, [edgeDrag, connectedTools, portLayout]);

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

  const handlePortPointerUp = useCallback((nodeId) => {
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

    if (window.confirm(t('tools.flow.detachConfirm'))) {
      onDisconnect?.(conn.toolSlug, conn.target);
    }
    setSelectedEdge(null);
    setContextMenu(null);
  }, [connections, onDisconnect, t]);

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

      // Persist positions after drag — localStorage + backend (durable)
      if (clickGuardRef.current) {
        setPositions(cur => {
          try { localStorage.setItem(LS_POSITIONS_KEY, JSON.stringify(cur)); } catch { /* ignore */ }
          if (dragInfo && !dragInfo.nodeId.startsWith('__')) {
            const pos = cur[dragInfo.nodeId];
            if (pos) onPositionSave?.(dragInfo.nodeId, pos);
          }
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
  }, [isDragging, screenToCanvas, connectedTools, onToolClick, onPositionSave]);

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

  /* ── Pinch zoom (touch) ────────────────── */
  const pointersRef = useRef(new Map());
  const pinchRef = useRef(null);

  const handlePointerDownCapture = useCallback((e) => {
    if (e.pointerType !== 'touch') return;
    pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointersRef.current.size === 2) {
      // Second finger: cancel node drag / pan, start pinch
      dragRef.current = null;
      panRef.current = null;
      setIsDragging(false);
      setIsPanning(false);
      const [p1, p2] = [...pointersRef.current.values()];
      pinchRef.current = {
        dist: Math.hypot(p2.x - p1.x, p2.y - p1.y),
        zoom: viewport.zoom,
        vpX: viewport.x,
        vpY: viewport.y,
      };
    }
  }, [viewport]);

  const handlePointerMoveCapture = useCallback((e) => {
    if (e.pointerType !== 'touch' || !pointersRef.current.has(e.pointerId)) return;
    pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (!pinchRef.current || pointersRef.current.size !== 2) return;
    e.preventDefault();

    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const [p1, p2] = [...pointersRef.current.values()];
    const dist = Math.hypot(p2.x - p1.x, p2.y - p1.y);
    if (!dist || !pinchRef.current.dist) return;

    const midX = (p1.x + p2.x) / 2 - rect.left;
    const midY = (p1.y + p2.y) / 2 - rect.top;
    const start = pinchRef.current;
    const newZoom = clamp(start.zoom * (dist / start.dist), ZOOM_MIN, ZOOM_MAX);
    const ratio = newZoom / start.zoom;
    setViewport({
      x: midX - (midX - start.vpX) * ratio,
      y: midY - (midY - start.vpY) * ratio,
      zoom: newZoom,
    });
  }, []);

  const handlePointerEndCapture = useCallback((e) => {
    if (e.pointerType !== 'touch') return;
    pointersRef.current.delete(e.pointerId);
    if (pointersRef.current.size < 2) pinchRef.current = null;
  }, []);

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
      const { w, h } = getNodeSize(id);
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
  }, [positions, getNodeSize]);

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

  /* ── Periodic refresh for canvas updates from Jeeves's bridge tools ── */
  useEffect(() => {
    if (!onRefresh) return;
    const interval = setInterval(onRefresh, 10000); // poll every 10s
    return () => clearInterval(interval);
  }, [onRefresh]);

  /* ── Two-agents legend (dismissible) ── */
  const [showLegend, setShowLegend] = useState(() => {
    try { return !localStorage.getItem('flow-legend-dismissed'); } catch { return true; }
  });
  const dismissLegend = () => {
    setShowLegend(false);
    try { localStorage.setItem('flow-legend-dismissed', '1'); } catch { /* ignore */ }
  };

  /* ── Living canvas: live pulses + usage heatmap ── */
  const [viewMode, setViewMode] = useState('live'); // 'live' | 'heatmap'
  const [liveEdges, setLiveEdges] = useState({});   // edgeId -> expiry ts
  const [heatCounts, setHeatCounts] = useState({}); // edgeId -> 7d call count
  const lastPollRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await toolsAPI.getFlowActivity(lastPollRef.current);
        if (cancelled) return;
        lastPollRef.current = res.data.now;
        const heat = {};
        (res.data.aggregates || []).forEach(a => { heat[`${a.slug}-${a.target}`] = a.count; });
        setHeatCounts(heat);
        if (res.data.events?.length) {
          const expiry = Date.now() + 4000;
          setLiveEdges(prev => {
            const next = { ...prev };
            res.data.events.forEach(ev => { next[`${ev.slug}-${ev.target}`] = expiry; });
            return next;
          });
        }
      } catch { /* canvas stays static if activity polling fails */ }
    };
    poll();
    const interval = setInterval(poll, 5000);
    const cleanup = setInterval(() => {
      const nowTs = Date.now();
      setLiveEdges(prev => {
        const entries = Object.entries(prev).filter(([, exp]) => exp > nowTs);
        return entries.length === Object.keys(prev).length ? prev : Object.fromEntries(entries);
      });
    }, 1000);
    return () => { cancelled = true; clearInterval(interval); clearInterval(cleanup); };
  }, []);

  const liveEdgeSet = useMemo(() => new Set(Object.keys(liveEdges)), [liveEdges]);

  /* ── Drop zone for tool cards from strip ── */
  const [dragOver, setDragOver] = useState(false);
  const [dragOverEdgeId, setDragOverEdgeId] = useState(null);
  const [isSkillDrag, setIsSkillDrag] = useState(false);
  const [skillDropPreview, setSkillDropPreview] = useState(null); // { x, y, edgeId }

  /** Pre-sampled points for each edge (computed once per connections change) */
  const edgeSamples = useMemo(() => {
    const SAMPLES = 16;
    return connections
      .filter(c => c.target !== 'escalation' && c.target !== 'channel')
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
      className={`flow-canvas relative w-full bg-stage border-[1.5px] border-stage-line rounded-lg overflow-hidden
        ${isPanning ? 'panning' : ''}
        ${dragOver && !isSkillDrag ? 'ring-2 ring-iris ring-inset bg-stage-deep' : ''}
        ${isSkillDrag && dragOverEdgeId ? 'ring-2 ring-iris ring-inset' : ''}
        ${isSkillDrag && !dragOverEdgeId ? 'ring-2 ring-stage-line ring-inset opacity-90' : ''}`}
      style={{ minHeight: `max(60vh, 500px)`, cursor: isPanning ? 'grabbing' : edgeDrag ? 'crosshair' : 'default', touchAction: 'none' }}
      onPointerDown={handleCanvasPointerDown}
      onPointerDownCapture={handlePointerDownCapture}
      onPointerMoveCapture={handlePointerMoveCapture}
      onPointerUpCapture={handlePointerEndCapture}
      onPointerCancelCapture={handlePointerEndCapture}
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
          className="absolute dot-grid-dark"
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
          liveEdges={liveEdgeSet}
          heatCounts={viewMode === 'heatmap' ? heatCounts : null}
        />

        {/* Core nodes */}
        {['assistant', 'manager', 'leads'].map(variant => {
          const nodeId = `__${variant}`;
          const pos = positions[nodeId];
          if (!pos) return null;
          const size = getNodeSize(nodeId);
          const makeSide = (side) => {
            const len = portLayout[nodeId]?.[side]?.length || 0;
            const count = Math.max(len, 1);
            return { count, connected: len, pitch: portPitch(count, size.h) };
          };

          return (
            <div
              key={nodeId}
              data-node-id={nodeId}
              className={`flow-draggable absolute ${isDragging && dragRef.current?.nodeId === nodeId ? 'dragging' : ''}`}
              style={{ left: pos.x, top: pos.y }}
              onPointerDown={(e) => handleNodePointerDown(nodeId, e)}
            >
              <CoreNode
                variant={variant}
                skills={skillsByTarget?.[variant]}
                ports={{ left: makeSide('left'), right: makeSide('right') }}
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
            className="absolute font-mono text-[10px] text-fog/90 tracking-wider uppercase pointer-events-none"
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
          const sides = toolPortSides[tool.slug];
          return (
            <div
              key={tool.slug}
              data-node-id={tool.slug}
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
                activeSides={{
                  left: !!sides?.has('left'),
                  right: !!sides?.has('right') || !sides,
                }}
              />
            </div>
          );
        })}

        {/* Customer channels — where the consultant talks to customers */}
        {channelNodes.map(ch => (
          <div
            key={ch.id}
            className="absolute pointer-events-none flow-node-enter"
            style={{ left: ch.x, top: ch.y, width: CHANNEL_W }}
          >
            <div className="px-3 py-2 rounded-lg bg-paper/95 border-[1.5px] border-sage
                            flex items-center gap-2 shadow-[0_0_18px_rgba(123,200,159,0.25)]">
              <span className="w-1.5 h-1.5 rounded-full bg-sage shrink-0" />
              <span className="text-[12px] font-medium text-ink truncate">{ch.name}</span>
            </div>
            <div className="font-mono text-[9px] uppercase tracking-wider text-fog mt-1 text-center">
              {t('tools.flow.channelLabel')}
            </div>
          </div>
        ))}

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
              {t('tools.flow.removeConnection')}
            </button>
          )}
          <button
            onClick={() => { setSelectedEdge(null); setContextMenu(null); }}
            className="flex items-center gap-2 w-full px-3 py-2 text-[13px] text-slate
                       hover:bg-mist hover:text-ink transition-colors cursor-pointer bg-transparent"
          >
            {t('tools.flow.cancel')}
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
            title={t('tools.flow.removeConnection')}
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
          onClick={() => setViewMode(m => m === 'live' ? 'heatmap' : 'live')}
          className={`p-1.5 rounded-sm transition-colors bg-transparent
            ${viewMode === 'heatmap' ? 'text-amber bg-mist' : 'text-slate hover:bg-mist hover:text-ink'}`}
          aria-label={t('tools.flow.heatmapToggle')}
          title={viewMode === 'heatmap' ? t('tools.flow.liveToggle') : t('tools.flow.heatmapToggle')}
        >
          {viewMode === 'heatmap' ? <Pulse size={16} weight="light" /> : <Fire size={16} weight="light" />}
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

      {/* ── Two-agents legend ── */}
      {showLegend && (
        <div className="absolute top-4 left-4 z-20 max-w-[300px] bg-paper/95 border-[1.5px] border-rule
                        rounded-lg p-3.5 shadow-ink-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] uppercase tracking-wider text-fog">
              {t('tools.flow.legendTitle')}
            </span>
            <button
              onClick={dismissLegend}
              className="text-fog hover:text-ink text-[14px] leading-none bg-transparent px-1"
              aria-label={t('tools.flow.cancel')}
            >
              ×
            </button>
          </div>
          <div className="flex items-start gap-2 text-[12px] text-ink leading-snug">
            <span className="w-2 h-2 rounded-full bg-iris mt-1 shrink-0" />
            {t('tools.flow.legendJeeves')}
          </div>
          <div className="flex items-start gap-2 text-[12px] text-ink leading-snug">
            <span className="w-2 h-2 rounded-full bg-sage mt-1 shrink-0" />
            {t('tools.flow.legendConcierge')}
          </div>
          <div className="flex items-start gap-2 text-[12px] text-ink leading-snug">
            <span className="w-2 h-2 rounded-full bg-amber mt-1 shrink-0" />
            {t('tools.flow.legendLeads')}
          </div>
        </div>
      )}

      {/* ── Keyboard hint ── */}
      {connectedTools.length > 0 && (
        <div className="absolute bottom-4 left-4 font-mono text-[10px] text-fog tracking-wide uppercase pointer-events-none select-none z-20">
          {t('tools.flow.canvasHint')}
        </div>
      )}
    </section>
  );
};

export default FlowCanvas;
