import cx from '../lib/cx'

// Rounded square holding an icon or short text: the header bell, file and link tiles,
// notification icons, date tiles. Tones: plain (default), primary, tint, white, solid, soft.
// Size is one number (square) or [width, height].
export default function IconBox({ size = 42, tone = 'plain', radius, column = false, className, style, children, ...rest }) {
  const [width, height] = Array.isArray(size) ? size : [size, size]
  return (
    <div
      className={cx('bellb', tone !== 'plain' && `tone-${tone}`, column && 'column', className)}
      style={{ width, height, borderRadius: radius, ...style }}
      {...rest}
    >
      {children}
    </div>
  )
}

// Date tile from "Upcoming deadlines": <DateTile day="05" month="NOV" />
export function DateTile({ day, month }) {
  return (
    <IconBox size={[44, 48]} tone="primary" column>
      <b>{day}</b>
      <span className="tiny">{month}</span>
    </IconBox>
  )
}
