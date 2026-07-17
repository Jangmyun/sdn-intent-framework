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


def sfc_inventory() -> TopologyInventory:
    """A device:s5 is present but declares no ports -- a registered-but-not-yet-
    deployed waypoint, used to isolate ``path_unknown_waypoint`` from a
    ``reference`` finding (a device string absent from the topology entirely
    would trigger both)."""
    return load_topology_inventory(
        {
            "entities": [
                {"id": "host:h1", "aliases": ["h1", "10.0.0.1"]},
                {"id": "device:s1", "aliases": ["s1", "of:0000000000000001"]},
                {"id": "device:s2", "aliases": ["s2", "of:0000000000000002"]},
                {"id": "device:s3", "aliases": ["s3", "of:0000000000000003"]},
                {"id": "device:s5", "aliases": ["s5", "of:0000000000000005"]},
            ],
            "ports": {
                "of:0000000000000001": [1, 2, 9],
                "of:0000000000000002": [1, 2],
                "of:0000000000000003": [1, 2],
            },
        }
    )


def sfc_program(rules: list[dict], sfc_chain: list[str] | None) -> IntentProgram:
    return IntentProgram.model_validate({"rules": rules, "sfc_chain": sfc_chain})


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


def test_validate_program_flags_path_chain_length_mismatch():
    value = sfc_program(
        [
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "ingress",
                "selector": {}, "enforcement": {"device": "s1", "egress_port": 1},
            },
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "transit",
                "selector": {}, "enforcement": {"device": "s2", "egress_port": 1},
            },
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "egress",
                "selector": {}, "enforcement": {"device": "s3", "egress_port": 1},
            },
        ],
        ["of:0000000000000002"],
    )
    report = validate_program(value, sfc_inventory())
    assert [(f.category, f.code) for f in report.findings] == [("path", "path_chain_length_mismatch")]


def test_validate_program_flags_path_waypoint_device_mismatch():
    value = sfc_program(
        [
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "ingress",
                "selector": {}, "enforcement": {"device": "s1", "egress_port": 1},
            },
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "transit",
                "selector": {}, "enforcement": {"device": "s2", "egress_port": 1},
            },
        ],
        ["of:0000000000000003"],
    )
    report = validate_program(value, sfc_inventory())
    assert [(f.category, f.code) for f in report.findings] == [("path", "path_waypoint_device_mismatch")]


def test_validate_program_flags_path_unknown_waypoint():
    value = sfc_program(
        [
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "ingress",
                "selector": {}, "enforcement": {"device": "s1", "egress_port": 1},
            },
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "egress",
                "selector": {}, "enforcement": {"device": "s5", "egress_port": 1},
            },
        ],
        ["of:0000000000000005"],
    )
    report = validate_program(value, sfc_inventory())
    assert [(f.category, f.code) for f in report.findings] == [("path", "path_unknown_waypoint")]


def test_validate_program_flags_path_waypoint_port_out_of_range():
    value = sfc_program(
        [
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "ingress",
                "selector": {}, "enforcement": {"device": "s1", "egress_port": 1},
            },
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "transit",
                "selector": {}, "enforcement": {"device": "s2", "egress_port": 1},
            },
        ],
        ["of:0000000000000002:9"],
    )
    report = validate_program(value, sfc_inventory())
    assert [(f.category, f.code) for f in report.findings] == [("path", "path_waypoint_port_out_of_range")]


def test_validate_program_flags_path_port_discontinuity():
    value = sfc_program(
        [
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "ingress",
                "selector": {}, "enforcement": {"device": "s1", "egress_port": 9},
            },
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "egress",
                "selector": {"ingress_port": 1}, "enforcement": {"device": "s1", "egress_port": 2},
            },
        ],
        ["of:0000000000000001:9"],
    )
    report = validate_program(value, sfc_inventory())
    assert [(f.category, f.code) for f in report.findings] == [("path", "path_port_discontinuity")]


@pytest.mark.parametrize(
    "roles",
    [
        ["ingress", "egress", "transit"],
        ["ingress", "ingress"],
    ],
)
def test_validate_program_flags_path_role_order_invalid(roles):
    rules = [
        {
            "intent_type": "sfc", "action": "forward", "sfc_role": role,
            "selector": {}, "enforcement": {"device": device, "egress_port": 1},
        }
        for role, device in zip(roles, ("s1", "s2", "s3"))
    ]
    chain = [f"of:000000000000000{i}" for i in range(2, len(rules) + 1)]
    report = validate_program(sfc_program(rules, chain), sfc_inventory())
    assert [(f.category, f.code) for f in report.findings] == [("path", "path_role_order_invalid")]


def test_validate_program_flags_path_avoid_device_conflict():
    value = program(
        {
            "intent_type": "reroute", "action": "forward",
            "selector": {},
            "enforcement": {"device": "s1", "egress_port": 1, "avoid_device": "s1"},
        }
    )
    report = validate_program(value, sfc_inventory())
    assert [(f.category, f.code) for f in report.findings] == [("path", "path_avoid_device_conflict")]


def test_validate_program_does_not_flag_a_correctly_formed_three_hop_chain():
    value = sfc_program(
        [
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "ingress",
                "selector": {}, "enforcement": {"device": "s1", "egress_port": 1},
            },
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "transit",
                "selector": {}, "enforcement": {"device": "s2", "egress_port": 1},
            },
            {
                "intent_type": "sfc", "action": "forward", "sfc_role": "egress",
                "selector": {}, "enforcement": {"device": "s3", "egress_port": 1},
            },
        ],
        ["of:0000000000000002", "of:0000000000000003"],
    )
    report = validate_program(value, sfc_inventory())
    assert report.is_valid


@pytest.mark.parametrize("intent_type", ["sfc", "reroute"])
def test_existing_categories_are_unaffected_by_new_intent_types(intent_type):
    """reference/feasibility/conflict checks only read selector/enforcement, so
    sfc/reroute rules must trip them exactly like a forwarding rule would."""
    extra = {"sfc_role": "ingress"} if intent_type == "sfc" else {}
    rules = [{"intent_type": intent_type, "action": "forward", "selector": {"source": {"host": "ghost"}}, "enforcement": {"device": "s1", "egress_port": 1}, **extra}]
    chain = ["of:0000000000000002"] if intent_type == "sfc" else None
    value = sfc_program(rules, chain) if intent_type == "sfc" else program(*rules)
    report = validate_program(value, sfc_inventory())
    assert ("reference", "unknown_host") in [(f.category, f.code) for f in report.findings]
