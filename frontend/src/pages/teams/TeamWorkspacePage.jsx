import { useEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router'
import { api, download, getAll, newIdempotencyKey } from '../../api/client'
import useApi from '../../api/useApi'
import { useAuth } from '../../auth/AuthContext'
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  Confirm,
  Empty,
  ErrorMessage,
  Icon,
  IconBox,
  Loading,
  Modal,
  PageError,
  ProgressBar,
  TextField,
  UploadDropZone,
  useToast,
} from '../../components'
import AppLayout from '../../layouts/AppLayout'
import { formatDay, formatDayMonth, formatDeadline, isPast } from '../../lib/datetime'
import { emailUser, fileSize, percentOf, plural, points } from '../../lib/format'

// Figma 06 (and 06b once marks are released): the team workspace of one assignment.
export default function TeamWorkspacePage() {
  const { teamId } = useParams()
  const { user } = useAuth()
  const location = useLocation()
  const team = useApi(() => api.get(`/teams/${teamId}`), [teamId])
  const t = team.data
  const isMember = t?.members.some((m) => m.user.id === user.id && m.status === 'active')

  const assignment = useApi(() => (t ? api.get(`/assignments/${t.assignment_id}`) : Promise.resolve(null)), [t?.assignment_id], {
    enabled: Boolean(t),
  })
  const course = useApi(() => (t ? api.get(`/courses/${t.course_id}`) : Promise.resolve(null)), [t?.course_id], { enabled: Boolean(t) })

  if (t && !isMember && (user.role === 'admin' || course.data?.my_status === 'teacher')) {
    return <Navigate to={`/assignments/${t.assignment_id}/review?team=${t.id}`} replace />
  }

  const a = assignment.data
  const c = course.data
  return (
    <AppLayout
      title={a?.title ?? 'Team workspace'}
      subtitle={c && t ? `${c.code} ${c.title} · ${t.kind === 'group' ? `Team ${t.name}` : 'Individual work'}` : ' '}
      activeNav="/courses"
    >
      {(team.loading || (t && (assignment.loading || course.loading))) && !a && <Loading />}
      {team.error && <PageError error={team.error} />}
      {t && a && (
        <Workspace
          team={t}
          assignment={a}
          reloadTeam={team.reload}
          showMarks={location.pathname.endsWith('/marks')}
          isMember={isMember}
        />
      )}
    </AppLayout>
  )
}

