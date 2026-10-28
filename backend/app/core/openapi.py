"""Helpers that put the standard error body into the OpenAPI description."""

from app.core.errors import ErrorBody

DESCRIPTIONS = {
    400: "Bad request",
    401: "Not logged in",
    403: "Not allowed",
    404: "Not found",
    409: "Conflict with the current state",
    413: "File too large",
    422: "Invalid input",
    429: "Too many requests",
    501: "Not implemented yet",
    503: "Service not available",
}


def errors(*codes: int) -> dict:
    """`responses=errors(401, 404)` documents those error responses on a route.

    422 and 500 are added to every route in main.py.
    """
    return {code: {"model": ErrorBody, "description": DESCRIPTIONS[code]} for code in codes}
