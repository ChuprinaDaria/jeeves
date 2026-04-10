/**
 * Base card — cream paper with 1.5px border, 14px corners.
 * Optional `accent` draws a 3px colored stripe on top (rose/sage/iris/amber).
 */
export default function Card({
  accent,
  className = '',
  children,
  hover = false,
  ...rest
}) {
  const accentClass = {
    rose:  'before:bg-rose',
    sage:  'before:bg-sage',
    iris:  'before:bg-iris',
    amber: 'before:bg-amber',
  }[accent];

  const stripe = accent
    ? `relative before:content-[''] before:absolute before:top-0 before:left-0 before:right-0 before:h-[3px] before:rounded-t-lg ${accentClass}`
    : '';

  return (
    <div
      className={`surface p-6 ${hover ? 'surface-hover' : ''} ${stripe} ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, action }) {
  return (
    <div className="flex justify-between items-center mb-5">
      <h3 className="text-[16px] font-semibold text-ink">{title}</h3>
      {action}
    </div>
  );
}

/** Small monospace link-button used inside card headers. */
export function CardAction({ children, onClick }) {
  return (
    <button
      onClick={onClick}
      className="font-mono text-[12px] text-iris border border-iris-soft px-2.5 py-1 rounded-sm
                 hover:border-iris transition-colors bg-transparent cursor-pointer"
    >
      {children}
    </button>
  );
}
