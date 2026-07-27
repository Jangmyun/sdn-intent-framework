from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from safe_intent_sdn.e1_evaluation import EvaluationCase

DATASET = Path("experiments/e1/data/intents_sfc_reroute.jsonl")
BASE = Path("experiments/e1/data/project_authored.jsonl")


def cases() -> list[EvaluationCase]:
    return [EvaluationCase.model_validate_json(x) for x in DATASET.read_text().splitlines()]


def test_distribution_and_unique_ids():
    x = cases()
    assert len(x) == 100
    assert len({c.id for c in x}) == 100
    assert Counter(c.category for c in x) == Counter(
        {"forwarding": 15, "security": 15, "qos": 10, "ambiguous_unsupported": 10, "sfc": 25, "reroute": 25}
    )


def test_reused_fifty_rows_are_dict_equal_to_project_authored():
    base_rows = [json.loads(line) for line in BASE.read_text().splitlines()]
    dataset_rows = [json.loads(line) for line in DATASET.read_text().splitlines()]
    by_id = {row["id"]: row for row in dataset_rows}
    for row in base_rows:
        assert by_id[row["id"]] == row


def test_sfc_and_reroute_rows_carry_provenance():
    x = [c for c in cases() if c.category in ("sfc", "reroute")]
    assert len(x) == 50
    assert all(c.provenance.repository and c.provenance.commit_sha for c in x)