function Workspace({ team, assignment, reloadTeam, showMarks, isMember }) {
  const submission = useApi(() => api.get(`/teams/${team.id}/submission`), [team.id])
  const drafts = useApi(() => getAll(`/teams/${team.id}/submission/drafts`), [team.id])
  const released = team.state === 'marks_released'
  const marks = useApi(() => (released ? api.get(`/teams/${team.id}/marks`) : Promise.resolve(null)), [team.id, released])
  const [brief, setBrief] = useState(false)
  const marksRef = useRef(null)

  useEffect(() => {
    if (showMarks && marks.data) marksRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [showMarks, marks.data])

  function refreshAll() {
    submission.reload()
    drafts.reload()
    reloadTeam()
  }

  const closed = isPast(assignment.due_at) || assignment.status === 'closed'
  return (
    <>
      <div className="row gap16 wrap">
        {team.kind === 'group' ? (
          <Badge tone="purple" icon="users">
            Group · {assignment.min_team}–{assignment.max_team} members
          </Badge>
        ) : (
          <Badge tone="purple" icon="user">
            Individual
          </Badge>
        )}
        <Badge tone="amber" icon="clock">
          {closed ? 'Closed' : 'Due'} {formatDeadline(assignment.due_at)}
        </Badge>
        <Badge tone="grey">Up to {plural(assignment.max_files, 'file')} · PDF or ZIP · 10 MB each</Badge>
        {assignment.requires_pdf && <Badge tone="grey">Final must include a PDF report</Badge>}
        <span className="grow" />
        <button type="button" className="small link" onClick={() => setBrief(true)}>
          View brief and rubric
        </button>
      </div>

      {marks.data && (
        <div ref={marksRef}>
          <MarksCard marks={marks.data} />
        </div>
      )}

      <div className="row gap24 start stack-md">
        <div className="col gap24 grow" style={{ minWidth: 0 }}>
          <FinalCard submission={submission} individual={team.kind !== 'group'} />
          <DraftsCard
            team={team}
            assignment={assignment}
            submission={submission.data}
            drafts={drafts}
            closed={closed}
            canAct={isMember && !released}
            onChanged={refreshAll}
          />
        </div>
        <div className="col gap24 side-col" style={{ width: 360 }}>
          {team.kind === 'group' && <MembersCard team={team} assignment={assignment} closed={closed} onChanged={reloadTeam} />}
          <LeaveCard team={team} assignment={assignment} closed={closed} />
        </div>
      </div>
      {brief && <BriefModal assignment={assignment} onClose={() => setBrief(false)} />}
    </>
  )
}

// Figma 06b: the result card at the top once marks are released.
function MarksCard({ marks }) {
  const adjustment = marks.adjustment_percent && Number(marks.adjustment_percent) !== 0
  return (
    <Card as="section" className="col gap16" style={{ border: '1.5px solid var(--badge-green-fg)' }} aria-labelledby="result-title">
      <div className="row gap16 wrap">
        <div className="col">
          <span id="result-title" className="eyebrow" style={{ color: 'var(--badge-green-fg)' }}>
            Your result · released {formatDayMonth(marks.released_at)}
          </span>
          <b style={{ fontSize: 32 }}>
            {points(marks.my_mark)}{' '}
            <span className="muted" style={{ fontSize: 18, fontWeight: 500 }}>
              / {points(marks.max_mark)}
            </span>
          </b>
        </div>
        <div className="col gap4 grow" style={{ marginLeft: 24 }}>
          <span className="small muted">
            Team mark {points(marks.team_mark)} / {points(marks.max_mark)} · your adjustment:{' '}
            {adjustment ? `${Number(marks.adjustment_percent) > 0 ? '+' : ''}${points(marks.adjustment_percent)}% (${marks.adjustment_reason})` : 'none'}
          </span>
          <ProgressBar value={percentOf(marks.my_mark, marks.max_mark)} height={10} color="var(--badge-green-fg)" label="Your mark" />
          {marks.overall_comment && <span className="small muted">Teacher's comment: "{marks.overall_comment}"</span>}
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Criterion</th>
              <th scope="col">Score</th>
              <th scope="col">Comment</th>
            </tr>
          </thead>
          <tbody>
            {marks.rubric.map((c) => (
              <tr key={c.criterion_id}>
                <td>
                  <b>{c.title}</b>
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <b>{points(c.points)}</b> / {points(c.max_points)}
                </td>
                <td className="muted">{c.comment}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function FilesList({ files }) {
  return files.map((f, i) => (
    <span key={f.id}>
      {i > 0 && ', '}
      <button type="button" className="file-link" onClick={() => download(`/submission-files/${f.id}/content`)} aria-label={`Download ${f.file_name}`}>
        {f.file_name}
      </button>{' '}
      · {fileSize(f.size_bytes)}
    </span>
  ))
}

function FinalCard({ submission, individual }) {
  const [choosing, setChoosing] = useState(false)
  const s = submission.data
  if (submission.loading && !s) return <Loading />
  if (!s) return <ErrorMessage error={submission.error} />
  const f = s.current_final
  if (!f) {
    return (
      <Card as="section" className="row gap16">
        <IconBox size={48} tone="soft">
          <Icon name="clock" size={24} />
        </IconBox>
        <div className="grow">
          <b style={{ fontSize: 16 }}>{s.state === 'not_submitted' ? 'Not submitted' : 'No final yet'}</b>
          <p className="small muted">
            {s.state === 'not_submitted'
              ? 'The deadline passed without any draft.'
              : `Upload a draft, then choose "Submit as final" before ${formatDeadline(s.due_at)}. At the deadline the latest draft is submitted automatically.`}
          </p>
        </div>
      </Card>
    )
  }
  const by =
    f.kind === 'at_deadline'
      ? `Submitted automatically at the deadline (latest draft)`
      : `Submitted by ${f.submitted_by?.name ?? 'a former member'} on ${formatDay(f.submitted_at)}, ${formatDeadline(f.submitted_at).split(', ')[1]}`
  return (
    <Card as="section" highlight className="row gap16" aria-labelledby="final-title">
      <IconBox size={48} tone="solid">
        <Icon name="check" size={24} color="#fff" strokeWidth={2.4} />
      </IconBox>
      <div className="grow">
        <b id="final-title" style={{ fontSize: 16 }}>
          {individual ? 'Your final' : "Your team's final"}: v{f.version_number}
        </b>
        <p className="small muted">
          {by} · {individual ? 'the teacher was notified' : 'every member and the teacher were notified'}
          {f.below_min_size && ' · the team was below the minimum size'}
          {s.replaced_finals > 0 && ` · replaces ${plural(s.replaced_finals, 'earlier final')}`}
        </p>
      </div>
      <Button
        variant="secondary"
        size="small"
        onClick={() => (f.files.length === 1 ? download(`/submission-files/${f.files[0].id}/content`) : setChoosing(true))}
      >
        Download
      </Button>
      {choosing && (
        <Modal title={`Final v${f.version_number}: files`} onClose={() => setChoosing(false)}>
          <ul className="col gap8" style={{ listStyle: 'none' }}>
            {f.files.map((file) => (
              <li key={file.id} className="row between gap12">
                <span>
                  {file.file_name} <span className="small muted">· {fileSize(file.size_bytes)}</span>
                </span>
                <Button variant="secondary" size="small" icon="download" onClick={() => download(`/submission-files/${file.id}/content`)}>
                  Download
                </Button>
              </li>
            ))}
          </ul>
        </Modal>
      )}
    </Card>
  )
}

function DraftsCard({ team, assignment, submission, drafts, closed, canAct, onChanged }) {
  const toast = useToast()
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null)
  const [conflict, setConflict] = useState(null)
  const currentFinal = submission?.current_final ?? null
  const list = drafts.data ?? []

  async function upload(files) {
    setError(null)
    if (files.length > assignment.max_files) {
      setError({ message: `At most ${plural(assignment.max_files, 'file')} per draft.` })
      return
    }
    const big = files.find((f) => f.size > 10 * 1024 * 1024)
    if (big) {
      setError({ message: `${big.name} is larger than 10 MB.` })
      return
    }
    setBusy('upload')
    try {
      const form = new FormData()
      for (const f of files) form.append('files', f)
      const draft = await api.post(`/teams/${team.id}/submission/drafts`, form, { headers: { 'Idempotency-Key': newIdempotencyKey() } })
      toast(`Draft v${draft.number} uploaded. Your teammates were notified.`)
      onChanged()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  async function submitFinal(draft, expected = currentFinal?.id ?? null) {
    setError(null)
    setBusy(`final-${draft.id}`)
    try {
      const final = await api.post(
        `/teams/${team.id}/submission/finals`,
        { version_id: draft.id, expected_final_id: expected },
        { headers: { 'Idempotency-Key': newIdempotencyKey() } },
      )
      toast(`v${final.version_number} is your team's final. Everyone was notified.`)
      setConflict(null)
      onChanged()
    } catch (err) {
      if (err.code === 'FINAL_CHANGED') {
        setConflict({ draft, current: err.details?.current_final })
        onChanged()
      } else setError(err)
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card as="section" className="col gap12" aria-labelledby="drafts-title">
      <div className="row between">
        <h3 id="drafts-title">Drafts</h3>
        <span className="small muted">Visible only to your team</span>
      </div>
      {drafts.loading && <Loading />}
      {drafts.data && list.length === 0 && <Empty>No drafts yet. Upload the first one below.</Empty>}
      {list.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Version</th>
                <th scope="col">Uploaded by</th>
                <th scope="col">When</th>
                <th scope="col">Files</th>
                <th scope="col">
                  <span className="sr-only">Final</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.map((d) => (
                <tr key={d.id}>
                  <td>
                    <b>v{d.number}</b>
                  </td>
                  <td>
                    <div className="row gap8">
                      <Avatar name={d.uploaded_by.name} size="small" />
                      {d.uploaded_by.name}
                    </div>
                  </td>
                  <td className="muted">{formatDeadline(d.created_at)}</td>
                  <td className="small">
                    <FilesList files={d.files} />
                  </td>
                  <td>
                    {d.is_current_final ? (
                      <Badge tone="green" icon="check" iconSize={13}>
                        Current final
                      </Badge>
                    ) : (
                      canAct &&
                      !closed && (
                        <Button variant="secondary" size="small" disabled={Boolean(busy)} onClick={() => submitFinal(d)}>
                          {busy === `final-${d.id}` ? 'Submitting…' : 'Submit as final'}
                        </Button>
                      )
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ErrorMessage error={error} />
      {canAct && !closed && (
        <UploadDropZone
          accept=".pdf,.zip"
          disabled={busy === 'upload'}
          buttonLabel={busy === 'upload' ? 'Uploading…' : 'Upload draft'}
          onFiles={upload}
        />
      )}
      {closed && <p className="small muted">The deadline has passed: no more drafts or finals.</p>}
      {conflict && (
        <Modal
          title="A teammate changed the final"
          onClose={() => setConflict(null)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setConflict(null)}>
                Keep their final
              </Button>
              <Button onClick={() => submitFinal(conflict.draft, conflict.current?.id ?? null)} disabled={Boolean(busy)}>
                Submit v{conflict.draft.number} anyway
              </Button>
            </>
          }
        >
          <p className="small muted">
            While you were looking, {conflict.current?.submitted_by?.name ?? 'a teammate'} submitted v{conflict.current?.version_number} as
            the final. Do you still want v{conflict.draft.number} to replace it? Everyone is notified again.
          </p>
        </Modal>
      )}
    </Card>
  )
}

function MembersCard({ team, assignment, closed, onChanged }) {
  const { user } = useAuth()
  const toast = useToast()
  const [email, setEmail] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const active = team.members.filter((m) => m.status === 'active')
  const canInvite = !team.closed && !closed && !assignment.teams_locked && team.places_left > 0 && active.some((m) => m.user.id === user.id)

  async function invite(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.post(`/teams/${team.id}/invitations`, { email: email.trim() })
      toast(`Invitation sent to ${email.trim()}`)
      setEmail('')
      onChanged()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  async function cancel(inv) {
    setError(null)
    try {
      await api.delete(`/invitations/${inv.id}`)
      toast('Invitation cancelled')
      onChanged()
    } catch (err) {
      setError(err)
    }
  }

  return (
    <Card as="section" className="col gap12" aria-labelledby="members-title">
      <div className="row between">
        <h3 id="members-title">Team members</h3>
        <span className="small muted">
          {active.length} of {assignment.max_team}
        </span>
      </div>
      {team.members.map((m) => (
        <div key={m.user.id} className="row gap12">
          <Avatar name={m.user.name} size="small" />
          <div className="grow" style={{ minWidth: 0 }}>
            <b>{m.user.name}</b>
            <p className="tiny muted">
              {[m.email && emailUser(m.email), team.created_by === m.user.id && 'Creator'].filter(Boolean).join(' · ')}
            </p>
          </div>
          <Badge tone={m.status === 'active' ? 'green' : 'grey'}>
            {m.status === 'active' ? 'Active' : m.status === 'removed' ? 'Removed' : 'Former member'}
          </Badge>
        </div>
      ))}
      {team.pending_invitations.map((inv) => (
        <div key={inv.id} className="row gap12">
          <Avatar name={inv.email} initials={inv.email.slice(0, 2).toUpperCase()} size="small" tone="amber" />
          <div className="grow" style={{ minWidth: 0 }}>
            <b style={{ overflow: 'hidden', textOverflow: 'ellipsis', display: 'block' }}>{inv.email}</b>
            <p className="tiny muted">Invited · expires {formatDayMonth(inv.expires_at)}</p>
          </div>
          <button type="button" className="small red" style={{ fontWeight: 600 }} onClick={() => cancel(inv)}>
            Cancel
          </button>
        </div>
      ))}
      <div className="hr" />
      <form className="col gap8" onSubmit={invite}>
        <label className="lbl" htmlFor="invite-email" style={{ margin: 0 }}>
          Invite a classmate
        </label>
        <div className="row gap8">
          <div className="inp grow small">
            <input
              id="invite-email"
              type="email"
              placeholder="name@iitdh.ac.in"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={!canInvite}
            />
          </div>
          <Button type="submit" size="small" disabled={!canInvite || busy || !email}>
            Invite
          </Button>
        </div>
      </form>
      <ErrorMessage error={error} />
      <p className="tiny muted">
        {assignment.teams_locked
          ? 'Your teacher locked the teams for this assignment.'
          : team.places_left === 0
            ? 'The team is full (members and pending invitations).'
            : 'Any member can invite. Places are held while an invitation is pending.'}
      </p>
      {!closed && !assignment.teams_locked && (
        <button type="button" className="small link" style={{ alignSelf: 'flex-start' }} onClick={() => setRenaming(true)}>
          Rename team
        </button>
      )}
      {renaming && <RenameTeam team={team} onClose={() => setRenaming(false)} onSaved={onChanged} />}
    </Card>
  )
}

function RenameTeam({ team, onClose, onSaved }) {
  const [name, setName] = useState(team.name)
  const [error, setError] = useState(null)
  async function save(event) {
    event.preventDefault()
    try {
      await api.patch(`/teams/${team.id}`, { name: name.trim() })
      onSaved()
      onClose()
    } catch (err) {
      setError(err)
    }
  }
  return (
    <Modal title="Rename team" onClose={onClose}>
      <form className="col gap16" onSubmit={save}>
        <TextField label="Team name" value={name} onChange={(e) => setName(e.target.value)} required />
        <ErrorMessage error={error} />
        <Button type="submit" disabled={!name.trim()}>
          Save
        </Button>
      </form>
    </Modal>
  )
}

function LeaveCard({ team, assignment, closed }) {
  const navigate = useNavigate()
  const toast = useToast()
  const [asking, setAsking] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  if (team.kind !== 'group') {
    return (
      <Card as="section" className="col gap8">
        <h3>Individual work</h3>
        <p className="small muted">This assignment is done alone: your drafts and final are only yours.</p>
      </Card>
    )
  }
  let reason = null
  if (team.has_final) reason = 'Not available: your team has submitted a final. Ask your teacher to move you.'
  else if (assignment.teams_locked) reason = 'Not available: your teacher locked the teams.'
  else if (closed) reason = 'Not available: the deadline has passed.'

  async function leave() {
    setBusy(true)
    try {
      await api.delete(`/teams/${team.id}/members/me`)
      toast(`You left ${team.name}`)
      navigate(`/assignments/${assignment.id}`, { replace: true })
    } catch (err) {
      setError(err)
      setBusy(false)
      setAsking(false)
    }
  }

  return (
    <Card as="section" className="col gap8">
      <h3>Leave team</h3>
      {reason ? (
        <p className="small muted">{reason}</p>
      ) : (
        <>
          <p className="small muted">You can leave before your team's first final and join another team. Your drafts stay with this team.</p>
          <Button variant="danger" size="small" style={{ alignSelf: 'flex-start' }} onClick={() => setAsking(true)}>
            Leave team
          </Button>
        </>
      )}
      <ErrorMessage error={error} />
      {asking && (
        <Confirm title={`Leave ${team.name}?`} danger confirmLabel="Leave team" busy={busy} onConfirm={leave} onCancel={() => setAsking(false)}>
          Your teammates are notified. If you are the last member, the team is closed.
        </Confirm>
      )}
    </Card>
  )
}

function BriefModal({ assignment, onClose }) {
  return (
    <Modal title={assignment.title} onClose={onClose} wide>
      <p style={{ whiteSpace: 'pre-wrap' }}>{assignment.description || 'No description.'}</p>
      <div>
        <span className="lbl">Rubric · {points(assignment.total_points)} points</span>
        <table>
          <thead>
            <tr>
              <th scope="col">Criterion</th>
              <th scope="col" style={{ width: 120 }}>
                Max points
              </th>
            </tr>
          </thead>
          <tbody>
            {assignment.rubric.map((c) => (
              <tr key={c.id}>
                <td>{c.title}</td>
                <td>{points(c.max_points)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {assignment.requires_pdf && <Alert tone="note">The final must include a PDF report.</Alert>}
    </Modal>
  )
}
