"""Removing names before a report is sent to the model.

1. Build the team's identifying strings: each member's full name and each
   part of it longer than two letters, their emails and the part before the
   @, roll numbers, and the team name.
2. Replace every match (ignoring case, only at word boundaries) with a
   placeholder such as [STUDENT_1].
3. Replace anything that looks like a roll number (CS26MT001 style) or an
   email address, even if it is not on the list.
4. Search the result again for every listed string; if any remains, refuse.

Names of people who are not in Unison (an interviewee, say) are not caught.
"""

import re
from dataclasses import dataclass

ROLL_NUMBER = re.compile(r"\b[A-Za-z]{2}\d{2}[A-Za-z]{2}\d{3}\b")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")


@dataclass
class Member:
    name: str
    emails: list[str]


def identifiers(members: list[Member], team_name: str) -> dict[str, str]:
    """Identifying string -> its placeholder. Longer strings first, so a full
    name is replaced before its parts."""
    found: dict[str, str] = {}
    for n, member in enumerate(members, start=1):
        tag = f"[STUDENT_{n}]"
        strings = [member.name, *[p for p in re.split(r"\s+", member.name) if len(p) > 2]]
        for email in member.emails:
            local = email.split("@")[0]
            strings += [email, local]
            if ROLL_NUMBER.fullmatch(local):
                strings.append(local.upper())
        for s in strings:
            s = s.strip()
            if s and s.lower() not in {k.lower() for k in found}:
                found[s] = tag
    if team_name and not team_name.startswith("Individual "):
        found.setdefault(team_name, "[TEAM]")
    return dict(sorted(found.items(), key=lambda kv: -len(kv[0])))


def _pattern(s: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(s) + r"(?!\w)", re.IGNORECASE)


def redact(text: str, ids: dict[str, str]) -> str:
    for s, tag in ids.items():
        text = _pattern(s).sub(tag, text)
    text = EMAIL.sub("[EMAIL]", text)
    text = ROLL_NUMBER.sub("[ROLL_NUMBER]", text)
    return text


def leftovers(text: str, ids: dict[str, str]) -> list[str]:
    """Listed strings still present after redaction (should be none)."""
    return [s for s in ids if _pattern(s).search(text)]


INJECTION_HINTS = re.compile(
    r"ignore (all |any |the )?(previous |above |prior )?(instructions|rubric|rules)|"
    r"(give|award) (me |us |this )?(full|maximum|max|perfect) (marks|points|score)|"
    r"you are now|system prompt|disregard (the|all|any)|as an ai",
    re.IGNORECASE,
)


def looks_like_injection(text: str) -> bool:
    return bool(INJECTION_HINTS.search(text))
