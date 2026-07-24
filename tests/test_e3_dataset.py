"""Shape and integrity tests for the E3 twin-fidelity dataset."""
from __future__ import annotations

from pathlib import Path

import pytest

from safe_intent_sdn.compiler import compile_prediction
from safe_intent_sdn.e3_evaluation import E3Case
from safe_intent_sdn.intent_ir import IntentPrediction

DATASET = Path(__file__).resolve().parents[1] / "experiments/e3/data/cases.jsonl"


@pytest.fixture(scope="module")
def cases() -> list[E3Case]:
    lines = DATASET.read_text(encoding="utf-8").splitlines()
    return [E3Case.model_validate_json(x) for x in lines if x.strip()]


def test_dataset_is_non_empty_and_ids_unique(cases: list[E3Case]) -> None:
    assert cases, "E3 dataset is empty -- run experiments/e3/build_dataset.py"
    ids = [c.id for c in cases]
    assert len(set(ids)) == len(ids), "duplicate case ids in E3 dataset"


def test_every_program_compiles(cases: list[E3Case]) -> None:
    for case in cases:
        compile_prediction(IntentPrediction(status="accepted", program=case.program))


def test_categories_are_within_the_allowed_set(cases: list[E3Case]) -> None:
    allowed = {"forwarding", "security", "qos", "reroute", "compound"}
    assert {c.intent_category for c in cases} <= allowed


def test_dataset_has_both_ground_truth_labels(cases: list[E3Case]) -> None:
    labels = {c.expected_ground_truth for c in cases}
    assert labels == {"SHOULD_PASS", "SHOULD_FAIL"}, (
        "E3 needs both approve and reject ground truths to measure fpr"
    )


def test_qos_cases_carry_a_bandwidth_target(cases: list[E3Case]) -> None:
    for case in cases:
        if case.intent_category == "qos":
            assert case.min_mbps is not None, f"{case.id}: qos case without min_mbps"


def test_bandwidth_target_only_on_bandwidth_intents(cases: list[E3Case]) -> None:
    # A min_mbps only makes sense where the bandwidth probe runs (reachable intents).
    for case in cases:
        if case.min_mbps is not None:
            assert case.intent_category in {"qos", "forwarding", "reroute"}, (
                f"{case.id}: min_mbps set on non-bandwidth category {case.intent_category}"
            )


def test_has_an_over_capacity_qos_should_fail_case(cases: list[E3Case]) -> None:
    """The headline scenario: a reachable-but-infeasible-target QoS case must
    exist, or the reach-only twin can never be shown to issue a wrong approval.

    "Infeasible" here means min_mbps exceeds the fast link's physical ceiling
    (safe_intent_sdn.twin.topology.DIAMOND_FAST_LINK_MBPS) -- no queue
    reservation, real or not, can ever satisfy it, so the case is deterministic
    regardless of background load.
    """
    from safe_intent_sdn.twin.topology import DIAMOND_FAST_LINK_MBPS

    over_capacity = [
        c for c in cases
        if c.intent_category == "qos"
        and c.expected_ground_truth == "SHOULD_FAIL"
        and c.min_mbps is not None
        and c.min_mbps > DIAMOND_FAST_LINK_MBPS
    ]
    assert over_capacity, "no over-capacity SHOULD_FAIL qos case -- fpr contrast is not exercisable"


def test_background_flows_reference_valid_endpoints(cases: list[E3Case]) -> None:
    for case in cases:
        for bf in case.background_traffic:
            assert bf.src != bf.dst, f"{case.id}: background flow with src==dst"
            assert bf.dst_ip, f"{case.id}: background flow missing dst_ip"
