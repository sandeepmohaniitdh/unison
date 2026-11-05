import { Navigate, useLocation } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { Loading } from '../components'
import { homeFor } from '../components/navigation'

// Pages for logged-in users. Others go to the login page and come back afterwards,
// except after "Log out": then the next login starts on that user's own home page.
// `roles` limits a page to some roles (for example the admin pages).
export default function RequireAuth({ roles, children }) {
  const { user, status, signedOut } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <Loading />
  if (status === 'out') {
    if (signedOut) return <Navigate to="/login" replace />
    const next = encodeURIComponent(location.pathname + location.search + location.hash)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  if (user.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }
  if (roles && !roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />
  return children
}
