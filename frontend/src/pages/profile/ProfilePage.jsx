import { useState } from 'react'
import { useNavigate } from 'react-router'
import { api, apiUrl, download } from '../../api/client'
import useApi from '../../api/useApi'
import { useAuth } from '../../auth/AuthContext'
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  ErrorMessage,
  GoogleLogo,
  Icon,
  Loading,
  Modal,
  TextField,
  Toggle,
  useToast,
} from '../../components'
import AppLayout from '../../layouts/AppLayout'
import { formatDate } from '../../lib/datetime'
import { plural } from '../../lib/format'
import { PasswordForm } from './PasswordForm'

// Figma 11: profile and account.
export default function ProfilePage() {
  const { user, setUser, refresh } = useAuth()
  return (
    <AppLayout title="Profile and account" subtitle="Manage your details, sign-in methods and emails">
      <div className="row gap24 start stack-sm">
        <div className="col gap24 grow" style={{ minWidth: 0 }}>
          <DetailsCard user={user} setUser={setUser} refresh={refresh} />
          <SignInCard user={user} refresh={refresh} />
          <DeleteCard />
        </div>
        <div className="col gap24 side-col" style={{ width: 420 }}>
          <PreferencesCard />
          <Card as="section" className="col gap8">
            <h3>Your data</h3>
            <p className="small muted">Download everything Unison holds about you as a JSON file.</p>
            <Button variant="secondary" icon="download" style={{ alignSelf: 'flex-start' }} onClick={() => download('/users/me/personal-data')}>
              Export my data
            </Button>
          </Card>
        </div>
      </div>
    </AppLayout>
  )
}

