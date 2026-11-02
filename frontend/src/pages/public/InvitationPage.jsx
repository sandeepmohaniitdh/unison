import { useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router'
import { api, getAll } from '../../api/client'
import useApi from '../../api/useApi'
import { primaryEmail, useAuth } from '../../auth/AuthContext'
import { Alert, Button, Card, ErrorMessage, Icon, IconBox, Loading, PageError } from '../../components'
import { homeFor } from '../../components/navigation'
import PublicPage from '../../layouts/PublicNav'
import { formatDeadline } from '../../lib/datetime'
import { formatTerm } from '../../lib/format'

// Figma 04: one invitation (team, course or staff), with Accept and Decline.
// Opened from the email (/invitations/<token>) or from a notification (/invitations?id=7).
export default function InvitationPage() {
  const { token } = useParams()
  const [params] = useSearchParams()
  const id = params.get('id')
  const { user, status } = useAuth()

  const invitation = useApi(
    async () => {
      if (token) return api.get(`/invitation-links/${encodeURIComponent(token)}`)
      const mine = await getAll('/users/me/invitations')
      const found = mine.find((i) => String(i.id) === id)
      if (!found) {
        const err = new Error('This invitation is no longer pending.')
        err.status = 404
        throw err
      }
      return found
    },
    [token, id, status],
    { enabled: Boolean(token) || status === 'in' },
  )

  if (!token && status === 'out') {
    return (
      <Frame>
        <Alert tone="info">Log in to see your invitations.</Alert>
        <Button to={`/login?next=${encodeURIComponent(`/invitations?id=${id}`)}`} full>
          Log in
        </Button>
      </Frame>
    )
  }
  if (invitation.loading || status === 'loading' || (!invitation.data && !invitation.error)) return <Frame><Loading /></Frame>
  if (invitation.error) {
    return (
      <Frame>
        <PageError error={invitation.error} />
        <Button variant="secondary" to={user ? homeFor(user.role) : '/catalogue'} full>
          {user ? 'Go to your dashboard' : 'Browse courses'}
        </Button>
      </Frame>
    )
  }
  return <InvitationCard inv={invitation.data} token={token} user={user} reload={invitation.reload} />
}

function Frame({ children }) {
  return (
    <PublicPage links={false}>
      <main
        id="main"
        className="grow"
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '76px 16px 0' }}
      >
        <Card className="col gap20" style={{ width: 560, maxWidth: '100%', padding: 40, textAlign: 'center', alignItems: 'center' }}>
          {children}
        </Card>
      </main>
    </PublicPage>
  )
}

function describe(inv) {
  const from = inv.invited_by.name
  if (inv.kind === 'team') {
    const t = inv.team
    return {
      eyebrow: 'Team invitation',
      title: `Join team ${t.name}`,
      text: (
        <>
          {from} invited you to their team for <b style={{ color: 'var(--color-text)' }}>{t.assignment_title}</b>
          {inv.course && ` in ${inv.course.code} ${inv.course.title}`}.
        </>
      ),
      rows: [
        ['Team members', `${t.members.length} of ${t.max_team} · ${t.members.join(', ')}`],
        ['Deadline', formatDeadline(t.due_at)],
      ],
      accept: 'Accept and join team',
      note: 'Accepting declines your other team invitations for this assignment.',
    }
  }
  if (inv.kind === 'course') {
    const c = inv.course
    return {
      eyebrow: 'Course invitation',
      title: `Join ${c.code} ${c.title}`,
      text: (
        <>
          {from} invited you to join <b style={{ color: 'var(--color-text)' }}>{c.code} {c.title}</b> as a {inv.role}.
        </>
      ),
      rows: [['Term', formatTerm(c.term)]],
      accept: inv.role === 'teacher' ? 'Accept and teach this course' : 'Accept and join course',
      note: 'You can leave a course only by asking its teacher.',
    }
  }
  return {
    eyebrow: 'Staff invitation',
    title: inv.role === 'admin' ? 'Become an administrator' : 'Become a teacher on Unison',
    text: (
      <>
        {from} invited you to join Unison as {inv.role === 'admin' ? 'an administrator' : 'a teacher'}.
      </>
    ),
    rows: [],
    accept: 'Accept invitation',
    note: 'Your account gets the new role as soon as you accept.',
  }
}

const PROBLEMS = {
  expired: 'This invitation has expired. Ask the sender for a new one.',
  used: 'This invitation was already accepted.',
  cancelled: 'The sender cancelled this invitation.',
  declined: 'You declined this invitation.',
  email_not_verified: 'Confirm your email address first (Profile and account), then open this invitation again.',
}

