from __future__ import annotations

import pytest

from safe_intent_sdn.intent_ir import IntentProgram
from safe_intent_sdn.validator import TopologyInventory, load_topology_inventory, validate_program


def program(*rules: dict) -> IntentProgram:
    return IntentProgram.model_validate({"rules": list(rules)})


def inventory() -> TopologyInventory:
    return load_topology_inventory(
        {
            "entities": [
                {"id": "host:h1", "aliases": ["h1", "10.0.0.1"]},
                {"id": "host:h2", "aliases": ["h2", "10.0.0.2"]},
                {"id": "device:s1", "aliases": ["s1", "of:0000000000000001"]},
                {"id": "device:s2", "aliases": ["s2", "of:0000000000000002"]},
            ],
            "ports": {"of:0000000000000001": [1, 2, 3], "of:0000000000000002": [1, 2]},
        }
    )


def test_load_topology_inventory_resolves_device_ports_by_alias():
    inv = inventory()
    assert inv.aliases["s1"] == "device:s1"
    assert inv.device_ports["device:s1"] == frozenset({1, 2, 3})


def test_validate_program_accepts_clean_program_with_no_findings():
    value = program(
        {
            "intent_type": "forwarding",
            "action": "forward",
            "selector": {"source": {"host": "h1"}, "destination": {"host": "h2"}},
            "enforcement": {"device": "s1", "egress_port": 2},
        }
    )
    report = validate_program(value, inventory())
    assert report.is_valid


def test_validate_program_flags_unknown_host_reference():
    value = program(
        {
            "intent_type": "forwarding",
            "action": "forward",
            "selector": {"source": {"host": "ghost"}},
            "enforcement": {"device": "s1", "egress_port": 1},
        }
    )
    report = validate_program(value, inventory())
    assert [(f.category, f.code) for f in report.findings] == [("reference", "unknown_host")]


def test_validate_program_flags_unknown_ip_endpoint_reference():
    value = program(
        {
            "intent_type": "forwarding",
            "action": "forward",
            "selector": {"destination": {"ip": "10.0.0.99"}},
            "enforcement": {"device": "s1", "egress_port": 1},
        }
    )
    report = validate_program(value, inventory())
    assert [(f.category, f.code) for f in report.findings] == [("reference", "unknown_ip")]


def test_validate_program_flags_unknown_device_reference():
    value = program(
        {
            "intent_type": "security",
            "action": "deny",
            "selector": {"source": {"host": "h1"}},
            "enforcement": {"device": "of:0000000000000099"},
        }
    )
    report = validate_program(value, inventory())
    assert [(f.category, f.code) for f in report.findings] == [("reference", "unknown_device")]


def test_validate_program_flags_egress_port_out_of_range():
    value = program(
        {
            "intent_type": "forwarding",
            "action": "forward",
            "selector": {},
            "enforcement": {"device": "s1", "egress_port": 99},
        }
    )
    report = validate_program(value, inventory())
    assert [(f.category, f.code) for f in report.findings] == [("feasibility", "egress_port_out_of_range")]


def test_validate_program_flags_ingress_port_out_of_range():
    value = program(
        {
            "intent_type": "forwarding",
            "action": "forward",
            "selector": {"ingress_port": 99},
            "enforcement": {"device": "s1", "egress_port": 1},
        }
    )
    report = validate_program(value, inventory())
    assert [(f.category, f.code) for f in report.findings] == [("feasibility", "ingress_port_out_of_range")]


def test_validate_program_flags_shadowed_rule_when_general_rule_precedes_specific_rule():
    value = program(
        {
            "intent_type": "security",
            "action": "deny",
            "selector": {},
            "enforcement": {"device": "s1"},
        },
        {
            "intent_type": "security",
            "action": "allow",
            "selector": {"source": {"host": "h1"}},
            "enforcement": {"device": "s1", "egress_port": 1},
        },
    )
    report = validate_program(value, inventory())
    assert [(f.category, f.code, f.rule_indices) for f in report.findings] == [
        ("conflict", "shadowed_rule", [0, 1])
    ]


def test_validate_program_does_not_flag_specific_rule_preceding_general_rule():
    value = program(
        {
            "intent_type": "security",
            "action": "allow",
            "selector": {"source": {"host": "h1"}},
            "enforcement": {"device": "s1", "egress_port": 1},
        },
        {
            "intent_type": "security",
            "action": "deny",
            "selector": {},
            "enforcement": {"device": "s1"},
        },
    )
    report = validate_program(value, inventory())
    assert report.is_valid


def test_validate_program_does_not_flag_identical_selectors_on_different_devices():
    value = program(
        {
            "intent_type": "security",
            "action": "deny",
            "selector": {"source": {"host": "h1"}},
            "enforcement": {"device": "s1"},
        },
        {
            "intent_type": "security",
            "action": "allow",
            "selector": {"source": {"host": "h1"}},
            "enforcement": {"device": "s2", "egress_port": 1},
        },
    )
    report = validate_program(value, inventory())
    assert report.is_valid


def test_validate_program_reports_multiple_simultaneous_findings_for_one_case():
    value = program(
        {
            "intent_type": "security",
            "action": "deny",
            "selector": {},
            "enforcement": {"device": "unknown-switch"},
        },
        {
            "intent_type": "security",
            "action": "allow",
            "selector": {"source": {"host": "ghost"}},
            "enforcement": {"device": "s1", "egress_port": 1},
        },
    )
    report = validate_program(value, inventory())
    codes = {(f.category, f.code) for f in report.findings}
    assert ("reference", "unknown_device") in codes
    assert ("reference", "unknown_host") in codes


@pytest.mark.parametrize(
    ("rules", "expected"),
    [
        (
            [
                {
                    "intent_type": "forwarding", "action": "forward",
                    "selector": {"source": {"ip": "203.0.113.9"}},
                    "enforcement": {"device": "s1", "egress_port": 1},
                }
            ],
            [("reference", "unknown_ip")],
        ),
        (
            [
                {
                    "intent_type": "qos", "action": "prioritize",
                    "selector": {"ingress_port": 4},
                    "qos": {"queue": 1},
                    "enforcement": {"device": "s2", "egress_port": 1},
                }
            ],
            [("feasibility", "ingress_port_out_of_range")],
        ),
    ],
)
def test_validate_program_single_defect_variants(rules, expected):
    report = validate_program(program(*rules), inventory())
    assert [(f.category, f.code) for f in report.findings] == expected
