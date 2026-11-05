# Unison frontend

React 19 + Vite, plain JavaScript, React Router. In Docker it is built and served by nginx, which also forwards `/api` to the backend, so the browser sees one site and the session cookie just works.

## Pages

Every page follows its Figma screen at 1440 px wide and also works on a phone (390 px). Pages that Figma does not draw reuse the same components and layout.

| Figma | Page | Address |
|---|---|---|
| 01 | Course catalogue | `/catalogue` (also `/` for visitors) |
| 02 | Course page (members) and course preview (visitors, join request) | `/courses/:id` |
| 03 | Log in and sign up | `/login`, `/signup` |
| 04 | Invitation (team, course and staff) | `/invitations/:token`, `/invitations?id=` |
| 05 | Student dashboard | `/dashboard` |
| 06, 06b | Team workspace, and the marks view for released results | `/teams/:id`, `/teams/:id/marks` |
| 07 | Teacher dashboard | `/dashboard` |
| 08 | Course management: details, resources, assignments, members, teams, email rules | `/courses/:id/manage` |
| 09 | Review, with the AI feedback draft | `/assignments/:id/review` |
| 10 | Admin dashboard | `/admin` |
| 11 | Profile and account | `/profile` |
| none | My courses, join requests, notifications | `/courses`, `/join-requests`, `/notifications` |
| none | Admin: users, one user, courses, departments, audit log, settings | `/admin/...` |
| none | Forgot and reset password, verify email, first-login password change | `/forgot-password`, `/reset-password`, `/verify-email`, `/change-password` |
| none | About and privacy, page not found | `/about`, any other address |

`/assignments/:id` sends a student to their team (or offers to create one) and a teacher to the review page. `/dev/components` shows every shared component.

## Running it

With the whole stack from the repository root: `docker compose up --build`, then http://localhost:8080.

For frontend work (Node 22), start the backend in Docker from the repository root with `docker compose up --build backend worker mailpit`, then start Vite in `frontend/`:

    npm ci
    npm run dev                 # http://localhost:5173, /api forwarded to port 8000
    npm run lint                # ESLint
    npm test                    # Vitest
    npx vitest run --coverage   # coverage report in coverage/index.html
    npm run build               # production build in dist/

If the backend is not running, pages show "The backend is not answering on http://127.0.0.1:8000". To use a backend elsewhere, start Vite with `API_TARGET=http://host:port npm run dev`.

Screens adapt to the width: above 1024 px the sidebar is always shown; below it, it opens from the **Menu** button. Stat cards go two by two below 1100 px, and side columns move under the main column below 1300 px (team workspace, review) or 1024 px (other pages).

Demo logins: `demo.student@example.com`, `demo.teacher@example.com`, `demo.admin@example.com`, password `unison-demo`.

## How the code is organised

| Path | What |
|---|---|
| `src/App.jsx` | Every route; `RequireAuth` guards the private ones by role |
| `src/api/client.js` | The only way pages talk to the API |
| `src/api/useApi.js` | Loads data for a page: `{ data, error, loading, reload, setData }` |
| `src/auth/` | Who is logged in, the unread count, "Keep me signed in" |
| `src/components/` | Shared components (cards, badges, buttons, form controls, tables, dialogs, toasts) |
| `src/layouts/` | The app shell with the sidebar, and the public top bar |
| `src/lib/` | IST dates, text helpers, dark mode, notification icons |
| `src/pages/` | One folder per area |
| `src/styles/tokens.css` | Every colour, size and shadow from Figma, plus dark mode |

Rules that keep the pages matching the design:

- Build pages from `src/components` (import from `../components`). Do not restyle them, add a UI library or invent new colours.
- Layout helpers have the mockup's names: `row`, `col`, `grow`, `between`, `start`, `wrap`, `gap8` to `gap32`, `muted`, `small`, `tiny`.
- Accessibility: every control has a label (`label` or `aria-label`), tables use `<th scope="col">`, dialogs take the focus and close with Escape, keyboard focus stays visible.

## Talking to the API

Use the client in `src/api/client.js`; never call `fetch` directly in a page. It adds the `X-Unison-Client: web` header that the backend's CSRF check needs on every change, and turns error bodies into `ApiError` with the backend's code.

```js
import { api, getAll, newIdempotencyKey } from '../api/client'

const page = await api.get('/courses', { q: 'CS301', page: 1, size: 20 })
const members = await getAll(`/courses/${id}/members`) // every page of a short list
try {
  await api.post(`/teams/${teamId}/submission/finals`, body, { headers: { 'Idempotency-Key': newIdempotencyKey() } })
} catch (error) {
  if (error.code === 'FINAL_CHANGED') {
    // a teammate submitted first: show their final and ask again
  }
}
```

Times from the API carry their offset (`+05:30`). Show them with the helpers in `src/lib/datetime.js`, for example `formatDeadline` gives "Thu 5 Nov, 23:59 IST".

## Tests

Tests sit next to the code they test (`*.test.js`, `*.test.jsx`) and run in jsdom.

- `src/lib`, `src/api`, `src/components`: unit tests.
- `src/pages/**`: page tests that open the whole app at an address, click and type like a user, and check what the page shows and what it sends to the API.
- `src/test/fakeApi.jsx` answers the page tests from `src/test/fixtures.json`: real responses recorded from the seeded demo backend for the anonymous visitor, the demo student, teacher and admin. A test can override any answer, for example to return `409 FINAL_CHANGED`.
- `src/test/setup.js` fixes "now" at Thu 29 Oct 2026, 19:30 IST, the time the fixtures were recorded.

CI fails if line coverage drops below 60%.
