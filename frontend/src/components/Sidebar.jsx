import { NavLink } from 'react-router'
import cx from '../lib/cx'
import Avatar from './Avatar'
import Brand from './Brand'
import Icon from './Icon'

// Left sidebar: brand, navigation with active state and count badges, then the footer
// with the dark-mode switch, the signed-in user and "Log out".
// `items`: [{ to, label, icon, count?, end?, active? }] (see navItemsFor in navigation.js).
// `active` forces an item on or off, e.g. "My courses" while inside a course.
// On tablets and phones the sidebar is a drawer: `open` shows it, `onClose` hides it.
export default function Sidebar({ items, user, onLogout, onToggleDarkMode, darkMode = false, open = false, onClose }) {
  return (
    <aside className={cx('side', open && 'open')} id="app-menu" aria-label="Menu">
      <Brand to="/dashboard" />
      <button type="button" className="btn o sm side-close" onClick={onClose} aria-label="Close menu">
        <Icon name="close" size={20} />
      </button>
      <nav className="side-nav" aria-label="Main">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => cx('nav', (item.active ?? isActive) && 'on')}
            onClick={onClose}
            aria-current={item.active ? 'page' : undefined}
          >
            <Icon name={item.icon} />
            <span>{item.label}</span>
            {item.count > 0 && (
              <span className="cnt">
                {item.count > 99 ? '99+' : item.count}
                <span className="sr-only"> new</span>
              </span>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="sidefoot">
        <button type="button" className="nav" onClick={onToggleDarkMode} aria-pressed={darkMode}>
          <Icon name="moon" />
          <span>Dark mode</span>
        </button>
        <div className="who">
          <Avatar name={user.name} initials={user.initials} />
          <div style={{ minWidth: 0 }}>
            <b>{user.name}</b>
            <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.email}</span>
          </div>
        </div>
        <button type="button" className="nav red" onClick={onLogout}>
          <Icon name="logout" />
          <span>Log out</span>
        </button>
      </div>
    </aside>
  )
}
