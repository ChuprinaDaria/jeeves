export const TOOL_TARGETS = {
  'whatsapp-meta':   ['assistant', 'manager'],
  'whatsapp-bridge': ['assistant', 'manager'],
  'telegram':        ['assistant', 'manager'],
  'instagram':       ['assistant', 'manager'],
  'email-smtp':      ['assistant', 'manager'],
  'web-widget':      ['assistant', 'manager', 'leads'],
  'rag-search':      ['assistant'],
  'translation':     ['assistant'],
  'xlsx-processor':  ['assistant', 'manager'],
  'hitl-matrix':     ['manager'],
  'calendar':        ['manager'],
  'crm':             ['assistant', 'manager'],
  'analytics':       ['assistant', 'manager'],
};

export const getToolTargets = (slug) => TOOL_TARGETS[slug] || ['assistant'];
