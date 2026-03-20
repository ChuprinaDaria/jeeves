export const TOOL_TARGETS = {
  'whatsapp-meta':   ['assistant'],
  'whatsapp-bridge': ['assistant'],
  'telegram':        ['assistant'],
  'instagram':       ['assistant'],
  'email-smtp':      ['assistant'],
  'web-widget':      ['assistant', 'leads'],
  'rag-search':      ['assistant'],
  'translation':     ['assistant'],
  'hitl-matrix':     ['manager'],
  'calendar':        ['manager'],
  'crm':             ['assistant', 'manager'],
  'analytics':       ['assistant', 'manager'],
};

export const getToolTargets = (slug) => TOOL_TARGETS[slug] || ['assistant'];
