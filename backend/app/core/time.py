"""Time handling.

The database stores UTC without a time zone (DATETIME(3)). The API speaks
Indian Standard Time: every datetime in a response carries +05:30, and a
datetime sent without an offset is read as IST. IST has no daylight saving,
so a fixed offset is exact.
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

from pydantic import AfterValidator, PlainSerializer, WithJsonSchema

IST = timezone(timedelta(hours=5, minutes=30), "IST")


def utcnow() -> datetime:
    """Current UTC time, naive, rounded down to milliseconds like DATETIME(3)."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


class Clock:
    """The time source. Tests replace it with a FrozenClock to jump past deadlines."""

    def now(self) -> datetime:
        return utcnow()


class FrozenClock(Clock):
    def __init__(self, at: datetime):
        self.at = at

    def now(self) -> datetime:
        return self.at

    def advance(self, **delta) -> None:
        self.at = self.at + timedelta(**delta)


def to_utc(value: datetime) -> datetime:
    """Any datetime from the API to naive UTC. Naive input is read as IST."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=IST)
    return value.astimezone(UTC).replace(tzinfo=None)


def to_ist(value: datetime) -> datetime:
    """A naive UTC datetime from the database to an aware IST datetime."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(IST)


def ist_text(value: datetime) -> str:
    """For emails and messages, e.g. '5 Nov 2026, 23:59 IST'."""
    local = to_ist(value)
    return f"{local.day} {local:%b %Y, %H:%M} IST"


def _serialize(value: datetime) -> str:
    return to_ist(value).isoformat(timespec="seconds")


# Use in response schemas: shown as ISO 8601 in IST, e.g. 2026-11-05T23:59:59+05:30.
IstDateTime = Annotated[
    datetime,
    PlainSerializer(_serialize, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "format": "date-time", "example": "2026-11-05T23:59:59+05:30"}),
]

# Use in request schemas: converted to naive UTC on the way in.
IstDateTimeIn = Annotated[
    datetime,
    AfterValidator(to_utc),
    WithJsonSchema(
        {
            "type": "string",
            "format": "date-time",
            "example": "2026-11-05T23:59:59+05:30",
            "description": "ISO 8601. A value without an offset is read as IST.",
        }
    ),
]
