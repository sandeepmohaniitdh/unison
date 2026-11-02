// Small text helpers shared by the pages.

// "Jul-Nov 2026" -> "Jul–Nov 2026" (the design uses an en dash between the months)
export function formatTerm(term = '') {
  return term.replace(/^([A-Za-z]{3})-([A-Za-z]{3})/, '$1–$2')
}

// 2400000 -> "2.3 MB", 340000 -> "332 KB"
export function fileSize(bytes) {
  if (bytes == null) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// "application/pdf" or "report.pdf" -> "PDF"
export function fileKind(fileName, mime) {
  const ext = fileName?.includes('.') ? fileName.split('.').pop() : null
  if (ext) return ext.toUpperCase()
  if (mime) return mime.split('/').pop().toUpperCase()
  return 'File'
}

// "Dr. Kavya Menon" -> "Dr. Menon", "Sandeep M" -> "Sandeep", "Km Shristi Singh" -> "Km"
export function shortName(name = '') {
  const title = name.match(/^(Dr|Prof)\.?\s+/i)
  const words = name.replace(/^(Dr|Prof)\.?\s+/i, '').split(/\s+/).filter(Boolean)
  if (title && words.length) return `${title[1]}. ${words[words.length - 1]}`
  return words[0] ?? name
}

// The greeting uses the same short form: "Good morning, Sandeep" / "Good morning, Dr. Menon"
export const greetingName = shortName

// "cs26mt001@iitdh.ac.in" -> "cs26mt001"
export function emailUser(email = '') {
  return email.split('@')[0]
}

// 1 -> "1 team", 3 -> "3 teams"
export function plural(count, word, many = `${word}s`) {
  return `${count} ${count === 1 ? word : many}`
}

// Marks and points come as decimal strings: "42.0" -> "42", "24.5" -> "24.5"
export function points(value) {
  if (value == null || value === '') return ''
  return String(Number(value))
}

export function percentOf(part, whole) {
  if (!whole) return 0
  return Math.round((Number(part) / Number(whole)) * 100)
}

// The submission state of a team, as a badge: [text, tone]
const STATE_BADGES = {
  no_team: ['No team yet', 'grey'],
  no_work: ['Not started', 'grey'],
  drafts: ['Draft only', 'amber'],
  final_submitted: ['Final submitted', 'green'],
  submitted_at_deadline: ['Submitted at deadline', 'amber'],
  not_submitted: ['Not submitted', 'red'],
  marks_released: ['Marks released', 'green'],
}

export function stateBadge(state) {
  return STATE_BADGES[state] ?? [state, 'grey']
}

// Short form for the dashboard's deadline list ("Final in")
export function deadlineBadge(state) {
  if (state === 'final_submitted') return ['Final in', 'green']
  return stateBadge(state)
}

export const ROLE_LABELS = { student: 'Student', teacher: 'Teacher', admin: 'Admin' }

export function capitalise(text = '') {
  return text.charAt(0).toUpperCase() + text.slice(1)
}