function InvitationCard({ inv, token, user, reload }) {
  const navigate = useNavigate()
  const { refresh, logout, refreshCounts } = useAuth()
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const info = describe(inv)
  const here = token ? `/invitations/${token}` : `/invitations?id=${inv.id}`

  async function respond(statusValue) {
    setBusy(statusValue)
    setError(null)
    try {
      const path = token ? `/invitation-links/${encodeURIComponent(token)}` : `/invitations/${inv.id}`
      const res = await api.patch(path, { status: statusValue })
      refreshCounts()
      if (statusValue === 'declined') {
        navigate(homeFor(user.role), { replace: true })
        return
      }
      if (res.kind === 'team' && res.team_id) navigate(`/teams/${res.team_id}`, { replace: true })
      else if (res.kind === 'course' && res.course_id) navigate(`/courses/${res.course_id}`, { replace: true })
      else {
        const me = await refresh()
        navigate(homeFor(me?.role ?? user.role), { replace: true })
      }
    } catch (err) {
      setError(err)
      reload()
    } finally {
      setBusy(null)
    }
  }

  const pending = inv.status === 'pending' && !['expired', 'used', 'cancelled', 'declined'].includes(inv.problem)
  return (
    <Frame>
      <IconBox size={64} tone="soft" radius={20}>
        <Icon name={inv.kind === 'course' ? 'book' : inv.kind === 'staff' ? 'shield' : 'users'} size={30} />
      </IconBox>
      <div>
        <div className="eyebrow">{info.eyebrow}</div>
        <h1 style={{ fontSize: 26, marginTop: 6 }}>{info.title}</h1>
        <p className="muted" style={{ marginTop: 8 }}>
          {info.text}
        </p>
      </div>
      <Card className="col gap8" style={{ width: '100%', background: 'var(--color-surface-tint)', textAlign: 'left' }}>
        {info.rows.map(([label, value]) => (
          <div key={label} className="row between small gap12">
            <span className="muted">{label}</span>
            <b style={{ textAlign: 'right' }}>{value}</b>
          </div>
        ))}
        <div className="row between small gap12">
          <span className="muted">Invitation expires</span>
          <b>{formatDeadline(inv.expires_at)}</b>
        </div>
        <div className="row between small gap12">
          <span className="muted">Sent to</span>
          <b>{inv.email}</b>
        </div>
      </Card>

      {!pending && <Alert tone="info">{PROBLEMS[inv.problem] ?? `This invitation is ${inv.status}.`}</Alert>}

      {pending && inv.problem === 'log_in' && (
        <>
          <p className="small muted">Log in or sign up with {inv.email} to answer.</p>
          <div className="row gap12" style={{ width: '100%' }}>
            <Button variant="secondary" className="grow" to={`/login?next=${encodeURIComponent(here)}`}>
              Log in
            </Button>
            <Button
              className="grow"
              to={`/signup?next=${encodeURIComponent(here)}${token ? `&invitation=${encodeURIComponent(token)}` : ''}`}
            >
              Sign up
            </Button>
          </div>
        </>
      )}

      {pending && inv.problem === 'wrong_account' && (
        <>
          <Alert tone="info">
            This invitation is for {inv.email}, but you are logged in as {primaryEmail(user)}. Add that email to your
            account (Profile and account), or log in with the right account.
          </Alert>
          <Button
            variant="secondary"
            full
            onClick={async () => {
              await logout()
              navigate(`/login?next=${encodeURIComponent(here)}`)
            }}
          >
            Log out and use another account
          </Button>
        </>
      )}

      {pending && inv.problem === 'email_not_verified' && (
        <>
          <Alert tone="info">{PROBLEMS.email_not_verified}</Alert>
          <Button variant="secondary" to="/profile" full>
            Open Profile and account
          </Button>
        </>
      )}

      {pending && (inv.can_accept || !inv.problem) && (
        <>
          <ErrorMessage error={error} className="full" />
          <div className="row gap12" style={{ width: '100%' }}>
            <Button variant="secondary" className="grow" onClick={() => respond('declined')} disabled={Boolean(busy)}>
              {busy === 'declined' ? 'Declining…' : 'Decline'}
            </Button>
            <Button className="grow" onClick={() => respond('accepted')} disabled={Boolean(busy)}>
              {busy === 'accepted' ? 'Joining…' : info.accept}
            </Button>
          </div>
          <p className="tiny muted">{info.note}</p>
        </>
      )}
    </Frame>
  )
}
