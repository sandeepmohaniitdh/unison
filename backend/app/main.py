"""The FastAPI application: every module's router under /api/v1."""

import logging

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
from sqlalchemy import text

from app.config import get_settings
from app.core.deps import DB
from app.core.errors import ErrorBody, install_error_handlers
from app.core.openapi import errors
from app.modules.admin.router import router as admin_router
from app.modules.ai.router import router as ai_router
from app.modules.assignments.router import router as assignments_router
from app.modules.auth.router import router as auth_router
from app.modules.courses.router import router as courses_router
from app.modules.invitations.router import router as invitations_router
from app.modules.notifications.router import router as notifications_router
from app.modules.resources.router import router as resources_router
from app.modules.reviews.router import router as reviews_router
from app.modules.submissions.router import router as submissions_router
from app.modules.teams.router import router as teams_router
from app.modules.users.router import router as users_router

VERSION = "1.0.0"

DESCRIPTION = """
REST API of **Unison**, a learning management system with collaborative group submissions
(CS602C Advanced Software Development Lab, IIT Dharwad, Team Bootstrap).

**Conventions**

- All paths are under `/api/v1`, plural and kebab-case.
- Every list takes `?page=1&size=20` (size 1 to 50) and returns `{items, page, size, total}`, in a fixed order.
- Every error has the same body: `{"error": {"code", "message", "details", "request_id"}}`.
- Times are ISO 8601 in Indian Standard Time (`+05:30`). A time sent without an offset is read as IST.
- 401: not logged in. 403: not allowed. 404: not found, or not yours to know about. 409: conflicts with
  the current state. 422: invalid input. 429: rate limit.

**Logging in**

- The site uses a session cookie (`POST /auth/login`). Requests that change something and use the cookie
  must also send the header `X-Unison-Client: web`.
- In demo mode (`AUTH_MODE=demo`, the default in docker-compose), click **Authorize** and type a seeded
  email in `X-Demo-User`, for example `demo.student@example.com`, `demo.teacher@example.com` or
  `demo.admin@example.com`.
"""

TAGS = [
    {"name": "auth", "description": "Sign-up, login, logout, email links and Google sign-in. Owner: Sandeep M."},
    {"name": "users", "description": "Profile, emails, data download and account deletion. Owner: Sandeep M."},
    {"name": "courses", "description": "Departments, catalogue, members and join requests. Owner: Km Shristi Singh."},
    {"name": "invitations", "description": "Course, team and staff invitations. Owner: Km Shristi Singh."},
    {"name": "resources", "description": "Course files and links. Owner: Tirtho Paul."},
    {"name": "assignments", "description": "Assignments, rubrics and deadlines. Owner: Tirtho Paul."},
    {"name": "teams", "description": "Teams and membership. Owner: Tirtho Paul."},
    {"name": "submissions", "description": "Drafts, the team's final and downloads. Owner: Sandeep M."},
    {"name": "reviews", "description": "Rubric marks, adjustments and releasing marks. Owner: Ujjwal Gupta."},
    {"name": "ai", "description": "AI feedback drafts for the teacher. Owner: Ujjwal Gupta."},
    {"name": "notifications", "description": "Notifications, email settings and dashboards. Owner: Ujjwal Gupta."},
    {"name": "admin", "description": "Users and roles, statistics, audit log and settings. Owner: Km Shristi Singh."},
    {"name": "health", "description": "Liveness and database check."},
]


class Health(BaseModel):
    status: str
    database: str
    version: str


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    app = FastAPI(
        title="Unison API",
        version=VERSION,
        description=DESCRIPTION.strip(),
        openapi_tags=TAGS,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        servers=[{"url": "/", "description": "This server"}],
        # Readable operation ids such as "courses_catalogue" (used by client generators).
        generate_unique_id_function=lambda route: f"{route.tags[0]}_{route.name}" if route.tags else route.name,
    )
    install_error_handlers(app)

    # Every route documents the standard error body for invalid input and server errors.
    api = APIRouter(
        prefix="/api/v1",
        responses={
            422: {"model": ErrorBody, "description": "Invalid input"},
            500: {"model": ErrorBody, "description": "Unexpected server error"},
        },
    )

    @api.get("/health", response_model=Health, tags=["health"], summary="Is the API up?", responses=errors(503))
    def health(db: DB):
        try:
            db.execute(text("SELECT 1"))
            database = "ok"
        except Exception:  # noqa: BLE001 - report, don't crash
            database = "unavailable"
        return {"status": "ok", "database": database, "version": VERSION}

    for router in (
        auth_router,
        users_router,
        courses_router,
        invitations_router,
        resources_router,
        assignments_router,
        teams_router,
        submissions_router,
        reviews_router,
        ai_router,
        notifications_router,
        admin_router,
    ):
        api.include_router(router)
    app.include_router(api)

    if settings.auth_mode == "demo":
        logging.getLogger("unison").warning(
            "AUTH_MODE=demo: the X-Demo-User header is accepted. Never use this in production."
        )
    return app


app = create_app()
