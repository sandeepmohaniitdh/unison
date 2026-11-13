"""Evaluate the AI feedback draft on the cases in evaluation/ai_cases.json.

    python scripts/evaluate_ai.py                     # offline: built-in fake model (as in CI)
    python scripts/evaluate_ai.py --live              # the real model set by AI_PROVIDER (e.g. Gemini)
    python scripts/evaluate_ai.py --live --markdown   # the same, as a Markdown table

With Docker Compose and the Gemini key in .env (AI_PROVIDER=gemini), from the repository root:

    docker compose exec -T backend python scripts/evaluate_ai.py --live --markdown > docs/ai_evaluation_results.md

Every case goes through the same code as a real draft: a PDF is made from the case's pages,
its text is extracted, names are removed (prepare_report), the prompt is built (build_prompt),
the model is asked, and its reply is checked and clamped (parse_reply). The checks:

- privacy: the listed names, emails and roll numbers never appear in what the model is sent;
- guardrails: injection flag, truncation, unreadable PDFs, invalid or out-of-range replies, timeouts;
- quality (only with --live): each suggested mark lies in the acceptable band for that report,
  and an injection attempt does not get more than the allowed share of the total.
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "sqlite://")  # the evaluation does not use the database

from app.core.pdf import text_pdf  # noqa: E402
from app.modules.ai.providers import FakeProvider, Provider, ProviderError  # noqa: E402
from app.modules.ai.redact import Member  # noqa: E402
from app.modules.ai.service import (  # noqa: E402
    MESSAGES,
    SYSTEM_PROMPT,
    build_prompt,
    extract_text,
    parse_reply,
    prepare_report,
)

CASES_FILE = Path(__file__).resolve().parent.parent / "evaluation" / "ai_cases.json"


@dataclass
class Result:
    case: dict
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    suggestions: list[dict] | None = None
    error: str | None = None
    seconds: float = 0.0

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, bool(ok), detail))

    @property
    def passed(self) -> bool:
        return all(ok for _name, ok, _detail in self.checks)


class Scripted(Provider):
    """A model that gives a fixed reply or a fixed error, for the robustness cases."""

    name = "scripted"
    model = "scripted"

    def __init__(self, reply=None, error=None):
        self.reply, self.error = reply, error

    def generate(self, system: str, prompt: str) -> dict:
        if self.error:
            raise ProviderError(self.error, "scripted error")
        return self.reply


class Recording(Provider):
    """Wraps a provider and keeps the prompts it was sent."""

    def __init__(self, inner: Provider):
        self.inner, self.prompts = inner, []
        self.name, self.model = inner.name, inner.model

    def generate(self, system: str, prompt: str) -> dict:
        self.prompts.append(prompt)
        return self.inner.generate(system, prompt)


def load(path: Path = CASES_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pages(case: dict) -> list[str]:
    return case["pages"] * case.get("repeat_pages", 1)


def _reply(case: dict):
    reply = case.get("scripted_reply")
    if reply and case.get("long_comment"):
        reply = json.loads(json.dumps(reply).replace('"LONG"', json.dumps("x" * case["long_comment"])))
    return reply


def run_case(data: dict, case: dict, model: Provider, live: bool) -> Result:
    result = Result(case)
    expect = case.get("expect", {})
    team = data["teams"][case["team"]]
    members = [Member(m["name"], m["emails"]) for m in team["members"]]
    criteria = [
        SimpleNamespace(id=c["id"], title=c["title"], max_points=Decimal(str(c["max_points"])))
        for c in data["rubrics"][case["rubric"]]
    ]
    assignment = SimpleNamespace(**data["assignment"])

    scripted = "scripted_reply" in case or "scripted_error" in case
    uses_model = live and case.get("live", True) and not scripted
    if uses_model:
        inner = model
    elif scripted:
        inner = Scripted(_reply(case), case.get("scripted_error"))
    else:
        inner = FakeProvider()
    provider = Recording(inner)

    started = time.monotonic()
    report = facts = None
    try:
        text, page_lengths = extract_text(text_pdf(_pages(case)))
        report, facts = prepare_report(text, page_lengths, members, team["name"])
        reply = provider.generate(SYSTEM_PROMPT, build_prompt(assignment, criteria, report))
        result.suggestions = parse_reply(reply, criteria)
    except ProviderError as exc:
        result.error = exc.code
    result.seconds = time.monotonic() - started
    sent = "\n".join(provider.prompts)

    if "error" in expect:
        result.check("error", result.error == expect["error"], f"got {result.error or 'no error'}")
    else:
        result.check("valid reply", result.error is None and result.suggestions is not None, result.error or "")
    if "message" in expect:
        result.check("message", MESSAGES.get(result.error) == expect["message"], MESSAGES.get(result.error, ""))
    if "model_called" in expect:
        result.check(
            "model called", bool(provider.prompts) == expect["model_called"], f"{len(provider.prompts)} call(s)"
        )
    for s in expect.get("absent", []):
        result.check(
            f"'{s}' removed", s.lower() not in sent.lower(), "found in the prompt" if s.lower() in sent.lower() else ""
        )
    for s in expect.get("present", []):
        result.check(f"'{s}' still sent (known)", s.lower() in sent.lower())
    if "injection_flag" in expect and facts is not None:
        result.check(
            "injection flag",
            facts["injection_suspected"] == expect["injection_flag"],
            f"flag={facts['injection_suspected']}",
        )
    if "truncated" in expect and facts is not None:
        result.check(
            "truncated",
            facts["truncated"] == expect["truncated"],
            f"{facts['chars_total']} chars, {facts['pages_read']}/{facts['pages_total']} pages read",
        )
    if "max_report_chars" in expect and report is not None:
        result.check("report length", len(report) <= expect["max_report_chars"], f"{len(report)} chars sent")
    by_title = {c.title: c for c in criteria}
    got = {next(c.title for c in criteria if c.id == s["criterion_id"]): s for s in result.suggestions or []}
    for title, value in expect.get("points_exact", {}).items():
        result.check(
            f"{title} = {value}", got.get(title, {}).get("points") == value, f"got {got.get(title, {}).get('points')}"
        )
    if "max_comment_chars" in expect and result.suggestions:
        longest = max(len(s["comment"]) for s in result.suggestions)
        result.check("comment length", longest <= expect["max_comment_chars"], f"longest {longest}")

    # Judging the marks needs a real model; the fake one always suggests 70%.
    if uses_model and result.suggestions:
        for title, (low, high) in expect.get("points", {}).items():
            maximum = float(by_title[title].max_points)
            points = got[title]["points"]
            result.check(
                f"{title} in {low:.0%}-{high:.0%}",
                low * maximum - 1e-9 <= points <= high * maximum + 1e-9,
                f"{points}/{maximum:g}",
            )
        if "max_total_fraction" in expect:
            total = sum(s["points"] for s in result.suggestions)
            maximum = float(sum(c.max_points for c in criteria))
            result.check(
                f"total <= {expect['max_total_fraction']:.0%}",
                total <= expect["max_total_fraction"] * maximum + 1e-9,
                f"{total:g}/{maximum:g}",
            )
    return result


def run(live: bool = False, model: Provider | None = None, pause: float = 0.0, only: str | None = None) -> list[Result]:
    data = load()
    if live and model is None:
        from app.config import get_settings
        from app.modules.ai.providers import get_provider

        model = get_provider(get_settings())
        if model is None or isinstance(model, FakeProvider):
            raise SystemExit("--live needs AI_PROVIDER=gemini (with GEMINI_API_KEY) or ollama.")
    results = []
    for case in data["cases"]:
        if only and not case["id"].startswith(only):
            continue
        results.append(run_case(data, case, model or FakeProvider(), live))
        if live and pause and case.get("live", True) and "scripted_reply" not in case:
            time.sleep(pause)
    return results


def _marks(r: Result) -> str:
    if r.error:
        return r.error
    return ", ".join(f"{s['points']:g}" for s in r.suggestions or [])


def report_text(results: list[Result], live: bool, model_name: str) -> str:
    lines = [f"AI feedback draft evaluation ({'live: ' + model_name if live else 'offline: fake model'})", ""]
    for r in results:
        failed = [f"{n} ({d})" if d else n for n, ok, d in r.checks if not ok]
        lines.append(f"{'PASS' if r.passed else 'FAIL'}  {r.case['id']}  {r.case['title']}  [{_marks(r)}]")
        lines += [f"      failed: {f}" for f in failed]
    lines.append("")
    lines.append(summary(results))
    return "\n".join(lines)


def summary(results: list[Result]) -> str:
    groups: dict[str, list[Result]] = {}
    for r in results:
        groups.setdefault(r.case["group"], []).append(r)
    parts = [f"{g}: {sum(r.passed for r in rs)}/{len(rs)}" for g, rs in groups.items()]
    checks = [ok for r in results for _n, ok, _d in r.checks]
    cases = f"Cases passed {sum(r.passed for r in results)}/{len(results)} ({', '.join(parts)})"
    return f"{cases}; checks passed {sum(checks)}/{len(checks)}."


def report_markdown(results: list[Result], live: bool, model_name: str) -> str:
    when = time.strftime("%Y-%m-%d %H:%M %Z")
    out = [
        "# AI feedback draft: evaluation results",
        "",
        f"Run on {when} with {'the live model `' + model_name + '`' if live else 'the offline fake model'} "
        "by `backend/scripts/evaluate_ai.py` on `backend/evaluation/ai_cases.json`. "
        "Privacy and robustness cases always use the offline or scripted model.",
        "",
        f"**{summary(results)}**",
        "",
        "| Case | Group | What it tests | Suggested marks | Result | Checks that failed |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        failed = "; ".join(f"{n} ({d})" if d else n for n, ok, d in r.checks if not ok) or ""
        verdict = "pass" if r.passed else "FAIL"
        out.append(f"| {r.case['id']} | {r.case['group']} | {r.case['title']} | {_marks(r)} | {verdict} | {failed} |")
    notes = [r for r in results if r.case.get("expect", {}).get("note")]
    if notes:
        out += ["", "Notes:", ""]
        out += [f"- {r.case['id']}: {r.case['expect']['note']}" for r in notes]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="ask the real model set by AI_PROVIDER")
    parser.add_argument("--markdown", action="store_true", help="print a Markdown table")
    parser.add_argument("--pause", type=float, default=4.0, help="seconds between live calls (free-tier rate limits)")
    parser.add_argument("--only", help="run only cases whose id starts with this, e.g. Q or I03")
    args = parser.parse_args()
    results = run(live=args.live, pause=args.pause if args.live else 0.0, only=args.only)
    name = "fake"
    if args.live:
        from app.config import get_settings
        from app.modules.ai.providers import model_name

        name = model_name(get_settings())
    print(report_markdown(results, args.live, name) if args.markdown else report_text(results, args.live, name))
    # Offline every check must pass (CI); a live run reports its results without failing.
    return 0 if args.live or all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
