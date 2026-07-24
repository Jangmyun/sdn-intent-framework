"""Build the E3 twin-fidelity dataset (experiments/e3/data/cases.jsonl).

Each case is constructed through the pydantic models so it is guaranteed to be a
valid IntentProgram and to compile to ONOS flows (asserted here), matching the
e1/e2/gold builder convention. Cases target the default diamond topology:

    h1=10.0.0.1, h2=10.0.0.2 on s1 ; h3=10.0.0.3, h4=10.0.0.4 on s4
    fast path s1-s3-s4 @ 10 Mbps ; slow path s1-s2-s4 @ 1 Mbps

The qos ``over capacity`` cases request a rate above the fast link's 10 Mbps
ceiling -- reachable, but no queue reservation can ever satisfy the target --
these are the cases where a reach-only twin issues a dangerous wrong approval
while the bandwidth-probing twin does not. See DATASET_CARD.md and
paper/experiment_protocol/e3_rationale.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from safe_intent_sdn.compiler import compile_prediction
from safe_intent_sdn.e3_evaluation import BackgroundFlow, E3Case
from safe_intent_sdn.intent_ir import (
    Endpoint,
    EnforcementConstraint,
    IntentPrediction,
    IntentProgram,
    IntentRule,
    QosConstraint,
    TrafficSelector,
)

S1 = "of:0000000000000001"
S2 = "of:0000000000000002"
IP = {"h1": "10.0.0.1", "h2": "10.0.0.2", "h3": "10.0.0.3", "h4": "10.0.0.4"}
FAST_EGRESS = "2"  # s1 port toward s3 (fast path)


def _forward(dst_ip: str, *, src_ip: str | None = None, proto="icmp", dport=None) -> IntentProgram:
    return IntentProgram(rules=[IntentRule(
        intent_type="forwarding", action="forward",
        selector=TrafficSelector(
            source=Endpoint(ip=src_ip) if src_ip else None,
            destination=Endpoint(ip=dst_ip), eth_type="ipv4",
            protocol=proto, destination_port=dport,
        ),
        enforcement=EnforcementConstraint(device=S1, egress_port=FAST_EGRESS),
    )])


def _deny(dst_ip: str, *, src_ip: str | None = None, proto="icmp", dport=None) -> IntentProgram:
    return IntentProgram(rules=[IntentRule(
        intent_type="security", action="deny",
        selector=TrafficSelector(
            source=Endpoint(ip=src_ip) if src_ip else None,
            destination=Endpoint(ip=dst_ip), eth_type="ipv4",
            protocol=proto, destination_port=dport,
        ),
        enforcement=EnforcementConstraint(device=S1),
    )])


def _qos(dst_ip: str, min_mbps: float, *, src_ip: str = "10.0.0.1") -> IntentProgram:
    return IntentProgram(rules=[IntentRule(
        intent_type="qos", action="prioritize",
        selector=TrafficSelector(
            source=Endpoint(ip=src_ip), destination=Endpoint(ip=dst_ip), eth_type="ipv4",
        ),
        qos=QosConstraint(min_bandwidth_mbps=min_mbps, queue=0),
        enforcement=EnforcementConstraint(device=S1, egress_port=FAST_EGRESS),
    )])


def _reroute(dst_ip: str, *, src_ip="10.0.0.1", avoid=S2) -> IntentProgram:
    return IntentProgram(rules=[IntentRule(
        intent_type="reroute", action="forward",
        selector=TrafficSelector(
            source=Endpoint(ip=src_ip), destination=Endpoint(ip=dst_ip), eth_type="ipv4",
        ),
        enforcement=EnforcementConstraint(device=S1, egress_port=FAST_EGRESS, avoid_device=avoid),
    )])


# Background load on the shared fast path: h2->h4 is meant to also route via
# s1-s3-s4, competing for the 10 Mbps links with an h1->h4 QoS flow.
#
# Destination is h4, NOT h3: the diamond topology's regression pair is fixed at
# (h2, h3) (safe_intent_sdn/twin/topology.py::get_test_host_pairs), so a
# background flow ALSO routed h2->h3 would make the regression check test
# exactly the pair we deliberately loaded -- a self-contradiction (of course a
# pair stays "affected" when it IS the background load). h2->h4 still crosses
# the same shared s1-s4 link without colliding with either the regression pair
# (h2,h3) or the primary intent pair (h1,h4)'s source.
def _bg(mbps: float) -> list[BackgroundFlow]:
    return [BackgroundFlow(src="h2", dst="h4", dst_ip=IP["h4"], mbps=mbps, proto="udp", duration=30)]


def _with_forced_bg_route(program: IntentProgram, bg_src_ip: str, bg_dst_ip: str) -> IntentProgram:
    """Append a forwarding rule that pins the background flow onto the fast path.

    s1-s4 has two equal-hop paths (s2 @ 1 Mbps, s3 @ 10 Mbps). The primary QoS
    intent forces its own first hop onto the fast path via `enforcement`, but the
    background flow has no such rule and is left entirely to ONOS's reactive
    `fwd` app -- which has no reason to prefer one equal-hop path over the other.
    Measured runs showed `fwd` sending the background flow over the *slow* path,
    so it never actually contended with the intent flow and congestion was not
    reproduced. Pinning the background flow's first hop the same way the intent
    flow is pinned makes the contention deterministic. See
    experiments/e3/DATASET_CARD.md and the "ground_truth_label_mismatch" guard in
    safe_intent_sdn/e3_evaluation.py, which is exactly the check that caught this.
    """
    route_rule = IntentRule(
        intent_type="forwarding", action="forward",
        selector=TrafficSelector(
            source=Endpoint(ip=bg_src_ip), destination=Endpoint(ip=bg_dst_ip), eth_type="ipv4",
        ),
        enforcement=EnforcementConstraint(device=S1, egress_port=FAST_EGRESS),
    )
    return IntentProgram(rules=[*program.rules, route_rule])


def build_cases() -> list[E3Case]:
    cases: list[E3Case] = []

    # forwarding -- reach-only twin is already faithful here (control category).
    # Both use ICMP, not a TCP port selector: see "TCP-selector forwarding cases"
    # in DATASET_CARD.md -- a forwarding rule that pins an egress port can send a
    # connection-oriented flow down a different path than ONOS's reactive `fwd`
    # app learned, breaking the round trip. That is an artifact of the twin/`fwd`
    # interaction, not a property E3 measures.
    cases.append(E3Case(id="E3-FWD-001", intent_category="forwarding",
                        program=_forward(IP["h4"], src_ip=IP["h1"]),
                        expected_ground_truth="SHOULD_PASS"))
    cases.append(E3Case(id="E3-FWD-002", intent_category="forwarding",
                        program=_forward(IP["h3"], src_ip=IP["h1"]),
                        expected_ground_truth="SHOULD_PASS"))

    # security (deny) -- a deny policy that correctly blocks is SHOULD_PASS
    cases.append(E3Case(id="E3-SEC-001", intent_category="security",
                        program=_deny(IP["h4"], src_ip=IP["h1"]),
                        expected_ground_truth="SHOULD_PASS"))
    cases.append(E3Case(id="E3-SEC-002", intent_category="security",
                        program=_deny(IP["h3"], src_ip=IP["h1"], proto="tcp", dport=22),
                        expected_ground_truth="SHOULD_PASS"))

    # qos within capacity -- the twin provisions a real OVS min-rate queue for
    # the requested target (see safe_intent_sdn/twin/twin_verifier.py's
    # provision_min_rate_queue), so a target at or below the fast link's 10 Mbps
    # capacity is a reservation that can genuinely be honored, background load
    # or not.
    cases.append(E3Case(id="E3-QOS-001", intent_category="qos",
                        program=_qos(IP["h4"], 8.0), min_mbps=8.0,
                        expected_ground_truth="SHOULD_PASS"))
    cases.append(E3Case(id="E3-QOS-002", intent_category="qos",
                        program=_with_forced_bg_route(_qos(IP["h4"], 5.0), IP["h2"], IP["h4"]), min_mbps=5.0,
                        background_traffic=_bg(3.0),  # reservation survives modest best-effort noise
                        expected_ground_truth="SHOULD_PASS"))

    # qos over capacity -- the requested rate exceeds what the fast link (10
    # Mbps) can ever physically deliver, so no queue configuration -- real or
    # not -- can satisfy it. Reachability holds (near-full link utilization,
    # no loss), so a reach-only twin wrongly PASSes; only the bandwidth probe
    # catches that the SLA itself is infeasible on this topology. No background
    # traffic is needed to cause this: the shortfall comes from the requested
    # target exceeding physical capacity, not from contention.
    cases.append(E3Case(id="E3-QOS-003", intent_category="qos",
                        program=_qos(IP["h4"], 12.0), min_mbps=12.0,
                        expected_ground_truth="SHOULD_FAIL"))
    cases.append(E3Case(id="E3-QOS-004", intent_category="qos",
                        program=_qos(IP["h4"], 15.0), min_mbps=15.0,
                        expected_ground_truth="SHOULD_FAIL"))
    # 13.0, not e.g. 11.0: the achievable near-line-rate on this link is ~9.3-9.4
    # Mbps (protocol overhead below the nominal 10 Mbps HTB cap), so a target of
    # 11 * DEFAULT_TOLERANCE(0.85) = 9.35 sits right at that ceiling and can pass
    # by measurement noise alone -- observed happening in practice. 13 keeps a
    # clear margin (13*0.85=11.05, safely above ~9.4) so this stays deterministic.
    cases.append(E3Case(id="E3-QOS-005", intent_category="qos",
                        program=_qos(IP["h4"], 13.0), min_mbps=13.0,
                        expected_ground_truth="SHOULD_FAIL"))

    # reroute -- avoid the slow path; reach-only check is faithful
    cases.append(E3Case(id="E3-RRT-001", intent_category="reroute",
                        program=_reroute(IP["h4"]),
                        expected_ground_truth="SHOULD_PASS"))
    cases.append(E3Case(id="E3-RRT-002", intent_category="reroute",
                        program=_reroute(IP["h3"]),
                        expected_ground_truth="SHOULD_PASS"))

    return cases


def main() -> None:
    cases = build_cases()
    # Fail closed: every program must compile to ONOS flows.
    for case in cases:
        compile_prediction(IntentPrediction(status="accepted", program=case.program))
    out = ROOT / "experiments/e3/data/cases.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(case.model_dump_json() + "\n")
    print(f"wrote {len(cases)} cases to {out}")


if __name__ == "__main__":
    main()
