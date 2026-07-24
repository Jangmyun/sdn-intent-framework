"""Score E3 arm logs into a twin-fidelity report (RQ3 payload).

Joins the ground_truth, twin_nobw and twin_bw logs by case id and reports, overall
and per intent category: each twin arm's confusion vs ground truth (accuracy,
precision, recall, and fpr -- the dangerous wrong-approval rate), and the change
from adding the bandwidth probe. Also cross-checks the measured ground truth
against each case's authored ``expected_ground_truth`` and records any mismatch,
since a mismatch means the emulated scenario did not reproduce the intended
condition and the numbers should not be trusted until it is fixed.

Scope caveat (see paper/experiment_protocol/e3_rationale.md): this validates the
twin as a decision instrument over emulated deployments, not the fidelity of
Mininet emulation to physical hardware.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from safe_intent_sdn.e3_evaluation import (
    E3Case,
    E3Result,
    check_ground_truth_labels,
    compute_fidelity_delta,
)


def load_cases(path: Path) -> list[E3Case]:
    return [E3Case.model_validate_json(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_results(path: Path) -> list[E3Result]:
    return [E3Result.model_validate_json(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "experiments/e3/data/cases.jsonl")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--scope-note",
        default=(
            "twin decision-fidelity over emulated diamond-topology deployments; "
            "validates the twin as a decision instrument, not Mininet-vs-hardware fidelity"
        ),
    )
    parser.add_argument("files", nargs="+", type=Path, help="arm result JSONL files (all three arms)")
    args = parser.parse_args()

    cases = load_cases(args.dataset)

    by_arm: dict[str, list[E3Result]] = {}
    for path in args.files:
        for result in load_results(path):
            by_arm.setdefault(result.arm, []).append(result)

    missing_arms = {"ground_truth", "twin_nobw", "twin_bw"} - set(by_arm)
    if missing_arms:
        raise SystemExit(f"missing arm log(s): {sorted(missing_arms)}")

    label_mismatch = check_ground_truth_labels(cases, by_arm["ground_truth"])
    report = {
        "scope": args.scope_note,
        "case_count": len(cases),
        "ground_truth_label_mismatch": label_mismatch,
        "ground_truth_label_note": (
            "case ids where measured ground truth disagrees with the authored "
            "expected_ground_truth; a non-empty list means the emulated scenario "
            "did not reproduce the intended condition -- fix before trusting fidelity"
        ),
        "fidelity": compute_fidelity_delta(
            cases, by_arm["ground_truth"], by_arm["twin_nobw"], by_arm["twin_bw"]
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)
    if label_mismatch:
        print(f"WARNING: ground-truth label mismatch on {label_mismatch}", file=sys.stderr)


if __name__ == "__main__":
    main()
