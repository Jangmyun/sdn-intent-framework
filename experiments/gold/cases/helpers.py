"""Shared constructors for the GOLD-350 candidate dataset.

Fixed topology (normative; also documented in ANNOTATION_GUIDELINE.md):

    h1 (10.0.0.1) -- s1 port 3        h3 (10.0.0.3) -- s4 port 3
    h2 (10.0.0.2) -- s1 port 4        h4 (10.0.0.4) -- s4 port 4

    s1 port 1 -> s2, port 2 -> s3, port 9 -> firewall middlebox
    s2 port 1 -> s1, port 2 -> s4    (IDS / DPI / LB service node)
    s3 port 1 -> s1, port 2 -> s4    (monitor / logging path)
    s4 port 1 -> s2, port 2 -> s3

The default inter-host path uses s2 (s1 <-> s2 <-> s4). These conventions
match the E1 SFC/Reroute extension golds in
``experiments/e1/data/project_authored_sfc_reroute.jsonl``.
"""
from __future__ import annotations

DEV = {n: f"of:{n:016d}" for n in (1, 2, 3, 4)}
IP = {"h1": "10.0.0.1", "h2": "10.0.0.2", "h3": "10.0.0.3", "h4": "10.0.0.4"}
HOST_OF_IP = {v: k for k, v in IP.items()}
HOST_SWITCH = {"h1": 1, "h2": 1, "h3": 4, "h4": 4}
PORT_TO = {
    (1, "s2"): "1", (1, "s3"): "2", (1, "h1"): "3", (1, "h2"): "4", (1, "fw"): "9",
    (2, "s1"): "1", (2, "s4"): "2",
    (3, "s1"): "1", (3, "s4"): "2",
    (4, "s2"): "1", (4, "s3"): "2", (4, "h3"): "3", (4, "h4"): "4",
}


def host_of(endpoint: str) -> str:
    """Map 'h1' or '10.0.0.1' to the canonical host name."""
    return endpoint if endpoint.startswith("h") else HOST_OF_IP[endpoint]


def toward(device: int, endpoint: str) -> str:
    """Egress port on `device` toward `endpoint`, using the default s2 spine."""
    host = host_of(endpoint)
    if (device, host) in PORT_TO:
        return PORT_TO[(device, host)]
    if device in (1, 4):
        return PORT_TO[(device, "s2")]
    target = "s1" if HOST_SWITCH[host] == 1 else "s4"
    return PORT_TO[(device, target)]


def ep(value: str | None) -> dict | None:
    if value is None:
        return None
    if value.startswith("h"):
        return {"host": value, "ip": None}
    return {"host": None, "ip": value}


def sel(src=None, dst=None, eth=None, proto=None, sport=None, dport=None, inport=None) -> dict:
    return {
        "source": ep(src), "destination": ep(dst), "eth_type": eth, "protocol": proto,
        "source_port": sport, "destination_port": dport, "ingress_port": inport,
    }


def enf(device: int | None = None, port: str | None = None, vlan: int | None = None) -> dict | None:
    if device is None and port is None and vlan is None:
        return None
    return {"device": DEV[device] if device else None, "egress_port": port, "set_vlan_id": vlan}


def qc(bw: float | None = None, lat: float | None = None, queue: int | None = None) -> dict:
    return {"min_bandwidth_mbps": bw, "max_latency_ms": lat, "queue": queue}


def rule(itype: str, action: str, selector: dict, qos: dict | None = None,
         enforcement: dict | None = None, sfc_role: str | None = None) -> dict:
    out = {"intent_type": itype, "action": action, "selector": selector,
           "qos": qos, "enforcement": enforcement}
    if sfc_role is not None:
        out["sfc_role"] = sfc_role
    return out


def accept(rules: list[dict], chain: list[str] | None = None) -> dict:
    program: dict = {"rules": rules}
    if chain is not None:
        program["sfc_chain"] = chain
    return {"status": "accepted", "program": program, "rejection": None}


def reject(reason: str) -> dict:
    return {"status": "rejected", "program": None, "rejection": {"reason": reason}}


def fwd(src=None, dst=None, eth=None, proto=None, sport=None, dport=None, inport=None,
        device=None, port=None) -> dict:
    return accept([rule("forwarding", "forward",
                        sel(src, dst, eth, proto, sport, dport, inport),
                        enforcement=enf(device, port))])


def deny(src=None, dst=None, eth=None, proto=None, sport=None, dport=None, inport=None,
         device=None) -> dict:
    return accept([rule("security", "deny",
                        sel(src, dst, eth, proto, sport, dport, inport),
                        enforcement=enf(device))])


