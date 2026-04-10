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
  // Concierge palette as SVG gradients.
  // Solid, warm, no electric neon — these are the same accents as the Dashboard.
  const gradients = useMemo(() => (
    <>
      {/* iris — assistant */}
      <linearGradient id="grad-assistant" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%"   stopColor="#9B7ED8" stopOpacity="0.75" />
        <stop offset="100%" stopColor="#D4C5F0" stopOpacity="0.45" />
      </linearGradient>
      {/* sage — manager / HITL */}
      <linearGradient id="grad-manager" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%"   stopColor="#7BC89F" stopOpacity="0.75" />
        <stop offset="100%" stopColor="#C5E8D5" stopOpacity="0.45" />
      </linearGradient>
      {/* amber — leads */}
      <linearGradient id="grad-leads" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%"   stopColor="#E8A86D" stopOpacity="0.75" />
        <stop offset="100%" stopColor="#F5DABC" stopOpacity="0.45" />
      </linearGradient>
      {/* muted slate — escalation fallback */}
      <linearGradient id="grad-escalation" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%"   stopColor="#9E9790" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#9E9790" stopOpacity="0.12" />
      </linearGradient>
      {/* iris ghost — drag preview */}
      <linearGradient id="grad-ghost" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%"   stopColor="#9B7ED8" stopOpacity="0.7" />
        <stop offset="100%" stopColor="#9B7ED8" stopOpacity="0.3" />
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
        // Solid dot colours from the Concierge palette
        const dotColor = conn.target === 'assistant' ? '#9B7ED8'
          : conn.target === 'leads' ? '#E8A86D' : '#7BC89F';

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

            {/* Selection indicator — iris dashed overlay */}
            {isSelected && (
              <path
                d={conn.pathD}
                fill="none"
                stroke="#9B7ED8"
                strokeWidth="1"
                strokeDasharray="4 4"
                opacity="0.7"
              />
            )}

            {(() => {
              const label = conn.toolSlug === '__escalation'
                ? 'Escalation'
                : EDGE_LABELS[conn.toolSlug]?.[conn.target];
              if (!label) return null;
              return (
                <text
                  fill="#9E9790"
                  fontSize="9"
                  fontFamily="'Ubuntu Mono', monospace"
                  fontWeight="400"
                  letterSpacing="0.5"
                  textAnchor="middle"
                  dy="-8"
                  opacity={isHighlighted ? 0.85 : 0}
                  style={{ transition: 'opacity 0.3s', pointerEvents: 'none', textTransform: 'uppercase' }}
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
