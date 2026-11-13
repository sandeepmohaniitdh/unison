# End-to-end tests

Playwright drives a real Chromium browser against the whole stack (`docker compose up`), with the seeded demo data and Mailpit.

| Test | Flow |
|---|---|
| `tests/signup-and-join.spec.js` | A new student signs up (consent box required), confirms the email from Mailpit, logs out and in, asks to join CS301; the teacher approves; the course appears under the student's courses |
| `tests/submit-and-review.spec.js` | The demo student uploads a PDF draft and submits it as final; the teacher opens the review page and gets the AI feedback draft (fake model) |
| `tests/access-control.spec.js` | Visitors and students cannot open the admin console (pages redirect, the API answers 401 and 403); after "Log out" the old session no longer works |

Run them (Node 22), with the stack running and `AI_PROVIDER=fake` in `.env`:

    npm ci
    npx playwright install chromium
    npx playwright test

`E2E_BASE_URL` (default http://localhost:8080) and `MAILPIT_URL` (default http://localhost:8025) point the tests elsewhere. In CI they run in the `compose` job after the stack has started; the HTML report is uploaded as the `playwright-report` artifact.

The tests change the demo data (a new account, a join request, a new final), so run them on a laptop stack you can reset with `docker compose down -v`.
