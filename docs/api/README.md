# Unison API guide

The API description is [docs/openapi.yaml](../openapi.yaml) (OpenAPI 3.1). It is generated from the FastAPI code, so it always matches what the server does; CI fails if the two disagree. [ENDPOINTS.md](ENDPOINTS.md) lists every operation by module.

## Viewing it

| How | Where |
|---|---|
| Swagger UI (try requests) | http://localhost:8000/api/v1/docs after `docker compose up` |
| ReDoc (easier reading) | http://localhost:8000/api/v1/redoc |
| Without running anything | Paste `docs/openapi.yaml` into https://editor.swagger.io |

## Conventions

- **Base path:** `/api/v1`. Paths are plural and kebab-case, for example `/courses/{course_id}/join-requests` and `/teams/{team_id}/submission/drafts`.
- **Paths are nouns; the method is the action.** `GET` reads, `POST` creates (201), `PATCH` changes some fields (200), `PUT` replaces a whole value such as a password or the scores (200 or 204), `DELETE` removes (204). Changes of state are `PATCH`es of a field: publishing an assignment is `PATCH /assignments/{id}` with `{"status": "published"}`, accepting an invitation is `PATCH /invitations/{id}` with `{"status": "accepted"}`, leaving a team is `DELETE /teams/{id}/members/me`. Only logging in and out (`/auth/register`, `/auth/login`, `/auth/logout`) are named as actions.
- **Status codes:**

  | Code | Meaning |
  |---|---|
  | 200 | OK |
  | 201 | Created (the body is the new item) |
  | 202 | Accepted: work continues in the background (emails, AI drafts, account deletion) |
  | 204 | Done, no body |
  | 400 | The request makes no sense (for example a bad link token) |
  | 401 | Not logged in |
  | 403 | Logged in, but not allowed |
  | 404 | Not found, or not yours to know about (a team you are not on, a draft for a teacher) |
  | 409 | Conflicts with the current state (deadline passed, team full, final changed) |
  | 413 | File too large |
  | 422 | Invalid input |
  | 429 | Too many requests (login attempts, sign-ups, join requests, AI drafts) |
  | 503 | An optional service is not set up (Google sign-in, AI) |

- **Every list** takes `?page=1&size=20` (`size` 1 to 50) and returns, in a fixed order (usually newest first):

      {"items": [...], "page": 1, "size": 20, "total": 57}

- **Errors** always have the same body:

      {"error": {"code": "TEAM_FULL", "message": "This team is full.", "details": null, "request_id": "4f1c2b9e7a3d4c5e"}}

  `code` is stable and meant for the frontend; `message` is for people. `request_id` is also in the `X-Request-ID` response header and in the server log. For invalid input (`422 VALIDATION_ERROR`), `details` lists `{field, problem}` pairs.
- **Times** are ISO 8601 in Indian Standard Time, for example `2026-11-05T23:59:59+05:30`. A time sent without an offset is read as IST. The database stores UTC. A deadline of 23:59 means 23:59:59 IST.
- **Points and marks** are decimals with one place, sent as strings in responses (`"24.5"`), so no precision is lost.

## Logging in

| Mode | How a request is identified |
|---|---|
| Session (the real site) | `POST /auth/login` or `POST /auth/register` sets an `HttpOnly`, `SameSite=Lax` cookie `unison_session` (7 days). Requests that change something and use the cookie must also send `X-Unison-Client: web` (CSRF protection). |
| Demo (`AUTH_MODE=demo`, the default in docker-compose) | Also accepts the header `X-Demo-User: <email of a seeded user>`. In Swagger: **Authorize**, fill `X-Demo-User`, close. Never use demo mode on a public server. |

Seeded accounts (password `unison-demo` for all of them):

| Email | Who |
|---|---|
| `demo.student@example.com` | Sandeep M, student, team Byte Builders in CS301 |
| `shristi.demo@example.com`, `tirtho.demo@example.com` | Km Shristi Singh and Tirtho Paul, same team |
| `ujjwal.demo@example.com` | Ujjwal Gupta, has a pending invitation to Byte Builders |
| `demo.teacher@example.com` | Dr. Kavya Menon, teaches CS301 Software Engineering |
| `demo.admin@example.com` | An administrator |
| `admin@example.com` | The first administrator (password `unison-admin`, must be changed at first login) |

Rate limits never lock an account: 5 failed logins for one email from one IP in 15 minutes pause that pair for 15 minutes; 30 failures from one IP pause the IP; failures for one email from many IPs only add a delay of up to 10 seconds. Sign-ups: 5 per IP per hour.

## Things that need care in the frontend

- **Submitting a final** (`POST /teams/{team_id}/submission/finals`) sends the id of the final the member last saw as `expected_final_id`. If a teammate changed it, the answer is `409 FINAL_CHANGED` with the current final in `details.current_final`: show it and ask again.
- **Idempotency:** uploads and finals need an `Idempotency-Key` header with a new UUID per click. Sending the same key again returns the first result instead of creating a second draft or final.
- **Uploads** are `multipart/form-data`. Drafts: field `files`, up to 5 PDF or ZIP files of 10 MB each. Resources: field `file`, up to 25 MB, PDF, Word, PowerPoint, Excel, text, PNG, JPEG or ZIP. The server checks the file's content, not only its name.
- **Downloads** always come as attachments (`Content-Disposition: attachment`).
- **AI drafts** are background jobs: `POST /teams/{team_id}/review/ai-drafts` answers `202` with a draft in `queued`; poll `GET /ai-drafts/{id}` every few seconds until `ready` or `failed`. `200` means a cached draft was reused. `503 AI_DISABLED` means the button should be disabled.
- **The bell:** poll `GET /notifications/unread-count` every 30 seconds.

