import { Link } from 'react-router'
import Icon from './Icon'
import IconBox from './IconBox'

// One notification in a list: icon tile, title, "course · time" line and an unread dot.
// Unread rows have a tinted icon and a bold title, as in the student dashboard.
export default function NotificationRow({ icon = 'bell', title, meta, unread = false, to }) {
  const body = (
    <>
      <IconBox size={36} tone={unread ? 'tint' : 'white'}>
        <Icon name={icon} size={17} />
      </IconBox>
      <div className="grow">
        <p style={{ fontWeight: unread ? 600 : 400 }}>{title}</p>
        <p className="small muted">{meta}</p>
      </div>
      {unread && (
        <span className="unread-dot">
          <span className="sr-only">Unread</span>
        </span>
      )}
    </>
  )
  const className = 'row gap12 start list-row'
  return to ? (
    <Link to={to} className={className}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  )
}
