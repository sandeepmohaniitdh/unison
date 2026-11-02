import { useState } from 'react'
import { api } from '../../api/client'
import { Badge, Button, ErrorMessage, Modal, Select, TextField, useToast } from '../../components'
import { daysUntil } from '../../lib/datetime'
import { capitalise } from '../../lib/format'

// Shared pieces of the admin pages (Figma 10).

export function userStatusBadge(u) {
  if (u.status === 'deactivated' && u.deletion_requested_at) {
    const left = daysUntil(new Date(new Date(u.deletion_requested_at).getTime() + 7 * 86400000))
    return <Badge tone="red">Deletion in {left} {left === 1 ? 'day' : 'days'}</Badge>
  }
  const tones = { active: 'green', suspended: 'red', deactivated: 'grey', deleted: 'grey' }
  return <Badge tone={tones[u.status] ?? 'grey'}>{capitalise(u.status)}</Badge>
}

// The role picker in the users table: changing it asks the server at once.
export function RolePicker({ user, onChanged }) {
  const toast = useToast()
  const [error, setError] = useState(null)
  async function change(role) {
    setError(null)
    try {
      const row = await api.patch(`/admin/users/${user.id}`, { role })
      toast(`${user.name} is now ${role === 'admin' ? 'an admin' : `a ${role}`}`)
      onChanged(row)
    } catch (err) {
      setError(err)
    }
  }
  return (
    <div>
      <Select
        aria-label={`Role of ${user.name}`}
        filled
        boxClassName="small"
        boxStyle={{ height: 34, width: 120 }}
        chevronSize={14}
        options={[
          { value: 'student', label: 'Student' },
          { value: 'teacher', label: 'Teacher' },
          { value: 'admin', label: 'Admin' },
        ]}
        value={user.role}
        onChange={change}
        disabled={user.status === 'deleted'}
      />
      {error && <p className="field-error">{error.message}</p>}
    </div>
  )
}

// "Invite teacher or admin"
export function StaffInviteDialog({ onClose, onSent }) {
  const toast = useToast()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('teacher')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  async function send(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.post('/admin/staff-invitations', { email: email.trim(), role })
      toast(`Invitation sent to ${email.trim()}`)
      onSent?.()
      onClose()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal title="Invite a teacher or admin" onClose={onClose}>
      <form className="col gap16" onSubmit={send}>
        <p className="small muted">
          The link works once, for 7 days. Signing up through it creates the account with this role; an existing student account
          is upgraded when it accepts.
        </p>
        <TextField label="Email" icon="mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <Select
          label="Role"
          filled
          options={[
            { value: 'teacher', label: 'Teacher' },
            { value: 'admin', label: 'Admin' },
          ]}
          value={role}
          onChange={setRole}
        />
        <ErrorMessage error={error} />
        <Button type="submit" disabled={busy || !email}>
          {busy ? 'Sending…' : 'Send invitation'}
        </Button>
      </form>
    </Modal>
  )
}

// A readable line for an audit log entry:
// "Admin Office changed role of Dr. Rohan Kulkarni: Student → Teacher"
export function describeAudit(e) {
  const action = e.action.replaceAll('_', ' ')
  const name = e.after?.name ?? e.before?.name ?? e.after?.email ?? e.before?.email
  let change = ''
  if (e.before && e.after && typeof e.before === 'object' && typeof e.after === 'object') {
    const keys = Object.keys(e.after).filter((k) => k !== 'name' && JSON.stringify(e.before[k]) !== JSON.stringify(e.after[k]))
    change = keys
      .slice(0, 2)
      .map((k) => `${k.replaceAll('_', ' ')}: ${show(e.before[k])} → ${show(e.after[k])}`)
      .join(', ')
  } else if (e.after && typeof e.after === 'object') {
    change = Object.entries(e.after)
      .filter(([k, v]) => k !== 'name' && v !== name)
      .slice(0, 2)
      .map(([k, v]) => `${k.replaceAll('_', ' ')}: ${show(v)}`)
      .join(', ')
  }
  const target = name ?? `${e.target_type.replace(/s$/, '')} #${e.target_id}`
  return { action, target, change }
}

function show(v) {
  if (v == null) return 'none'
  if (typeof v === 'boolean') return v ? 'yes' : 'no'
  if (typeof v === 'object') return JSON.stringify(v)
  const text = String(v)
  // Roles and statuses read better capitalised ("Student → Teacher"); emails and names stay as they are.
  return /^[a-z_]+$/.test(text) ? capitalise(text.replaceAll('_', ' ')) : text
}
