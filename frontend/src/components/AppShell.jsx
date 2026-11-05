import { useEffect, useState } from 'react'
import { useLocation } from 'react-router'
import Brand from './Brand'
import Icon from './Icon'
import Sidebar from './Sidebar'
import TopHeader from './TopHeader'
import { navItemsFor } from './navigation'

// Layout of every signed-in page (Figma screens 02 and 05 to 11):
// sidebar on the left, header on top, page content below.
//
//   <AppShell user={user} title="Good morning, Sandeep" subtitle="..." unreadCount={3}>
//     ...page content...
//   </AppShell>
//
// `user`: { name, email, role, shortName, initials? }. `activeNav` is the path of the
// sidebar item to highlight (for pages inside a course, "My courses").
// Up to 1024 px wide the sidebar becomes a drawer, opened from the menu button in a slim
// top bar.
export default function AppShell({
  user,
  title,
  subtitle,
  unreadCount = 0,
  counts,
  navItems,
  activeNav,
  headerActions,
  menuItems,
  contentClassName,
  contentStyle,
  onLogout,
  onToggleDarkMode,
  darkMode = false,
  children,
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  // Close the drawer on every page change, and with Escape.
  useEffect(() => setMenuOpen(false), [location.pathname])
  useEffect(() => {
    if (!menuOpen) return undefined
    const onKey = (event) => event.key === 'Escape' && setMenuOpen(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [menuOpen])

  const items = (navItems ?? navItemsFor(user.role, { notifications: unreadCount, ...counts })).map((item) =>
    activeNav ? { ...item, active: item.to === activeNav } : item,
  )
  return (
    <div className="app">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <div className="mobilebar">
        <Brand to="/dashboard" />
        <button
          type="button"
          className="btn o sm"
          onClick={() => setMenuOpen(true)}
          aria-expanded={menuOpen}
          aria-controls="app-menu"
        >
          <Icon name="menu" size={18} />
          Menu
        </button>
      </div>
      {menuOpen && <div className="side-backdrop" onClick={() => setMenuOpen(false)} aria-hidden="true" />}
      <Sidebar
        items={items}
        user={user}
        onLogout={onLogout}
        onToggleDarkMode={onToggleDarkMode}
        darkMode={darkMode}
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
      />
      <div className="main">
        <TopHeader
          title={title}
          subtitle={subtitle}
          unreadCount={unreadCount}
          user={user}
          menuItems={menuItems}
          onLogout={onLogout}
          actions={headerActions}
        />
        <main id="main" className={['content', contentClassName].filter(Boolean).join(' ')} style={contentStyle}>
          {children}
        </main>
      </div>
    </div>
  )
}
