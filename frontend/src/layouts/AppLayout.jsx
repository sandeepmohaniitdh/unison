import { useState } from 'react'
import { useNavigate } from 'react-router'
import { primaryEmail, useAuth } from '../auth/AuthContext'
import { AppShell } from '../components'
import { shortName } from '../lib/format'
import { toggleTheme } from '../lib/theme'

// Every signed-in page uses this: the design's sidebar and header, filled in with the
// logged-in user, the unread count and (for teachers) the number of join requests.
export default function AppLayout({ title, subtitle, activeNav, headerActions, contentStyle, contentClassName, children }) {
  const { user, unread, joinRequests, logout } = useAuth()
  const navigate = useNavigate()
  const [dark, setDark] = useState(() => document.documentElement.dataset.theme === 'dark')

  async function onLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  const shellUser = {
    name: user.name,
    email: primaryEmail(user),
    role: user.role,
    shortName: shortName(user.name),
  }
  const menuItems =
    user.role === 'admin'
      ? [
          { to: '/admin', label: 'Admin overview' },
          { to: '/notifications', label: 'Notifications' },
          { to: '/profile', label: 'Profile and account' },
          { to: '/catalogue', label: 'Course catalogue' },
        ]
      : [
          { to: '/dashboard', label: 'Dashboard' },
          { to: '/profile', label: 'Profile and account' },
          { to: '/catalogue', label: 'Course catalogue' },
        ]

  return (
    <AppShell
      user={shellUser}
      title={title}
      subtitle={subtitle}
      unreadCount={unread}
      counts={{ joinRequests }}
      activeNav={activeNav}
      headerActions={headerActions}
      menuItems={menuItems}
      contentStyle={contentStyle}
      contentClassName={contentClassName}
      onLogout={onLogout}
      darkMode={dark}
      onToggleDarkMode={() => setDark(toggleTheme() === 'dark')}
    >
      {children}
    </AppShell>
  )
}
