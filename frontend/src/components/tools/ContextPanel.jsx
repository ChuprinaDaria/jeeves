import { useState } from 'react';
import { CaretRight, Database, Shield, ChatCircle, StackSimple } from '@phosphor-icons/react';
import ToolIcon from './ToolIcon';

const ContextPanel = ({ tools }) => {
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
        className="absolute top-3 right-3 z-20 px-2.5 py-2 rounded-lg
          bg-paper border-[1.5px] border-rule
          text-slate hover:text-ink transition-all cursor-pointer
          hover:bg-mist shadow-ink-sm"
        title="Merged Context"
      >
        <StackSimple weight="light" size={16} />
      </button>
    );
  }

  return (
    <div className="absolute top-3 right-3 z-20 w-[260px] context-panel-enter
      bg-paper rounded-lg border-[1.5px] border-rule
      shadow-ink-lg overflow-hidden">

      <div className="flex items-center justify-between px-4 py-3 border-b-[1.5px] border-rule">
        <span className="label-mono">Merged Context</span>
        <button
          onClick={() => setCollapsed(true)}
          className="text-fog hover:text-ink transition-colors cursor-pointer"
        >
          <CaretRight weight="light" size={16} />
        </button>
      </div>

      <div className="p-3 space-y-3 max-h-[400px] overflow-y-auto">
        {dataSources.length > 0 && (
          <Section icon={Database} title="Data Sources" items={dataSources} />
        )}
        {channels.length > 0 && (
          <Section icon={ChatCircle} title="Channels" items={channels} />
        )}
        {skills.length > 0 && (
          <Section icon={Shield} title="Active Skills" items={skills} />
        )}
        {connected.length === 0 && (
          <div className="text-center py-4 text-xs text-fog">
            No tools connected
          </div>
        )}
      </div>

      <div className="px-4 py-2 border-t-[1.5px] border-rule">
        <div className="label-mono-sm">
          {connected.length} sources active
        </div>
      </div>
    </div>
  );
};

const Section = ({ icon: Icon, title, items }) => (
  <div>
    <div className="flex items-center gap-1.5 mb-1.5">
      <Icon weight="light" size={14} className="text-fog" />
      <span className="label-mono-sm">{title}</span>
    </div>
    <div className="space-y-1">
      {items.map(tool => (
        <div
          key={tool.slug}
          className="flex items-center gap-2 px-2 py-1 rounded-sm bg-linen border-[1.5px] border-rule"
        >
          <ToolIcon name={tool.icon} className="w-3.5 h-3.5 text-slate" />
          <span className="text-[11px] text-ink truncate">{tool.name}</span>
          <span className="ml-auto w-1.5 h-1.5 rounded-full bg-sage shrink-0" />
        </div>
      ))}
    </div>
  </div>
);

export default ContextPanel;
