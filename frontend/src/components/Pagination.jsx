import cx from '../lib/cx'

// "Previous 1 2 3 Next" under a list (catalogue, admin tables). Shows at most 5 numbers.
export default function Pagination({ page, size, total, onChange, className }) {
  const pages = Math.max(1, Math.ceil(total / size))
  if (pages <= 1) return null
  const from = Math.max(1, Math.min(page - 2, pages - 4))
  const numbers = []
  for (let n = from; n <= Math.min(pages, from + 4); n += 1) numbers.push(n)
  return (
    <nav className={cx('row gap8', className)} style={{ justifyContent: 'center' }} aria-label="Pages">
      <button type="button" className="btn o sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        Previous
      </button>
      {numbers.map((n) => (
        <button
          key={n}
          type="button"
          className={cx('btn sm', n === page ? 'p' : 'o')}
          aria-current={n === page ? 'page' : undefined}
          onClick={() => onChange(n)}
        >
          {n}
        </button>
      ))}
      <button type="button" className="btn o sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>
        Next
      </button>
    </nav>
  )
}
