import { Link, NavLink } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { Avatar, Button, Icon, PublicLayout } from '../components'
import { homeFor } from '../components/navigation'
import { shortName } from '../lib/format'

// Top bar of the public pages (Figma 01 and 04): brand, "Courses" and "About", then
// "Log in" and "Sign up", or the user chip when someone is logged in.
export default function PublicPage({ children, links = true }) {
  const { user, status } = useAuth()
  const linkClass = ({ isActive }) => (isActive ? 'text-primary' : 'muted')
  const nav = (
    <>
      {links ? (
        <nav className="row gap24 grow" style={{ marginLeft: 24 }} aria-label="Main">
          <NavLink to="/catalogue" className={linkClass} style={({ isActive }) => ({ fontWeight: isActive ? 700 : 400 })}>
            Courses
          </NavLink>
          <NavLink to="/about" className={linkClass} style={({ isActive }) => ({ fontWeight: isActive ? 700 : 400 })}>
            About
          </NavLink>
        </nav>
      ) : (
        <div className="grow" />
      )}
      {status === 'in' && user ? (
        <Link to={homeFor(user.role)} className="chip-user" aria-label={`${user.name}: open your dashboard`}>
          <Avatar name={user.name} size="small" />
          {shortName(user.name)}
          <Icon name="chevronDown" size={16} />
        </Link>
      ) : (
        status === 'out' && (
          <>
            <Button variant="secondary" to="/login">
              Log in
            </Button>
            <Button to="/signup">Sign up</Button>
          </>
        )
      )}
    </>
  )
  return <PublicLayout nav={nav}>{children}</PublicLayout>
}
