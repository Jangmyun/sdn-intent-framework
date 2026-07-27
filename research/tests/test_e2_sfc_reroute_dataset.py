from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from safe_intent_sdn.e2_evaluation import E2Case
from safe_intent_sdn.validator import load_topology_inventory, validate_program

DATASET = Path("experiments/e2/data/cases_sfc_reroute.jsonl")
TOPOLOGY = Path("experiments/e1/data/topology_diamond.json")


def cases() -> list[E2Case]:
    return [E2Case.model_validate_json(x) for x in DATASET.read_text().splitlines()]


def test_distribution_and_unique_ids():
    x = cases()
    assert len(x) == 65
    assert len({c.id for c in x}) == 65
    assert Counter(c.category for c in x) == Counter(
        {"clean": 50, "path": 8, "feasibility": 3, "conflict": 2, "reference": 1, "multi": 1}
    )


def test_every_authored_fixture_round_trips_through_the_validator():
    """Build-time correctness net: catches an authored-fixture/validator drift
    immediately, rather than only surfacing it later at run_validation.py time."""
    inventory = load_topology_inventory(json.loads(TOPOLOGY.read_text()))
    for case in cases():
        if case.category == "clean":
            continue
        report = validate_program(case.program, inventory)
        assert sorted({f.category for f in report.findings}) == sorted(case.expected_findings)
        if case.expected_codes:
            assert sorted({f.code for f in report.findings}) == sorted(case.expected_codes)


def test_clean_cases_have_no_findings():
    inventory = load_topology_inventory(json.loads(TOPOLOGY.read_text()))
    for case in cases():
        if case.category != "clean":
            continue
        assert validate_program(case.program, inventory).is_valid
