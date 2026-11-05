// Joins class names, skipping empty ones: cx('btn', primary && 'p') -> 'btn p'
export default function cx(...names) {
  return names.filter(Boolean).join(' ')
}
