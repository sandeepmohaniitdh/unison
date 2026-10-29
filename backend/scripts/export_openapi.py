"""Write the OpenAPI description to docs/openapi.yaml (and the endpoint list docs/api/ENDPOINTS.md).

python scripts/export_openapi.py          # write the files
python scripts/export_openapi.py --check  # fail if they are out of date (CI)
"""

import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "sqlite://")  # the spec does not need a database

from app.main import create_app  # noqa: E402

ROOT = Path(os.environ.get("DOCS_DIR", Path(__file__).resolve().parents[2] / "docs"))
YAML_FILE = ROOT / "openapi.yaml"
LIST_FILE = ROOT / "api" / "ENDPOINTS.md"
METHODS = ("get", "post", "put", "patch", "delete")


def build() -> tuple[str, str]:
    spec = create_app().openapi()
    text = yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=120)
    lines = [
        "# Unison API: every endpoint",
        "",
        "Generated from the code by `backend/scripts/export_openapi.py`; do not edit by hand.",
        "The full description (bodies, responses, errors) is in [docs/openapi.yaml](../openapi.yaml).",
        "",
    ]
    by_tag: dict[str, list[tuple[str, str, str]]] = {}
    for path, ops in spec["paths"].items():
        for method in METHODS:
            if method in ops:
                op = ops[method]
                by_tag.setdefault(op["tags"][0], []).append((method.upper(), path, op.get("summary", "")))
    total = sum(len(v) for v in by_tag.values())
    lines.append(f"{total} operations under `/api/v1`.")
    for tag in [t["name"] for t in spec["tags"]]:
        if tag not in by_tag:
            continue
        lines += ["", f"## {tag}", "", "| Method | Path | What it does |", "|---|---|---|"]
        lines += [f"| {m} | `{p}` | {s} |" for m, p, s in by_tag[tag]]
    return text, "\n".join(lines) + "\n"


def main() -> int:
    text, listing = build()
    if "--check" in sys.argv:
        stale = [f for f, new in ((YAML_FILE, text), (LIST_FILE, listing)) if not f.exists() or f.read_text() != new]
        if stale:
            print("Out of date:", ", ".join(str(f) for f in stale))
            print("Run: python scripts/export_openapi.py  (from backend/), then commit the files.")
            return 1
        print("OpenAPI files are up to date.")
        return 0
    YAML_FILE.parent.mkdir(parents=True, exist_ok=True)
    LIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    YAML_FILE.write_text(text)
    LIST_FILE.write_text(listing)
    print(f"Wrote {YAML_FILE} and {LIST_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
