import { useMemo } from 'react';

const EDGE_LABELS = {
  'rag-search': { assistant: 'Fetch semantic query', manager: 'Fetch semantic profile' },
  'email-smtp': { assistant: 'Send email', manager: 'Send email' },
  'telegram': { assistant: 'Send message', manager: 'Escalation' },
  'whatsapp-bridge': { assistant: 'Send message', manager: 'Escalation' },
  'web-widget': { assistant: 'Send message', manager: 'Escalation' },
  'instagram': { assistant: 'Send message', manager: 'Escalation' },
  'hitl-matrix': { assistant: 'Escalation', manager: 'Live handoff' },
  'crm': { assistant: 'Query CRM data', manager: 'Query CRM data' },
  'analytics': { assistant: 'Fetch analytics', manager: 'Fetch analytics' },
  'xlsx-processor': { assistant: 'Process spreadsheet' },
  'translation': { assistant: 'Translate text' },
  'leads': { leads: 'Capture lead' },
  'sales-intel': { leads: 'Enrich lead data' },
  'coaching': { assistant: 'Apply coaching rules' },
  'email': { assistant: 'Fetch email context' },
  '__escalation': { escalation: 'Escalation' },
};

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
  isSkillDrag,
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
        const isSkillTarget = isSkillDrag && conn.target !== 'escalation';
        const opacity = isSkillDrag
          ? (isDragOver ? 1 : 0.25)
          : (isHighlighted ? 1 : 0.08);

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
              strokeWidth={isDragOver && isSkillDrag ? 18 : isDragOver ? 12 : isSelected ? 10 : isSkillTarget ? 8 : 6}
              opacity={isDragOver && isSkillDrag ? 0.4 : isDragOver ? 0.25 : isSelected ? 0.2 : isSkillTarget ? 0.12 : 0.08}
              className={isDragOver ? 'animate-pulse' : ''}
            />

            {/* Main line */}
            <path
              id={`edge-path-${conn.id}`}
              d={conn.pathD}
              fill="none"
              stroke={`url(#${gradId})`}
              strokeWidth={isDragOver && isSkillDrag ? 5 : isSelected ? 3 : isDragOver ? 4 : isSkillTarget ? 2.5 : 2}
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

            {(() => {
              const label = conn.toolSlug === '__escalation'
                ? 'Escalation'
                : EDGE_LABELS[conn.toolSlug]?.[conn.target];
              if (!label) return null;
              return (
                <text
                  fill="#94a3b8"
                  fontSize="9"
                  fontFamily="'Fira Sans', sans-serif"
                  fontWeight="500"
                  textAnchor="middle"
                  dy="-8"
                  opacity={isHighlighted ? 0.9 : 0}
                  style={{ transition: 'opacity 0.3s', pointerEvents: 'none' }}
                >
                  <textPath href={`#edge-path-${conn.id}`} startOffset="40%">
                    {label}
                  </textPath>
                </text>
              );
            })()}

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
