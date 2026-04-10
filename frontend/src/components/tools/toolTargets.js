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
  'calendar':        ['manager'],
  'crm':             ['assistant', 'manager'],
  'analytics':       ['assistant', 'manager'],
  'leads':           ['assistant', 'manager'],
  'sales-intel':     ['assistant'],
  'email':           ['assistant', 'manager'],
  'coaching':        ['assistant'],
};

export const getToolTargets = (slug) => TOOL_TARGETS[slug] || ['assistant'];
