import { useRef, useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import FlipToolCard from './FlipToolCard';

/* ── Category mapping: slug → tab group ── */
const SLUG_TO_GROUP = {
  'rag-search':      'servers',
  'translation':     'skills',
  'email-smtp':      'servers',
  'telegram':        'servers',
  'web-widget':      'servers',
  'whatsapp-meta':   'servers',
  'whatsapp-bridge': 'servers',
  'hitl-matrix':     'servers',
  'instagram':       'servers',
  'calendar':        'tools',
  'crm':             'tools',
  'analytics':       'tools',
};

const getToolGroup = (slug) => SLUG_TO_GROUP[slug] || 'tools';

const TABS = [
  { id: 'all',     labelKey: 'tools.flow.tabAll' },
  { id: 'servers', labelKey: 'tools.flow.tabServers' },
  { id: 'skills',  labelKey: 'tools.flow.tabSkills' },
  { id: 'tools',   labelKey: 'tools.flow.tabTools' },
];

const ToolCatalogStrip = ({ tools, onConnected, onToolHover, onToolHoverEnd }) => {
  const { t } = useTranslation();
  const scrollRef = useRef(null);
  const [showLeftFade, setShowLeftFade] = useState(false);
  const [showRightFade, setShowRightFade] = useState(false);
  const [activeTab, setActiveTab] = useState('all');

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
            filteredTools.map(tool => (
              <FlipToolCard
                key={tool.slug}
                tool={tool}
                onConnected={onConnected}
                onMouseEnter={onToolHover}
                onMouseLeave={onToolHoverEnd}
              />
            ))
          ) : (
            <div className="w-full py-6 text-center text-sm text-gray-400 dark:text-gray-500">
              {t('tools.flow.emptyCategory', { defaultValue: 'No tools in this category yet' })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ToolCatalogStrip;
