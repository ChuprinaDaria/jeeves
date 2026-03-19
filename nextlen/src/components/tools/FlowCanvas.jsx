import { useRef, useState, useEffect, useCallback, useMemo } from 'react';
import CoreNode from './CoreNode';
import CanvasToolNode from './CanvasToolNode';
import ConnectionsLayer from './ConnectionsLayer';
import OnboardingHint from './OnboardingHint';
import { getToolTargets } from './toolTargets';

const FlowCanvas = ({ tools, onToolClick, highlightedTool }) => {
  const canvasRef = useRef(null);
  const assistantRef = useRef(null);
  const managerRef = useRef(null);
  const toolRefs = useRef({});
  const [connections, setConnections] = useState([]);
  const [, setTick] = useState(0); // force re-render for ref reads

  const connectedTools = useMemo(
    () => tools.filter(t => t.connection?.status === 'connected' && t.connection?.enabled),
    [tools]
  );

  const groups = useMemo(() => {
    const left = [];    // assistant only
    const right = [];   // manager only
    const both = [];    // both

    connectedTools.forEach(tool => {
      const targets = getToolTargets(tool.slug);
      if (targets.includes('assistant') && targets.includes('manager')) both.push(tool);
      else if (targets.includes('manager')) right.push(tool);
      else left.push(tool);
    });

    return { left, right, both };
  }, [connectedTools]);

  // Canvas min-height: max(60vh, 400px, content-based)
  const maxGroupSize = Math.max(groups.left.length, groups.right.length, 1);
  const contentHeight = maxGroupSize * 80 + 200;
  // 60vh is applied via CSS, this is the pixel minimum
  const canvasMinHeight = Math.max(400, contentHeight);

  // Compute positions and bezier paths
  const computeConnections = useCallback(() => {
    const canvas = canvasRef.current;
    const aNode = assistantRef.current;
    const mNode = managerRef.current;
    if (!canvas || !aNode || !mNode) return;

    const canvasRect = canvas.getBoundingClientRect();
    const newConns = [];

    const getCenter = (el) => {
      const r = el.getBoundingClientRect();
      return {
        x: r.left + r.width / 2 - canvasRect.left,
        y: r.top + r.height / 2 - canvasRect.top,
      };
    };

    const getPort = (el, side) => {
      const r = el.getBoundingClientRect();
      return {
        x: (side === 'left' ? r.left : r.right) - canvasRect.left,
        y: r.top + r.height / 2 - canvasRect.top,
      };
    };

    // Escalation link between assistant and manager
    const aCenter = getCenter(aNode);
    const mCenter = getCenter(mNode);
    const aRight = getPort(aNode, 'right');
    const mLeft = getPort(mNode, 'left');
    const escCpX = aRight.x + (mLeft.x - aRight.x) * 0.5;
    newConns.push({
      id: 'escalation',
      pathD: `M${aRight.x},${aRight.y} C${escCpX},${aRight.y} ${escCpX},${mLeft.y} ${mLeft.x},${mLeft.y}`,
      target: 'escalation',
      toolSlug: null,
    });

    // Tool connections
    const addToolConn = (toolSlug, sourceEl, targetEl, target) => {
      if (!sourceEl || !targetEl) return;
      const src = getPort(sourceEl, 'right');
      const tgt = getPort(targetEl, 'left');
      const cpX = src.x + (tgt.x - src.x) * 0.55;
      newConns.push({
        id: `${toolSlug}-${target}`,
        pathD: `M${src.x},${src.y} C${cpX},${src.y} ${cpX},${tgt.y} ${tgt.x},${tgt.y}`,
        target,
        toolSlug,
      });
    };

    connectedTools.forEach(tool => {
      const ref = toolRefs.current[tool.slug];
      if (!ref) return;
      const targets = getToolTargets(tool.slug);
      if (targets.includes('assistant')) addToolConn(tool.slug, ref, aNode, 'assistant');
      if (targets.includes('manager')) addToolConn(tool.slug, ref, mNode, 'manager');
    });

    setConnections(newConns);
  }, [connectedTools]);

  // Recompute on mount, resize, and tool changes
  useEffect(() => {
    // Wait for refs to be set
    const t = setTimeout(() => {
      setTick(n => n + 1);
      computeConnections();
    }, 100);
    return () => clearTimeout(t);
  }, [connectedTools, computeConnections]);

  useEffect(() => {
    let timeout;
    const handleResize = () => {
      clearTimeout(timeout);
      timeout = setTimeout(computeConnections, 150);
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      clearTimeout(timeout);
    };
  }, [computeConnections]);

  // Auto-layout: position tool nodes
  const getToolStyle = (tool, group, index, total) => {
    const canvasH = canvasMinHeight;
    const padding = 40;
    const usableH = canvasH - padding * 2;
    const spacing = total > 1 ? usableH / (total - 1) : 0;
    const yStart = total > 1 ? padding : canvasH / 2 - 30;
    const y = yStart + index * spacing;

    if (group === 'left') return { top: `${y}px`, left: '40px' };
    if (group === 'right') return { top: `${y}px`, right: '40px' };
    // both: horizontal row above center
    const xCenter = 50; // percent
    const offset = (index - (total - 1) / 2) * 180;
    return { top: `${padding}px`, left: `calc(${xCenter}% + ${offset}px)`, transform: 'translateX(-50%)' };
  };

  return (
    <div
      ref={canvasRef}
      className="relative w-full bg-gray-50 dark:bg-gray-900 rounded-xl overflow-hidden"
      style={{ minHeight: `max(60vh, ${canvasMinHeight}px)` }}
    >
      {/* Dot grid (dark only) */}
      <div className="absolute inset-0 dot-grid hidden dark:block" />

      {/* Onboarding hint */}
      {connectedTools.length === 0 && <OnboardingHint />}

      {/* SVG connections */}
      <ConnectionsLayer connections={connections} highlightedTool={highlightedTool} />

      {/* Core nodes */}
      <CoreNode
        ref={assistantRef}
        variant="assistant"
        connectedCount={groups.left.length + groups.both.length}
        style={{ top: '50%', left: '35%', transform: 'translate(-50%, -50%)' }}
      />
      <CoreNode
        ref={managerRef}
        variant="manager"
        connectedCount={groups.right.length + groups.both.length}
        style={{ top: '50%', left: '65%', transform: 'translate(-50%, -50%)' }}
      />

      {/* Escalation label */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[10px] text-gray-400 dark:text-gray-500 font-medium tracking-wider uppercase pointer-events-none">
        escalation
      </div>

      {/* Connected tool nodes */}
      {groups.left.map((tool, i) => (
        <CanvasToolNode
          key={tool.slug}
          ref={el => { toolRefs.current[tool.slug] = el; }}
          tool={tool}
          onClick={onToolClick}
          isHighlighted={highlightedTool === null ? null : highlightedTool === tool.slug}
          style={getToolStyle(tool, 'left', i, groups.left.length)}
        />
      ))}
      {groups.right.map((tool, i) => (
        <CanvasToolNode
          key={tool.slug}
          ref={el => { toolRefs.current[tool.slug] = el; }}
          tool={tool}
          onClick={onToolClick}
          isHighlighted={highlightedTool === null ? null : highlightedTool === tool.slug}
          style={getToolStyle(tool, 'right', i, groups.right.length)}
        />
      ))}
      {groups.both.map((tool, i) => (
        <CanvasToolNode
          key={tool.slug}
          ref={el => { toolRefs.current[tool.slug] = el; }}
          tool={tool}
          onClick={onToolClick}
          isHighlighted={highlightedTool === null ? null : highlightedTool === tool.slug}
          style={getToolStyle(tool, 'both', i, groups.both.length)}
        />
      ))}
    </div>
  );
};

export default FlowCanvas;
