import { useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router'
import { apiUrl } from '../../api/client'
import useApi from '../../api/useApi'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { rememberChoice } from '../../auth/session'
import { Alert, Button, Card, Checkbox, ErrorMessage, GoogleLogo, Icon, Tabs, TextField } from '../../components'
import { homeFor } from '../../components/navigation'

// Only paths inside this site are allowed as "next" (no redirects to other sites).
export function safeNext(next) {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : null
}

// Figma 03: sign up and log in. The left half is the purple brand panel.
export default function LoginPage({ mode = 'login' }) {
  const { user, status } = useAuth()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const next = safeNext(params.get('next'))
  const config = useApi(() => api.get('/auth/config'), [])

  if (status === 'in' && user) {
    return <Navigate to={user.must_change_password ? '/change-password' : (next ?? homeFor(user.role))} replace />
  }

  const tab = mode === 'signup' ? 'signup' : 'login'
  const query = params.toString() ? `?${params}` : ''
  return (
    <div className="screen-auth" style={{ display: 'flex', minHeight: '100vh', background: 'var(--color-canvas)' }}>
      <BrandPanel />
      <main id="main" className="grow" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, minWidth: 0 }}>
        <Card className="col gap16" style={{ width: 440, maxWidth: '100%', padding: 36 }}>
          <Tabs
            label="Log in or sign up"
            tabs={[
              { id: 'login', label: 'Log in' },
              { id: 'signup', label: 'Sign up' },
            ]}
            value={tab}
            onChange={(id) => navigate(`/${id}${query}`, { replace: true })}
            style={{ justifyContent: 'center' }}
          />
          {tab === 'login' ? (
            <LoginForm config={config.data} next={next} />
          ) : (
            <SignupForm config={config.data} next={next} invitation={params.get('invitation')} />
          )}
        </Card>
      </main>
    </div>
  )
}

