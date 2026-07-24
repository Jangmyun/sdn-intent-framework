"""Case/result models and scoring for Experiment 3 (Twin decision fidelity, RQ3).

E3 measures how well the Digital Twin's automated PASS/FAIL verdict matches the
real behavioral outcome of an emulated deployment. Three arms run over the same
cases (see experiments/e3/run_twin_fidelity.py):

  * ``ground_truth`` -- deploy under replayed background load and measure the
    *true* outcome (reachability AND delivered bandwidth vs target AND regression);
    PASS means the policy actually achieves its intent (SHOULD_PASS).
  * ``twin_nobw``    -- the twin verdict using reachability checks only.
  * ``twin_bw``      -- the twin verdict adding the iperf3 bandwidth probe.

Fidelity is the agreement between a twin arm's verdict and the ground-truth
outcome. The positive class is "policy should be approved" (ground truth PASS),
so a **false positive is a dangerous wrong approval** (twin says PASS, reality is
FAIL) and ``fpr`` is the headline safety metric. See
paper/experiment_protocol/e3_rationale.md for the scope caveat: this validates
the twin as a *decision instrument* over emulated deployments, not the fidelity
of Mininet emulation to physical hardware.
"""
from __future__ import annotations

from statistics import mean
from typing import Any, Callable, Iterable, Literal

from pydantic import Field

from .intent_ir import IntentProgram, StrictModel

Arm = Literal["ground_truth", "twin_nobw", "twin_bw"]
IntentCategory = Literal["forwarding", "security", "qos", "reroute", "compound"]
Outcome = Literal["PASS", "FAIL"]
GroundTruthLabel = Literal["SHOULD_PASS", "SHOULD_FAIL"]


class BackgroundFlow(StrictModel):
    src: str
    dst: str
    dst_ip: str
    mbps: float = Field(gt=0)
    proto: Literal["tcp", "udp"] = "udp"
    duration: int = Field(default=30, gt=0)


class E3Case(StrictModel):
    """One twin-fidelity case: a policy plus how its true outcome is judged."""

    id: str
    intent_category: IntentCategory
    topology_id: str = "diamond"
    program: IntentProgram
    background_traffic: list[BackgroundFlow] = Field(default_factory=list)
    # QoS target for the primary intent pair; None for non-bandwidth intents.
    min_mbps: float | None = Field(default=None, gt=0)
    # Author-adjudicated anchor for the empirical ground-truth outcome; the runner
    # fails closed if the measured ground truth disagrees with it.
    expected_ground_truth: GroundTruthLabel


class E3Result(StrictModel):
    """One arm's result for one case."""

    case_id: str
    arm: Arm
    intent_category: IntentCategory
    # Normalized verdict. For ground_truth, PASS == SHOULD_PASS (policy achieves
    # its intent). For twin arms, PASS == the twin verified the FlowRule.
    outcome: Outcome
    twin_status: Literal["passed", "failed", "skipped", "error"]
    measured_mbps: float | None = Field(default=None, ge=0)
    checks: dict[str, bool] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


