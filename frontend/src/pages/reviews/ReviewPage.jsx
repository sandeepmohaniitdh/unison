import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { api, download, getAll } from '../../api/client'
import useApi from '../../api/useApi'
import {
  AiFeedbackPanel,
  AiSuggestion,
  Alert,
  Badge,
  Button,
  Card,
  Confirm,
  Empty,
  ErrorMessage,
  Loading,
  NumberBox,
  PageError,
  Select,
  TextField,
  useToast,
} from '../../components'
import AppLayout from '../../layouts/AppLayout'
import { formatDay, formatDeadline, formatShort, isPast } from '../../lib/datetime'
import { plural, points } from '../../lib/format'

// Figma 09: the review page. Teachers see only each team's current final, never drafts.
export default function ReviewPage() {
  const { assignmentId } = useParams()
  const [params, setParams] = useSearchParams()
  const assignment = useApi(() => api.get(`/assignments/${assignmentId}`), [assignmentId])
  const a = assignment.data
  const course = useApi(() => (a ? api.get(`/courses/${a.course_id}`) : Promise.resolve(null)), [a?.course_id], { enabled: Boolean(a) })
  const rows = useApi(() => getAll(`/assignments/${assignmentId}/reviews`), [assignmentId])
  const [search, setSearch] = useState('')

  const teamId = params.get('team') ?? rows.data?.find((r) => r.final_id)?.team.id ?? rows.data?.[0]?.team.id
  const chosen = rows.data?.find((r) => String(r.team.id) === String(teamId))
  const shown = (rows.data ?? []).filter((r) => r.team.name.toLowerCase().includes(search.trim().toLowerCase()))
  const c = course.data

  const subtitle = a
    ? `${c?.code ?? ''} · ${plural(rows.data?.length ?? 0, a.kind === 'group' ? 'team' : 'submission')} · ${isPast(a.due_at) ? 'deadline passed' : 'due'} ${formatDeadline(a.due_at)}`
    : ' '

  return (
    <AppLayout
      title={a ? `Review · ${a.title}` : 'Review'}
      subtitle={subtitle}
      activeNav="/courses"
      contentStyle={{ flexDirection: 'row', alignItems: 'flex-start' }}
      contentClassName="stack-sm"
      headerActions={a && rows.data ? <DraftAll assignment={a} rows={rows.data} /> : null}
    >
      {(assignment.loading || rows.loading) && !rows.data && <Loading />}
      {(assignment.error || rows.error) && <PageError error={assignment.error ?? rows.error} />}
      {a && rows.data && (
        <>
          <Card as="nav" className="col gap4 tl side-col" style={{ width: 236, flex: 'none', padding: 14 }} aria-label="Teams">
            <TextField
              icon="search"
              iconSize={15}
              boxClassName="small"
              boxStyle={{ marginBottom: 8 }}
              aria-label="Search teams"
              placeholder={a.kind === 'group' ? 'Search teams' : 'Search students'}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {shown.length === 0 && <Empty>No teams.</Empty>}
            <div className="col gap4" style={{ maxHeight: 720, overflowY: 'auto' }}>
              {shown.map((r) => {
                const [text, tone] = rowBadge(r)
                const on = String(r.team.id) === String(teamId)
                return (
                  <button
                    key={r.team.id}
                    type="button"
                    className={`row between gap8 team-pick${on ? ' on' : ''}`}
                    aria-current={on ? 'true' : undefined}
                    onClick={() => setParams({ team: r.team.id })}
                  >
                    <b>{r.team.name}</b>
                    <Badge tone={tone}>{text}</Badge>
                  </button>
                )
              })}
            </div>
          </Card>
          <div className="col gap20 grow" style={{ minWidth: 0 }}>
            {chosen ? (
              <ReviewSheet
                key={chosen.team.id}
                row={chosen}
                assignment={a}
                onChanged={rows.reload}
                bulk={<BulkRelease assignment={a} rows={rows.data} onChanged={rows.reload} />}
              />
            ) : (
              <Card>
                <Empty>Choose a team on the left.</Empty>
              </Card>
            )}
          </div>
        </>
      )}
    </AppLayout>
  )
}

