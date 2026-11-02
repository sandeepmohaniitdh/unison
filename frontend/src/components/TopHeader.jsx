import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import Avatar from './Avatar'
import Icon from './Icon'

// White header of every signed-in page: page title and subtitle, the notification bell
// with its red unread count, and the user chip with a small menu.
export default function TopHeader({
  title,
  subtitle,
  unreadCount = 0,
  user,
  notificationsPath = '/notifications',
  menuItems = [],
  onLogout,
  actions,
}) {
  const [open, setOpen] = useState(false)
  const wrap = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    function close(event) {
      if (event.type === 'keydown' && event.key !== 'Escape') return
      if (event.type === 'mousedown' && wrap.current?.contains(event.target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  return (
    <header className="top">
      <div className="grow" style={{ minWidth: 0 }}>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions}
      <Link
        to={notificationsPath}
        className="bellb"
        aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : 'Notifications'}
      >
        <Icon name="bell" size={20} />
        {unreadCount > 0 && (
          <span className="dot" aria-hidden="true">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </Link>
      <div className="menu-wrap" ref={wrap}>
        <button
          type="button"
          className="chip-user"
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <Avatar name={user.name} initials={user.initials} size="small" />
          {user.shortName}
          <Icon name="chevronDown" size={16} />
        </button>
        {open && (
          <div className="menu" role="menu">
            {menuItems.map((item) => (
              <Link key={item.to} to={item.to} role="menuitem" onClick={() => setOpen(false)}>
                {item.label}
              </Link>
            ))}
            {onLogout && (
              <button type="button" role="menuitem" className="red" onClick={onLogout}>
                Log out
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
