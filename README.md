# Unison

**A learning management system with collaborative group submissions.**
Course project for CS602C Advanced Software Development Lab, IIT Dharwad (2026), by Team Bootstrap.

Unison is an LMS for one institute, built around group assignments. Administrators organise courses by department and assign teachers. Teachers publish notes and assignments and bring students in by email invitation or by approving join requests. Students form teams by inviting classmates, share private drafts, and any member submits one draft as the team's final. Every member and the teacher are notified in the app and by email, and the teacher sees only that final. Teachers give one mark per team, can adjust it for a member whose contribution differed, and release it; students then see their marks and comments. An optional AI feature drafts rubric-based feedback that the teacher reviews before anything reaches students.

> **Status: design phase (MS-1).** The repository holds the plan; code starts at MS-2. The "How to run" section describes the target setup.

## Links

| What | Where |
|---|---|
| Design document (MS-1) | Submitted to the instructor; a copy will be added under `docs/` |
| Figma prototype (MS-2) | https://www.figma.com/design/HyKek9301fGwxNf429wi8m |

## Main features

- **Accounts and roles:** sign-up with an `@iitdh.ac.in` email or Google account always creates a student; teachers and admins join by invitation from an admin.
- **Courses:** departments, course catalogue, email invitations and join requests, resources (notes, slides, links) that stay drafts until published.
- **Teams:** any active member can invite classmates; invitations reserve places so a team never exceeds its size limit.
- **Group submission:** private team drafts, one shared final submitted by any member, conflict-safe and duplicate-free; at the deadline the latest draft is submitted automatically.
- **Marks:** one team mark against a rubric, an optional per-member adjustment (−20% to +10%, with a reason), and a marks view for students.
- **Notifications:** always in the app; email on by default, with an opt-out per type.
- **Admin console:** departments, users and roles, any course, platform settings and an audit log of every admin action.
- **AI feedback draft:** suggested rubric marks and comments for the teacher, with names removed before anything is sent.

All deadlines are in IST (Asia/Kolkata).

## Planned stack

| Layer | Choice |
|---|---|
| Frontend | React + Vite, served by nginx |
| Backend | Python 3.12, FastAPI (modular monolith), REST under `/api/v1`, OpenAPI 3 YAML |
| Database | MySQL 8, SQLAlchemy 2.0, Alembic migrations |
| Background work | Worker container using MySQL as its job queue (email outbox, deadlines, AI jobs) |
| Email | SMTP via a transactional outbox; Mailpit for local development |
| AI | Gemini API (`google-genai`) or a local model through Ollama |
| Testing and CI | pytest, Playwright, GitHub Actions |
| Packaging | Docker Compose: `db`, `init`, `backend`, `worker`, `frontend`, `mailpit` |

## How to run (target, from MS-2)

    git clone https://github.com/sandeepmohaniitdh/unison.git
    cd unison
    docker compose up

- Site: http://localhost:8080
- Local inbox (Mailpit): http://localhost:8025
- The first administrator is created on first start from `ADMIN_EMAIL` and `ADMIN_PASSWORD`; Compose supplies development defaults, so no `.env` file is needed.
- Google sign-in and the AI feature are optional. Without their keys the site still runs with password login and the AI button disabled.

## Dataset

All data is synthetic. Department names and course codes and titles are invented by the team (for example "CS301 Software Engineering"); nothing is copied from the institute's curriculum or any other site. People are generated with [Faker](https://faker.readthedocs.io/) (`en_IN` locale) using `example.com` emails, so no seeded email can reach a real inbox. The seed script uses a fixed random seed, so every fresh clone gets the same data.

## Team and ownership

| Member | Roll number | Backend modules | Pages | Shared task |
|---|---|---|---|---|
| Sandeep M | CS26MT001 | auth, users, submissions | Sign up and log in, Profile | Docker Compose, CI, OpenAPI drift check, Playwright setup |
| Km Shristi Singh | CS26MT011 | courses and departments, invitations, admin | Course catalogue, Invitation, Admin dashboard | Dataset and seed script; second marker for the AI evaluation |
| Tirtho Paul | CS26MT024 | resources, assignments and rubrics, teams | Course page, Team workspace, Course management | ER diagram and migrations |
| Ujjwal Gupta | CS26MT025 | notifications, reviews, AI | Student dashboard, Teacher dashboard, Review | AI evaluation set; accessibility check |

## How we work

- `main` is protected: every change arrives through a pull request with one approving review from another member, and all review conversations must be resolved. Nobody, including admins, can push to `main` directly.
- One branch per piece of work, named `<area>/<short-description>`, for example `teams/invite-limits`.
- The owner of a module or page writes its code and tests and opens its pull requests, so Git history shows each member's own work.

## Milestones

| Milestone | Date | Main deliverables |
|---|---|---|
| MS-1 | 15 Oct | Design document; repository and branch protection |
| MS-2 | 22 Oct | Figma prototype; ER diagram; FastAPI, Docker, Mailpit and worker skeleton; CI skeleton |
| MS-3 | 29 Oct | OpenAPI YAML for every endpoint (unbuilt routes return `501`); migrations and seed; course, resource, assignment, team and invitation endpoints; catalogue, course and invitation pages |
| MS-4 | 5 Nov | Drafts and finals; reviews and marks; notifications and email worker; dashboards, team workspace, course management, review and profile pages; 60% coverage |
| MS-5 | 12 Nov | Password and Google sign-in; password reset; account deletion; admin dashboard; notification settings; AI feature and evaluation; Playwright tests; 70% coverage |
| MS-6 | 19 Nov | Final report, presentation and live demo |
