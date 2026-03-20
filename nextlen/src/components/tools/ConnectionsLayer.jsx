import { useMemo } from 'react';

const supportsOffsetPath = typeof CSS !== 'undefined' && CSS.supports?.('offset-path', 'path("")');

const ConnectionsLayer = ({ connections, highlightedTool, canvasW = 1200, canvasH = 600 }) => {
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
    </>
  ), []);

  return (
    <svg
      className="absolute inset-0 pointer-events-none"
      style={{ zIndex: 1, width: canvasW, height: canvasH, overflow: 'visible' }}
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
        const opacity = isHighlighted ? 1 : 0.08;

        return (
          <g
            key={conn.id}
            className="transition-opacity duration-300"
            style={{ opacity, animationDelay: `${i * 200}ms` }}
          >
            {/* Glow / shadow */}
            <path
              d={conn.pathD}
              fill="none"
              stroke={`url(#${gradId})`}
              strokeWidth="6"
              opacity="0.08"
            />

            {/* Main line */}
            <path
              d={conn.pathD}
              fill="none"
              stroke={`url(#${gradId})`}
              strokeWidth="2"
              className="flow-line-animated"
            />

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
    </svg>
  );
};

export default ConnectionsLayer;
