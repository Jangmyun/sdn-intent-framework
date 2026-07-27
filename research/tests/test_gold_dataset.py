"""Behavioral checks for the GOLD-350 candidate dataset and blind split."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from safe_intent_sdn.e1_evaluation import EvaluationCase

GOLD_DIR = Path(__file__).resolve().parents[1] / "experiments" / "gold"
CANDIDATES = GOLD_DIR / "data" / "candidates.jsonl"
GOLD = GOLD_DIR / "data" / "gold.jsonl"
BLIND = GOLD_DIR / "data" / "blind" / "instructions.jsonl"
ID_MAP = GOLD_DIR / "data" / "blind" / "id_map.json"
ANN_A = GOLD_DIR / "annotations" / "annotator_a.jsonl"
ANN_B = GOLD_DIR / "annotations" / "annotator_b.jsonl"
FINAL = GOLD_DIR / "annotations" / "final_labels.jsonl"

EXPECTED = Counter({
    "forwarding": 50, "security": 50, "qos": 50, "sfc": 50,
    "reroute": 50, "compound": 50, "ambiguous_unsupported": 50,
})


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return _jsonl(CANDIDATES)


def test_candidates_validate_and_distribute(cases: list[dict]) -> None:
    assert len(cases) == 350
    for case in cases:
        EvaluationCase.model_validate(case)
    assert Counter(c["category"] for c in cases) == EXPECTED
    assert len({c["id"] for c in cases}) == 350
    assert len({c["instruction"] for c in cases}) == 350


def test_status_matches_category(cases: list[dict]) -> None:
    for case in cases:
        rejected = case["category"] == "ambiguous_unsupported"
        assert (case["expected"]["status"] == "rejected") == rejected, case["id"]


def test_rule_counts_by_category(cases: list[dict]) -> None:
    for case in cases:
        if case["expected"]["status"] != "accepted":
            continue
        rules = case["expected"]["program"]["rules"]
        if case["category"] == "compound":
            assert len(rules) >= 2, case["id"]
        elif case["category"] == "sfc":
            assert len(rules) >= 2, case["id"]
            assert case["expected"]["program"]["sfc_chain"], case["id"]
        else:
            assert len(rules) == 1, case["id"]


def test_blind_split_is_consistent(cases: list[dict]) -> None:
    blind = _jsonl(BLIND)
    id_map = json.loads(ID_MAP.read_text(encoding="utf-8"))
    assert len(blind) == 350
    assert sorted(id_map) == sorted(r["blind_id"] for r in blind)
    by_id = {c["id"]: c for c in cases}
    for row in blind:
        case = by_id[id_map[row["blind_id"]]]
        assert row["instruction"] == case["instruction"]
        assert set(row) == {"blind_id", "instruction"}, "blind rows must not leak labels"


def test_blind_order_not_grouped_by_category(cases: list[dict]) -> None:
    blind = _jsonl(BLIND)
    id_map = json.loads(ID_MAP.read_text(encoding="utf-8"))
    by_id = {c["id"]: c["category"] for c in cases}
    sequence = [by_id[id_map[r["blind_id"]]] for r in blind]
    run, longest = 1, 1
    for prev, cur in zip(sequence, sequence[1:]):
        run = run + 1 if cur == prev else 1
        longest = max(longest, run)
    assert longest < 10, "blind file appears grouped by category"


def test_annotators_and_final_labels_align_with_gold() -> None:
    if not (ANN_A.exists() and ANN_B.exists() and FINAL.exists() and GOLD.exists()):
        pytest.skip("annotation/gold artifacts not present")
    a = {json.loads(l)["blind_id"]: json.loads(l) for l in ANN_A.read_text().splitlines() if l.strip()}
    b = {json.loads(l)["blind_id"]: json.loads(l) for l in ANN_B.read_text().splitlines() if l.strip()}
    final = {json.loads(l)["blind_id"]: json.loads(l) for l in FINAL.read_text().splitlines() if l.strip()}
    id_map = json.loads(ID_MAP.read_text(encoding="utf-8"))
    assert set(a) == set(b) == set(final) == set(id_map) and len(a) == 350

    # perfect inter-annotator agreement was recorded; every unanimous final label
    # must equal both annotators, and any divergence must be marked adjudicated.
    for bid in id_map:
        if final[bid]["source"] == "unanimous":
            assert a[bid]["category"] == b[bid]["category"] == final[bid]["category"], bid
        else:
            assert final[bid]["source"] == "adjudicated", bid

    gold = {c["id"]: c for c in _jsonl(GOLD)}
    assert len(gold) == 350
    for bid, case_id in id_map.items():
        assert gold[case_id]["category"] == final[bid]["category"], case_id
