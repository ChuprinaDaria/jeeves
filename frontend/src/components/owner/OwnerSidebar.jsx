import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

const NAV = [
  { to: '/owner/dashboard', label: 'Dashboard' },
  { to: '/owner/branches', label: 'Branches' },
  { to: '/owner/specializations', label: 'Specializations' },
  { to: '/owner/clients', label: 'Clients' },
  { to: '/owner/mcp-servers', label: 'MCP Servers' },
  {
    label: 'AI Providers',
    prefix: '/owner/ai-providers',
    children: [
      { to: '/owner/ai-providers/llm', label: 'LLM Providers' },
      { to: '/owner/ai-providers/embeddings', label: 'Embedding Models' },
      { to: '/owner/ai-providers/pairs', label: 'Model Pairs' },
    ],
  },
  {
    label: 'Settings',
    prefix: '/owner/settings',
    children: [
      { to: '/owner/settings', label: 'General' },
      { to: '/owner/settings/defaults', label: 'Platform Defaults' },
      { to: '/owner/feature-flags', label: 'Feature Flags' },
      { to: '/owner/system-messages', label: 'System Messages' },
    ],
  },
];

const linkClass = ({ isActive }) =>
  [
    'block px-4 py-2 text-sm rounded-sm transition-colors',
    isActive
      ? 'bg-ink text-cream font-medium'
      : 'text-ink hover:bg-ink/10',
  ].join(' ');

const childLinkClass = ({ isActive }) =>
  [
    'block px-6 py-1.5 text-sm rounded-sm transition-colors',
    isActive
      ? 'bg-ink text-cream font-medium'
      : 'text-ink/80 hover:bg-ink/10',
  ].join(' ');

const isGroupActive = (item, pathname) => {
  if (item.prefix && pathname.startsWith(item.prefix)) return true;
  return item.children.some((child) => pathname.startsWith(child.to));
};

const OwnerSidebar = () => {
  const { pathname } = useLocation();

  // Track which groups are expanded by label
  const initialExpanded = () => {
    const set = new Set();
    for (const item of NAV) {
      if (item.children && isGroupActive(item, pathname)) {
        set.add(item.label);
      }
    }
    return set;
  };

  const [expandedGroups, setExpandedGroups] = useState(initialExpanded);

  const toggleGroup = (label) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(label)) {
        next.delete(label);
      } else {
        next.add(label);
      }
      return next;
    });
  };

  return (
    <aside className="w-60 bg-paper border-r border-ink/10 min-h-screen p-4 flex flex-col">
      <div className="mb-6 px-2">
        <div className="label-mono text-ink/60">Jeeves Admin</div>
        <div className="text-lg font-semibold text-ink">Owner Panel</div>
      </div>
      <nav className="space-y-1">
        {NAV.map((item) => {
          if (item.children) {
            const open = expandedGroups.has(item.label) || isGroupActive(item, pathname);
            return (
              <div key={item.label}>
                <button
                  type="button"
                  onClick={() => toggleGroup(item.label)}
                  className="w-full text-left block px-4 py-2 text-sm rounded-sm text-ink hover:bg-ink/10"
                >
                  {item.label} {open ? '▾' : '▸'}
                </button>
                {open && (
                  <div className="space-y-0.5 mt-0.5">
                    {item.children.map((child) => (
                      <NavLink
                        key={child.to}
                        to={child.to}
                        end={child.to === '/owner/settings'}
                        className={childLinkClass}
                      >
                        {child.label}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            );
          }
          return (
            <NavLink key={item.to} to={item.to} className={linkClass}>
              {item.label}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
};

export default OwnerSidebar;
