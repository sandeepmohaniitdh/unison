import { download } from '../../api/client'
import { Badge, Button, Icon, IconBox } from '../../components'
import { formatDayMonth, formatDeadline } from '../../lib/datetime'
import { fileKind, fileSize, stateBadge } from '../../lib/format'

// Pieces shared by the course page (Figma 02) and course management (Figma 08).

export function typeBadge(a) {
  return a.kind === 'group' ? (
    <Badge tone="purple">
      Group · {a.min_team}–{a.max_team}
    </Badge>
  ) : (
    <Badge tone="grey">Individual</Badge>
  )
}

export function statusBadge(a) {
  if (!a.my_team) return null
  const [text, tone] = stateBadge(a.my_team.state)
  return <Badge tone={tone}>{text}</Badge>
}

// The assignments table of the course page.
export function AssignmentTable({ assignments, isTeacher }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Assignment</th>
            <th scope="col">Type</th>
            <th scope="col">Deadline</th>
            <th scope="col">{isTeacher ? 'Status' : 'Your status'}</th>
            <th scope="col">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {assignments.map((a) => (
            <tr key={a.id}>
              <td>
                <b>{a.title}</b>
              </td>
              <td>{typeBadge(a)}</td>
              <td>{formatDeadline(a.due_at)}</td>
              <td>
                {isTeacher ? (
                  <Badge tone={a.status === 'draft' ? 'grey' : a.status === 'closed' ? 'amber' : 'green'}>
                    {a.status === 'draft' ? 'Draft' : a.status === 'closed' ? 'Closed' : 'Published'}
                  </Badge>
                ) : (
                  statusBadge(a)
                )}
              </td>
              <td style={{ textAlign: 'right' }}>
                {isTeacher ? (
                  <Button variant="secondary" size="small" to={`/assignments/${a.id}/review`}>
                    Review
                  </Button>
                ) : a.my_team?.team_id ? (
                  <Button variant="secondary" size="small" to={`/teams/${a.my_team.team_id}`}>
                    {a.kind === 'group' ? 'Open team' : 'Open'}
                  </Button>
                ) : (
                  <Button variant="secondary" size="small" to={`/assignments/${a.id}`}>
                    {a.kind === 'group' && a.my_team?.state === 'no_team' ? 'Find a team' : 'Open'}
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// One resource row: icon tile, title, "PDF · 1.2 MB · 4 Aug", and a download or open icon.
export function ResourceRow({ resource, actions, showStatus = false }) {
  const isLink = resource.kind === 'link'
  const meta = isLink
    ? ['Link', resource.published_at && formatDayMonth(resource.published_at)]
    : [fileKind(resource.file_name, resource.mime_type), fileSize(resource.size_bytes), resource.published_at && formatDayMonth(resource.published_at)]
  return (
    <div className="row gap12" style={{ padding: '12px 0', borderBottom: '1px solid var(--color-row-divider)' }}>
      <IconBox size={38} tone="primary">
        <Icon name={isLink ? 'link' : 'file'} size={18} />
      </IconBox>
      <div className="grow" style={{ minWidth: 0 }}>
        <b style={{ fontWeight: 600 }}>{resource.title}</b>
        <p className="small muted">
          {meta.filter(Boolean).join(' · ')}
          {resource.description ? ` · ${resource.description}` : ''}
        </p>
      </div>
      {showStatus && resource.status === 'draft' && <Badge tone="grey">Draft</Badge>}
      {actions}
      {isLink ? (
        <a href={resource.url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${resource.title}`} className="row">
          <Icon name="link" size={18} color="var(--color-primary)" />
        </a>
      ) : (
        <button type="button" onClick={() => download(`/resources/${resource.id}/content`)} aria-label={`Download ${resource.title}`}>
          <Icon name="download" size={18} color="var(--color-primary)" />
        </button>
      )}
    </div>
  )
}
