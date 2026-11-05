import Card from './Card'

const NOTE_CLASS = { muted: 'small muted', accent: 'small accent', link: 'small link' }

// Summary card at the top of dashboards: label, big number, and a note or a bar below.
//   <StatCard label="Due this week" value="2" note="Next: Wed 5 Nov, 23:59 IST" noteTone="accent" />
//   <StatCard label="Finals submitted" value="3 / 5"><ProgressBar value={60} /></StatCard>
export default function StatCard({ label, value, note, noteTone = 'muted', children }) {
  return (
    <Card className="col gap8 grow">
      <span className="small muted">{label}</span>
      <b className="stat-value">{value}</b>
      {note && (
        <span className={NOTE_CLASS[noteTone]} style={noteTone === 'muted' ? undefined : { fontWeight: 600 }}>
          {note}
        </span>
      )}
      {children}
    </Card>
  )
}
