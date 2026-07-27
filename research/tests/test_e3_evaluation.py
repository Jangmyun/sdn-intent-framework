"""Scoring and fail-closed-integrity tests for E3 (no Mininet needed)."""
from __future__ import annotations

import pytest

from safe_intent_sdn.e3_evaluation import (
    E3Case,
    E3Result,
    check_ground_truth_labels,
    compute_fidelity_delta,
    score_arm,
    validate_results,
)
from safe_intent_sdn.intent_ir import (
    Endpoint,
    EnforcementConstraint,
    IntentProgram,
    IntentRule,
    TrafficSelector,
)


def _program(dst_ip: str = "10.0.0.4") -> IntentProgram:
    return IntentProgram(rules=[IntentRule(
        intent_type="forwarding", action="forward",
        selector=TrafficSelector(destination=Endpoint(ip=dst_ip), eth_type="ipv4"),
        enforcement=EnforcementConstraint(device="of:0000000000000001", egress_port="2"),
    )])


def _case(cid: str, category: str, expected_gt: str, min_mbps=None) -> E3Case:
    return E3Case(
        id=cid, intent_category=category, program=_program(),
        min_mbps=min_mbps, expected_ground_truth=expected_gt,
    )


def _result(cid: str, arm: str, category: str, outcome: str, status: str = "passed") -> E3Result:
    return E3Result(case_id=cid, arm=arm, intent_category=category, outcome=outcome, twin_status=status)


# ── a small fixed scenario reused across tests ──────────────────────────────
# c1 congested qos (SHOULD_FAIL): reach-only wrongly PASSes, bandwidth arm FAILs.
# c2 qos SHOULD_PASS, c3 forwarding SHOULD_PASS, c4 security SHOULD_PASS.
CASES = [
    _case("c1", "qos", "SHOULD_FAIL", min_mbps=8.0),
    _case("c2", "qos", "SHOULD_PASS", min_mbps=8.0),
    _case("c3", "forwarding", "SHOULD_PASS"),
    _case("c4", "security", "SHOULD_PASS"),
]
GROUND_TRUTH = [
    _result("c1", "ground_truth", "qos", "FAIL", "failed"),
    _result("c2", "ground_truth", "qos", "PASS"),
    _result("c3", "ground_truth", "forwarding", "PASS"),
    _result("c4", "ground_truth", "security", "PASS"),
]
TWIN_NOBW = [
    _result("c1", "twin_nobw", "qos", "PASS"),          # wrong approval (FP)
    _result("c2", "twin_nobw", "qos", "PASS"),
    _result("c3", "twin_nobw", "forwarding", "PASS"),
    _result("c4", "twin_nobw", "security", "PASS"),
]
TWIN_BW = [
    _result("c1", "twin_bw", "qos", "FAIL", "failed"),  # correctly rejected (TN)
    _result("c2", "twin_bw", "qos", "PASS"),
    _result("c3", "twin_bw", "forwarding", "PASS"),
    _result("c4", "twin_bw", "security", "PASS"),
]


def test_validate_results_accepts_a_clean_log() -> None:
    assert validate_results(CASES, TWIN_NOBW) == TWIN_NOBW


def test_missing_case_fails_closed() -> None:
    with pytest.raises(ValueError, match="missing"):
        validate_results(CASES, TWIN_NOBW[:-1])


def test_extra_result_fails_closed() -> None:
    extra = TWIN_NOBW + [_result("c9", "twin_nobw", "qos", "PASS")]
    with pytest.raises(ValueError, match="extra"):
        validate_results(CASES, extra)


def test_duplicate_result_fails_closed() -> None:
    with pytest.raises(ValueError, match="duplicate case_id"):
        validate_results(CASES, TWIN_NOBW + [TWIN_NOBW[0]])


def test_mixed_arms_fail_closed() -> None:
    mixed = TWIN_NOBW[:-1] + [_result("c4", "twin_bw", "security", "PASS")]
    with pytest.raises(ValueError, match="mixes arms"):
        validate_results(CASES, mixed)


def test_category_drift_fails_closed() -> None:
    drifted = TWIN_NOBW[:-1] + [_result("c4", "twin_nobw", "qos", "PASS")]
    with pytest.raises(ValueError, match="!="):
        validate_results(CASES, drifted)


def test_skipped_twin_status_fails_closed() -> None:
    skipped = TWIN_NOBW[:-1] + [_result("c4", "twin_nobw", "security", "FAIL", "skipped")]
    with pytest.raises(ValueError, match="skipped"):
        validate_results(CASES, skipped)


def test_reach_only_arm_has_high_fpr() -> None:
    report = score_arm(CASES, GROUND_TRUTH, TWIN_NOBW)
    overall = report["overall"]
    assert (overall["tp"], overall["fp"], overall["fn"], overall["tn"]) == (3, 1, 0, 0)
    assert overall["fpr"] == 1.0          # the one bad policy was wrongly approved
    assert overall["accuracy"] == 0.75


def test_bandwidth_arm_eliminates_wrong_approval() -> None:
    report = score_arm(CASES, GROUND_TRUTH, TWIN_BW)
    overall = report["overall"]
    assert (overall["tp"], overall["fp"], overall["fn"], overall["tn"]) == (3, 0, 0, 1)
    assert overall["fpr"] == 0.0
    assert overall["accuracy"] == 1.0


def test_per_category_isolates_the_qos_blind_spot() -> None:
    nobw = score_arm(CASES, GROUND_TRUTH, TWIN_NOBW)["by_category"]
    assert nobw["qos"]["fpr"] == 1.0
    # forwarding/security have no defect-positive cases, so fpr is undefined (None)
    assert nobw["forwarding"]["fpr"] is None
    assert nobw["security"]["fpr"] is None


def test_fidelity_delta_shows_bandwidth_probe_cuts_qos_fpr() -> None:
    delta = compute_fidelity_delta(CASES, GROUND_TRUTH, TWIN_NOBW, TWIN_BW)
    assert delta["overall_delta"]["fpr"] == -1.0     # 0.0 - 1.0
    assert delta["overall_delta"]["accuracy"] == 0.25
    assert delta["by_category_delta"]["qos"]["fpr"] == -1.0


def test_ground_truth_label_mismatch_is_detected() -> None:
    assert check_ground_truth_labels(CASES, GROUND_TRUTH) == []
    # Flip c1's measured outcome to PASS while the author label says SHOULD_FAIL.
    tampered = [_result("c1", "ground_truth", "qos", "PASS")] + GROUND_TRUTH[1:]
    assert check_ground_truth_labels(CASES, tampered) == ["c1"]


def test_score_arm_rejects_wrong_arm_in_ground_truth_slot() -> None:
    with pytest.raises(ValueError, match="ground_truth log has wrong arm"):
        score_arm(CASES, TWIN_NOBW, TWIN_BW)
