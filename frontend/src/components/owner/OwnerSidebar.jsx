import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

const NAV = [
  { to: '/owner/dashboard', label: 'Dashboard' },
  { to: '/owner/branches', label: 'Branches' },
  { to: '/owner/specializations', label: 'Specializations' },
  { to: '/owner/clients', label: 'Clients' },
  {
    label: 'AI Providers',
    children: [
      { to: '/owner/ai-providers/llm', label: 'LLM Providers' },
      { to: '/owner/ai-providers/embeddings', label: 'Embedding Models' },
      { to: '/owner/ai-providers/pairs', label: 'Model Pairs' },
    ],
  },
  { to: '/owner/settings', label: 'Settings' },
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

const OwnerSidebar = () => {
  const { pathname } = useLocation();
  const aiOpen = pathname.startsWith('/owner/ai-providers');
  const [expanded, setExpanded] = useState(aiOpen);

  return (
    <aside className="w-60 bg-paper border-r border-ink/10 min-h-screen p-4 flex flex-col">
      <div className="mb-6 px-2">
        <div className="label-mono text-ink/60">Jeeves Admin</div>
        <div className="text-lg font-semibold text-ink">Owner Panel</div>
      </div>
      <nav className="space-y-1">
        {NAV.map((item) => {
          if (item.children) {
            return (
              <div key={item.label}>
                <button
                  type="button"
                  onClick={() => setExpanded((v) => !v)}
                  className="w-full text-left block px-4 py-2 text-sm rounded-sm text-ink hover:bg-ink/10"
                >
                  {item.label} {expanded || aiOpen ? '▾' : '▸'}
                </button>
                {(expanded || aiOpen) && (
                  <div className="space-y-0.5 mt-0.5">
                    {item.children.map((child) => (
                      <NavLink
                        key={child.to}
                        to={child.to}
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
