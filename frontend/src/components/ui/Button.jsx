export default function Button({
  children,
  onClick,
  disabled = false,
  variant = 'primary',
  className = '',
  type = 'button',
  style
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`app-btn app-btn--${variant} ${className}`.trim()}
      style={style}
    >
      {children}
    </button>
  )
}
