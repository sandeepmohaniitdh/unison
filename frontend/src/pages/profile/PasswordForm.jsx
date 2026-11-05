import { useState } from 'react'
import { useNavigate } from 'react-router'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Button, ErrorMessage, TextField } from '../../components'
import { homeFor } from '../../components/navigation'
import { CenteredCard } from '../public/AccountLinkPages'

// Change (or, for Google-only accounts, set) the password. Used on the profile page and
// on the forced "change your password" page of the first administrator.
export function PasswordForm({ hasPassword = true, onDone, submitLabel = 'Save the new password' }) {
  const [current, setCurrent] = useState('')
  const [password, setPassword] = useState('')
  const [again, setAgain] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.put('/users/me/password', { current_password: hasPassword ? current : null, new_password: password })
      onDone?.()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="col gap16" onSubmit={onSubmit}>
      {hasPassword && (
        <TextField
          label="Current password"
          icon="lock"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
        />
      )}
      <TextField
        label="New password"
        icon="lock"
        type="password"
        autoComplete="new-password"
        placeholder="At least 8 characters"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      <div>
        <TextField
          label="Type it again"
          icon="lock"
          type="password"
          autoComplete="new-password"
          value={again}
          onChange={(e) => setAgain(e.target.value)}
          required
        />
        {again && again !== password && <p className="field-error">The two passwords are different.</p>}
      </div>
      <ErrorMessage error={error} />
      <Button
        type="submit"
        full
        disabled={busy || password.length < 8 || password !== again || (hasPassword && !current)}
      >
        {busy ? 'Saving…' : submitLabel}
      </Button>
    </form>
  )
}

// The first administrator logs in with ADMIN_PASSWORD and must choose a new password.
export default function ChangePasswordPage() {
  const { user, refresh } = useAuth()
  const navigate = useNavigate()
  return (
    <CenteredCard icon="lock" eyebrow="First login" title="Choose your own password">
      <Alert tone="info">
        {user?.name}, your account was created with a temporary password. Choose a new one to continue.
      </Alert>
      <PasswordForm
        hasPassword={user?.has_password ?? true}
        onDone={async () => {
          const me = await refresh()
          navigate(homeFor(me?.role ?? 'student'), { replace: true })
        }}
      />
    </CenteredCard>
  )
}
