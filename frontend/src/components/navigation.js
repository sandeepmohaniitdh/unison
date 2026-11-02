// Sidebar items for each role, as drawn in the Figma screens (05, 07 and 10).
export function navItemsFor(role, counts = {}) {
  if (role === 'admin') {
    return [
      { to: '/admin', label: 'Overview', icon: 'chart', end: true },
      { to: '/admin/users', label: 'Users', icon: 'users' },
      { to: '/admin/courses', label: 'Courses', icon: 'grid' },
      { to: '/admin/departments', label: 'Departments', icon: 'book' },
      { to: '/admin/audit-log', label: 'Audit log', icon: 'shield' },
      { to: '/admin/settings', label: 'Settings', icon: 'settings' },
    ]
  }
  const items = [
    { to: '/dashboard', label: 'Dashboard', icon: 'home' },
    { to: '/courses', label: 'My courses', icon: 'grid' },
  ]
  if (role === 'teacher') {
    items.push({ to: '/join-requests', label: 'Join requests', icon: 'users', count: counts.joinRequests })
  }
  items.push(
    { to: '/notifications', label: 'Notifications', icon: 'bell', count: counts.notifications },
    { to: '/profile', label: 'Profile', icon: 'user' },
  )
  return items
}

// Where each role lands after logging in.
export function homeFor(role) {
  return role === 'admin' ? '/admin' : '/dashboard'
}
