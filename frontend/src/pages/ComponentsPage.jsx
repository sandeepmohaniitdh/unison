import { useState } from 'react'
import {
  AiFeedbackPanel,
  AiSuggestion,
  AppShell,
  Avatar,
  Badge,
  Button,
  Card,
  Checkbox,
  DateTile,
  Icon,
  ICON_NAMES,
  NotificationRow,
  NumberBox,
  ProgressBar,
  Select,
  StatCard,
  Tabs,
  TextArea,
  TextField,
  Toggle,
  UploadDropZone,
} from '../components'

// Developer page listing every shared component with the demo data of the Figma screens.
// Use it to check a component against the design before building pages with it.
// It is not one of the eleven pages and will be removed or hidden before MS-6.

const DEMO_USER = {
  name: 'Sandeep M',
  shortName: 'Sandeep',
  email: 'cs26mt001@iitdh.ac.in',
  role: 'student',
}

const DEPARTMENTS = [
  { value: 'all', label: 'All' },
  { value: 'cse', label: 'Computer Science and Engineering' },
  { value: 'ee', label: 'Electrical Engineering' },
]

export default function ComponentsPage() {
  const [tab, setTab] = useState('overview')
  const [department, setDepartment] = useState('all')
  const [requiresPdf, setRequiresPdf] = useState(true)
  const [keepSignedIn, setKeepSignedIn] = useState(true)
  const [minTeam, setMinTeam] = useState('2')
  const [adjustment, setAdjustment] = useState('0')
  const [lastUpload, setLastUpload] = useState('')

  return (
    <AppShell
      user={DEMO_USER}
      title="Components"
      subtitle="Shared building blocks of the Figma design, with its demo data"
      unreadCount={3}
    >
      <Tabs
        label="Course sections"
        value={tab}
        onChange={setTab}
        tabs={[
          { id: 'overview', label: 'Overview' },
          { id: 'resources', label: 'Resources' },
          { id: 'assignments', label: 'Assignments' },
          { id: 'members', label: 'Members' },
        ]}
      />

      <div className="row gap20">
        <StatCard label="Courses" value="4" note="Jul–Nov 2026" />
        <StatCard label="Due this week" value="2" note="Next: Wed 5 Nov, 23:59 IST" noteTone="accent" />
        <StatCard label="Finals submitted" value="3 / 5">
          <ProgressBar value={60} label="Finals submitted" />
        </StatCard>
        <StatCard label="Marks released" value="2" note="View results" noteTone="link" />
      </div>

      <div className="row gap24 start">
        <div className="col gap24 grow">
          <Card className="col gap12">
            <h3>Buttons</h3>
            <div className="row gap12 wrap">
              <Button>Upload draft</Button>
              <Button variant="secondary">Save draft</Button>
              <Button variant="tint">Manage</Button>
              <Button variant="danger" icon="trash" iconColor="var(--color-red)">
                Delete my account
              </Button>
              <Button size="small">Accept</Button>
              <Button variant="secondary" size="small">
                Decline
              </Button>
              <Button variant="secondary" size="small" icon="download">
                Download
              </Button>
            </div>
          </Card>

          <Card className="col gap12">
            <h3>Badges and avatars</h3>
            <div className="row gap8 wrap">
              <Badge>CS301</Badge>
              <Badge tone="green" icon="check" iconSize={13}>
                Current final
              </Badge>
              <Badge tone="amber">Draft only</Badge>
              <Badge tone="red">Not submitted</Badge>
              <Badge tone="grey">Invite only</Badge>
              <Badge icon="users">Group · 2–4 members</Badge>
              <Badge tone="amber" icon="clock">
                Due Wed 5 Nov, 23:59 IST
              </Badge>
            </div>
            <div className="row gap12">
              <Avatar name="Sandeep M" />
              <Avatar name="Km Shristi Singh" size="small" />
              <Avatar name="Ujjwal Gupta" size="small" tone="amber" />
              <Avatar name="Sandeep M" size="large" />
              <DateTile day="05" month="NOV" />
              <AiSuggestion>AI suggests 9</AiSuggestion>
            </div>
          </Card>

          <Card className="col gap16">
            <h3>Form controls</h3>
            <div className="row gap12">
              <TextField
                className="grow"
                icon="search"
                iconSize={18}
                placeholder="Search by code, title or teacher"
                aria-label="Search courses"
              />
              <Select
                prefix="Department"
                aria-label="Department"
                options={DEPARTMENTS}
                value={department}
                onChange={setDepartment}
                boxStyle={{ width: 280 }}
              />
            </div>
            <div className="row gap16">
              <TextField className="grow" label="Institute email" icon="mail" type="email" defaultValue="cs26mt001@iitdh.ac.in" />
              <TextField className="grow" label="Password" icon="lock" type="password" defaultValue="unison-demo" />
            </div>
            <TextArea
              label="Description"
              defaultValue="Build a small web app for booking library study rooms. Submit a report (PDF) and your code (ZIP)."
            />
            <div className="row gap16">
              <div>
                <span className="lbl" id="team-size">
                  Team size
                </span>
                <div className="row gap8" role="group" aria-labelledby="team-size">
                  <NumberBox value={minTeam} onChange={setMinTeam} aria-label="Minimum team size" />
                  <span className="muted">to</span>
                  <NumberBox value="4" aria-label="Maximum team size" readOnly />
                </div>
              </div>
              <div>
                <span className="lbl" id="adjustment">
                  Adjustment
                </span>
                <NumberBox value={adjustment} onChange={setAdjustment} suffix="%" width={70} aria-labelledby="adjustment" />
              </div>
              <div className="grow">
                <span className="lbl">Requires a PDF report</span>
                <div className="row gap8" style={{ height: 42 }}>
                  <Toggle checked={requiresPdf} onChange={setRequiresPdf} label="Requires a PDF report" />
                  <span className="small muted">Needed for the AI feedback draft</span>
                </div>
              </div>
            </div>
            <div className="row between small">
              <Checkbox checked={keepSignedIn} onChange={setKeepSignedIn}>
                Keep me signed in
              </Checkbox>
              <a href="#forgot" className="link">
                Forgot password?
              </a>
            </div>
          </Card>

          <Card className="col gap12">
            <div className="row between">
              <h3>Drafts</h3>
              <span className="small muted">Visible only to your team</span>
            </div>
            <table>
              <thead>
                <tr>
                  <th scope="col">Version</th>
                  <th scope="col">Uploaded by</th>
                  <th scope="col">When</th>
                  <th scope="col">Files</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>
                    <b>v2</b>
                  </td>
                  <td>
                    <div className="row gap8">
                      <Avatar name="Km Shristi Singh" size="small" />
                      Km Shristi Singh
                    </div>
                  </td>
                  <td className="muted">Sun 2 Nov, 18:05 IST</td>
                  <td className="small">report.pdf · 2.3 MB, code.zip · 6.0 MB</td>
                  <td>
                    <Badge tone="green" icon="check" iconSize={13}>
                      Current final
                    </Badge>
                  </td>
                </tr>
                <tr>
                  <td>
                    <b>v1</b>
                  </td>
                  <td>
                    <div className="row gap8">
                      <Avatar name="Sandeep M" size="small" />
                      Sandeep M
                    </div>
                  </td>
                  <td className="muted">Thu 30 Oct, 20:15 IST</td>
                  <td className="small">report.pdf · 1.8 MB</td>
                  <td>
                    <Button variant="secondary" size="small">
                      Submit as final
                    </Button>
                  </td>
                </tr>
              </tbody>
            </table>
            <UploadDropZone accept=".pdf,.zip" onFiles={(files) => setLastUpload(files.map((f) => f.name).join(', '))} />
            {lastUpload && <p className="small muted">Picked: {lastUpload}</p>}
          </Card>
        </div>

        <div className="col gap24" style={{ width: 380 }}>
          <Card className="col">
            <div className="row between">
              <h3>Notifications</h3>
              <button type="button" className="small link">
                Mark all as read
              </button>
            </div>
            <NotificationRow
              unread
              icon="users"
              title="Km Shristi Singh submitted v2 as your team's final"
              meta="CS301 · Group Project · 2 Nov, 18:12 IST"
            />
            <NotificationRow
              unread
              icon="star"
              title="Marks released for Lab 3: Git workflow"
              meta="CS301 · 30 Oct, 16:00 IST"
            />
            <NotificationRow icon="upload" title="Tirtho Paul uploaded draft v3" meta="CS301 · Group Project · 3 Nov, 21:40 IST" />
          </Card>

          <AiFeedbackPanel
            width="auto"
            warning="Only the first 12,000 characters (about 6 of 9 pages) were read."
            footnote="Names, emails and roll numbers were removed before sending. Suggestions are never shown to students."
            actions={
              <>
                <Button variant="secondary" size="small" className="grow">
                  Regenerate (2 left)
                </Button>
                <Button variant="tint" size="small" className="grow">
                  Use all
                </Button>
              </>
            }
          >
            <p className="small">
              <b>Implementation, 20/25:</b> booking conflicts are handled; input validation is missing in the room form.
            </p>
            <p className="small">
              <b>Testing, 7/10:</b> good unit tests, no integration tests.
            </p>
          </AiFeedbackPanel>

          <Card className="col gap12">
            <h3>Icons</h3>
            <div className="row gap12 wrap text-primary">
              {ICON_NAMES.map((name) => (
                <span key={name} title={name}>
                  <Icon name={name} label={name} />
                </span>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  )
}
