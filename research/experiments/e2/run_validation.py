"""Run B1 (compiler only) or B2 (Static Validator + compiler) over the E2 dataset.

This is a component-level, fixed-IR evaluation of the compiler-vs-validator
boundary: it starts from gold/authored Intent IR fixtures, not LLM output, so B1/B2
here are narrower than the paper's full LLM+IR system B1/B2 -- see
paper/experiment_protocol/e2_rationale.md.

No LLM calls, no repetition, no seeding needed for the pass/fail *result* itself:
validate_program/compile_prediction are pure deterministic functions of the
authored/reused IR fixtures in experiments/e2/data/cases.jsonl, so a single pass
per treatment is exhaustive for outcome/findings/error. Wall-clock *timing*, on
the other hand, is noisy at sub-millisecond scale even for deterministic code, so
each stage is additionally timed over several warmed-up repeated calls and
reported as a median (see ``_timed_ms``); the pass/fail result itself still comes
from a single call, since re-running a pure function only for timing cannot
change it.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from safe_intent_sdn.compiler import CompilationError, compile_prediction
from safe_intent_sdn.e2_evaluation import E2Case, E2Result
from safe_intent_sdn.intent_ir import IntentPrediction
from safe_intent_sdn.validator import TopologyInventory, load_topology_inventory, validate_program

TIMING_REPEATS = 31
TIMING_WARMUP = 1


def _timed_ms(fn: Callable[[], Any], *, repeats: int = TIMING_REPEATS, warmup: int = TIMING_WARMUP) -> float:
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def load_cases(path: Path) -> list[E2Case]:
    return [E2Case.model_validate_json(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _is_ip(value: str) -> bool:
    try:
        ip_address(value)
        return True
    except ValueError:
        return False


def host_ip_map(topology: dict[str, Any]) -> dict[str, str]:
    """Complete host-alias -> IP map, so B1's compiler is a fair (non-degenerate)
    baseline: it must be given every real host alias, not an empty resolver, or it
    would reject every host-bearing rule regardless of whether it's hallucinated.
    """
    mapping: dict[str, str] = {}
    for entity in topology["entities"]:
        if not entity["id"].startswith("host:"):
            continue
        ip = next((alias for alias in entity["aliases"] if _is_ip(alias)), None)
        if ip is None:
            continue
        for alias in entity["aliases"]:
            if alias != ip:
                mapping[alias] = ip
    return mapping


def run_case(
    case: E2Case, *, treatment: str, endpoint_ips: dict[str, str], inventory: TopologyInventory
) -> E2Result:
    prediction = IntentPrediction(status="accepted", program=case.program, rejection=None)
    outcome, findings, rejection_stage, error = "accepted", [], None, None
    validator_duration_ms: float | None = None
    compiler_duration_ms: float | None = None

    if treatment == "B2":
        report = validate_program(case.program, inventory)
        validator_duration_ms = _timed_ms(lambda: validate_program(case.program, inventory))
        if not report.is_valid:
            outcome, findings, rejection_stage = "rejected", report.findings, "validator"

    if outcome == "accepted":
        try:
            compile_prediction(prediction, endpoint_ips=endpoint_ips)
        except CompilationError as exc:
            outcome, rejection_stage, error = "rejected", "compiler", str(exc)

        def _compile_once() -> None:
            try:
                compile_prediction(prediction, endpoint_ips=endpoint_ips)
            except CompilationError:
                pass

        compiler_duration_ms = _timed_ms(_compile_once)

    duration_ms = (validator_duration_ms or 0.0) + (compiler_duration_ms or 0.0)
    return E2Result(
        case_id=case.id, treatment=treatment, outcome=outcome,
        findings=findings, rejection_stage=rejection_stage, error=error,
        validator_duration_ms=validator_duration_ms, compiler_duration_ms=compiler_duration_ms,
        duration_ms=duration_ms,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--treatment", choices=["B1", "B2"], required=True)
    parser.add_argument("--dataset", type=Path, default=ROOT / "experiments/e2/data/cases.jsonl")
    parser.add_argument("--topology", type=Path, default=ROOT / "experiments/e1/data/topology.json")
    parser.add_argument("--case-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    if args.case_id:
        cases = [c for c in cases if c.id == args.case_id]
    if args.limit:
        cases = cases[: args.limit]

    topology = json.loads(args.topology.read_text(encoding="utf-8"))
    inventory = load_topology_inventory(topology)
    endpoint_ips = host_ip_map(topology)

    results = [
        run_case(case, treatment=args.treatment, endpoint_ips=endpoint_ips, inventory=inventory)
        for case in cases
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for result in results:
            fh.write(result.model_dump_json() + "\n")
    print(f"wrote {len(results)} results to {args.output}")


if __name__ == "__main__":
    main()
