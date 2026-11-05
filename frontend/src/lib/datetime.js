// Every time is shown in IST (Asia/Kolkata), as in the design: "Wed 5 Nov, 23:59 IST".
// The API sends ISO times with an offset (+05:30); a time without one is read as UTC.

const IST = 'Asia/Kolkata'

export function parseTime(value) {
  if (value instanceof Date) return value
  const hasZone = /(Z|[+-]\d\d:?\d\d)$/.test(value)
  return new Date(hasZone ? value : `${value}Z`)
}

function parts(value, options) {
  const formatter = new Intl.DateTimeFormat('en-GB', { timeZone: IST, ...options })
  // en-GB writes September as "Sept"; the design uses three letters everywhere.
  return Object.fromEntries(formatter.formatToParts(parseTime(value)).map((p) => [p.type, p.value === 'Sept' ? 'Sep' : p.value]))
}

const TIME = { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }

// "Wed 5 Nov, 23:59 IST"
export function formatDeadline(value) {
  const p = parts(value, { weekday: 'short', day: 'numeric', month: 'short', ...TIME })
  return `${p.weekday} ${p.day} ${p.month}, ${p.hour}:${p.minute} IST`
}

// "Wed 5 Nov 2026, 23:59"
export function formatDeadlineLong(value) {
  const p = parts(value, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', ...TIME })
  return `${p.weekday} ${p.day} ${p.month} ${p.year}, ${p.hour}:${p.minute}`
}

// "2 Nov, 18:12 IST"
export function formatShort(value) {
  const p = parts(value, { day: 'numeric', month: 'short', ...TIME })
  return `${p.day} ${p.month}, ${p.hour}:${p.minute} IST`
}

// "Thu 30 Oct"
export function formatDay(value) {
  const p = parts(value, { weekday: 'short', day: 'numeric', month: 'short' })
  return `${p.weekday} ${p.day} ${p.month}`
}

// "4 Aug"
export function formatDayMonth(value) {
  const p = parts(value, { day: 'numeric', month: 'short' })
  return `${p.day} ${p.month}`
}

// "1 Oct 2026"
export function formatDate(value) {
  const p = parts(value, { day: 'numeric', month: 'short', year: 'numeric' })
  return `${p.day} ${p.month} ${p.year}`
}

// "17:00 IST"
export function formatTime(value) {
  const p = parts(value, TIME)
  return `${p.hour}:${p.minute} IST`
}

// Date tile of "Upcoming deadlines": { day: '05', month: 'NOV' }
export function dateTile(value) {
  const p = parts(value, { day: '2-digit', month: 'short' })
  return { day: p.day, month: p.month.toUpperCase() }
}

// Value for <input type="datetime-local">, in IST: "2026-11-05T23:59"
export function toIstInput(value) {
  if (!value) return ''
  const p = parts(value, { year: 'numeric', month: '2-digit', day: '2-digit', ...TIME })
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`
}

// Back from the input to the API: the typed time is IST. 23:59 means 23:59:59.
export function fromIstInput(text) {
  if (!text) return null
  const seconds = text.endsWith('23:59') ? ':59' : ':00'
  return `${text}${seconds}+05:30`
}

// "Good morning" / "Good afternoon" / "Good evening", by the time in IST.
export function greeting(now = new Date()) {
  const hour = Number(parts(now, { hour: '2-digit', hourCycle: 'h23' }).hour)
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export function isPast(value, now = new Date()) {
  return parseTime(value).getTime() <= now.getTime()
}

// Within the next 7 days (the dashboard's "Due this week").
export function isWithinDays(value, days, now = new Date()) {
  const t = parseTime(value).getTime()
  return t > now.getTime() && t <= now.getTime() + days * 86400000
}

// Whole days from now until the time, rounded up ("Deletion in 5 days").
export function daysUntil(value, now = new Date()) {
  return Math.max(0, Math.ceil((parseTime(value).getTime() - now.getTime()) / 86400000))
}