def validate_results(cases: Iterable[E3Case], results: Iterable[E3Result]) -> list[E3Result]:
    """Fail closed on any log-integrity problem before scoring.

    Guards the same failure modes E2 does -- missing/extra/duplicate cases, a log
    that mixes arms, and category drift between a result and its case -- so an
    incomplete or mislabeled run cannot silently inflate fidelity.
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

    arms = {r.arm for r in results}
    if len(arms) > 1:
        raise ValueError(f"result log mixes arms, expected exactly one: {sorted(arms)}")

    category = {c.id: c.intent_category for c in cases}
    for r in results:
        if r.intent_category != category[r.case_id]:
            raise ValueError(
                f"{r.case_id}: result category {r.intent_category!r} != dataset {category[r.case_id]!r}"
            )
        if r.twin_status == "skipped":
            raise ValueError(
                f"{r.case_id}: arm {r.arm!r} was skipped (twin not runnable); "
                "run the twin arms on a Linux+root host with ONOS before scoring"
            )
    return results


def check_ground_truth_labels(
    cases: Iterable[E3Case], ground_truth: Iterable[E3Result]
) -> list[str]:
    """Return case ids where the measured ground truth contradicts the author label.

    The empirically measured ground-truth outcome is the reference used for
    scoring, but ``expected_ground_truth`` is an independent human-authored anchor:
    a non-empty return here means the emulation did not reproduce the intended
    scenario (e.g. congestion did not actually starve a QoS flow) and the dataset
    or load parameters need adjustment before the fidelity numbers are trusted.
    """
    by_id = {r.case_id: r for r in ground_truth if r.arm == "ground_truth"}
    mismatched: list[str] = []
    for case in cases:
        result = by_id.get(case.id)
        if result is None:
            continue
        measured = "SHOULD_PASS" if result.outcome == "PASS" else "SHOULD_FAIL"
        if measured != case.expected_ground_truth:
            mismatched.append(case.id)
    return mismatched


def _confusion(
    cases: list[E3Case],
    gt_by_id: dict[str, E3Result],
    twin_by_id: dict[str, E3Result],
) -> dict[str, Any]:
    """Confusion of a twin arm vs ground truth (positive class = PASS/approve)."""
    tp = fp = fn = tn = 0
    for case in cases:
        expected = gt_by_id[case.id].outcome == "PASS"
        actual = twin_by_id[case.id].outcome == "PASS"
        if expected and actual:
            tp += 1
        elif expected and not actual:
            fn += 1
        elif not expected and actual:
            fp += 1
        else:
            tn += 1
    total = tp + fp + fn + tn
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": (tp + tn) / total if total else None,
        "precision": tp / (tp + fp) if (tp + fp) else None,
        "recall": tp / (tp + fn) if (tp + fn) else None,
        # Dangerous-approval rate: bad policies the twin wrongly passes.
        "fpr": fp / (fp + tn) if (fp + tn) else None,
    }


def score_arm(
    cases: Iterable[E3Case],
    ground_truth: Iterable[E3Result],
    twin: Iterable[E3Result],
) -> dict[str, Any]:
    """Score one twin arm's fidelity against ground truth, overall + per category."""
    cases = list(cases)
    gt = validate_results(cases, ground_truth)
    tw = validate_results(cases, twin)
    if gt[0].arm != "ground_truth":
        raise ValueError(f"ground_truth log has wrong arm: {gt[0].arm!r}")
    if tw[0].arm not in ("twin_nobw", "twin_bw"):
        raise ValueError(f"twin log has non-twin arm: {tw[0].arm!r}")

    gt_by_id = {r.case_id: r for r in gt}
    twin_by_id = {r.case_id: r for r in tw}

    report: dict[str, Any] = {
        "arm": tw[0].arm,
        "overall": _confusion(cases, gt_by_id, twin_by_id),
        "by_category": {},
    }
    categories = sorted({c.intent_category for c in cases})
    for category in categories:
        subset = [c for c in cases if c.intent_category == category]
        report["by_category"][category] = _confusion(subset, gt_by_id, twin_by_id)
    return report


def compute_fidelity_delta(
    cases: Iterable[E3Case],
    ground_truth: Iterable[E3Result],
    twin_nobw: Iterable[E3Result],
    twin_bw: Iterable[E3Result],
) -> dict[str, Any]:
    """Contrast reach-only vs reach+bandwidth twin fidelity (the E3 headline).

    Reports each arm's accuracy/fpr overall and per category, plus the change from
    adding the bandwidth probe. The bandwidth probe is expected to cut ``fpr`` on
    the ``qos`` category (dangerous wrong approvals of congested QoS policies)
    while leaving forwarding/security unchanged.
    """
    cases = list(cases)
    nobw = score_arm(cases, ground_truth, twin_nobw)
    withbw = score_arm(cases, ground_truth, twin_bw)

    def _delta(a: dict[str, Any], b: dict[str, Any], key: str) -> float | None:
        if a[key] is None or b[key] is None:
            return None
        return b[key] - a[key]

    delta: dict[str, Any] = {
        "twin_nobw": nobw,
        "twin_bw": withbw,
        "overall_delta": {
            "accuracy": _delta(nobw["overall"], withbw["overall"], "accuracy"),
            "fpr": _delta(nobw["overall"], withbw["overall"], "fpr"),
        },
        "by_category_delta": {},
    }
    for category in nobw["by_category"]:
        delta["by_category_delta"][category] = {
            "accuracy": _delta(nobw["by_category"][category], withbw["by_category"][category], "accuracy"),
            "fpr": _delta(nobw["by_category"][category], withbw["by_category"][category], "fpr"),
        }
    return delta