function DetailsCard({ user, setUser, refresh }) {
  const toast = useToast()
  const [name, setName] = useState(user.name)
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const primary = user.emails.find((e) => e.is_primary)
  const second = user.emails.find((e) => !e.is_primary)

  async function save() {
    setBusy(true)
    setError(null)
    try {
      const me = await api.patch('/users/me', { name: name.trim() })
      setUser(me)
      toast('Your details were saved')
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  async function emailAction(fn, message) {
    setError(null)
    try {
      await fn()
      toast(message)
      await refresh()
    } catch (err) {
      setError(err)
    }
  }

  return (
    <Card as="section" className="col gap16" aria-labelledby="details-title">
      <h3 id="details-title">Your details</h3>
      <div className="row gap16 wrap">
        <Avatar name={user.name} size="large" />
        <TextField className="grow" label="Full name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
        <div className="grow">
          <span className="lbl">Institute email</span>
          <div className="inp f" aria-label={`Institute email ${primary?.email}, cannot be changed here`}>
            <Icon name="lock" size={15} />
            {primary?.email}
          </div>
        </div>
      </div>
      <div className="row gap16 wrap">
        <div className="grow">
          <span className="lbl">Additional verified email</span>
          {second ? (
            <div className="inp f">
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{second.email}</span>
              <Badge tone={second.verified ? 'green' : 'amber'} style={{ marginLeft: 'auto' }}>
                {second.verified ? 'Verified' : 'Not verified'}
              </Badge>
            </div>
          ) : (
            <div className="inp">No second email. Invitations to it would also reach you.</div>
          )}
        </div>
        {second ? (
          <div className="row gap8" style={{ alignSelf: 'flex-end' }}>
            {!second.verified && (
              <Button variant="secondary" size="small" onClick={() => emailAction(() => api.post(`/users/me/emails/${second.id}/verifications`), 'Verification link sent')}>
                Resend link
              </Button>
            )}
            {second.verified && (
              <Button variant="secondary" size="small" onClick={() => emailAction(() => api.patch(`/users/me/emails/${second.id}`, { is_primary: true }), 'Primary email changed')}>
                Make primary
              </Button>
            )}
            <Button variant="danger" size="small" onClick={() => emailAction(() => api.delete(`/users/me/emails/${second.id}`), 'Email removed')}>
              Remove
            </Button>
          </div>
        ) : (
          <Button variant="secondary" style={{ alignSelf: 'flex-end' }} onClick={() => setAdding(true)}>
            Add email
          </Button>
        )}
      </div>
      {primary && !primary.verified && <Alert tone="info">Your institute email is not verified yet. Check your inbox for the link.</Alert>}
      <ErrorMessage error={error} />
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <Button onClick={save} disabled={busy || !name.trim()}>
          {busy ? 'Saving…' : 'Save changes'}
        </Button>
      </div>
      {adding && <AddEmail onClose={() => setAdding(false)} onAdded={async () => { setAdding(false); await refresh() }} />}
    </Card>
  )
}

function AddEmail({ onClose, onAdded }) {
  const toast = useToast()
  const [email, setEmail] = useState('')
  const [error, setError] = useState(null)
  async function add(event) {
    event.preventDefault()
    try {
      await api.post('/users/me/emails', { email: email.trim() })
      toast('Check that inbox for the verification link')
      onAdded()
    } catch (err) {
      setError(err)
    }
  }
  return (
    <Modal title="Add a second email" onClose={onClose}>
      <form className="col gap16" onSubmit={add}>
        <p className="small muted">We send a link to confirm it. Once verified, invitations sent to it reach this account.</p>
        <TextField label="Email" icon="mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <ErrorMessage error={error} />
        <Button type="submit" disabled={!email}>
          Send verification link
        </Button>
      </form>
    </Modal>
  )
}

function SignInCard({ user, refresh }) {
  const toast = useToast()
  const config = useApi(() => api.get('/auth/config'), [])
  const [changing, setChanging] = useState(false)
  const [error, setError] = useState(null)
  const primary = user.emails.find((e) => e.is_primary)?.email

  async function unlink() {
    setError(null)
    try {
      await api.delete('/users/me/google')
      toast('Google is unlinked')
      refresh()
    } catch (err) {
      setError(err)
    }
  }

  return (
    <Card as="section" className="col gap12" aria-labelledby="signin-title">
      <h3 id="signin-title">Sign-in methods</h3>
      <div className="row gap12">
        <GoogleLogo />
        <div className="grow">
          <b>Google</b>
          <p className="small muted">
            {user.google_linked ? `Linked to ${primary}` : config.data?.google_enabled ? 'Not linked' : 'Not set up on this server'}
          </p>
        </div>
        {user.google_linked ? (
          <Button variant="secondary" size="small" onClick={unlink} disabled={!user.has_password} title={user.has_password ? undefined : 'Set a password first'}>
            Unlink
          </Button>
        ) : (
          config.data?.google_enabled && (
            <a className="btn o sm" href={apiUrl('/auth/google', { return_to: '/profile' }).toString()}>
              Link Google
            </a>
          )
        )}
      </div>
      <div className="row gap12">
        <Icon name="lock" size={18} color="var(--color-primary)" />
        <div className="grow">
          <b>Password</b>
          <p className="small muted">{user.has_password ? `Account created ${formatDate(user.created_at)}` : 'No password yet: you sign in with Google'}</p>
        </div>
        <Button variant="secondary" size="small" onClick={() => setChanging(true)}>
          {user.has_password ? 'Change password' : 'Set a password'}
        </Button>
      </div>
      <ErrorMessage error={error} />
      {changing && (
        <Modal title={user.has_password ? 'Change password' : 'Set a password'} onClose={() => setChanging(false)}>
          <p className="small muted">You stay logged in here; other devices are logged out.</p>
          <PasswordForm
            hasPassword={user.has_password}
            onDone={() => {
              setChanging(false)
              toast('Password changed')
              refresh()
            }}
          />
        </Modal>
      )}
    </Card>
  )
}

function DeleteCard() {
  const preview = useApi(() => api.get('/users/me/deletion'), [])
  const [asking, setAsking] = useState(false)
  const p = preview.data
  return (
    <Card as="section" className="col gap12" style={{ borderColor: 'var(--color-danger-border)' }} aria-labelledby="delete-title">
      <h3 id="delete-title" className="red">
        Delete account
      </h3>
      <p className="small muted">
        Your account is deactivated at once and deleted after {p?.grace_days ?? 7} days; logging back in within that time cancels it. Team
        work you uploaded stays with your team as "Former member".
        {p && ` You are in ${plural(p.running_courses, 'running course')} and ${plural(p.active_teams, 'team')}.`}
      </p>
      {p && !p.can_delete && <Alert tone="info">You are the last administrator. Make someone else an administrator first.</Alert>}
      <div className="row gap12 wrap">
        <Button variant="secondary" icon="download" onClick={() => download('/users/me/personal-data')}>
          Download my data first
        </Button>
        <Button variant="danger" icon="trash" iconColor="var(--color-red)" onClick={() => setAsking(true)} disabled={!p?.can_delete}>
          Delete my account
        </Button>
      </div>
      {asking && <DeleteDialog preview={p} onClose={() => setAsking(false)} />}
    </Card>
  )
}

function DeleteDialog({ preview, onClose }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  if (!preview) return <Loading />

  async function remove(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const res = await api.post('/users/me/deletion', { password: user.has_password ? password : null })
      await logout().catch(() => null)
      navigate(`/login?deleted=${encodeURIComponent(res.final_deletion_at)}`, { replace: true })
    } catch (err) {
      if (err.code === 'REAUTH_REQUIRED') {
        window.location.href = apiUrl('/auth/google', { return_to: '/profile' }).toString()
        return
      }
      setError(err)
      setBusy(false)
    }
  }

  return (
    <Modal title="Delete your account?" onClose={onClose}>
      <form className="col gap16" onSubmit={remove}>
        <p className="small muted">
          You will be logged out everywhere. Your teammates and teachers are told. You can still cancel by logging in within{' '}
          {preview.grace_days} days.
        </p>
        {user.has_password ? (
          <TextField
            label="Confirm with your password"
            icon="lock"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        ) : (
          <p className="small muted">You sign in with Google, so we ask Google to confirm it is you.</p>
        )}
        <ErrorMessage error={error} />
        <div className="row gap12" style={{ justifyContent: 'flex-end' }}>
          <Button variant="secondary" onClick={onClose}>
            Keep my account
          </Button>
          <Button type="submit" variant="danger" disabled={busy || (user.has_password && !password)}>
            {busy ? 'Deleting…' : 'Delete my account'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

// The design groups the email switches (Figma 11); each group turns several event types on or off.
const PREFERENCE_GROUPS = [
  ['Enrolment decisions', ['enrolment_approved', 'enrolment_rejected', 'removed_from_course']],
  ['Join requests (teachers)', ['join_request_received']],
  ['New resources (bundled)', ['resources_published']],
  ['Assignments published or extended', ['assignment_published', 'deadline_extended']],
  ['Final submitted or replaced', ['final_submitted', 'final_replaced', 'final_at_deadline']],
  ['Marks released', ['marks_released']],
]

function PreferencesCard() {
  const toast = useToast()
  const prefs = useApi(() => api.get('/users/me/notification-preferences', { size: 50 }), [])
  const [error, setError] = useState(null)
  const items = prefs.data?.items ?? []
  const grouped = new Set(PREFERENCE_GROUPS.flatMap(([, events]) => events))
  const groups = [
    ...PREFERENCE_GROUPS.map(([label, events]) => [label, events.filter((e) => items.some((p) => p.event_type === e))]),
    ...items.filter((p) => !grouped.has(p.event_type)).map((p) => [p.label, [p.event_type]]),
  ].filter(([, events]) => events.length > 0)

  async function flip(events, value) {
    const next = items.map((p) => (events.includes(p.event_type) ? { ...p, email_enabled: value } : p))
    prefs.setData((d) => ({ ...d, items: next }))
    try {
      await api.put('/users/me/notification-preferences', { items: next.map(({ event_type, email_enabled }) => ({ event_type, email_enabled })) })
      toast(value ? 'Emails on' : 'Emails off')
    } catch (err) {
      setError(err)
      prefs.reload()
    }
  }

  return (
    <Card as="section" className="col" aria-labelledby="prefs-title">
      <h3 id="prefs-title">Email notifications</h3>
      <p className="small muted" style={{ margin: '4px 0 6px' }}>
        In-app notifications always appear. Invitations, verification and password reset emails always send.
      </p>
      {prefs.loading && <Loading />}
      <ErrorMessage error={error ?? prefs.error} />
      {groups.map(([label, events]) => {
        const on = events.every((e) => items.find((p) => p.event_type === e)?.email_enabled)
        return (
          <div key={label} className="row between gap12" style={{ padding: '10px 0', borderBottom: '1px solid var(--color-row-divider)' }}>
            <span>{label}</span>
            <Toggle checked={on} onChange={(v) => flip(events, v)} label={`Email me: ${label}`} />
          </div>
        )
      })}
    </Card>
  )
}
