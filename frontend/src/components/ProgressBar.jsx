// Thin purple progress bar, e.g. "Finals submitted 3 / 5" or "12 of 15 teams submitted".
export default function ProgressBar({ value, label, height, color, className }) {
  const percent = Math.max(0, Math.min(100, value))
  return (
    <div
      className={['bar', className].filter(Boolean).join(' ')}
      style={height ? { height } : undefined}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(percent)}
    >
      <i style={{ width: `${percent}%`, background: color }} />
    </div>
  )
}
