import { useRef, useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import FlipToolCard from './FlipToolCard';
import ConnectModal from './ConnectModal';
import ToolIcon from './ToolIcon';
import { toolsAPI } from '../../api/tools';

/* ── Category mapping: slug → tab group ── */
const SLUG_TO_GROUP = {
  'rag-search':      'servers',
  'translation':     'skills',
  'xlsx-processor':  'skills',
  'email-smtp':      'tools',
  'telegram':        'tools',
  'web-widget':      'tools',
  'whatsapp-bridge': 'tools',
  'hitl-matrix':     'servers',
  'instagram':       'tools',
  'calendar':        'tools',
  'crm':             'tools',
  'analytics':       'tools',
  'leads':           'servers',
  'sales-intel':     'servers',
};

const getToolGroup = (slug) => SLUG_TO_GROUP[slug] || 'tools';

const TABS = [
  { id: 'all',     labelKey: 'tools.flow.tabAll' },
  { id: 'servers', labelKey: 'tools.flow.tabServers' },
  { id: 'skills',  labelKey: 'tools.flow.tabSkills' },
  { id: 'tools',   labelKey: 'tools.flow.tabTools' },
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
      <div className="w-11 h-11 rounded-full border-2 border-primary-200 dark:border-primary-700
        bg-white dark:bg-gray-800 flex items-center justify-center
        shadow-sm group-hover:shadow-md group-hover:border-primary-400 dark:group-hover:border-primary-500
        group-hover:scale-110 transition-all duration-200
        group-active:scale-95">
        <ToolIcon name={tool.icon} className="w-5 h-5 text-primary-500" />
      </div>
      <span className="text-[10px] text-gray-500 dark:text-gray-400 font-medium text-center leading-tight max-w-[60px] truncate">
        {tool.name}
      </span>
    </div>
  );
};

const SERVER_COLORS = {
  'telegram':        { border: 'border-[#229ED9]', bg: 'bg-[#229ED9]/10', text: 'text-[#229ED9]' },
  'whatsapp-meta':   { border: 'border-[#25D366]', bg: 'bg-[#25D366]/10', text: 'text-[#25D366]' },
  'whatsapp-bridge': { border: 'border-[#25D366]', bg: 'bg-[#25D366]/10', text: 'text-[#25D366]' },
  'instagram':       { border: 'border-[#E4405F]', bg: 'bg-[#E4405F]/10', text: 'text-[#E4405F]' },
  'email-smtp':      { border: 'border-[#EA4335]', bg: 'bg-[#EA4335]/10', text: 'text-[#EA4335]' },
  'web-widget':      { border: 'border-[#6c5ce7]', bg: 'bg-[#6c5ce7]/10', text: 'text-[#6c5ce7]' },
  'hitl-matrix':     { border: 'border-[#00a67e]', bg: 'bg-[#00a67e]/10', text: 'text-[#00a67e]' },
  'rag-search':      { border: 'border-[#f59e0b]', bg: 'bg-[#f59e0b]/10', text: 'text-[#f59e0b]' },
  'leads':           { border: 'border-[#10b981]', bg: 'bg-[#10b981]/10', text: 'text-[#10b981]' },
  'sales-intel':     { border: 'border-[#3b82f6]', bg: 'bg-[#3b82f6]/10', text: 'text-[#3b82f6]' },
};

const ServerChip = ({ tool, onConnected, onMouseEnter, onMouseLeave, onOpenAuth }) => {
  const { t } = useTranslation();
  const isConnected = tool.connection?.status === 'connected' && tool.connection?.enabled;
  const colors = SERVER_COLORS[tool.slug] || { border: 'border-gray-400', bg: 'bg-gray-400/10', text: 'text-gray-500' };

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
      className={`shrink-0 w-[180px] rounded-2xl border-2 p-4 select-none transition-all duration-200 cursor-pointer
        ${isConnected
          ? `${colors.border} bg-white dark:bg-gray-800 shadow-md`
          : 'border-dashed border-gray-300 dark:border-gray-600 bg-white/60 dark:bg-gray-800/60 opacity-70 hover:opacity-100'
        }
        hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]`}
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
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${colors.bg} ${colors.text}`}>
          <ToolIcon name={tool.icon} className="w-5 h-5" />
        </div>
        <div>
          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 leading-tight">
            {tool.name}
          </div>
          <div className={`text-[10px] font-medium mt-0.5 ${isConnected ? 'text-green-500' : 'text-gray-400'}`}>
            {isConnected ? t('tools.connected') : t('tools.notConnected')}
          </div>
        </div>
      </div>
      {tool.tagline && (
        <p className="text-[10px] text-gray-500 dark:text-gray-400 leading-snug mb-2 line-clamp-2">
          {tool.tagline}
        </p>
      )}
      {isConnected && (
        <div className={`w-full h-1 rounded-full ${colors.bg}`}>
          <div className={`h-full rounded-full ${colors.border.replace('border-', 'bg-')} w-full`} />
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
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer
                ${isActive
                  ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 border border-primary-200 dark:border-primary-700'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 border border-transparent hover:bg-gray-200 dark:hover:bg-gray-700'
                }`}
            >
              {t(tab.labelKey, { defaultValue: tab.id.charAt(0).toUpperCase() + tab.id.slice(1) })}
              {count > 0 && (
                <span className={`ml-1.5 px-1.5 py-0.5 rounded-full text-[10px] font-semibold
                  ${isActive
                    ? 'bg-primary-200 dark:bg-primary-800 text-primary-800 dark:text-primary-200'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
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
          <div className="absolute left-0 top-0 bottom-0 w-12 bg-gradient-to-r from-gray-50 dark:from-gray-900 to-transparent z-10 pointer-events-none" />
        )}
        {showRightFade && (
          <div className="absolute right-0 top-0 bottom-0 w-12 bg-gradient-to-l from-gray-50 dark:from-gray-900 to-transparent z-10 pointer-events-none" />
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
              if (group === 'servers') {
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
            <div className="w-full py-6 text-center text-sm text-gray-400 dark:text-gray-500">
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
