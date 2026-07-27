"""Run one E3 arm (ground_truth | twin_nobw | twin_bw) over the twin-fidelity dataset.

Each case's IntentProgram is compiled to ONOS flows with the same deterministic
compiler the pipeline uses (safe_intent_sdn.compiler.compile_prediction) and then
deployed to a Mininet Digital Twin. Every arm replays the same background load so
the only thing that varies is the twin's check logic:

  * ground_truth -- reach + bandwidth + regression under load; its PASS/FAIL is the
                    reference outcome (cross-checked against each case's authored
                    expected_ground_truth by experiments/e3/score.py).
  * twin_nobw    -- reach + regression only (no bandwidth probe).
  * twin_bw      -- reach + bandwidth + regression.

REQUIRES Linux + root + Mininet + a running ONOS (./scripts/onos.sh start). On any
other host the twin returns status="skipped" and score.py will fail closed. Results
are appended incrementally and re-running resumes (skips case ids already logged),
because a twin run takes minutes per case.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from safe_intent_sdn.compiler import compile_prediction
from safe_intent_sdn.e3_evaluation import E3Case, E3Result
from safe_intent_sdn.intent_ir import IntentPrediction
from safe_intent_sdn.twin.twin_verifier import REACH_AND_BANDWIDTH, REACH_ONLY, TwinVerifier

HOST_IPS = {"h1": "10.0.0.1", "h2": "10.0.0.2", "h3": "10.0.0.3", "h4": "10.0.0.4"}

ARM_CHECKS = {
    "ground_truth": REACH_AND_BANDWIDTH,
    "twin_nobw": REACH_ONLY,
    "twin_bw": REACH_AND_BANDWIDTH,
}

_STATUS_TO_OUTCOME = {"passed": "PASS", "failed": "FAIL", "error": "FAIL", "skipped": "FAIL"}


def load_cases(path: Path) -> list[E3Case]:
    return [E3Case.model_validate_json(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def already_logged(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {E3Result.model_validate_json(x).case_id for x in path.read_text(encoding="utf-8").splitlines() if x.strip()}


def run_case(case: E3Case, arm: str, verifier: TwinVerifier) -> E3Result:
    flow_set = compile_prediction(
        IntentPrediction(status="accepted", program=case.program), endpoint_ips=HOST_IPS
    )
    flowrule = flow_set.model_dump(mode="json")
    background = [bf.model_dump() for bf in case.background_traffic]

    result = verifier.verify(
        flowrule,
        checks=ARM_CHECKS[arm],
        min_mbps=case.min_mbps,
        background_traffic=background or None,
    )
    return E3Result(
        case_id=case.id,
        arm=arm,
        intent_category=case.intent_category,
        outcome=_STATUS_TO_OUTCOME[result.status],
        twin_status=result.status,
        measured_mbps=result.evidence.get("measured_mbps"),
        checks=result.checks,
        evidence=result.evidence,
        error=result.reason if result.status in ("error", "skipped") else None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=list(ARM_CHECKS), required=True)
    parser.add_argument("--dataset", type=Path, default=ROOT / "experiments/e3/data/cases.jsonl")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--onos-url", default="http://127.0.0.1:8181/onos/v1")
    parser.add_argument("--onos-user", default="onos")
    parser.add_argument("--onos-password", default="rocks")
    parser.add_argument("--case-id", help="run only this case id")
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    if args.case_id:
        cases = [c for c in cases if c.id == args.case_id]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    done = already_logged(args.output)
    verifier = TwinVerifier(
        onos_url=args.onos_url, onos_user=args.onos_user, onos_password=args.onos_password
    )

    written = 0
    with args.output.open("a", encoding="utf-8") as fh:
        for case in cases:
            if case.id in done:
                print(f"[{args.arm}] skip {case.id} (already logged)")
                continue
            print(f"[{args.arm}] running {case.id} ({case.intent_category})...")
            result = run_case(case, args.arm, verifier)
            fh.write(result.model_dump_json() + "\n")
            fh.flush()
            written += 1
            print(f"[{args.arm}] {case.id}: {result.outcome} (twin_status={result.twin_status})")

    print(f"wrote {written} new result(s) to {args.output}")


if __name__ == "__main__":
    main()