def allow(src=None, dst=None, eth=None, proto=None, sport=None, dport=None,
          device=None) -> dict:
    return accept([rule("security", "allow",
                        sel(src, dst, eth, proto, sport, dport),
                        enforcement=enf(device))])


def qos_case(src=None, dst=None, eth=None, proto=None, dport=None,
             bw=None, lat=None, queue=None, device=None) -> dict:
    return accept([rule("qos", "prioritize", sel(src, dst, eth, proto, dport=dport),
                        qos=qc(bw, lat, queue), enforcement=enf(device))])


def sfc_fw(src, dst, eth=None, proto=None, dport=None) -> dict:
    """Single-switch firewall bypass at s1 port 9 (two rules, chain s1:9)."""
    ingress = rule("sfc", "forward", sel(src, dst, eth, proto, dport=dport),
                   enforcement=enf(1, PORT_TO[(1, "fw")]), sfc_role="ingress")
    egress = rule("sfc", "forward", sel(dst=dst, inport=9),
                  enforcement=enf(1, toward(1, dst)), sfc_role="egress")
    return accept([ingress, egress], chain=[DEV[1] + ":9"])


def sfc_via(src, dst, waypoint: int, eth=None, proto=None, dport=None) -> dict:
    """Chain through a single service switch (s2 or s3): ingress + egress rules."""
    src_dev = HOST_SWITCH[host_of(src)]
    wp_name = f"s{waypoint}"
    ingress = rule("sfc", "forward", sel(src, dst, eth, proto, dport=dport),
                   enforcement=enf(src_dev, PORT_TO[(src_dev, wp_name)]), sfc_role="ingress")
    dst_side = "s1" if HOST_SWITCH[host_of(dst)] == 1 else "s4"
    egress = rule("sfc", "forward", sel(src, dst, eth, proto, dport=dport),
                  enforcement=enf(waypoint, PORT_TO[(waypoint, dst_side)]), sfc_role="egress")
    return accept([ingress, egress], chain=[DEV[waypoint]])


def sfc_two(src, dst, eth=None, proto=None, dport=None) -> dict:
    """Two-waypoint chain s1 -> s2 -> s4 for src on s1, dst on s4."""
    ingress = rule("sfc", "forward", sel(src, dst, eth, proto, dport=dport),
                   enforcement=enf(1, PORT_TO[(1, "s2")]), sfc_role="ingress")
    transit = rule("sfc", "forward", sel(src, dst, eth, proto, dport=dport),
                   enforcement=enf(2, PORT_TO[(2, "s4")]), sfc_role="transit")
    egress = rule("sfc", "forward", sel(src, dst, eth, proto, dport=dport),
                  enforcement=enf(4, PORT_TO[(4, host_of(dst))]), sfc_role="egress")
    return accept([ingress, transit, egress], chain=[DEV[2], DEV[4]])


def sfc_fw_then(src, dst, waypoint: int, eth=None, proto=None, dport=None) -> dict:
    """Firewall at s1:9 followed by a service switch (B10 pattern)."""
    ingress = rule("sfc", "forward", sel(src, dst, eth, proto, dport=dport),
                   enforcement=enf(1, PORT_TO[(1, "fw")]), sfc_role="ingress")
    transit = rule("sfc", "forward", sel(dst=dst, inport=9),
                   enforcement=enf(1, PORT_TO[(1, f"s{waypoint}")]), sfc_role="transit")
    dst_side = "s1" if HOST_SWITCH[host_of(dst)] == 1 else "s4"
    egress = rule("sfc", "forward", sel(src, dst, eth, proto, dport=dport),
                  enforcement=enf(waypoint, PORT_TO[(waypoint, dst_side)]), sfc_role="egress")
    return accept([ingress, transit, egress], chain=[DEV[1] + ":9", DEV[waypoint]])


def reroute(device: int, port: str, src=None, dst=None, eth=None, proto=None,
            dport=None, inport=None) -> dict:
    return accept([rule("reroute", "forward", sel(src, dst, eth, proto, dport=dport, inport=inport),
                        enforcement=enf(device, port))])


def case(cid: str, category: str, variation: str, instruction: str, expected: dict) -> dict:
    return {
        "id": cid, "cohort": "project_authored", "category": category,
        "variation": variation, "instruction": instruction, "expected": expected,
        "provenance": {"source_row": None, "repository": "local:sdn-intent-framework",
                       "commit_sha": "WORKTREE", "csv_sha256": None},
    }


def number(prefix: str, category: str, entries: list[tuple[str, str, dict]]) -> list[dict]:
    return [case(f"{prefix}-{i:03d}", category, variation, instruction, expected)
            for i, (variation, instruction, expected) in enumerate(entries, start=1)]
