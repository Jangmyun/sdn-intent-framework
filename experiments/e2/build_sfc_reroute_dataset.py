"""Build the E2-path extension dataset: all 50 accepted sfc/reroute gold cases from
``experiments/e1/data/intents_sfc_reroute.jsonl`` reused as ``clean`` true negatives
(no per-category quota -- ``validate_program``/``compile_prediction`` are cheap
deterministic functions, so there is no cost reason to subsample), plus 15
hand-authored sfc/reroute-specific defect fixtures. This is a separate benchmark
from ``experiments/e2/data/cases.jsonl`` (the original 48-case validator benchmark)
and never merges numbers with it -- see
``paper/experiment_protocol/e2_rationale_sfc_reroute_addendum.md``.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from safe_intent_sdn.e2_evaluation import E2Case

EXPECTED_DISTRIBUTION = Counter({"clean": 50, "path": 8, "feasibility": 3, "conflict": 2, "reference": 1, "multi": 1})


def select_clean_cases(intents_path: Path) -> list[E2Case]:
    rows = [json.loads(line) for line in intents_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = [
        E2Case(id=f"clean-{row['id']}", category="clean", program=row["expected"]["program"])
        for row in rows
        if row["category"] in ("sfc", "reroute") and row["expected"]["status"] == "accepted"
    ]
    if len(selected) != 50:
        raise ValueError(f"expected 50 accepted sfc/reroute gold cases, found {len(selected)}")
    return selected


def load_defective_cases(path: Path) -> list[E2Case]:
    return [E2Case.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    intents_path = ROOT / "experiments/e1/data/intents_sfc_reroute.jsonl"
    defective_path = ROOT / "experiments/e2/data/defective_sfc_reroute.jsonl"
    output_path = ROOT / "experiments/e2/data/cases_sfc_reroute.jsonl"

    cases = select_clean_cases(intents_path) + load_defective_cases(defective_path)

    distribution = Counter(c.category for c in cases)
    if distribution != EXPECTED_DISTRIBUTION:
        raise ValueError(f"unexpected category distribution: {dict(distribution)} != {dict(EXPECTED_DISTRIBUTION)}")
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case id")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(case.model_dump_json() + "\n")
    print(f"wrote {len(cases)} cases to {output_path}")


if __name__ == "__main__":
    main()
