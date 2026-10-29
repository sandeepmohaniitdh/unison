# Unison backend

FastAPI + SQLAlchemy 2 + Alembic on MySQL 8. See the main [README](../README.md) for running everything with Docker, and the [API guide](../docs/api/README.md).

## How a request flows

1. `app/main.py` sends `/api/v1/...` to a module's `router.py`.
2. The router checks the input with the Pydantic schemas in `schemas.py` and gets the current user from `app/core/deps.py` (`CurrentUser`).
3. It calls one function in the module's `service.py`, which checks permissions (`app/core/permissions.py`), applies the rules, writes to the database through the models in `models.py`, calls `notifications.service.notify()` if someone must be told, and commits.
4. Errors are raised as `AppError` (`app/core/errors.py`) and turned into the standard error body.

## Modules and owners

| Module | Owner | Tables |
|---|---|---|
| auth | Sandeep M | oauth_identities, sessions, login_attempts, email_tokens |
| users | Sandeep M | users, user_emails |
| submissions | Sandeep M | submissions, submission_versions, final_submissions, submission_files |
| courses | Km Shristi Singh | departments, courses, enrollments |
| invitations | Km Shristi Singh | invitations |
| admin | Km Shristi Singh | audit_log, platform_settings |
| resources | Tirtho Paul | resources |
| assignments | Tirtho Paul | assignments, rubric_criteria |
| teams | Tirtho Paul | teams, team_members |
| notifications | Ujjwal Gupta | notifications, notification_preferences, notification_rules, email_outbox |
| reviews | Ujjwal Gupta | reviews, review_scores, member_adjustments |
| ai | Ujjwal Gupta | ai_feedback |

## Settings

Every setting is an environment variable with a default (`app/config.py`), so no `.env` file is needed. The important ones:

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `mysql+pymysql://unison:unison@db:3306/unison` | The database |
| `AUTH_MODE` | `session` (`demo` in docker-compose) | `demo` also accepts the `X-Demo-User` header |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | `admin@example.com`, `unison-admin` | The first administrator |
| `SEED_ON_START` | `true` | Load the demo data into an empty database |
| `AI_PROVIDER` | `none` | `gemini` (with `GEMINI_API_KEY`), `ollama` or `fake` |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | empty | Google sign-in, off when empty |
| `TRUST_PROXY` | `false` | Trust `X-Forwarded-For` (only behind our nginx) |

## Tests

    docker compose --profile test run --rm --build tests

The tests need MySQL: a database whose name ends in `_test` (`TEST_DATABASE_URL`). Each test runs in a transaction that is rolled back. The clock is frozen at 10:00 IST on 2 November 2026, so tests can jump past deadlines with `clock.advance(days=4)`.
