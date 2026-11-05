import { useState } from 'react'
import { api } from '../../../api/client'
import useApi from '../../../api/useApi'
import { Alert, Button, Card, ErrorMessage, TextArea, Toggle, useToast } from '../../../components'
import { plural } from '../../../lib/format'

// The right-hand cards of Figma 08.

// "Invite students": paste emails, one per line.
export function InviteStudentsCard({ courseId, archived, onSent, role = 'student' }) {
  const toast = useToast()
  const [text, setText] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const pending = useApi(() => api.get(`/courses/${courseId}/invitations`, { status: 'pending', size: 1 }), [courseId])
  const emails = [...new Set(text.split(/[\s,;]+/).map((e) => e.trim()).filter((e) => e.includes('@')))]

  async function send() {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.post(`/courses/${courseId}/invitations`, { emails, role })
      setResult(res)
      setText('')
      toast(`${plural(res.created.length, 'invitation')} sent`)
      pending.reload()
      onSent?.()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card as="section" className="col gap12" aria-labelledby="invite-title">
      <h3 id="invite-title">{role === 'teacher' ? 'Invite a co-teacher' : 'Invite students'}</h3>
      <p className="small muted">Paste institute emails, one per line. Each gets a single-use link valid for 7 days.</p>
      <TextArea
        aria-label="Emails to invite"
        boxClassName="small"
        placeholder={'cs26mt061@iitdh.ac.in\ncs26mt062@iitdh.ac.in'}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <ErrorMessage error={error} />
      {result?.skipped.length > 0 && (
        <Alert tone="info">
          Skipped: {result.skipped.map((s) => `${s.email} (${s.reason.replaceAll('_', ' ')})`).join(', ')}
        </Alert>
      )}
      <Button full onClick={send} disabled={busy || emails.length === 0 || archived}>
        {busy ? 'Sending…' : emails.length ? `Send ${plural(emails.length, 'invitation')}` : 'Send invitations'}
      </Button>
      <div className="row between small">
        <span className="muted">Pending invitations</span>
        <b>{pending.data?.total ?? '…'}</b>
      </div>
    </Card>
  )
}

// "Email notifications": the course's rules, shown as "event → who".
const SHOWN = [
  ['final_submitted', 'email_members', 'Final submitted → team members'],
  ['final_submitted', 'email_teachers', 'Final submitted → teachers'],
  ['join_request_received', 'email_teachers', 'Join request → teachers'],
]

export function EmailRulesCard({ courseId, archived, onShowAll }) {
  const toast = useToast()
  const rules = useApi(() => api.get(`/courses/${courseId}/notification-rules`, { size: 50 }), [courseId])
  const [error, setError] = useState(null)

  async function flip(eventType, field, value) {
    const items = rules.data.items.map((r) => (r.event_type === eventType ? { ...r, [field]: value } : r))
    rules.setData((d) => ({ ...d, items }))
    try {
      await api.put(`/courses/${courseId}/notification-rules`, {
        items: items.map(({ event_type, email_members, email_teachers }) => ({ event_type, email_members, email_teachers })),
      })
      toast('Email rule saved')
    } catch (err) {
      setError(err)
      rules.reload()
    }
  }

  return (
    <Card as="section" className="col gap12" aria-labelledby="rules-title">
      <h3 id="rules-title">Email notifications</h3>
      <ErrorMessage error={error ?? rules.error} />
      {rules.data &&
        SHOWN.map(([eventType, field, label]) => {
          const rule = rules.data.items.find((r) => r.event_type === eventType)
          if (!rule) return null
          return (
            <div key={label} className="row between gap12">
              <span className="small">{label}</span>
              <Toggle checked={rule[field]} onChange={(v) => flip(eventType, field, v)} label={label} disabled={archived} />
            </div>
          )
        })}
      <p className="tiny muted">
        In-app notifications are always on. Students can also turn emails off for themselves.
        {onShowAll && (
          <>
            {' '}
            <button type="button" className="link tiny" onClick={onShowAll}>
              All rules
            </button>
          </>
        )}
      </p>
    </Card>
  )
}

// "Teams": lock the teams of the assignment being edited.
export function TeamsLockCard({ assignment, onChanged, archived }) {
  const toast = useToast()
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const usable = assignment && assignment.kind === 'group' && assignment.status !== 'draft'

  async function setLock(value) {
    setBusy(true)
    setError(null)
    try {
      const saved = await api.patch(`/assignments/${assignment.id}`, { teams_locked: value })
      toast(value ? 'Teams locked' : 'Teams unlocked')
      onChanged(saved)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card as="section" className="col gap8" aria-labelledby="lock-title">
      <h3 id="lock-title">Teams</h3>
      <div className="row between small gap12">
        <span>Lock teams for this assignment</span>
        <Toggle
          checked={Boolean(assignment?.teams_locked)}
          onChange={setLock}
          label="Lock teams for this assignment"
          disabled={!usable || busy || archived}
        />
      </div>
      <p className="tiny muted">
        {usable
          ? "Locked teams can't add, leave or change members."
          : 'Choose a published group assignment to lock its teams.'}
      </p>
      <ErrorMessage error={error} />
    </Card>
  )
}
