import { useMemo } from 'react';

const supportsOffsetPath = typeof CSS !== 'undefined' && CSS.supports?.('offset-path', 'path("")');

const ConnectionsLayer = ({
  connections,
  highlightedTool,
  canvasW = 1200,
  canvasH = 600,
  selectedEdge,
  onEdgeClick,
  onEdgePointerDown,
  ghostEdge,
  dragOverEdgeId,
}) => {
  const gradients = useMemo(() => (
    <>
      <linearGradient id="grad-assistant" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stopColor="#6c5ce7" stopOpacity="0.6" />
        <stop offset="100%" stopColor="#a29bfe" stopOpacity="0.3" />
      </linearGradient>
      <linearGradient id="grad-manager" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stopColor="#00a67e" stopOpacity="0.6" />
        <stop offset="100%" stopColor="#00d9a3" stopOpacity="0.3" />
      </linearGradient>
      <linearGradient id="grad-leads" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.6" />
        <stop offset="100%" stopColor="#fbbf24" stopOpacity="0.3" />
      </linearGradient>
      <linearGradient id="grad-escalation" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stopColor="#6b7280" stopOpacity="0.3" />
        <stop offset="100%" stopColor="#6b7280" stopOpacity="0.1" />
      </linearGradient>
      <linearGradient id="grad-ghost" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.6" />
        <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.3" />
      </linearGradient>
    </>
  ), []);

  return (
    <svg
      className="absolute inset-0"
      style={{ zIndex: 1, width: canvasW, height: canvasH, overflow: 'visible', pointerEvents: 'none' }}
      viewBox={`0 0 ${canvasW} ${canvasH}`}
    >
      <defs>{gradients}</defs>

      {connections.map((conn, i) => {
        const gradId = conn.target === 'escalation' ? 'grad-escalation'
          : conn.target === 'leads' ? 'grad-leads'
          : conn.target === 'assistant' ? 'grad-assistant' : 'grad-manager';
        const dotColor = conn.target === 'assistant' ? '#a29bfe'
          : conn.target === 'leads' ? '#fbbf24' : '#00d9a3';

        const isHighlighted = highlightedTool === null
          ? true
          : highlightedTool === conn.toolSlug;
        const isSelected = selectedEdge === conn.id;
        const isDragOver = dragOverEdgeId === conn.id;
        const opacity = isHighlighted ? 1 : 0.08;

        return (
          <g
            key={conn.id}
            className="transition-opacity duration-300"
            style={{ opacity, animationDelay: `${i * 200}ms` }}
          >
            {/* Invisible hit area for interaction */}
            <path
              d={conn.pathD}
              fill="none"
              stroke="transparent"
              strokeWidth="20"
              style={{ pointerEvents: 'stroke', cursor: 'pointer' }}
              onClick={(e) => {
                e.stopPropagation();
                onEdgeClick?.(conn.id, e);
              }}
              onPointerDown={(e) => {
                if (e.button !== 0) return;
                e.stopPropagation();
                onEdgePointerDown?.(conn.id, e);
              }}
            />

            {/* Glow / shadow */}
            <path
              d={conn.pathD}
              fill="none"
              stroke={`url(#${gradId})`}
              strokeWidth={isDragOver ? 12 : isSelected ? 10 : 6}
              opacity={isDragOver ? 0.25 : isSelected ? 0.2 : 0.08}
              className={isDragOver ? 'animate-pulse' : ''}
            />

            {/* Main line */}
            <path
              d={conn.pathD}
              fill="none"
              stroke={`url(#${gradId})`}
              strokeWidth={isSelected ? 3 : isDragOver ? 4 : 2}
              className="flow-line-animated"
            />

            {/* Selection indicator */}
            {isSelected && (
              <path
                d={conn.pathD}
                fill="none"
                stroke="#8b5cf6"
                strokeWidth="1"
                strokeDasharray="4 4"
                opacity="0.6"
              />
            )}

            {/* Animated particles */}
            {conn.target !== 'escalation' && [0, 1, 2].map(p => (
              supportsOffsetPath ? (
                <circle
                  key={p}
                  r="3"
                  fill={dotColor}
                  className="flow-particle"
                  style={{
                    offsetPath: `path("${conn.pathD}")`,
                    '--particle-duration': `${2 + Math.random() * 0.5}s`,
                    '--particle-delay': `${p * 0.8}s`,
                  }}
                />
              ) : (
                <circle key={p} r="3" fill={dotColor} opacity="0">
                  <animateMotion
                    dur={`${2 + Math.random() * 0.5}s`}
                    repeatCount="indefinite"
                    begin={`${p * 0.8}s`}
                    path={conn.pathD}
                  />
                  <animate
                    attributeName="opacity"
                    values="0;1;1;0"
                    keyTimes="0;0.1;0.9;1"
                    dur={`${2 + Math.random() * 0.5}s`}
                    repeatCount="indefinite"
                    begin={`${p * 0.8}s`}
                  />
                </circle>
              )
            ))}
          </g>
        );
      })}

      {/* Ghost edge during drag */}
      {ghostEdge && (
        <path
          d={ghostEdge.pathD}
          fill="none"
          stroke="url(#grad-ghost)"
          strokeWidth="2"
          strokeDasharray="6 4"
          opacity="0.7"
        />
      )}
    </svg>
  );
};

export default ConnectionsLayer;
