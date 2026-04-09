const ACTION_MAP = {
  'send-email':    ['Resend', 'View in History'],
  'send_email':    ['Resend', 'View in History'],
  'rag-search':    ['Search Again', 'Save Answer'],
  'search':        ['Search Again', 'Save Answer'],
  'lead-search':   ['Show Details', 'Export CSV'],
  'search_leads':  ['Show Details', 'Export CSV'],
  'lead-create':   ['View Lead', 'Add Another'],
  'create_lead':   ['View Lead', 'Add Another'],
  'web-research':  ['Tell me more', 'Search Again'],
  'web_search':    ['Tell me more', 'Search Again'],
};

const DEFAULT_ACTIONS = ['Tell me more', 'Start over'];

const COLOR_CLASSES = {
  green:  'border-emerald-400/30 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10',
  purple: 'border-violet-400/30 text-violet-600 dark:text-violet-400 hover:bg-violet-500/10',
  amber:  'border-amber-400/30 text-amber-600 dark:text-amber-400 hover:bg-amber-500/10',
  gray:   'border-gray-400/30 text-gray-600 dark:text-gray-400 hover:bg-gray-500/10',
};

const QuickActions = ({ lastTool, toolColor = 'gray', onAction }) => {
  const actions = ACTION_MAP[lastTool] || DEFAULT_ACTIONS;
  const colorClass = COLOR_CLASSES[toolColor] || COLOR_CLASSES.gray;

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {actions.map((action, i) => (
        <button
          key={action}
          onClick={() => onAction(action)}
          className={`chat-chip-pop rounded-full px-3 py-1.5 text-xs border ${colorClass} transition-colors cursor-pointer`}
          style={{ animationDelay: `${i * 50}ms` }}
        >
          {action}
        </button>
      ))}
    </div>
  );
};

export default QuickActions;