function BrandPanel() {
  const ticks = [
    'Private team drafts with full history',
    "Any member can submit the team's final",
    'In-app and email notifications',
  ]
  return (
    <div
      className="auth-panel"
      style={{
        width: 620,
        flex: 'none',
        background: 'var(--color-primary-strong, var(--color-primary))',
        color: '#fff',
        padding: 64,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: 32,
      }}
    >
      <Link to="/catalogue" className="row gap12" aria-label="Unison for IIT Dharwad, course catalogue">
        <div style={{ background: '#fff', borderRadius: 14, padding: 8 }}>
          <img src="/assets/iitdh_logo.png" alt="" style={{ width: 52, height: 60, objectFit: 'contain' }} />
        </div>
        <div>
          <b style={{ fontSize: 24 }}>Unison</b>
          <p style={{ opacity: 0.8 }}>for IIT Dharwad</p>
        </div>
      </Link>
      <div className="col gap16">
        <h1 style={{ fontSize: 40, lineHeight: 1.15 }}>
          Group work,
          <br />
          handed in together.
        </h1>
        <p style={{ fontSize: 16, opacity: 0.85, maxWidth: 430 }}>
          Share drafts with your team, submit one final for everyone, and get notified the moment anything changes.
        </p>
        <ul className="col gap12" style={{ marginTop: 8, listStyle: 'none' }}>
          {ticks.map((text) => (
            <li key={text} className="row gap12">
              <Icon name="check" size={18} color="#F6B35C" strokeWidth={2.4} />
              <span>{text}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="small" style={{ opacity: 0.7 }}>
        A student-built course project · CS602C
      </p>
    </div>
  )
}

function GoogleButton({ config, next }) {
  const [note, setNote] = useState(false)
  const enabled = config?.google_enabled
  const href = apiUrl('/auth/google', { return_to: next ?? '/dashboard' }).toString()
  return (
    <div className="col gap4">
      <a
        href={href}
        className="btn o full"
        style={{ height: 46, color: 'var(--color-text)' }}
        onClick={(e) => {
          if (!enabled) {
            e.preventDefault()
            setNote(true)
          }
        }}
      >
        <GoogleLogo /> Continue with Google
      </a>
      {note && (
        <p className="tiny muted" role="status" style={{ textAlign: 'center' }}>
          Google sign-in is not set up on this server. Use your email and password.
        </p>
      )}
    </div>
  )
}

function Divider() {
  return (
    <div className="row gap12 muted small" aria-hidden="true">
      <div className="grow" style={{ height: 1, background: 'var(--color-border)' }} />
      or
      <div className="grow" style={{ height: 1, background: 'var(--color-border)' }} />
    </div>
  )
}

function LoginForm({ config, next }) {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [keep, setKeep] = useState(true)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [params] = useSearchParams()

  async function onSubmit(event) {
    event.preventDefault()
    if (!email.trim() || !password) {
      setError({ message: 'Type your institute email and your password.' })
      return
    }
    setBusy(true)
    setError(null)
    try {
      const me = await login(email.trim(), password)
      rememberChoice(keep)
      navigate(me.must_change_password ? '/change-password' : (next ?? homeFor(me.role)), { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const domain = config?.allowed_email_domain ?? 'iitdh.ac.in'
  return (
    <form className="col gap16" onSubmit={onSubmit} noValidate>
      <div style={{ textAlign: 'center' }}>
        <h2 style={{ fontSize: 24 }}>Welcome back</h2>
        <p className="muted small" style={{ marginTop: 4 }}>
          Only @{domain} accounts are allowed
        </p>
      </div>
      {params.get('error') && <Alert tone="error">{googleError(params.get('error'))}</Alert>}
      {params.get('reset') === 'done' && <Alert tone="success">Your password was changed. Log in with the new one.</Alert>}
      {params.get('deleted') && (
        <Alert tone="info">
          Your account is deactivated and will be deleted after 7 days. Log in again before then to cancel the deletion.
        </Alert>
      )}
      <GoogleButton config={config} next={next} />
      <Divider />
      <TextField
        label="Institute email"
        icon="mail"
        type="email"
        autoComplete="email"
        placeholder={`you@${domain}`}
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <TextField
        label="Password"
        icon="lock"
        type="password"
        autoComplete="current-password"
        placeholder="Your password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      <div className="row between small">
        <Checkbox checked={keep} onChange={setKeep}>
          Keep me signed in
        </Checkbox>
        <Link to="/forgot-password" className="link">
          Forgot password?
        </Link>
      </div>
      <ErrorMessage error={error} />
      <Button type="submit" full style={{ height: 46 }} disabled={busy}>
        {busy ? 'Logging in…' : 'Log in'}
      </Button>
      <p className="tiny muted" style={{ textAlign: 'center' }}>
        New here? Sign up creates a student account. Teachers join through an invitation from the administrator.
      </p>
    </form>
  )
}

function googleError(code) {
  const messages = {
    GOOGLE_EMAIL_NOT_VERIFIED: 'Google says this email is not verified.',
    EMAIL_DOMAIN_NOT_ALLOWED: 'Only institute accounts can sign in.',
    ACCOUNT_SUSPENDED: 'Your account is suspended. Contact an administrator.',
  }
  return messages[code] ?? 'Google sign-in did not work. Please try again.'
}

function SignupForm({ config, next, invitation }) {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', password: '', consent: false })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const domain = config?.allowed_email_domain ?? 'iitdh.ac.in'
  const short = form.password.length > 0 && form.password.length < 8

  async function onSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const me = await register({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
        consent: form.consent,
        invitation_token: invitation || null,
      })
      rememberChoice(true)
      navigate(next ?? homeFor(me.role), { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="col gap16" onSubmit={onSubmit} noValidate>
      <div style={{ textAlign: 'center' }}>
        <h2 style={{ fontSize: 24 }}>Create your account</h2>
        <p className="muted small" style={{ marginTop: 4 }}>
          Only @{domain} accounts are allowed
        </p>
      </div>
      <GoogleButton config={config} next={next} />
      <Divider />
      <TextField label="Full name" icon="user" autoComplete="name" placeholder="Your name" value={form.name} onChange={set('name')} required />
      <TextField
        label="Institute email"
        icon="mail"
        type="email"
        autoComplete="email"
        placeholder={`you@${domain}`}
        value={form.email}
        onChange={set('email')}
        required
      />
      <div>
        <TextField
          label="Password"
          icon="lock"
          type="password"
          autoComplete="new-password"
          placeholder="At least 8 characters"
          value={form.password}
          onChange={set('password')}
          required
          aria-describedby="password-hint"
        />
        <p id="password-hint" className={short ? 'field-error' : 'tiny muted'} style={{ marginTop: 4 }}>
          At least 8 characters. A long phrase is easier to remember than symbols.
        </p>
      </div>
      <Checkbox checked={form.consent} onChange={(v) => setForm((f) => ({ ...f, consent: v }))} className="small">
        <span>
          I agree that Unison stores my name, email and course work to run the course (see <Link to="/about#privacy" className="link">privacy</Link>).
        </span>
      </Checkbox>
      <ErrorMessage error={error} />
      <Button
        type="submit"
        full
        style={{ height: 46 }}
        disabled={busy || !form.name || !form.email || form.password.length < 8 || !form.consent}
      >
        {busy ? 'Creating your account…' : 'Sign up'}
      </Button>
      <p className="tiny muted" style={{ textAlign: 'center' }}>
        Sign up creates a student account. Teachers join through an invitation from the administrator.
      </p>
    </form>
  )
}
