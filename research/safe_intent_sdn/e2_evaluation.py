"""Case/result models and scoring for Experiment 2 (Static Validator vs deterministic
compiler, RQ2).

This is a component-level, fixed-IR conformance evaluation: cases are gold/authored
Intent IR fixtures, not LLM output, so B1/B2 here measure only the compiler-vs-
validator boundary (``run_validation.py``'s ``--treatment B1|B2``), not an
end-to-end LLM+IR system comparison. See paper/experiment_protocol/e2_rationale.md
for the full scope caveat and construction-bias limitation (positive fixtures were
authored to match the validator's own taxonomy, so precision/recall here measure
conformance to that taxonomy, not generalization to independent/held-out defects).
"""
from __future__ import annotations

from statistics import mean, median
from typing import Any, Callable, Iterable, Literal, get_args

from pydantic import Field

from .intent_ir import IntentProgram, StrictModel
from .validator import FindingCategory, ValidationFinding


class E2Case(StrictModel):
    id: str
    category: Literal["clean", "reference", "conflict", "feasibility", "multi", "path"]
    expected_findings: list[FindingCategory] = Field(default_factory=list)
    expected_codes: list[str] = Field(default_factory=list)
    program: IntentProgram


class E2Result(StrictModel):
    case_id: str
    treatment: Literal["B1", "B2"]
    outcome: Literal["accepted", "rejected"]
    findings: list[ValidationFinding] = Field(default_factory=list)
    rejection_stage: Literal["validator", "compiler"] | None = None
    error: str | None = None
    # Median of repeated, warmed-up timings (see experiments/e2/run_validation.py).
    # duration_ms is the observed end-to-end per-case latency (whichever stages
    # actually ran) -- NOT a stage-isolated "validator overhead" measurement, since
    # B2 short-circuits on a rejected validator report and never runs the compiler.
    # Use compute_validator_overhead() for the overhead claim instead.
    validator_duration_ms: float | None = Field(default=None, ge=0)
    compiler_duration_ms: float | None = Field(default=None, ge=0)
    duration_ms: float = Field(ge=0)


def validate_results(cases: Iterable[E2Case], results: Iterable[E2Result]) -> list[E2Result]:
    """Fail closed on any log-integrity problem before scoring.

    Guards against exactly the failure modes that would let an incomplete or
    corrupt run silently produce an inflated precision/recall: missing cases
    (previously skipped instead of counted as a miss), duplicate case ids
    (previously the last one silently won), a log that mixes treatments, and a
    result whose outcome/rejection_stage/findings/error are internally
    inconsistent -- including a rejected-at-"validator" result with no findings,
    which would otherwise let outcome alone (with no supporting finding) inflate
    any_defect recall.
    """
    cases = list(cases)
    results = list(results)

    case_ids = [c.id for c in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("duplicate case id in dataset")

    result_ids = [r.case_id for r in results]
    if len(set(result_ids)) != len(result_ids):
        raise ValueError("duplicate case_id in result log")

    if set(result_ids) != set(case_ids):
        missing = sorted(set(case_ids) - set(result_ids))
        extra = sorted(set(result_ids) - set(case_ids))
        raise ValueError(f"result log does not match dataset 1:1: missing={missing} extra={extra}")

    treatments = {r.treatment for r in results}
    if len(treatments) > 1:
        raise ValueError(f"result log mixes treatments, expected exactly one: {sorted(treatments)}")

    for r in results:
        if r.outcome == "accepted":
            if r.rejection_stage is not None or r.findings or r.error is not None:
                raise ValueError(f"{r.case_id}: accepted result carries rejection metadata")
        elif r.rejection_stage == "validator":
            if r.treatment != "B2":
                raise ValueError(f"{r.case_id}: only B2 can reject at the validator stage")
            if not r.findings:
                raise ValueError(f"{r.case_id}: validator rejection must carry at least one finding")
            if r.error is not None:
                raise ValueError(f"{r.case_id}: validator rejection must not carry a compiler error")
        elif r.rejection_stage == "compiler":
            if r.findings:
                raise ValueError(f"{r.case_id}: compiler rejection must not carry categorized findings")
            if not r.error:
                raise ValueError(f"{r.case_id}: compiler rejection must carry a non-empty error message")
        else:
            raise ValueError(f"{r.case_id}: rejected result is missing rejection_stage")

    return results


def _confusion(
    cases: list[E2Case],
    by_id: dict[str, E2Result],
    expected_fn: Callable[[E2Case], bool],
    actual_fn: Callable[[E2Result], bool],
) -> dict[str, Any]:
    tp = fp = fn = tn = 0
    for case in cases:
        expected, actual = expected_fn(case), actual_fn(by_id[case.id])
        if expected and actual:
            tp += 1
        elif expected and not actual:
            fn += 1
        elif not expected and actual:
            fp += 1
        else:
            tn += 1
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp / (tp + fp) if (tp + fp) else None,
        "recall": tp / (tp + fn) if (tp + fn) else None,
    }


