/**
 * Outline button. Pink / green / violet / amber variants.
 * The signature element of the Concierge aesthetic — never filled.
 */
export default function Button({
  variant = 'violet',
  icon: Icon,
  children,
  className = '',
  ...rest
}) {
  const variantClass = {
    pink: 'btn-pink',
    green: 'btn-green',
    violet: 'btn-violet',
    amber: 'btn-amber',
  }[variant] || 'btn-violet';

  return (
    <button className={`btn ${variantClass} ${className}`} {...rest}>
      {Icon && <Icon size={16} weight="light" />}
      {children}
    </button>
  );
}
