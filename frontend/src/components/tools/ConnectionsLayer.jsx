import { useMemo } from 'react';

const EDGE_LABELS = {
  'rag-search': { assistant: 'Fetch semantic query', manager: 'Fetch semantic profile' },
  'email-smtp': { assistant: 'Send email', manager: 'Send email' },
  'telegram': { assistant: 'Send message', manager: 'Escalation' },
  'whatsapp-bridge': { assistant: 'Send message', manager: 'Escalation' },
  'web-widget': { assistant: 'Send message', manager: 'Escalation' },
  'instagram': { assistant: 'Send message', manager: 'Escalation' },
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
  liveEdges,
  heatCounts,
}) => {
  // Concierge palette as SVG gradients — boosted opacities + glow so the
  // edges read as light against the dark canvas stage.
  const gradients = useMemo(() => (
    <>
      {/* iris — assistant */}
      <linearGradient id="grad-assistant" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%"   stopColor="#9B7ED8" stopOpacity="0.95" />
        <stop offset="100%" stopColor="#D4C5F0" stopOpacity="0.65" />
      </linearGradient>
      {/* sage — manager / HITL */}
      <linearGradient id="grad-manager" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%"   stopColor="#7BC89F" stopOpacity="0.95" />
        <stop offset="100%" stopColor="#C5E8D5" stopOpacity="0.65" />
      </linearGradient>
      {/* amber — leads */}
      <linearGradient id="grad-leads" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%"   stopColor="#E8A86D" stopOpacity="0.95" />
        <stop offset="100%" stopColor="#F5DABC" stopOpacity="0.65" />
      </linearGradient>
      {/* muted slate — escalation fallback */}
      <linearGradient id="grad-escalation" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%"   stopColor="#9E9790" stopOpacity="0.55" />
        <stop offset="100%" stopColor="#9E9790" stopOpacity="0.25" />
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
        const isChannel = conn.target === 'channel';
        // Solid dot colours from the Concierge palette
        const dotColor = conn.target === 'assistant' ? '#9B7ED8'
          : conn.target === 'leads' ? '#E8A86D' : '#7BC89F';

        const isHighlighted = highlightedTool === null
          ? true
          : highlightedTool === conn.toolSlug;
        const isSelected = selectedEdge === conn.id;
        const isDragOver = dragOverEdgeId === conn.id;
        const isSkillTarget = isSkillDrag && conn.target !== 'escalation';
        const isLive = liveEdges?.has(conn.id);
        const heatCount = heatCounts ? (heatCounts[conn.id] || 0) : null;
        // Heatmap: edge weight = real 7-day usage; unused edges fade out
        const heatWidth = heatCount !== null
          ? 1.5 + Math.min(6, Math.log2(1 + heatCount) * 1.4)
          : null;
        const baseOpacity = isSkillDrag
          ? (isDragOver ? 1 : 0.25)
          : (isHighlighted ? 1 : 0.08);
        const opacity = heatCount !== null && heatCount === 0 && conn.target !== 'escalation'
          ? Math.min(baseOpacity, 0.2)
          : baseOpacity;

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
              style={{ pointerEvents: isChannel ? 'none' : 'stroke', cursor: 'pointer' }}
              onClick={(e) => {
                if (isChannel) return;
                e.stopPropagation();
                onEdgeClick?.(conn.id, e);
              }}
              onPointerDown={(e) => {
                if (isChannel || e.button !== 0) return;
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

            {/* Main line — glows against the dark stage */}
            <path
              id={`edge-path-${conn.id}`}
              d={conn.pathD}
              fill="none"
              stroke={`url(#${gradId})`}
              strokeWidth={heatWidth ?? (isDragOver && isSkillDrag ? 5 : isSelected ? 3 : isDragOver ? 4 : isSkillTarget ? 2.5 : isLive ? 3.5 : 2)}
              className="flow-line-animated edge-glow"
              style={{ '--edge-glow': isLive ? dotColor : `${dotColor}55` }}
            />

            {/* Live pulse — the agent used this tool just now */}
            {isLive && (
              <path
                d={conn.pathD}
                fill="none"
                stroke={dotColor}
                strokeWidth="4"
                strokeLinecap="round"
                className="edge-live"
                style={{ filter: `drop-shadow(0 0 8px ${dotColor})` }}
              />
            )}

            {/* Heatmap count label */}
            {heatCount !== null && heatCount > 0 && conn.target !== 'escalation' && (
              <text
                fill={dotColor}
                fontSize="10"
                fontFamily="'Ubuntu Mono', monospace"
                fontWeight="700"
                textAnchor="middle"
                dy="14"
                style={{ pointerEvents: 'none' }}
              >
                <textPath href={`#edge-path-${conn.id}`} startOffset="50%">
                  {heatCount}×
                </textPath>
              </text>
            )}

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
                  fill="#B8B0A6"
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
            {conn.target !== 'escalation' && (isChannel ? [0] : [0, 1, 2]).map(p => (
              supportsOffsetPath ? (
                <circle
                  key={p}
                  r="3.5"
                  fill={dotColor}
                  className="flow-particle"
                  style={{
                    offsetPath: `path("${conn.pathD}")`,
                    filter: `drop-shadow(0 0 4px ${dotColor})`,
                    '--particle-duration': isLive ? '0.8s' : `${2 + Math.random() * 0.5}s`,
                    '--particle-delay': `${p * (isLive ? 0.25 : 0.8)}s`,
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
