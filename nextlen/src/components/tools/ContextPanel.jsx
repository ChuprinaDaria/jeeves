import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronRight, Database, Shield, MessageSquare, Layers } from 'lucide-react';
import ToolIcon from './ToolIcon';

const ContextPanel = ({ tools }) => {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(true);

  const connected = tools.filter(tool => {
    if (tool.connections) return tool.connections.some(c => c.status === 'connected' && c.enabled);
    return tool.connection?.status === 'connected' && tool.connection?.enabled;
  });

  const dataSources = connected.filter(t => ['rag-search', 'email', 'crm', 'sales-intel'].includes(t.slug));
  const channels = connected.filter(t => ['telegram', 'web-widget', 'whatsapp-bridge', 'instagram', 'email-smtp'].includes(t.slug));
  const skills = connected.filter(t => ['translation', 'xlsx-processor'].includes(t.slug));

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="absolute top-3 right-3 z-20 px-2.5 py-2 rounded-xl
          bg-gray-900/80 dark:bg-gray-800/90 backdrop-blur-sm border border-gray-700/50
          text-gray-400 hover:text-gray-200 transition-all cursor-pointer
          hover:bg-gray-800/90 shadow-lg"
        title="Merged Context"
      >
        <Layers className="w-4 h-4" />
      </button>
    );
  }

  return (
    <div className="absolute top-3 right-3 z-20 w-[260px] context-panel-enter
      bg-gray-900/90 dark:bg-gray-800/95 backdrop-blur-md rounded-2xl border border-gray-700/50
      shadow-2xl overflow-hidden">

      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700/50">
        <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">Merged Context</span>
        <button
          onClick={() => setCollapsed(true)}
          className="text-gray-500 hover:text-gray-300 transition-colors cursor-pointer"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      <div className="p-3 space-y-3 max-h-[400px] overflow-y-auto scrollbar-hide">
        {dataSources.length > 0 && (
          <Section icon={Database} title="Data Sources" items={dataSources} />
        )}
        {channels.length > 0 && (
          <Section icon={MessageSquare} title="Channels" items={channels} />
        )}
        {skills.length > 0 && (
          <Section icon={Shield} title="Active Skills" items={skills} />
        )}
        {connected.length === 0 && (
          <div className="text-center py-4 text-xs text-gray-500">
            No tools connected
          </div>
        )}
      </div>

      <div className="px-4 py-2 border-t border-gray-700/50">
        <div className="text-[9px] text-gray-500 font-mono">
          {connected.length} sources active
        </div>
      </div>
    </div>
  );
};

const Section = ({ icon: Icon, title, items }) => (
  <div>
    <div className="flex items-center gap-1.5 mb-1.5">
      <Icon className="w-3 h-3 text-gray-500" />
      <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">{title}</span>
    </div>
    <div className="space-y-1">
      {items.map(tool => (
        <div key={tool.slug} className="flex items-center gap-2 px-2 py-1 rounded-lg bg-gray-800/50">
          <ToolIcon name={tool.icon} className="w-3.5 h-3.5 text-gray-400" />
          <span className="text-[11px] text-gray-300 truncate">{tool.name}</span>
          <span className="ml-auto w-1.5 h-1.5 rounded-full bg-green-500 shrink-0" />
        </div>
      ))}
    </div>
  </div>
);

export default ContextPanel;
