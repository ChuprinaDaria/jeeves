import { NavLink } from 'react-router-dom';

const NAV = [
  { to: '/owner/dashboard', label: 'Dashboard' },
  { to: '/owner/branches', label: 'Branches' },
  { to: '/owner/specializations', label: 'Specializations' },
  { to: '/owner/clients', label: 'Clients' },
  { to: '/owner/ai-providers', label: 'AI Providers' },
  { to: '/owner/settings', label: 'Settings' },
];

const linkClass = ({ isActive }) =>
  [
    'block px-4 py-2 text-sm rounded-sm transition-colors',
    isActive
      ? 'bg-ink text-cream font-medium'
      : 'text-ink hover:bg-ink/10',
  ].join(' ');

const OwnerSidebar = () => (
  <aside className="w-60 bg-paper border-r border-ink/10 min-h-screen p-4 flex flex-col">
    <div className="mb-6 px-2">
      <div className="label-mono text-ink/60">Jeeves Admin</div>
      <div className="text-lg font-semibold text-ink">Owner Panel</div>
    </div>
    <nav className="space-y-1">
      {NAV.map((item) => (
        <NavLink key={item.to} to={item.to} className={linkClass}>
          {item.label}
        </NavLink>
      ))}
    </nav>
  </aside>
);

export default OwnerSidebar;
