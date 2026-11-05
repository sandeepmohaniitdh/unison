import { useNavigate } from 'react-router'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { Icon, IconBox } from '../../components'
import { formatShort } from '../../lib/datetime'
import { notificationIcon, notificationLink } from '../../lib/notifications'

// Rows of notifications as in Figma 05. Clicking one marks it read and opens its page.
// `courseCodes` maps course ids to codes for the "CS301 · 2 Nov, 18:12 IST" line.
export default function NotificationList({ items, courseCodes = {}, onChange }) {
  const navigate = useNavigate()
  const { refreshCounts } = useAuth()

  async function open(n) {
    if (!n.read) {
      try {
        await api.patch(`/notifications/${n.id}`, { read: true })
        onChange?.({ ...n, read: true })
        refreshCounts()
      } catch {
        // opening the page matters more than the read mark
      }
    }
    navigate(notificationLink(n.link))
  }

  return (
    <ul style={{ listStyle: 'none' }}>
      {items.map((n) => {
        const meta = [courseCodes[n.course_id], formatShort(n.created_at)].filter(Boolean).join(' · ')
        return (
          <li key={n.id}>
            <button
              type="button"
              className="row gap12 start list-row hoverable"
              style={{ width: '100%', textAlign: 'left' }}
              onClick={() => open(n)}
            >
              <IconBox size={36} tone={n.read ? 'white' : 'tint'}>
                <Icon name={notificationIcon(n.event_type)} size={17} />
              </IconBox>
              <div className="grow">
                <p style={{ fontWeight: n.read ? 400 : 600 }}>{n.title}</p>
                <p className="small muted">{meta}</p>
              </div>
              {!n.read && (
                <span className="unread-dot">
                  <span className="sr-only">Unread</span>
                </span>
              )}
            </button>
          </li>
        )
      })}
    </ul>
  )
}
