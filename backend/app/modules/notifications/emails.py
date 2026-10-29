"""Plain-text email templates. Each returns (subject, body).

Links point at the frontend (FRONTEND_URL). Nothing here sends: the worker
renders an outbox row with render() just before sending it.
"""

from app.config import get_settings


def _link(path: str) -> str:
    return get_settings().frontend_url.rstrip("/") + path


def render(template: str, payload: dict) -> tuple[str, str]:
    if template == "verify_email":
        return (
            "Confirm your email for Unison",
            f"Hello {payload['name']},\n\n"
            f"Please confirm {payload['email']} by opening this link:\n"
            f"{_link('/verify-email?token=' + payload['token'])}\n\n"
            "The link works once. If you did not ask for this, ignore this email.\n",
        )
    if template == "reset_password":
        return (
            "Reset your Unison password",
            f"Hello {payload['name']},\n\n"
            "Open this link within 30 minutes to choose a new password:\n"
            f"{_link('/reset-password?token=' + payload['token'])}\n\n"
            "If you did not ask for this, ignore this email; your password stays the same.\n",
        )
    if template == "invitation":
        return (
            payload["subject"],
            f"Hello,\n\n{payload['text']}\n\n"
            f"Open the invitation (valid until {payload['expires']}):\n"
            f"{_link('/invitations/' + payload['token'])}\n\n"
            f"The invitation is for {payload['email']}. Sign in or sign up with that address to accept.\n",
        )
    if template == "resources_published":
        titles = "\n".join(f"- {t}" for t in payload["titles"])
        return (
            f"New resources in {payload['course']}",
            f"Hello {payload['name']},\n\nNew resources were published in {payload['course']}:\n{titles}\n\n"
            f"Open the course: {_link(payload['link'])}\n",
        )
    # Every other event uses the notification's own title and link.
    return (
        payload["title"],
        f"Hello {payload['name']},\n\n{payload['title']}\n\nOpen in Unison: {_link(payload['link'])}\n\n"
        "You can turn off emails like this on your profile page.\n",
    )
