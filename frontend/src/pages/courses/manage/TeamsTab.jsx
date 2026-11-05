import { useState } from 'react'
import { Link } from 'react-router'
import { api, getAll } from '../../../api/client'
import useApi from '../../../api/useApi'
import { Avatar, Badge, Button, Card, Empty, ErrorMessage, Loading, Modal, Select, useToast } from '../../../components'
import { stateBadge } from '../../../lib/format'
import { TeamsLockCard } from './SideCards'

// Course management, Teams: every team of a group assignment. Teachers can remove or move
// members (also after the first final, until marks are released) and lock the teams.
export default function TeamsTab({ assignments, archived, onAssignmentChanged }) {
  const groups = assignments.filter((a) => a.kind === 'group' && a.status !== 'draft')
  const [chosen, setChosen] = useState(groups[0]?.id ?? '')
  const assignment = groups.find((a) => String(a.id) === String(chosen))
  const teams = useApi(() => (chosen ? getAll(`/assignments/${chosen}/teams`) : Promise.resolve([])), [chosen])
  const [moving, setMoving] = useState(null)
  const [error, setError] = useState(null)
  const toast = useToast()

  async function remove(team, member) {
    setError(null)
    try {
      await api.delete(`/teams/${team.id}/members/${member.user.id}`)
      toast(`${member.user.name} was removed from ${team.name}`)
      teams.reload()
    } catch (err) {
      setError(err)
    }
  }

  if (groups.length === 0) {
    return (
      <Card className="col gap8">
        <h3>Teams</h3>
        <Empty>Teams appear here once a group assignment is published.</Empty>
      </Card>
    )
  }

  const list = teams.data ?? []
  return (
    <div className="row gap24 start stack-sm">
      <Card as="section" className="col gap12 grow" style={{ minWidth: 0 }}>
        <div className="row between gap12 wrap">
          <h3>Teams</h3>
          <Select
            aria-label="Assignment"
            prefix="Assignment"
            className="grow"
            style={{ maxWidth: 340 }}
            boxStyle={{ width: '100%', height: 36 }}
            options={groups.map((a) => ({ value: a.id, label: a.title }))}
            value={chosen}
            onChange={setChosen}
          />
        </div>
        <ErrorMessage error={error ?? teams.error} />
        {teams.loading && <Loading />}
        {teams.data && list.length === 0 && <Empty>No teams yet.</Empty>}
        {list.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Team</th>
                  <th scope="col">Members</th>
                  <th scope="col">Places left</th>
                  <th scope="col">State</th>
                </tr>
              </thead>
              <tbody>
                {list.map((t) => {
                  const [text, tone] = stateBadge(t.state)
                  return (
                    <tr key={t.id}>
                      <td style={{ verticalAlign: 'top' }}>
                        <b>{t.name}</b>
                        {t.closed && <p className="tiny muted">Closed</p>}
                        <p className="tiny">
                          <Link to={`/assignments/${t.assignment_id}/review?team=${t.id}`} className="link">
                            Open review
                          </Link>
                        </p>
                      </td>
                      <td>
                        <div className="col gap8">
                          {t.members.map((m) => (
                            <div key={m.user.id} className="row gap8">
                              <Avatar name={m.user.name} size="small" />
                              <span className="grow">
                                {m.user.name}
                                {m.status !== 'active' && <span className="tiny muted"> · {m.status}</span>}
                              </span>
                              {m.status === 'active' && !archived && (
                                <>
                                  <button type="button" className="small link" onClick={() => setMoving({ team: t, member: m })}>
                                    Move
                                  </button>
                                  <button type="button" className="small red" style={{ fontWeight: 600 }} onClick={() => remove(t, m)}>
                                    Remove
                                  </button>
                                </>
                              )}
                            </div>
                          ))}
                          {t.pending_invitations.map((p) => (
                            <span key={p.id} className="tiny muted">
                              Invited: {p.email}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td>{t.places_left}</td>
                      <td>
                        <Badge tone={tone}>{text}</Badge>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <div className="col gap24 side-col" style={{ width: 400 }}>
        <TeamsLockCard assignment={assignment} archived={archived} onChanged={onAssignmentChanged} />
        {assignment && (
          <Card className="col gap8">
            <h3>Team rules</h3>
            <p className="small muted">
              Teams of {assignment.min_team} to {assignment.max_team}. Students create teams and invite classmates;
              pending invitations hold a place. After a team's first final, only you can change it.
            </p>
          </Card>
        )}
      </div>
      {moving && (
        <MoveMember
          move={moving}
          teams={list.filter((t) => t.id !== moving.team.id && !t.closed)}
          onClose={() => setMoving(null)}
          onMoved={() => {
            setMoving(null)
            teams.reload()
          }}
        />
      )}
    </div>
  )
}

function MoveMember({ move, teams, onClose, onMoved }) {
  const toast = useToast()
  const [target, setTarget] = useState(teams[0]?.id ?? '')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true)
    try {
      await api.patch(`/teams/${move.team.id}/members/${move.member.user.id}`, { team_id: Number(target) })
      toast(`${move.member.user.name} moved`)
      onMoved()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title={`Move ${move.member.user.name}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} disabled={busy || !target}>
            Move
          </Button>
        </>
      }
    >
      <p className="small muted">From {move.team.name} to another team of this assignment. Both teams are notified.</p>
      {teams.length === 0 ? (
        <Empty>There is no other open team.</Empty>
      ) : (
        <Select
          label="New team"
          filled
          options={teams.map((t) => ({ value: t.id, label: `${t.name} (${t.places_left} places left)` }))}
          value={target}
          onChange={setTarget}
        />
      )}
      <ErrorMessage error={error} />
    </Modal>
  )
}
