import cx from '../lib/cx'

// White card with the design's border, radius 16 and soft shadow.
// `highlight` gives the purple-bordered version used for "Needs your action" and the final.
export default function Card({ as: Tag = 'div', highlight = false, className, children, ...rest }) {
  return (
    <Tag className={cx('card', highlight && 'hl', className)} {...rest}>
      {children}
    </Tag>
  )
}
