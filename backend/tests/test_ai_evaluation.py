"""The AI evaluation set runs offline in CI: privacy, guardrails and robustness checks must all pass.

The quality bands need a real model: `python scripts/evaluate_ai.py --live` (see that file).
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "evaluate_ai.py"


def _evaluation():
    spec = importlib.util.spec_from_file_location("evaluate_ai", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_evaluation_set_has_at_least_20_cases_in_every_group():
    data = _evaluation().load()
    groups = {c["group"] for c in data["cases"]}
    assert len(data["cases"]) >= 20
    assert groups == {"quality", "injection", "privacy", "robustness"}
    assert len({c["id"] for c in data["cases"]}) == len(data["cases"])


def test_every_offline_check_passes():
    evaluation = _evaluation()
    results = evaluation.run(live=False)
    failed = [(r.case["id"], n, d) for r in results for n, ok, d in r.checks if not ok]
    assert failed == []
    text = evaluation.report_text(results, live=False, model_name="fake")
    assert "Cases passed 26/26" in text
    assert "| Q01 | quality |" in evaluation.report_markdown(results, live=False, model_name="fake")


def test_live_bands_are_judged_with_a_real_model():
    """A model that always gives full marks fails the quality bands and the injection limit."""
    evaluation = _evaluation()

    class Generous(evaluation.Provider):
        name = model = "generous"

        def generate(self, system, prompt):
            import json

            rubric = json.loads(prompt.split("RUBRIC_JSON:", 1)[1].split("\n", 1)[0])
            return {
                "criteria": [
                    {"criterion_id": c["id"], "points": c["max_points"], "comment": "Perfect."} for c in rubric
                ]
            }

    results = {r.case["id"]: r for r in evaluation.run(live=True, model=Generous())}
    assert results["Q01"].passed  # a strong report deserves high marks
    assert not results["Q02"].passed and not results["I01"].passed  # weak and injected reports must not
    assert results["P01"].passed and results["R03"].passed  # privacy and robustness never use the live model