## Error codes

| Area | Codes |
|---|---|
| General | `VALIDATION_ERROR`, `NOT_FOUND`, `FORBIDDEN`, `INTERNAL_ERROR`, `METHOD_NOT_ALLOWED` |
| Login and accounts | `NOT_AUTHENTICATED`, `SESSION_EXPIRED`, `CSRF_HEADER_MISSING`, `DEMO_USER_UNKNOWN`, `INVALID_CREDENTIALS`, `TOO_MANY_ATTEMPTS`, `TOO_MANY_SIGNUPS`, `ACCOUNT_SUSPENDED`, `ACCOUNT_INACTIVE`, `ACCOUNT_DELETED`, `PASSWORD_CHANGE_REQUIRED`, `WRONG_PASSWORD`, `PASSWORD_TOO_SHORT`, `PASSWORD_TOO_LONG`, `CONSENT_REQUIRED`, `EMAIL_DOMAIN_NOT_ALLOWED`, `EMAIL_TAKEN`, `EMAIL_LIMIT`, `EMAIL_NOT_VERIFIED`, `ALREADY_VERIFIED`, `PRIMARY_EMAIL`, `NO_PASSWORD`, `INVALID_TOKEN`, `REAUTH_REQUIRED`, `LAST_ADMIN` |
| Google | `GOOGLE_NOT_CONFIGURED`, `GOOGLE_STATE_MISSING`, `GOOGLE_STATE_INVALID`, `GOOGLE_EXCHANGE_FAILED`, `GOOGLE_TOKEN_INVALID`, `GOOGLE_EMAIL_NOT_VERIFIED` |
| Courses | `TEACHERS_ONLY`, `STUDENTS_ONLY`, `ADMIN_ONLY`, `NOT_COURSE_TEACHER`, `NOT_COURSE_MEMBER`, `NOT_COURSE_STUDENT`, `COURSE_EXISTS`, `COURSE_ARCHIVED`, `DEPARTMENT_EXISTS`, `UNKNOWN_DEPARTMENT`, `NOT_A_TEACHER`, `LAST_TEACHER`, `NOT_REMOVED`, `CANNOT_UNARCHIVE`, `JOIN_REQUESTS_CLOSED`, `JOIN_REQUEST_LIMIT`, `ALREADY_MEMBER`, `ALREADY_REQUESTED`, `REMOVED_FROM_COURSE` |
| Invitations | `ALREADY_INVITED`, `ALREADY_STAFF`, `NOT_ENROLLED`, `CANNOT_INVITE_SELF`, `WRONG_ACCOUNT`, `INVITATION_NOT_PENDING`, `INVALID_INVITATION`, `NOT_PENDING` |
| Assignments and teams | `DEADLINE_IN_PAST`, `DEADLINE_PASSED`, `NOT_LATER`, `ASSIGNMENT_PUBLISHED`, `ALREADY_PUBLISHED`, `ASSIGNMENT_NOT_OPEN`, `TEAM_SIZE`, `NOT_GROUP`, `TEAMS_LOCKED`, `TEAM_FULL`, `TEAM_CLOSED`, `TEAM_HAS_FINAL`, `TEAM_NAME_TAKEN`, `ALREADY_IN_TEAM`, `SAME_TEAM`, `MARKS_RELEASED` |
| Files | `FILE_TYPE_NOT_ALLOWED`, `FILE_TYPE_MISMATCH`, `FILE_TOO_LARGE`, `FILE_EMPTY`, `NO_FILES`, `TOO_MANY_FILES`, `RESOURCE_IS_LINK`, `NOT_A_LINK` |
| Submissions | `IDEMPOTENCY_KEY_INVALID`, `FINAL_CHANGED`, `ALREADY_FINAL`, `TEAM_BELOW_MIN_SIZE`, `PDF_REQUIRED` |
| Reviews | `NO_FINAL`, `SUBMISSION_OPEN`, `REVIEW_RELEASED`, `REVIEW_INCOMPLETE`, `UNKNOWN_CRITERION`, `POINTS_OUT_OF_RANGE` |
| AI | `AI_DISABLED`, `NO_PDF_REPORT`, `CHOOSE_PDF`, `NOT_A_PDF_IN_FINAL`, `AI_LIMIT_SUBMISSION`, `AI_LIMIT_COURSE`; failed drafts carry `TIMEOUT`, `PROVIDER_ERROR`, `QUOTA_EXHAUSTED`, `INVALID_OUTPUT`, `REDACTION_FAILED`, `PDF_UNREADABLE` |
| Admin and settings | `USER_DELETED`, `USER_NOT_ACTIVE`, `USER_NOT_SUSPENDED`, `CANNOT_SUSPEND_SELF`, `INVALID_SETTING`, `UNKNOWN_EVENT_TYPE` |

## Updating the YAML

After changing any route or schema, from `backend/`:

    python scripts/export_openapi.py

or with Docker only:

    docker compose run --rm --no-deps --user root -v "${PWD}/docs:/docs-out" -e DOCS_DIR=/docs-out backend python scripts/export_openapi.py

Commit `docs/openapi.yaml` and `docs/api/ENDPOINTS.md` with the code change.