function rowBadge(r) {
  if (r.review_status === 'released') return ['Released', 'green']
  if (r.state === 'not_submitted') return ['Not submitted', 'red']
  if (!r.final_id) return [r.state === 'drafts' ? 'Drafts only' : 'No final yet', 'grey']
  if (r.below_min_size) return [`Final v${r.version_number} · below min size`, 'amber']
  if (r.final_kind === 'at_deadline') return ['Submitted at deadline', 'amber']
  if (r.review_status === 'draft') return [`Final v${r.version_number} · reviewing`, 'purple']
  return [`Final v${r.version_number}`, 'green']
}

function ReviewSheet({ row, assignment, onChanged, bulk }) {
  const toast = useToast()
  const sheet = useApi(() => api.get(`/teams/${row.team.id}/review`), [row.team.id], { enabled: Boolean(row.final_id) })
  const s = sheet.data
  const [scores, setScores] = useState({})
  const [comment, setComment] = useState('')
  const [adjust, setAdjust] = useState({})
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null)
  const [releasing, setReleasing] = useState(false)
  const [suggestions, setSuggestions] = useState({})

  useEffect(() => {
    if (!s) return
    setScores(Object.fromEntries(s.rubric.map((c) => [c.criterion_id, { points: c.points == null ? '' : points(c.points), comment: c.comment ?? '' }])))
    setComment(s.overall_comment ?? '')
    setAdjust(
      Object.fromEntries(s.members.map((m) => [m.user.id, { percent: m.adjustment_percent == null ? '0' : points(m.adjustment_percent), reason: m.reason ?? '' }])),
    )
  }, [s])

  const total = useMemo(() => Object.values(scores).reduce((sum, x) => sum + (Number(x.points) || 0), 0), [scores])
  const onAiReady = useCallback((list) => setSuggestions(Object.fromEntries((list ?? []).map((sg) => [sg.criterion_id, sg]))), [])

  if (!row.final_id) {
    const open = !isPast(assignment.due_at)
    return (
      <Card className="col gap8">
        <b style={{ fontSize: 17 }}>{row.team.name}</b>
        <p className="small muted">
          {row.state === 'not_submitted'
            ? 'This team did not submit anything before the deadline.'
            : open
              ? `No final yet. The deadline is ${formatDeadline(assignment.due_at)}; teachers never see drafts.`
              : 'No final.'}
        </p>
      </Card>
    )
  }
  if (sheet.loading && !s) return <Loading />
  if (sheet.error) {
    if (sheet.error.code === 'SUBMISSION_OPEN') {
      return (
        <Card className="col gap8">
          <b style={{ fontSize: 17 }}>
            {row.team.name} · final v{row.version_number}
          </b>
          <Alert tone="info">Reviews start after the deadline ({formatDeadline(assignment.due_at)}), so the final cannot change while you mark it.</Alert>
        </Card>
      )
    }
    return <PageError error={sheet.error} />
  }
  if (!s) return null

  const released = s.status === 'released'
  const f = s.final
  const by = f.kind === 'at_deadline' ? 'Submitted automatically at the deadline' : `Submitted by ${f.submitted_by?.name ?? 'a former member'}`

  async function save({ quiet = false } = {}) {
    setBusy('save')
    setError(null)
    try {
      await api.put(`/teams/${row.team.id}/review`, {
        overall_comment: comment.trim() || null,
        scores: s.rubric
          .filter((c) => scores[c.criterion_id]?.points !== '')
          .map((c) => ({ criterion_id: c.criterion_id, points: scores[c.criterion_id].points, comment: scores[c.criterion_id].comment.trim() || null })),
      })
      for (const m of s.members) {
        const want = adjust[m.user.id]
        const had = m.adjustment_percent == null ? 0 : Number(m.adjustment_percent)
        const now = Number(want?.percent || 0)
        if (now !== 0 && (now !== had || want.reason !== (m.reason ?? ''))) {
          await api.put(`/teams/${row.team.id}/review/adjustments/${m.user.id}`, { percent: want.percent, reason: want.reason.trim() })
        } else if (now === 0 && m.adjustment_percent != null) {
          await api.delete(`/teams/${row.team.id}/review/adjustments/${m.user.id}`)
        }
      }
      if (!quiet) toast('Review saved. Students see nothing until you release.')
      sheet.reload()
      onChanged()
      return true
    } catch (err) {
      setError(err)
      return false
    } finally {
      setBusy(null)
    }
  }

  async function releaseTeam() {
    if (!(await save({ quiet: true }))) {
      setReleasing(false)
      return
    }
    setBusy('release')
    try {
      await api.patch(`/teams/${row.team.id}/review`, { status: 'released' })
      toast(`Marks released to ${row.team.name}. Every member was notified.`)
      sheet.reload()
      onChanged()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
      setReleasing(false)
    }
  }

  return (
    <>
      <Card as="section" className="row gap16 wrap" aria-labelledby="final-title">
        <div className="grow">
          <b id="final-title" style={{ fontSize: 17 }}>
            {row.team.name} · final v{f.version_number}
          </b>
          <p className="small muted">
            {by}, {formatDay(f.submitted_at)} {formatShort(f.submitted_at).split(', ')[1]} · drafts are not shown to teachers
            {f.below_min_size && ' · below the minimum team size'}
          </p>
        </div>
        {f.files.map((file) => (
          <Badge key={file.id} tone="grey" icon="file" iconSize={13}>
            {file.file_name}
          </Badge>
        ))}
        <Button
          variant="secondary"
          size="small"
          icon="download"
          onClick={() => f.files.forEach((file, i) => setTimeout(() => download(`/submission-files/${file.id}/content`), i * 400))}
        >
          Download
        </Button>
      </Card>

      <div className="row gap20 start stack-md">
        <Card as="section" className="col gap12 grow" style={{ minWidth: 0 }} aria-labelledby="rubric-title">
          <div className="row between">
            <h3 id="rubric-title">Rubric</h3>
            <b>
              Total {points(total)} / {points(s.max_mark)}
            </b>
          </div>
          {released && <Alert tone="success">Released {formatShort(s.released_at)}. Marks can no longer change.</Alert>}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Criterion</th>
                  <th scope="col">Score</th>
                  <th scope="col">
                    <span className="sr-only">AI suggestion</span>
                  </th>
                  <th scope="col">Comment</th>
                </tr>
              </thead>
              <tbody>
                {s.rubric.map((c) => {
                  const value = scores[c.criterion_id] ?? { points: '', comment: '' }
                  const suggestion = suggestions[c.criterion_id]
                  return (
                    <tr key={c.criterion_id}>
                      <td>
                        <b>{c.title}</b>
                        <p className="tiny muted">max {points(c.max_points)}</p>
                      </td>
                      <td>
                        <NumberBox
                          value={value.points}
                          aria-label={`Score for ${c.title}, out of ${points(c.max_points)}`}
                          disabled={released}
                          onChange={(v) => setScores((x) => ({ ...x, [c.criterion_id]: { ...value, points: v } }))}
                        />
                      </td>
                      <td>
                        {suggestion && <AiSuggestion>AI suggests {points(suggestion.points)}</AiSuggestion>}
                      </td>
                      <td style={{ minWidth: 110 }}>
                        <div className="inp small" style={{ height: 38 }}>
                          <input
                            aria-label={`Comment on ${c.title}`}
                            placeholder="Comment…"
                            value={value.comment}
                            disabled={released}
                            onChange={(e) => setScores((x) => ({ ...x, [c.criterion_id]: { ...value, comment: e.target.value } }))}
                          />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div>
            <label className="lbl" htmlFor="overall">
              Overall comment (shown to the team)
            </label>
            <div className="inp">
              <input id="overall" placeholder="Solid team effort…" value={comment} disabled={released} onChange={(e) => setComment(e.target.value)} />
            </div>
          </div>
        </Card>
        <AiPanel
          team={row.team}
          finalId={f.id}
          files={f.files}
          disabled={released}
          onUse={(suggestions) =>
            setScores((x) => {
              const next = { ...x }
              for (const sg of suggestions) next[sg.criterion_id] = { points: points(sg.points), comment: sg.comment ?? x[sg.criterion_id]?.comment ?? '' }
              return next
            })
          }
          onReady={onAiReady}
        />
      </div>

      <Card as="section" className="col gap12" aria-labelledby="contrib-title">
        <div className="row between wrap gap12">
          <h3 id="contrib-title">Contribution and individual adjustment</h3>
          <span className="small muted">Adjustment range −20% to +10% of the team mark</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Member</th>
                <th scope="col">Drafts uploaded</th>
                <th scope="col">Last upload</th>
                <th scope="col">Final</th>
                <th scope="col">Adjustment</th>
              </tr>
            </thead>
            <tbody>
              {s.contribution.map((ct) => {
                const value = adjust[ct.user.id] ?? { percent: '0', reason: '' }
                const member = s.members.find((m) => m.user.id === ct.user.id)
                return (
                  <tr key={ct.user.id}>
                    <td>
                      <b>{ct.user.name}</b>
                      {ct.status !== 'active' && <p className="tiny muted">{ct.status}</p>}
                    </td>
                    <td>{ct.drafts_uploaded}</td>
                    <td className="muted">{ct.last_upload_at ? formatDay(ct.last_upload_at) : '—'}</td>
                    <td>{ct.submitted_current_final ? `Submitted final v${f.version_number}` : '—'}</td>
                    <td>
                      {member ? (
                        <div className="row gap8">
                          <NumberBox
                            width={70}
                            value={value.percent}
                            suffix="%"
                            aria-label={`Adjustment for ${ct.user.name}, percent`}
                            disabled={released}
                            onChange={(v) => setAdjust((x) => ({ ...x, [ct.user.id]: { ...value, percent: v } }))}
                          />
                          <div className="inp small grow" style={{ height: 38 }}>
                            <input
                              aria-label={`Reason for ${ct.user.name} (shown to the student)`}
                              placeholder="Reason (shown to student)"
                              value={value.reason}
                              disabled={released}
                              onChange={(e) => setAdjust((x) => ({ ...x, [ct.user.id]: { ...value, reason: e.target.value } }))}
                            />
                          </div>
                        </div>
                      ) : (
                        <span className="muted small">Not marked</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {s.members.some((m) => m.mark != null) && (
          <p className="tiny muted">
            Member marks: {s.members.map((m) => `${m.user.name} ${m.mark == null ? '—' : points(m.mark)}`).join(' · ')}
          </p>
        )}
      </Card>
      <ErrorMessage error={error} />
      <div className="row gap12 wrap" style={{ justifyContent: 'flex-end' }}>
        {!released && (
          <>
            <Button variant="secondary" onClick={() => save()} disabled={Boolean(busy)}>
              {busy === 'save' ? 'Saving…' : 'Save'}
            </Button>
            <Button variant="tint" onClick={() => setReleasing(true)} disabled={Boolean(busy)}>
              Release for {row.team.name} only
            </Button>
          </>
        )}
        {bulk}
      </div>
      {releasing && (
        <Confirm
          title={`Release marks to ${row.team.name}?`}
          confirmLabel="Release marks"
          busy={busy === 'release'}
          onConfirm={releaseTeam}
          onCancel={() => setReleasing(false)}
        >
          Every member sees their mark, the scores and comments, and their own adjustment. Marks cannot change after release.
        </Confirm>
      )}
    </>
  )
}

function AiPanel({ team, finalId, files, disabled, onUse, onReady }) {
  const toast = useToast()
  const status = useApi(() => api.get('/ai/status'), [])
  const drafts = useApi(() => api.get(`/teams/${team.id}/review/ai-drafts`, { size: 10 }), [team.id, finalId])
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const items = drafts.data?.items ?? []
  const latest = items[0]
  const pending = latest && (latest.status === 'queued' || latest.status === 'running')
  const pdfs = files.filter((f) => f.mime_type === 'application/pdf')
  const [fileId, setFileId] = useState(pdfs[0]?.id ?? null)

  // Poll a queued draft every 3 seconds until it is ready or failed.
  useEffect(() => {
    if (!pending) return undefined
    const timer = setInterval(async () => {
      try {
        const d = await api.get(`/ai-drafts/${latest.id}`)
        if (d.status !== latest.status) drafts.reload()
      } catch {
        // keep polling
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [pending, latest, drafts])

  const ready = items.find((d) => d.status === 'ready')
  useEffect(() => {
    onReady(ready?.suggestions)
  }, [ready, onReady])

  async function ask() {
    setBusy(true)
    setError(null)
    try {
      await api.post(`/teams/${team.id}/review/ai-drafts`, { file_id: pdfs.length > 1 ? fileId : null })
      toast('AI draft requested')
      drafts.reload()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const s = status.data
  const left = s ? Math.max(0, s.requests_per_submission - items.length) : 0
  let body
  if (status.loading) body = <Loading />
  else if (!s?.enabled) body = <p className="small muted">The AI feedback draft is not set up on this server (AI_PROVIDER is off). Review manually.</p>
  else if (pdfs.length === 0) body = <p className="small muted">No PDF report in this final. The AI draft reads only the PDF report.</p>
  else if (pending) body = <p className="small muted">Reading the report… this takes a few seconds.</p>
  else if (latest?.status === 'failed')
    body = (
      <p className="small muted">
        Feedback draft unavailable; review manually. {latest.message ? `(${latest.message})` : ''}
      </p>
    )
  else if (ready)
    body = (
      <>
        {ready.injection_suspected && (
          <p className="small red">The report contains text that looks like instructions to the AI. Check these suggestions carefully.</p>
        )}
        {ready.suggestions.map((sg) => (
          <p key={sg.criterion_id} className="small">
            <b>
              {sg.title}, {points(sg.points)}/{points(sg.max_points)}:
            </b>{' '}
            {sg.comment}
          </p>
        ))}
      </>
    )
  else body = <p className="small muted">Ask for a suggested mark and a one-line comment per criterion. Students never see it.</p>

  return (
    <AiFeedbackPanel
      warning={ready?.truncation_note}
      footnote="Names, emails and roll numbers were removed before sending. Suggestions are never shown to students."
      actions={
        s?.enabled && pdfs.length > 0 && !disabled ? (
          <>
            <Button variant="secondary" size="small" className="grow" onClick={ask} disabled={busy || pending || left === 0}>
              {items.length === 0 ? 'Draft feedback' : `Regenerate (${left} left)`}
            </Button>
            <Button variant="tint" size="small" className="grow" disabled={!ready} onClick={() => onUse(ready.suggestions)}>
              Use all
            </Button>
          </>
        ) : null
      }
    >
      {pdfs.length > 1 && s?.enabled && (
        <Select
          prefix="Read"
          aria-label="PDF report to read"
          boxClassName="small"
          boxStyle={{ height: 36 }}
          options={pdfs.map((p) => ({ value: p.id, label: p.file_name }))}
          value={fileId ?? ''}
          onChange={(v) => setFileId(Number(v))}
        />
      )}
      {body}
      <ErrorMessage error={error ?? drafts.error} />
    </AiFeedbackPanel>
  )
}

function BulkRelease({ assignment, rows, onChanged }) {
  const toast = useToast()
  const [asking, setAsking] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const ready = rows.filter((r) => r.review_status === 'draft').length

  async function releaseAll() {
    setBusy(true)
    setError(null)
    try {
      const res = await api.patch(`/assignments/${assignment.id}/reviews`, { status: 'released' })
      toast(`${plural(res.released, 'team')} released${res.skipped.length ? `, ${res.skipped.length} skipped (review not complete)` : ''}`)
      onChanged()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
      setAsking(false)
    }
  }

  return (
    <>
      <Button onClick={() => setAsking(true)} disabled={busy || ready === 0} title={ready === 0 ? 'Save a complete review first' : undefined}>
        Release marks for this assignment
      </Button>
      {error && <ErrorMessage error={error} />}
      {asking && (
        <Confirm title="Release every complete review?" confirmLabel="Release marks" busy={busy} onConfirm={releaseAll} onCancel={() => setAsking(false)}>
          {plural(ready, 'team')} with a saved, complete review get their marks now, and every member is notified. Teams without a complete
          review are skipped.
        </Confirm>
      )}
    </>
  )
}

// "Draft all": one background job asks for an AI draft for every final.
function DraftAll({ assignment, rows }) {
  const toast = useToast()
  const status = useApi(() => api.get('/ai/status'), [])
  const [asking, setAsking] = useState(false)
  const [busy, setBusy] = useState(false)
  const finals = rows.filter((r) => r.final_id && r.review_status !== 'released').length
  if (!status.data?.enabled) return null

  async function run() {
    setBusy(true)
    try {
      const res = await api.post(`/assignments/${assignment.id}/ai-drafts`)
      toast(`${plural(res.queued, 'AI draft')} queued${res.skipped.length ? `, ${res.skipped.length} skipped` : ''}`)
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
      setAsking(false)
    }
  }

  return (
    <>
      <Button variant="secondary" size="small" icon="sparkle" onClick={() => setAsking(true)} disabled={busy || finals === 0}>
        Draft all
      </Button>
      {asking && (
        <Confirm title="Ask for AI drafts for every final?" confirmLabel="Draft all" busy={busy} onConfirm={run} onCancel={() => setAsking(false)}>
          One background job reads each final's PDF report, one team at a time. Teams without a PDF or with an existing draft are skipped.
          Students never see the drafts.
        </Confirm>
      )}
    </>
  )
}
