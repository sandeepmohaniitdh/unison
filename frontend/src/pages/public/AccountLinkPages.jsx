import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Button, Card, ErrorMessage, Icon, IconBox, TextField } from '../../components'
import { homeFor } from '../../components/navigation'
import PublicPage from '../../layouts/PublicNav'

// Pages opened from emailed links, in the style of Figma 04: a centred card under the
// public top bar. Not drawn in Figma; built from the same components.

export function CenteredCard({ icon, eyebrow, title, children, width = 480 }) {
  return (
    <PublicPage links={false}>
      <main
        id="main"
        className="grow"
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '116px 16px 48px', minWidth: 0, width: '100%' }}
      >
        <Card className="col gap20 centered-card" style={{ width, maxWidth: '100%' }}>
          <div className="col gap12" style={{ alignItems: 'center', textAlign: 'center' }}>
            {icon && (
              <IconBox size={64} tone="soft" radius={20}>
                <Icon name={icon} size={30} />
              </IconBox>
            )}
            <div>
              {eyebrow && <div className="eyebrow">{eyebrow}</div>}
              <h1 style={{ fontSize: 26, marginTop: eyebrow ? 6 : 0 }}>{title}</h1>
            </div>
          </div>
          {children}
        </Card>
      </main>
    </PublicPage>
  )
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const res = await api.post('/auth/password-reset-requests', { email: email.trim() })
      setSent(res.message)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <CenteredCard icon="lock" eyebrow="Password" title="Forgot your password?">
      {sent ? (
        <>
          <Alert tone="success">{sent}</Alert>
          <p className="small muted" style={{ textAlign: 'center' }}>
            The link works once and only for 30 minutes. Check your spam folder if nothing arrives.
          </p>
          <Button variant="secondary" to="/login" full>
            Back to log in
          </Button>
        </>
      ) : (
        <form className="col gap16" onSubmit={onSubmit}>
          <p className="muted small" style={{ textAlign: 'center' }}>
            Type the email of your account. If it exists, we send a link to choose a new password.
          </p>
          <TextField
            label="Email"
            icon="mail"
            type="email"
            autoComplete="email"
            placeholder="you@iitdh.ac.in"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <ErrorMessage error={error} />
          <Button type="submit" full disabled={busy || !email}>
            {busy ? 'Sending…' : 'Email me a reset link'}
          </Button>
          <Link to="/login" className="link small" style={{ textAlign: 'center' }}>
            Back to log in
          </Link>
        </form>
      )}
    </CenteredCard>
  )
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [again, setAgain] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const mismatch = again.length > 0 && again !== password

  async function onSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.post('/auth/password-resets', { token, new_password: password })
      navigate('/login?reset=done', { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <CenteredCard icon="lock" eyebrow="Password" title="Choose a new password">
      {!token ? (
        <Alert tone="error">This link is incomplete. Open the link from the email again, or ask for a new one.</Alert>
      ) : (
        <form className="col gap16" onSubmit={onSubmit}>
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
            {mismatch && <p className="field-error">The two passwords are different.</p>}
          </div>
          <ErrorMessage error={error} />
          <Button type="submit" full disabled={busy || password.length < 8 || password !== again}>
            {busy ? 'Saving…' : 'Save the new password'}
          </Button>
          <p className="tiny muted" style={{ textAlign: 'center' }}>
            Saving logs you out on every device. The link stops working once it is used.
          </p>
        </form>
      )}
      <Link to="/forgot-password" className="link small" style={{ textAlign: 'center' }}>
        Ask for a new link
      </Link>
    </CenteredCard>
  )
}

export function VerifyEmailPage() {
  const [params] = useSearchParams()
  const { user, refresh } = useAuth()
  const token = params.get('token') ?? ''
  const [state, setState] = useState({ busy: Boolean(token), result: null, error: null })
  const started = useRef(false)

  useEffect(() => {
    if (!token || started.current) return
    started.current = true
    api
      .post('/auth/email-verifications', { token })
      .then((result) => {
        setState({ busy: false, result, error: null })
        refresh()
      })
      .catch((error) => setState({ busy: false, result: null, error }))
  }, [token, refresh])

  return (
    <CenteredCard icon="mail" eyebrow="Email" title="Confirm your email">
      {!token && <Alert tone="error">This link is incomplete. Open the link from the email again.</Alert>}
      {state.busy && <p className="muted" style={{ textAlign: 'center' }}>Confirming…</p>}
      {state.result && <Alert tone="success">{state.result.message}</Alert>}
      <ErrorMessage error={state.error} />
      <Button to={user ? homeFor(user.role) : '/login'} full variant={state.result ? 'primary' : 'secondary'}>
        {user ? 'Go to your dashboard' : 'Log in'}
      </Button>
    </CenteredCard>
  )
}
