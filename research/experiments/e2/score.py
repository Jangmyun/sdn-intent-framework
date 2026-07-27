"""Score E2 B1/B2 prediction logs into a precision/recall report (RQ2 payload).

Scope caveat (see paper/experiment_protocol/e2_rationale.md): this is a
component-level, fixed-IR conformance evaluation of the compiler-vs-validator
boundary, not an end-to-end LLM+IR system comparison. Positive fixtures were
authored to match the validator's own reference/conflict/feasibility taxonomy, so
precision/recall here measure conformance to that taxonomy on this dataset, not
generalization to independent or held-out defects.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from safe_intent_sdn.e2_evaluation import E2Case, E2Result, compute_validator_overhead, score_treatment


def load_cases(path: Path) -> list[E2Case]:
    return [E2Case.model_validate_json(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_results(path: Path) -> list[E2Result]:
    return [E2Result.model_validate_json(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "experiments/e2/data/cases.jsonl")
    parser.add_argument(
        "--scope-note",
        default=(
            "component-level controlled evaluation of the B1-B2 validation boundary "
            "on 48 fixed IR fixtures (not an end-to-end LLM+IR system comparison)"
        ),
        help="scope description recorded in the report; override when scoring a different dataset (e.g. the sfc/reroute extension) so its report is never mistaken for the original 48-case one",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("files", nargs="+", type=Path, help="B1/B2 result JSONL files to score")
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    results: list[E2Result] = []
    for path in args.files:
        results.extend(load_results(path))

    by_treatment: dict[str, list[E2Result]] = {}
    for result in results:
        by_treatment.setdefault(result.treatment, []).append(result)

    report: dict = {
        "scope": args.scope_note,
        **{treatment: score_treatment(cases, treatment_results) for treatment, treatment_results in sorted(by_treatment.items())},
    }
    if "B1" in report and "B2" in report:
        b1, b2 = report["B1"]["any_defect"], report["B2"]["any_defect"]
        report["B2_minus_B1"] = {
            metric: (b2[metric] - b1[metric] if b1[metric] is not None and b2[metric] is not None else None)
            for metric in ("precision", "recall")
        }
        report["B2_minus_B1"]["incremental_rejections"] = b2["tp"] - b1["tp"]
        report["B2_minus_B1"]["note"] = (
            "incremental_rejections counts defect-positive cases B2 rejects that B1 does not; "
            "this is a potential reduction in cases that would reach a not-yet-built Digital Twin "
            "stage (E3+), not an already-measured Twin-execution saving."
        )
        report["validator_overhead"] = {
            **compute_validator_overhead(cases, by_treatment["B1"], by_treatment["B2"]),
            "note": (
                "The only apples-to-apples overhead figure: restricted to true-negative cases "
                "where both B1 and B2 run the compiler (B2 never short-circuits on these), so "
                "added_overhead_ms isolates the validator's own cost. Do NOT use each treatment's "
                "top-level observed_latency_ms for an overhead claim -- B2's population there "
                "includes defect-positive cases that skip the compiler entirely, which can make "
                "B2's overall mean look faster than B1's for reasons unrelated to validator cost."
            ),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
