import { Button, Card, Icon } from '../../components'
import PublicPage from '../../layouts/PublicNav'

// "About" from the public top bar (not drawn in Figma): what Unison is, and the privacy
// notice the sign-up form links to.
export default function AboutPage() {
  const features = [
    ['users', 'Group submissions', 'Teams share private drafts, and any member submits one final for everyone.'],
    ['bell', 'Notifications', 'In-app and email notices for invitations, deadlines, finals and marks.'],
    ['star', 'Fair marking', 'One team mark from the rubric, with a small adjustment per member and a reason.'],
    ['sparkle', 'AI feedback draft', 'Teachers can ask for a suggested mark per criterion. Students never see it.'],
  ]
  return (
    <PublicPage>
      <main id="main" className="col gap24 page-pad" style={{ maxWidth: 1180 }}>
        <div>
          <div className="eyebrow">About Unison</div>
          <h1 style={{ marginTop: 6 }}>Group work, handed in together</h1>
          <p className="muted" style={{ marginTop: 6, maxWidth: 720 }}>
            Unison is a learning management system for IIT Dharwad courses, built by Team Bootstrap for CS602C
            Advanced Software Development Lab. Teachers publish resources and assignments; students form teams,
            share drafts and submit one final per team.
          </p>
        </div>
        <div className="row wrap gap24 start">
          {features.map(([icon, title, text]) => (
            <Card key={title} className="col gap12" style={{ flex: '1 1 220px' }}>
              <span className="bellb tone-soft" style={{ width: 42, height: 42 }}>
                <Icon name={icon} size={20} />
              </span>
              <h2 style={{ fontSize: 16, fontWeight: 600 }}>{title}</h2>
              <p className="small muted">{text}</p>
            </Card>
          ))}
        </div>
        <Card id="privacy" className="col gap8" style={{ maxWidth: 820 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>Privacy</h2>
          <p className="small muted">
            Unison keeps only what it needs to run your courses: your name, your institute email, your courses, your
            team work and your marks. Passwords are stored as Argon2 hashes. You can download everything Unison
            holds about you from Profile and account, and delete your account at any time: it is deactivated at
            once and deleted after 7 days.
          </p>
          <p className="small muted">
            The AI feedback draft reads only the PDF report of a team's final, after names, emails and roll numbers
            are removed.
          </p>
        </Card>
        <div className="row gap12">
          <Button to="/catalogue">Browse courses</Button>
          <Button variant="secondary" to="/signup">
            Sign up
          </Button>
        </div>
      </main>
    </PublicPage>
  )
}
