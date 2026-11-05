import { useAuth } from '../../auth/AuthContext'
import { Button } from '../../components'
import { homeFor } from '../../components/navigation'
import { CenteredCard } from './AccountLinkPages'

export default function NotFoundPage() {
  const { user } = useAuth()
  return (
    <CenteredCard icon="search" eyebrow="Error 404" title="This page does not exist">
      <p className="muted small" style={{ textAlign: 'center' }}>
        The link may be old, or the page was moved. Check the address, or start again from here.
      </p>
      <Button to={user ? homeFor(user.role) : '/catalogue'} full>
        {user ? 'Go to your dashboard' : 'Browse courses'}
      </Button>
    </CenteredCard>
  )
}
