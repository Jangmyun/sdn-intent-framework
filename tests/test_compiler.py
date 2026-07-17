from __future__ import annotations

import pytest

from safe_intent_sdn.compiler import CompilationError, compile_prediction
from safe_intent_sdn.intent_ir import IntentPrediction
from safe_intent_sdn.onos import parse_onos_response


def prediction(*rules: dict) -> IntentPrediction:
    return IntentPrediction.model_validate(
        {"status": "accepted", "program": {"rules": list(rules)}, "rejection": None}
    )


def test_compile_forwarding_selector_and_host_resolution():
    value = prediction(
        {
            "intent_type": "forwarding",
            "action": "forward",
            "selector": {
                "source": {"host": "h1"},
                "destination": {"ip": "10.0.0.3"},
                "protocol": "tcp",
                "destination_port": 80,
            },
            "enforcement": {"device": "of:0000000000000001", "egress_port": 2},
        }
    )
    result = compile_prediction(value, endpoint_ips={"h1": "10.0.0.1"})
    flow = result.flows[0]
    assert flow.priority == 500 and flow.isPermanent is True
    assert [item.type for item in flow.selector.criteria] == [
        "ETH_TYPE", "IP_PROTO", "IPV4_SRC", "IPV4_DST", "TCP_DST"
    ]
    assert flow.treatment.instructions[-1].port == 2
    assert parse_onos_response(result.model_dump(mode="json")).program.rules[0].selector.source.ip == "10.0.0.1"


def test_compile_ordered_deny_then_allow_with_descending_priority():
    value = prediction(
        {
            "intent_type": "security",
            "action": "deny",
            "selector": {"source": {"ip": "10.0.0.13"}},
            "enforcement": {"device": "of:0000000000000002"},
        },
        {
            "intent_type": "security",
            "action": "allow",
            "selector": {"destination": {"ip": "10.0.0.13"}},
            "enforcement": {"device": "of:0000000000000002", "egress_port": 7},
        },
    )
    flows = compile_prediction(value).flows
    assert [flow.priority for flow in flows] == [500, 499]
    assert flows[0].treatment is None
    assert flows[1].treatment.instructions[0].type == "OUTPUT"


def test_compile_qos_vlan_instruction_order():
    value = prediction(
        {
            "intent_type": "qos",
            "action": "prioritize",
            "selector": {"eth_type": "ipv4", "protocol": "udp", "destination_port": 161},
            "qos": {"queue": 3, "max_latency_ms": 5},
            "enforcement": {
                "device": "of:0000000000000004", "egress_port": "5", "set_vlan_id": 100
            },
        }
    )
    instructions = compile_prediction(value).flows[0].treatment.instructions
    assert [item.type for item in instructions] == ["QUEUE", "L2MODIFICATION", "OUTPUT"]


@pytest.mark.parametrize(
    ("rule", "message"),
    [
        ({"intent_type": "forwarding", "action": "forward", "selector": {}}, "device"),
        (
            {
                "intent_type": "qos", "action": "prioritize", "selector": {},
                "qos": {"max_latency_ms": 5},
                "enforcement": {"device": "s1", "egress_port": 1},
            },
            "queue",
        ),
        (
            {
                "intent_type": "forwarding", "action": "forward",
                "selector": {"source": {"host": "unknown"}},
                "enforcement": {"device": "s1", "egress_port": 1},
            },
            "no IP mapping",
        ),
    ],
)
def test_compile_fails_closed_when_ir_lacks_required_lowering_data(rule, message):
    with pytest.raises(CompilationError, match=message):
        compile_prediction(prediction(rule))


def test_rejected_intent_cannot_be_compiled():
    rejected = IntentPrediction.model_validate(
        {"status": "rejected", "program": None, "rejection": {"reason": "ambiguous"}}
    )
    with pytest.raises(CompilationError, match="rejected"):
        compile_prediction(rejected)


def test_compile_sfc_program_matches_equivalent_forwarding_shape():
    """sfc rules use action="forward" like plain forwarding rules; the compiler
    has no sfc-specific branch, so an sfc program and an equivalent forwarding
    program (same selector/enforcement, sfc_role/sfc_chain stripped) must produce
    the same OnosFlow shape."""
    sfc = IntentPrediction.model_validate(
        {
            "status": "accepted",
            "program": {
                "rules": [
                    {
                        "intent_type": "sfc", "action": "forward", "sfc_role": "ingress",
                        "selector": {"source": {"ip": "10.0.0.1"}, "destination": {"ip": "10.0.0.3"}},
                        "enforcement": {"device": "of:0000000000000001", "egress_port": "9"},
                    },
                    {
                        "intent_type": "sfc", "action": "forward", "sfc_role": "egress",
                        "selector": {"destination": {"ip": "10.0.0.3"}, "ingress_port": 9},
                        "enforcement": {"device": "of:0000000000000001", "egress_port": "1"},
                    },
                ],
                "sfc_chain": ["of:0000000000000001:9"],
            },
            "rejection": None,
        }
    )
    forwarding = IntentPrediction.model_validate(
        {
            "status": "accepted",
            "program": {
                "rules": [
                    {
                        "intent_type": "forwarding", "action": "forward",
                        "selector": {"source": {"ip": "10.0.0.1"}, "destination": {"ip": "10.0.0.3"}},
                        "enforcement": {"device": "of:0000000000000001", "egress_port": "9"},
                    },
                    {
                        "intent_type": "forwarding", "action": "forward",
                        "selector": {"destination": {"ip": "10.0.0.3"}, "ingress_port": 9},
                        "enforcement": {"device": "of:0000000000000001", "egress_port": "1"},
                    },
                ],
            },
            "rejection": None,
        }
    )
    assert compile_prediction(sfc).model_dump() == compile_prediction(forwarding).model_dump()


def test_compile_reroute_program_matches_equivalent_forwarding_shape():
    reroute = IntentPrediction.model_validate(
        {
            "status": "accepted",
            "program": {
                "rules": [
                    {
                        "intent_type": "reroute", "action": "forward",
                        "selector": {"destination": {"ip": "10.0.0.4"}},
                        "enforcement": {"device": "of:0000000000000001", "egress_port": 1, "avoid_device": "of:0000000000000003"},
                    },
                ],
            },
            "rejection": None,
        }
    )
    forwarding = prediction(
        {
            "intent_type": "forwarding", "action": "forward",
            "selector": {"destination": {"ip": "10.0.0.4"}},
            "enforcement": {"device": "of:0000000000000001", "egress_port": 1},
        }
    )
    assert compile_prediction(reroute).model_dump() == compile_prediction(forwarding).model_dump()
