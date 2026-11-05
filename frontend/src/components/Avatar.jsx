import cx from '../lib/cx'

const SIZES = { medium: null, small: 's', large: 'l' }

// "Km Shristi Singh" -> "KS", "Dr. Kavya Menon" -> "KM", "Sandeep M" -> "SM"
export function initialsOf(name = '') {
  const words = name
    .replace(/^(Dr|Prof|Mr|Ms|Mrs)\.?\s+/i, '')
    .split(/\s+/)
    .filter(Boolean)
  if (words.length === 0) return '?'
  const first = words[0][0]
  const last = words.length > 1 ? words[words.length - 1][0] : ''
  return (first + last).toUpperCase()
}

// Round avatar with initials. tone="amber" marks someone who is only invited.
export default function Avatar({ name, initials, size = 'medium', tone, className }) {
  return (
    <span className={cx('av', SIZES[size], tone === 'amber' && 'amber', className)} aria-hidden="true">
      {initials ?? initialsOf(name)}
    </span>
  )
}
