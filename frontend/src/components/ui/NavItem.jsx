import { NavLink } from 'react-router-dom';

/**
 * Sidebar navigation item. Uses react-router NavLink for active state.
 * Active = 1.5px iris border, otherwise transparent with hover bg.
 */
export default function NavItem({ to, icon: Icon, label, badge, end = false }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-sm text-[14px] transition-all duration-200
         border-[1.5px] ${
           isActive
             ? 'border-iris text-ink [&>svg]:text-iris'
             : 'border-transparent text-slate hover:bg-linen hover:text-ink'
         }`
      }
    >
      {Icon && <Icon size={20} weight="light" className="shrink-0" />}
      <span className="flex-1 truncate">{label}</span>
      {badge != null && (
        <span
          className="font-mono text-[11px] px-2 py-0.5 rounded-[10px] border-[1.5px] border-rose text-rose"
        >
          {badge}
        </span>
      )}
    </NavLink>
  );
}
