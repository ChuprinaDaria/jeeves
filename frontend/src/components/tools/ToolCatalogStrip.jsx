import { useRef, useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import FlipToolCard from './FlipToolCard';
import ConnectModal from './ConnectModal';
import ToolIcon from './ToolIcon';
import { toolsAPI } from '../../api/tools';
import RichCardWrapper, { hasRichCard } from './richcards/RichCardWrapper';

const SLUG_TO_GROUP = {
  'rag-search':      'data',
  'email':           'data',
  'crm':             'data',
  'sales-intel':     'data',
  'coaching':        'logic',
  'hitl-matrix':     'logic',
  'translation':     'skills',
  'xlsx-processor':  'skills',
  'leads':           'skills',
  'telegram':        'comm',
  'web-widget':      'comm',
  'whatsapp-bridge': 'comm',
  'whatsapp-meta':   'comm',
  'meta-facebook':   'comm',
  'meta-instagram':  'comm',
  'linkedin':        'comm',
  'instagram':       'comm',
  'email-smtp':      'comm',
  'calendar':        'comm',
  'analytics':       'analytics',
};

const getToolGroup = (slug) => SLUG_TO_GROUP[slug] || 'comm';

const TABS = [
  { id: 'all',       labelKey: 'tools.flow.tabAll' },
  { id: 'data',      labelKey: 'tools.flow.tabData' },
  { id: 'logic',     labelKey: 'tools.flow.tabLogic' },
  { id: 'skills',    labelKey: 'tools.flow.tabSkills' },
  { id: 'comm',      labelKey: 'tools.flow.tabComm' },
  { id: 'analytics', labelKey: 'tools.flow.tabAnalytics' },
];

const SkillChip = ({ tool, onMouseEnter, onMouseLeave }) => {
  return (
    <div
      className="shrink-0 flex flex-col items-center gap-1.5 group cursor-grab active:cursor-grabbing"
      draggable={true}
      onDragStart={(e) => {
        e.dataTransfer.setData('tool-slug', tool.slug);
        e.dataTransfer.setData('tool-group', 'skills');
        e.dataTransfer.setData('is-skill', '1');
        e.dataTransfer.effectAllowed = 'copy';
      }}
      onMouseEnter={() => onMouseEnter?.(tool.slug)}
      onMouseLeave={() => onMouseLeave?.()}
      title={`${tool.name} — drag onto an edge`}
    >
      <div className="w-11 h-11 rounded-full border-[2px] border-rule
        bg-paper flex items-center justify-center
        shadow-ink-sm group-hover:shadow-ink group-hover:border-iris
        group-hover:scale-110 transition-all duration-200
        group-active:scale-95">
        <ToolIcon name={tool.icon} className="w-5 h-5 text-iris" />
      </div>
      <span className="font-mono text-[10px] uppercase tracking-wider text-fog text-center leading-tight max-w-[60px] truncate">
        {tool.name}
      </span>
    </div>
  );
};

// Semantic accent mapping per slug — only 4 accents allowed
const SERVER_ACCENT = {
  'telegram':        'iris',
  'whatsapp-meta':   'sage',
  'whatsapp-bridge': 'sage',
  'meta-facebook':   'iris',
  'meta-instagram':  'rose',
  'linkedin':        'iris',
  'instagram':       'rose',
  'email-smtp':      'rose',
  'email':           'rose',
  'web-widget':      'iris',
  'hitl-matrix':     'sage',
  'rag-search':      'amber',
  'leads':           'sage',
  'sales-intel':     'iris',
  'coaching':        'iris',
  'crm':             'iris',
  'analytics':       'amber',
  'calendar':        'sage',
};

const ACCENT_CLASSES = {
  iris:  { border: 'border-iris',  bg: 'bg-iris/10',  text: 'text-iris'  },
  sage:  { border: 'border-sage',  bg: 'bg-sage/10',  text: 'text-sage'  },
  rose:  { border: 'border-rose',  bg: 'bg-rose/10',  text: 'text-rose'  },
  amber: { border: 'border-amber', bg: 'bg-amber/10', text: 'text-amber' },
};

const ServerChip = ({ tool, onConnected, onMouseEnter, onMouseLeave, onOpenAuth }) => {
  const { t } = useTranslation();
  const isConnected = tool.connection?.status === 'connected' && tool.connection?.enabled;
  const accentKey = SERVER_ACCENT[tool.slug] || 'iris';
  const accent = ACCENT_CLASSES[accentKey];

  const handleClick = () => {
    if (isConnected) return;
    if (tool.auth_type === 'none') {
      toolsAPI.connect(tool.slug, {}).then(() => onConnected(tool.slug)).catch(() => {});
    } else {
      onOpenAuth?.(tool);
    }
  };

  return (
    <div
      className={`shrink-0 w-[180px] rounded-lg p-4 select-none transition-all duration-200 cursor-pointer border-[1.5px]
        ${isConnected
          ? `${accent.border} bg-paper shadow-ink-sm`
          : 'border-dashed border-rule bg-paper/60 opacity-70 hover:opacity-100'
        }
        hover:shadow-ink hover:-translate-y-[2px] active:translate-y-0`}
      draggable={true}
      onDragStart={(e) => {
        e.dataTransfer.setData('tool-slug', tool.slug);
        e.dataTransfer.setData('tool-group', 'servers');
        e.dataTransfer.effectAllowed = 'copy';
      }}
      onClick={handleClick}
      onMouseEnter={() => isConnected && onMouseEnter?.(tool.slug)}
      onMouseLeave={() => isConnected && onMouseLeave?.()}
    >
      <div className="flex items-center gap-3 mb-2">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 border-[1.5px] ${accent.border} ${accent.bg} ${accent.text}`}>
          <ToolIcon name={tool.icon} className="w-5 h-5" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-ink leading-tight truncate">
            {tool.name}
          </div>
          <div className={`font-mono text-[10px] uppercase tracking-wider mt-0.5 ${isConnected ? 'text-sage' : 'text-fog'}`}>
            {isConnected ? t('tools.connected') : t('tools.notConnected')}
          </div>
        </div>
      </div>
      {tool.tagline && (
        <p className="text-[10px] text-slate leading-snug mb-2 line-clamp-2">
          {tool.tagline}
        </p>
      )}
      {hasRichCard(tool.slug) && (
        <div className="mb-2">
          <RichCardWrapper slug={tool.slug} />
        </div>
      )}
      {isConnected && (
        <div className={`w-full h-1 rounded-full ${accent.bg}`}>
          <div className={`h-full rounded-full ${accent.bg.replace('/10', '')} w-full`} />
        </div>
      )}
    </div>
  );
};

const ToolCatalogStrip = ({ tools, onConnected, onToolHover, onToolHoverEnd }) => {
  const { t } = useTranslation();
  const scrollRef = useRef(null);
  const [showLeftFade, setShowLeftFade] = useState(false);
  const [showRightFade, setShowRightFade] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [authTool, setAuthTool] = useState(null);

  const updateFades = () => {
    const el = scrollRef.current;
    if (!el) return;
    setShowLeftFade(el.scrollLeft > 10);
    setShowRightFade(el.scrollLeft < el.scrollWidth - el.clientWidth - 10);
  };

  useEffect(() => {
    updateFades();
    const el = scrollRef.current;
    el?.addEventListener('scroll', updateFades);
    window.addEventListener('resize', updateFades);
    return () => {
      el?.removeEventListener('scroll', updateFades);
      window.removeEventListener('resize', updateFades);
    };
  }, [tools, activeTab]);

  // Count tools per group
  const groupCounts = {};
  tools.forEach(tool => {
    const g = getToolGroup(tool.slug);
    groupCounts[g] = (groupCounts[g] || 0) + 1;
  });

  const filteredTools = activeTab === 'all'
    ? tools
    : tools.filter(tool => getToolGroup(tool.slug) === activeTab);

  return (
    <div className="space-y-3">
      {/* Tabs */}
      <div className="flex gap-1.5 flex-wrap">
        {TABS.map(tab => {
          const count = tab.id === 'all' ? tools.length : (groupCounts[tab.id] || 0);
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-sm font-mono text-[11px] uppercase tracking-wider transition-all cursor-pointer border-[1.5px]
                ${isActive
                  ? 'bg-linen text-iris border-iris'
                  : 'bg-paper text-slate border-rule hover:bg-mist hover:border-fog'
                }`}
            >
              {t(tab.labelKey, {
                defaultValue: {
                  all: 'All',
                  data: 'Data Sources',
                  logic: 'Business Logic',
                  skills: 'Skills',
                  comm: 'Communication',
                  analytics: 'Analytics',
                }[tab.id] || tab.id,
              })}
              {count > 0 && (
                <span className={`ml-1.5 px-1.5 py-0.5 rounded-sm text-[10px] font-semibold border-[1.5px]
                  ${isActive
                    ? 'bg-iris-soft text-iris border-iris'
                    : 'bg-linen text-slate border-rule'
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Card strip */}
      <div className="relative">
        {showLeftFade && (
          <div className="absolute left-0 top-0 bottom-0 w-12 bg-gradient-to-r from-cream to-transparent z-10 pointer-events-none" />
        )}
        {showRightFade && (
          <div className="absolute right-0 top-0 bottom-0 w-12 bg-gradient-to-l from-cream to-transparent z-10 pointer-events-none" />
        )}

        <div
          ref={scrollRef}
          className="flex gap-3 items-start overflow-x-auto pb-2 px-1 scrollbar-hide"
          style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
        >
          {filteredTools.length > 0 ? (
            filteredTools.map(tool => {
              const group = getToolGroup(tool.slug);
              if (group === 'skills') {
                return (
                  <SkillChip
                    key={tool.slug}
                    tool={tool}
                    onMouseEnter={onToolHover}
                    onMouseLeave={onToolHoverEnd}
                  />
                );
              }
              if (group === 'data' || group === 'logic' || group === 'analytics') {
                return (
                  <ServerChip
                    key={tool.slug}
                    tool={tool}
                    onConnected={onConnected}
                    onMouseEnter={onToolHover}
                    onMouseLeave={onToolHoverEnd}
                    onOpenAuth={setAuthTool}
                  />
                );
              }
              return (
                <FlipToolCard
                  key={tool.slug}
                  tool={{ ...tool, _group: group }}
                  onConnected={onConnected}
                  onMouseEnter={onToolHover}
                  onMouseLeave={onToolHoverEnd}
                />
              );
            })
          ) : (
            <div className="w-full py-6 text-center text-sm text-fog">
              {t('tools.flow.emptyCategory', { defaultValue: 'No tools in this category yet' })}
            </div>
          )}
        </div>
      </div>

      {/* Auth modal for servers */}
      {authTool && (
        <ConnectModal
          tool={authTool}
          onClose={() => setAuthTool(null)}
          onConnected={(slug) => {
            setAuthTool(null);
            onConnected(slug);
          }}
        />
      )}
    </div>
  );
};

export default ToolCatalogStrip;
