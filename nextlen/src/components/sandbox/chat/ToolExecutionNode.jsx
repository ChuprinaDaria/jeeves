import { Mail, Search, Users, UserPlus, Globe, FileDown, Wrench, Check, X, Loader2 } from 'lucide-react';

const TOOL_MAP = {
  'send-email':    { icon: Mail,     label: 'Email',          color: 'green' },
  'send_email':    { icon: Mail,     label: 'Email',          color: 'green' },
  'rag-search':    { icon: Search,   label: 'Knowledge Base', color: 'purple' },
  'search':        { icon: Search,   label: 'Knowledge Base', color: 'purple' },
  'lead-search':   { icon: Users,    label: 'Leads',          color: 'amber' },
  'search_leads':  { icon: Users,    label: 'Leads',          color: 'amber' },
  'lead-create':   { icon: UserPlus, label: 'Create Lead',    color: 'amber' },
  'create_lead':   { icon: UserPlus, label: 'Create Lead',    color: 'amber' },
  'web-research':  { icon: Globe,    label: 'Web Research',   color: 'purple' },
  'web_search':    { icon: Globe,    label: 'Web Research',   color: 'purple' },
  'generate-file': { icon: FileDown, label: 'Generate File',  color: 'green' },
};

const COLOR_MAP = {
  green:  { border: 'border-l-emerald-400', bg: 'bg-emerald-500/10', text: 'text-emerald-400', dot: 'bg-emerald-400' },
  purple: { border: 'border-l-violet-400',  bg: 'bg-violet-500/10',  text: 'text-violet-400',  dot: 'bg-violet-400' },
  amber:  { border: 'border-l-amber-400',   bg: 'bg-amber-500/10',   text: 'text-amber-400',   dot: 'bg-amber-400' },
  gray:   { border: 'border-l-gray-400',    bg: 'bg-gray-500/10',    text: 'text-gray-400',    dot: 'bg-gray-400' },
};

const ToolExecutionNode = ({ tool, params, status = 'running', summary, error, style }) => {
  const mapped = TOOL_MAP[tool] || { icon: Wrench, label: tool, color: 'gray' };
  const Icon = mapped.icon;
  const colors = COLOR_MAP[mapped.color];
  const paramEntries = params ? Object.entries(params).slice(0, 4) : [];

  return (
    <div
      className={`chat-tool-node border-l-4 ${colors.border} rounded-xl border border-gray-200 dark:border-gray-700/50 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm p-3 my-2`}
      style={style}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <div className={`w-7 h-7 rounded-lg ${colors.bg} flex items-center justify-center`}>
            <Icon size={14} className={colors.text} />
          </div>
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{mapped.label}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {status === 'running' && (
            <>
              <Loader2 size={12} className="text-gray-400 animate-spin" />
              <span className="text-xs text-gray-400">Processing...</span>
            </>
          )}
          {status === 'success' && (
            <>
              <div className="w-4 h-4 rounded-full bg-emerald-500/20 flex items-center justify-center">
                <Check size={10} className="text-emerald-400" />
              </div>
              <span className="text-xs text-emerald-400">Done</span>
            </>
          )}
          {status === 'error' && (
            <>
              <div className="w-4 h-4 rounded-full bg-red-500/20 flex items-center justify-center">
                <X size={10} className="text-red-400" />
              </div>
              <span className="text-xs text-red-400">Failed</span>
            </>
          )}
        </div>
      </div>

      {paramEntries.length > 0 && (
        <div className="mt-2 space-y-0.5">
          {status === 'running' ? (
            paramEntries.map(([key]) => (
              <div key={key} className="flex items-center gap-2">
                <span className="text-[10px] text-gray-500 dark:text-gray-400 w-16 shrink-0">{key}:</span>
                <div className="h-3 flex-1 rounded chat-shimmer bg-gray-200 dark:bg-gray-700" />
              </div>
            ))
          ) : (
            paramEntries.map(([key, value]) => (
              <div key={key} className="flex items-center gap-2 text-xs">
                <span className="text-gray-500 dark:text-gray-400 w-16 shrink-0">{key}:</span>
                <span className="text-gray-700 dark:text-gray-300 truncate">{String(value)}</span>
              </div>
            ))
          )}
        </div>
      )}

      {status === 'success' && summary && (
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400 border-t border-gray-100 dark:border-gray-700/50 pt-1.5">{summary}</p>
      )}
      {status === 'error' && error && (
        <p className="mt-2 text-xs text-red-400 border-t border-gray-100 dark:border-gray-700/50 pt-1.5">{error}</p>
      )}
    </div>
  );
};

export { TOOL_MAP, COLOR_MAP };
export default ToolExecutionNode;