def score_treatment(cases: Iterable[E2Case], results: Iterable[E2Result]) -> dict[str, Any]:
    """Score one treatment's B1/B2 log against the dataset's expected findings.

    Calls ``validate_results`` first, so an incomplete/duplicate/inconsistent log
    raises instead of silently understating defects.

    ``any_defect`` is comparable across B1 and B2 (rejected vs. not, regardless of
    whether a category breakdown exists). ``defect_positive_total``/``rejected_count``
    expose the raw "N/25 rejected" counts PLAN.md asks for directly (redundant with
    tp+fn/tp but avoids readers having to reconstruct them).

    ``unknown_host_subset`` isolates the one sub-metric where B1's compiler
    incidentally catches a defect (an unmapped host alias) as a side effect of
    needing a host->IP resolver to run at all, not as a designed validation
    feature -- see paper/experiment_protocol/e2_rationale.md.

    ``by_category`` is case-level category detection: a case counts as a hit for
    category X if the validator reported at least one finding tagged X anywhere in
    that case, regardless of whether the specific ``code``/``rule_indices`` are
    correct. It is only meaningful for B2, the only treatment that reports
    categorized findings. ``code_mismatch_cases`` is a separate, stricter
    diagnostic (not folded into precision/recall) listing cases where B2's actual
    finding codes differ from ``expected_codes`` even though the category-level
    hit was correct -- inspect it before citing category recall as "every defect
    detected correctly."
    """
    cases = list(cases)
    results = list(results)
    validate_results(cases, results)
    by_id = {r.case_id: r for r in results}
    treatment = results[0].treatment if results else None

    defect_positive = [c for c in cases if c.expected_findings]
    any_defect = _confusion(
        cases, by_id,
        lambda case: bool(case.expected_findings),
        lambda result: result.outcome == "rejected",
    )
    report: dict[str, Any] = {
        "any_defect": any_defect,
        "defect_positive_total": len(defect_positive),
        "true_negative_total": len(cases) - len(defect_positive),
        "rejected_count": any_defect["tp"],
    }

    host_subset = [c for c in cases if c.expected_codes == ["unknown_host"]]
    if host_subset:
        report["unknown_host_subset"] = _confusion(
            host_subset, by_id, lambda case: True, lambda result: result.outcome == "rejected",
        )

    # Observed end-to-end per-case latency across whichever stages actually ran.
    # NOT a stage-isolated overhead measurement -- see compute_validator_overhead.
    durations = [r.duration_ms for r in results]
    report["observed_latency_ms"] = {
        "mean": mean(durations), "median": median(durations), "min": min(durations), "max": max(durations), "total": sum(durations),
    }

    if treatment == "B2":
        report["by_category"] = {
            category: _confusion(
                cases, by_id,
                lambda case, category=category: category in case.expected_findings,
                lambda result, category=category: category in {f.category for f in result.findings},
            )
            for category in get_args(FindingCategory)
        }
        report["code_mismatch_cases"] = [
            case.id
            for case in cases
            if case.expected_codes
            and {f.code for f in by_id[case.id].findings} != set(case.expected_codes)
        ]

    return report


def compute_validator_overhead(
    cases: Iterable[E2Case], b1_results: Iterable[E2Result], b2_results: Iterable[E2Result]
) -> dict[str, Any]:
    """Isolate the validator's added latency on the *common path only*.

    B2's overall mean duration can come out lower than B1's simply because
    defect-positive cases return early from the validator instead of running the
    compiler -- that is a real effect of catching defects early, not evidence
    about the validator's own cost. To isolate the cost, restrict the comparison
    to true-negative cases (``expected_findings == []``): both B1 and B2 run the
    compiler on every one of these, so B2's extra time on this subset is exactly
    the validator's added overhead over the B1 baseline.
    """
    cases = list(cases)
    b1_results, b2_results = list(b1_results), list(b2_results)
    validate_results(cases, b1_results)
    validate_results(cases, b2_results)
    b1_by_id = {r.case_id: r for r in b1_results}
    b2_by_id = {r.case_id: r for r in b2_results}

    common_path_ids = [c.id for c in cases if not c.expected_findings]
    b1_totals = [b1_by_id[i].duration_ms for i in common_path_ids]
    b2_validator = [b2_by_id[i].validator_duration_ms for i in common_path_ids]
    b2_compiler = [b2_by_id[i].compiler_duration_ms for i in common_path_ids]
    b2_totals = [b2_by_id[i].duration_ms for i in common_path_ids]

    def _stats(values: list[float]) -> dict[str, float]:
        return {"mean": mean(values), "median": median(values)}

    return {
        "case_count": len(common_path_ids),
        "b1_compiler_only_ms": _stats(b1_totals),
        "b2_validator_ms": _stats(b2_validator),
        "b2_compiler_ms": _stats(b2_compiler),
        "b2_total_ms": _stats(b2_totals),
        "added_overhead_ms": {
            "mean": mean(b2_totals) - mean(b1_totals),
            "median": median(b2_totals) - median(b1_totals),
        },
    }
