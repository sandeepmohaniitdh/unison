// A small pie chart (with a hole in the middle, showing the total) and its legend.
//
//   <PieChart
//     label="Users by role"
//     data={[{ label: 'Students', value: 300 }, { label: 'Teachers', value: 15 }, { label: 'Admins', value: 2 }]}
//   />
//
// Colours come from --chart-1, --chart-2 and --chart-3 in tokens.css, in that order. The
// legend lists every slice with its number and share, so nothing depends on colour alone.

const COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)']
const MIN_SWEEP = 0.025 // tiny slices (2 admins of 317 users) stay visible

export default function PieChart({ data, label, size = 168, centerLabel = 'total' }) {
  const total = data.reduce((sum, d) => sum + d.value, 0)
  const r = size / 2
  const hole = r * 0.58
  const slices = sweeps(data, total)

  let angle = -Math.PI / 2 // start at 12 o'clock
  const paths = slices.map((sweep, i) => {
    const start = angle
    angle += sweep * 2 * Math.PI
    return { ...data[i], color: data[i].color ?? COLORS[i % COLORS.length], d: arc(r, hole, start, angle, sweep) }
  })

  const summary = data.map((d) => `${d.label} ${d.value}`).join(', ')
  return (
    <div className="pie">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${label}: ${summary}`}>
        {total === 0 ? (
          <circle cx={r} cy={r} r={(r + hole) / 2} fill="none" stroke="var(--color-divider)" strokeWidth={r - hole} />
        ) : (
          paths.map((p) =>
            p.d ? (
              <path key={p.label} d={p.d} fill={p.color} stroke="var(--color-surface)" strokeWidth="2" strokeLinejoin="round">
                <title>{`${p.label}: ${p.value} (${share(p.value, total)})`}</title>
              </path>
            ) : null,
          )
        )}
        <text x={r} y={r - 2} textAnchor="middle" className="pie-total">
          {total}
        </text>
        <text x={r} y={r + 16} textAnchor="middle" className="pie-sub">
          {centerLabel}
        </text>
      </svg>
      <ul className="pie-legend">
        {paths.map((p) => (
          <li key={p.label}>
            <i style={{ background: p.color }} aria-hidden="true" />
            <span>{p.label}</span>
            <b>{p.value}</b>
            <span className="muted">{share(p.value, total)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function share(value, total) {
  if (!total) return '0%'
  const pct = (value / total) * 100
  return `${pct > 0 && pct < 1 ? pct.toFixed(1) : Math.round(pct)}%`
}

// Each slice's share of the circle (0 to 1). Non-zero slices get at least MIN_SWEEP,
// taken from the largest slice.
function sweeps(data, total) {
  if (!total) return data.map(() => 0)
  const out = data.map((d) => (d.value > 0 ? Math.max(d.value / total, MIN_SWEEP) : 0))
  const extra = out.reduce((a, b) => a + b, 0) - 1
  const biggest = out.indexOf(Math.max(...out))
  out[biggest] -= extra
  return out
}

// One ring slice from angle a0 to a1. A slice that is the whole circle is drawn as a ring.
function arc(r, hole, a0, a1, sweep) {
  if (sweep <= 0) return null
  const c = r
  if (sweep >= 0.9999) {
    return `M ${c} ${c - r} A ${r} ${r} 0 1 1 ${c - 0.01} ${c - r} Z M ${c} ${c - hole} A ${hole} ${hole} 0 1 0 ${c - 0.01} ${c - hole} Z`
  }
  const large = a1 - a0 > Math.PI ? 1 : 0
  const p = (radius, a) => `${(c + radius * Math.cos(a)).toFixed(2)} ${(c + radius * Math.sin(a)).toFixed(2)}`
  return [
    `M ${p(r, a0)}`,
    `A ${r} ${r} 0 ${large} 1 ${p(r, a1)}`,
    `L ${p(hole, a1)}`,
    `A ${hole} ${hole} 0 ${large} 0 ${p(hole, a0)}`,
    'Z',
  ].join(' ')
}
