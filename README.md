# Unison

**A learning management system with collaborative group submissions.**
Course project for CS602C Advanced Software Development Lab, IIT Dharwad (2026), by Team Bootstrap.

Unison is an LMS for one institute, built around group assignments. Administrators organise courses by department and assign teachers. Teachers publish notes and assignments and bring students in by email invitation or by approving join requests. Students form teams by inviting classmates, share private drafts, and any member submits one draft as the team's final. Every member and the teacher are notified in the app and by email, and the teacher sees only that final. Teachers give one mark per team, can adjust it for a member whose contribution differed, and release it; students then see their marks and comments. An optional AI feature drafts rubric-based feedback that the teacher reviews before anything reaches students.

> **Status: backend complete (MS-3).** The API, database, migrations, seed data, background worker, tests and CI run with one `docker compose up`. The frontend follows in its own pull requests.

## Links

| What | Where |
|---|---|
| Design document (MS-1) | [docs/Unison_MS1_Design_Document.pdf](docs/Unison_MS1_Design_Document.pdf) |
| ER diagram and data model (MS-2) | [docs/Unison_ER_Diagram.pdf](docs/Unison_ER_Diagram.pdf) |
| ER diagram, single page (MS-2) | [docs/Unison_ER_Diagram_Full.pdf](docs/Unison_ER_Diagram_Full.pdf) |
| Figma prototype (MS-2) | [Open the prototype](https://www.figma.com/proto/om1QUA9cFgcnGmX6WvVcMx/new_unison--Copy-?node-id=2-2&p=f&t=fg6lFnAHWouVsMsE-1&scaling=min-zoom&content-scaling=fixed&page-id=0%3A1&starting-point-node-id=2%3A2&show-proto-sidebar=1) |
| Prototype walkthrough video (MS-2) | [Watch on Google Drive](https://drive.google.com/file/d/139FEv3z5U7PNt7YEiOYTNQquafv_i0h-/view?usp=sharing) |
| API description, OpenAPI 3 (MS-3) | [docs/openapi.yaml](docs/openapi.yaml) |
| API guide and every endpoint (MS-3) | [docs/api/README.md](docs/api/README.md), [docs/api/ENDPOINTS.md](docs/api/ENDPOINTS.md) |

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

## Stack

| Layer | Choice |
|---|---|
| Frontend | React + Vite, served by nginx (in progress) |
| Backend | Python 3.12, FastAPI (modular monolith, 12 modules), REST under `/api/v1`, OpenAPI 3 YAML |
| Database | MySQL 8.4, SQLAlchemy 2, Alembic migrations |
| Background work | Worker container using MySQL as its job queue (email outbox, deadlines, invitation expiry, AI jobs, account deletion) |
| Email | SMTP via a transactional outbox; Mailpit for local development |
| AI | Gemini API or a local model through Ollama (both optional) |
| Testing and CI | pytest with coverage against MySQL, Ruff, GitHub Actions |
| Packaging | Docker Compose: `db`, `init`, `backend`, `worker`, `mailpit` (`frontend` to come) |

## How to run

You need **Docker Desktop** (running) and Git. Nothing else: MySQL, Python and the mail server all run in containers.

    git clone https://github.com/sandeepmohaniitdh/unison.git
    cd unison
    docker compose up --build

The first start takes a few minutes. When `init` has finished (migrations, the first admin and the demo data):

| Address | What |
|---|---|
| http://localhost:8000/api/v1/docs | Swagger UI: every endpoint, try them out |
| http://localhost:8000/api/v1/health | `{"status": "ok", "database": "ok", ...}` |
| http://localhost:8025 | Mailpit: every email the site sends lands here |
| `localhost:3307` | MySQL, user `unison`, password `unison` (for MySQL Workbench) |

**Trying the API in Swagger:** click **Authorize**, type a demo email in `X-Demo-User` (for example `demo.student@example.com`, `demo.teacher@example.com` or `demo.admin@example.com`) and close. Every seeded account also logs in with the password `unison-demo`. The first administrator is `admin@example.com` with `unison-admin`, and must change the password at first login. More in the [API guide](docs/api/README.md).

Stop with `Ctrl+C`. `docker compose down` removes the containers; `docker compose down -v` also deletes the database and uploads, so the next start seeds fresh data.

Google sign-in and the AI feature are optional. Without their keys the site runs with password login and the AI button disabled. To try them, set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, or `AI_PROVIDER=gemini` and `GEMINI_API_KEY`, before `docker compose up`.

## Repository layout

| Path | What |
|---|---|
| `backend/app/main.py` | The FastAPI app; every module's router under `/api/v1` |
| `backend/app/core/` | Shared parts: error format, pagination, IST times, security, file storage, email, permissions |
| `backend/app/modules/<module>/` | One folder per module: `models.py` (tables), `schemas.py` (request and response bodies), `service.py` (rules), `router.py` (endpoints) |
| `backend/app/worker.py` | The background worker |
| `backend/app/bootstrap.py` | The `init` job: migrations, first admin, seed |
| `backend/app/seed/` | The synthetic dataset |
| `backend/alembic/` | Database migrations |
| `backend/tests/` | pytest tests (run against MySQL) |
| `docs/openapi.yaml`, `docs/api/` | The OpenAPI description, the endpoint list and the API guide |
| `db/init/` | Creates the `unison_test` database on first start |
| `.github/workflows/ci.yml` | CI: lint, migrations, tests with coverage, OpenAPI check, full compose start |

## Development

Run the tests (they use the `unison_test` database in the `db` container):

    docker compose --profile test run --rm --build tests

Lint and format (from `backend/`, with Python 3.12 and `pip install -r requirements-dev.txt`, or inside the tests container):

    ruff check . && ruff format .

After changing a model, create a migration (the new file appears in `backend/alembic/versions/`), read it, then apply it:

    docker compose run --rm --user root -v "${PWD}/backend:/app" backend alembic revision --autogenerate -m "what changed"
    docker compose run --rm init

After changing a route or schema, regenerate the API description (see [the API guide](docs/api/README.md#updating-the-yaml)) and commit `docs/openapi.yaml` and `docs/api/ENDPOINTS.md`.

## Dataset

All data is synthetic. Department names and course codes and titles are invented by the team (for example "CS301 Software Engineering"); nothing is copied from the institute's curriculum or any other site. People are generated with [Faker](https://faker.readthedocs.io/) (`en_IN` locale) using `example.com` emails, so no seeded email can reach a real inbox. The seed script uses a fixed random seed, so every fresh clone gets the same data.

Size: 5 departments, 20 courses, 300 students, 15 teachers and 2 admins; 1,200 enrolments and 60 join requests; 60 assignments; about 380 group teams and 1,440 teams of one; about 2,400 drafts with 3,400 placeholder PDFs; about 1,270 released reviews; 400 invitations; 100 resources; 1,500 notifications. CS301 Software Engineering contains the people and team shown in the Figma screens.

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
