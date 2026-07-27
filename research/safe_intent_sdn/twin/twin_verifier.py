"""Digital Twin FlowRule verification on Mininet (E3, RQ3).

Slim port of ``sdn-xai-pipeline/pipeline/stage4_twin/twin_verifier.py``. Changes
made for this repo:

  * No module-level ``config`` dependency -- ONOS connection details are passed in.
  * No web/SSE coupling (``progress_cb``) and no on-disk custom-topology load; the
    caller passes ``custom_data`` explicitly.
  * ``verify()`` takes a ``checks`` set so the same machinery serves both the
    reach-only ``twin_nobw`` arm and the reach+bandwidth ``twin_bw`` /
    ``ground_truth`` arms, plus a ``background_traffic`` list that every arm
    replays so the fidelity gap is attributable to the check logic, not to the
    twin lacking production load. See paper/experiment_protocol/e3_rationale.md.

Requires Linux + root + Mininet + a reachable ONOS controller; otherwise
``verify()`` returns ``status="skipped"``.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from .bandwidth import measure_bandwidth, meets_target

_STEERING_COOKIE = "0xdeadbeef"

# Default check set: reachability of the intent pair plus a regression pair.
REACH_ONLY: frozenset[str] = frozenset({"reach", "regression"})
REACH_AND_BANDWIDTH: frozenset[str] = frozenset({"reach", "regression", "bandwidth"})

_DEFAULT_IP_MAP = {"10.0.0.1": "h1", "10.0.0.2": "h2", "10.0.0.3": "h3", "10.0.0.4": "h4"}

# Fraction of link capacity a QoS queue may reserve, leaving the rest for
# best-effort traffic (ARP/ICMP/return path). See provision_min_rate_queue.
_MIN_RATE_HEADROOM = 0.9

# Reachability probes are retried across the gap between ONOS reporting a flow
# ADDED and OVS/`fwd` actually converging on the (possibly redirected) path.
_REACH_ATTEMPTS = 3
_REACH_RETRY_DELAY = 1.5


def _device_id_to_sw_name(device_id: str, custom_data: Optional[dict]) -> Optional[str]:
    """'of:0000000000000002' -> 's2' (via custom topology, else numeric decode)."""
    if custom_data:
        for sw in custom_data.get("switches", []):
            if f"of:{sw.get('dpid', '')}" == device_id:
                return sw["id"]
    try:
        return f"s{int(device_id.replace('of:', ''), 16)}"
    except ValueError:
        return None


def _find_host_switch(host_id: str, custom_data: Optional[dict]) -> Optional[str]:
    if not custom_data:
        return None
    sw_ids = {sw["id"] for sw in custom_data.get("switches", [])}
    for lnk in custom_data.get("links", []):
        s, t = lnk["source"], lnk["target"]
        if s == host_id and t in sw_ids:
            return t
        if t == host_id and s in sw_ids:
            return s
    return None


def _bfs_sw_path(src_sw: str, dst_sw: str, custom_data: dict) -> list[str]:
    sw_ids = {sw["id"] for sw in custom_data.get("switches", [])}
    adj: dict[str, list[str]] = {s: [] for s in sw_ids}
    for lnk in custom_data.get("links", []):
        s, t = lnk["source"], lnk["target"]
        if s in sw_ids and t in sw_ids:
            adj[s].append(t)
            adj[t].append(s)
    q: deque[list[str]] = deque([[src_sw]])
    visited = {src_sw}
    while q:
        path = q.popleft()
        if path[-1] == dst_sw:
            return path
        for nb in adj.get(path[-1], []):
            if nb not in visited:
                visited.add(nb)
                q.append(path + [nb])
    return []


def _find_mininet_port(net, sw_from: str, sw_to: str) -> Optional[int]:
    """OpenFlow port on ``sw_from`` toward ``sw_to``.

    ``TCIntf`` has no ``.port`` attribute, so prefer the ``OVSSwitch.ports``
    dict and fall back to parsing the interface name ('s1-eth2' -> 2).
    """
    sw_node = net.get(sw_from)
    for link in net.links:
        n1, n2 = link.intf1.node.name, link.intf2.node.name
        if n1 == sw_from and n2 == sw_to:
            intf = link.intf1
        elif n2 == sw_from and n1 == sw_to:
            intf = link.intf2
        else:
            continue
        if hasattr(sw_node, "ports") and intf in sw_node.ports:
            return sw_node.ports[intf]
        try:
            return int(intf.name.split("eth")[-1])
        except (ValueError, IndexError):
            pass
    return None


def _ofport_to_ifname(net, sw_name: str, ofport: str | int) -> Optional[str]:
    """Resolve an OpenFlow port number on ``sw_name`` to its Linux interface name."""
    out = net.get(sw_name).cmd(f"ovs-vsctl --bare -- --columns=name find interface ofport={ofport}").strip()
    return out or None


def provision_min_rate_queue(
    net, sw_name: str, ofport: str | int, min_rate_mbps: float, max_rate_mbps: float, queue_id: int = 0
) -> bool:
    """Configure a real OVS HTB min-rate queue on a switch port.

    A compiled QoS flow's ``QUEUE(queueId=...)`` action only has meaningful
    effect if OVS actually has that queue configured on the egress port;
    otherwise its behavior is implementation-defined -- observed in practice as
    near-total packet loss rather than a bandwidth reservation. This gives the
    "prioritize" action a real min-rate guarantee, so it can genuinely be
    checked (and can genuinely fail when the request exceeds what the queue's
    ``max_rate_mbps`` -- the physical link capacity -- can ever deliver).

    The reservation is capped at ``_MIN_RATE_HEADROOM`` of link capacity rather
    than at capacity itself. Clamping a request straight to capacity (e.g. a 15
    Mbps target on a 10 Mbps link) makes queue 0 reserve the *entire* link,
    starving everything not in that queue -- ARP, ICMP, and return traffic --
    which was observed breaking an unrelated reachability check on the very
    over-capacity cases the dataset relies on. Leaving headroom keeps
    best-effort traffic alive while still making an over-capacity target
    unreachable.

    Returns True if the port's interface could be resolved and provisioning was
    attempted.
    """
    ifname = _ofport_to_ifname(net, sw_name, ofport)
    if not ifname:
        return False
    min_bps = int(min(min_rate_mbps, max_rate_mbps * _MIN_RATE_HEADROOM) * 1_000_000)
    max_bps = int(max_rate_mbps * 1_000_000)
    net.get(sw_name).cmd(
        f"ovs-vsctl -- set port {ifname} qos=@newqos "
        f"-- --id=@newqos create qos type=linux-htb other-config:max-rate={max_bps} queues:{queue_id}=@q{queue_id} "
        f"-- --id=@q{queue_id} create queue other-config:min-rate={min_bps} other-config:max-rate={max_bps}"
    )
    return True


def clear_ovs_qos() -> None:
    """Destroy every OVS QoS/Queue record left behind by prior runs.

    ``provision_min_rate_queue`` creates rows in ovsdb's QoS and Queue tables and
    attaches them to a port. ``mn -c`` tears down the bridges and ports but does
    **not** garbage-collect those rows, so without this they accumulate across
    every case of every arm (33+ per full E3 run).

    Scoped assumption: OVS on this host is dedicated to the experiment (the same
    assumption ``mn -c`` already makes by wiping all Mininet state), so clearing
    all QoS records is safe here. Failures are ignored -- this is best-effort
    hygiene, not a check.
    """
    for table in ("qos", "queue"):
        try:
            subprocess.run(
                ["ovs-vsctl", "--all", "destroy", table],
                capture_output=True, timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            pass


@dataclass
class TwinResult:
    """Outcome of a Digital Twin verification."""

    status: str  # "passed" | "failed" | "skipped" | "error"
    reason: str = ""
    checks: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)

    def summary(self) -> str:
        label = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP", "error": "ERROR"}.get(
            self.status, self.status.upper()
        )
        return f"{label}: {self.reason}" if self.reason else label


class TwinVerifier:
    """Deploy a FlowRule to a Mininet twin and check its behavior."""

    def __init__(
        self,
        onos_url: str = "http://127.0.0.1:8181/onos/v1",
        onos_user: str = "onos",
        onos_password: str = "rocks",
        controller_ip: str = "127.0.0.1",
        controller_port: int = 6653,
    ) -> None:
        self.onos_url = onos_url
        self.onos_user = onos_user
        self.onos_password = onos_password
        self.controller_ip = controller_ip
        self.controller_port = controller_port

    def _log(self, msg: str) -> None:
        print(f"    [Twin] {msg}")

    def verify(
        self,
        flowrule: dict,
        *,
        checks: frozenset[str] = REACH_ONLY,
        min_mbps: float | None = None,
        background_traffic: list[dict] | None = None,
        custom_data: dict | None = None,
        ip_map: dict[str, str] | None = None,
    ) -> TwinResult:
        """Deploy ``flowrule`` to the twin and verify its behavior.

        Args:
            flowrule: ``{"flows": [...]}`` compiled ONOS flow payload.
            checks: which checks contribute to the verdict. ``"bandwidth"`` runs
                the iperf3 probe (omitted by the reach-only arm).
            min_mbps: required delivered rate for the bandwidth check.
            background_traffic: constant-rate flows replayed under the test (see
                traffic_generator.start_background_traffic).
            custom_data: optional ``{switches, hosts, links}`` topology; ``None``
                uses the diamond builder.
            ip_map: optional ip->host map; ``None`` uses the diamond default.

        Returns:
            TwinResult. ``evidence`` always carries ``measured_mbps`` when the
            bandwidth probe ran, so a caller can label ground truth from it.
        """
        skip_reason = self._check_platform()
        if skip_reason:
            return TwinResult(status="skipped", reason=skip_reason)

        from .onos_client import OnosClient
        from .topology import (
            build_network,
            build_network_from_custom,
            get_expected_device_ids,
            get_test_host_pairs,
        )
        from .traffic_generator import start_background_traffic

        client = OnosClient(
            base_url=self.onos_url, username=self.onos_user, password=self.onos_password
        )
        expected_ids = get_expected_device_ids(custom_data)
        primary_pair, regression_pair = get_test_host_pairs(custom_data)

        if flowrule.get("sfc_chain"):
            return TwinResult(
                status="skipped",
                reason="SFC intents cannot be verified in the twin without a waypoint device",
            )

        flows = flowrule.get("flows", [])
        intent_specs = self._extract_intent_specs(flowrule)
        if not intent_specs:
            return TwinResult(
                status="skipped",
                reason="FlowRule has no IPV4_SRC/DST criteria to target a traffic check",
            )
        action, src_ip, dst_ip, flow_proto, flow_dst_port, flow = intent_specs[0]

        ip_to_host = dict(ip_map) if ip_map else self._ip_to_host(custom_data)
        host_to_ip = {hid: ip for ip, hid in ip_to_host.items()}

        dst_host = ip_to_host.get(dst_ip or "", primary_pair[1])
        if src_ip is not None:
            src_host = ip_to_host.get(src_ip, primary_pair[0])
        else:
            src_host = next((h for h in ip_to_host.values() if h != dst_host), primary_pair[0])
        baseline_dst_ip = dst_ip or host_to_ip.get(primary_pair[1], "10.0.0.4")

        net = None
        traffic = None
        checks_result: dict = {}
        evidence: dict = {}

        try:
            self._log("(1) waiting for ONOS controller...")
            client.wait_until_ready(timeout=60.0)

            self._log("(2) activating ONOS OpenFlow apps...")
            for app in ("org.onosproject.openflow-base", "org.onosproject.openflow", "org.onosproject.fwd"):
                try:
                    client.activate_application(app)
                except Exception:
                    pass
            time.sleep(2)

            self._log("(3) clearing existing flows...")
            client.clear_app_flows()
            time.sleep(1)

            self._log("(4) cleaning stale Mininet interfaces...")
            subprocess.run(["mn", "-c"], capture_output=True, timeout=15)
            clear_ovs_qos()

            if custom_data:
                self._log("(4) starting Mininet (custom topology)...")
                net = build_network_from_custom(custom_data, self.controller_ip, self.controller_port)
            else:
                self._log("(4) starting Mininet (diamond topology)...")
                net = build_network(self.controller_ip, self.controller_port)
            net.start()
            client.wait_for_devices(expected_ids, timeout=90.0)
            time.sleep(3)

            # Warm up the dataplane before any measurement. The topologies build
            # with autoStaticArp=True, so hosts never emit ARP and ONOS -- which
            # places hosts from packet-ins -- cannot know where they are until
            # they send real traffic. Without this, `fwd` has no path to install
            # and the very first reachability probe intermittently reads
            # "blocked", including the pre-deployment baseline check (observed).
            #
            # Measured finding: the pingAll is what actually fixes this. ONOS
            # frequently still reports only 0-1 of 4 hosts in its host table when
            # wait_for_hosts times out, yet every reachability check passes -- so
            # host-table registration is NOT the readiness signal; priming `fwd`
            # and the OVS dataplane is. wait_for_hosts is kept anyway because it
            # returns early when registration does succeed and otherwise doubles
            # as settling time, which the clean run depended on. Do not shorten
            # its timeout without re-measuring flakiness.
            self._log("(4a) warming up host discovery (pingAll)...")
            try:
                net.pingAll(timeout="1")
            except Exception as exc:
                self._log(f"   (note) warm-up pingAll raised {exc!r}; continuing")
            client.wait_for_hosts(len(net.hosts), timeout=30.0)

            if min_mbps is not None and not custom_data:
                from .topology import DIAMOND_FAST_LINK_MBPS
                qos_device = _device_id_to_sw_name(flow.get("deviceId", ""), custom_data)
                qos_port = self._egress_port(flow)
                if qos_device and qos_port is not None:
                    self._log(f"(4c) provisioning min-rate queue: {qos_device} port {qos_port} -> {min_mbps} Mbps")
                    provision_min_rate_queue(net, qos_device, qos_port, min_mbps, DIAMOND_FAST_LINK_MBPS)

            if background_traffic:
                self._log(f"(4b) replaying {len(background_traffic)} background flow(s)...")
                traffic = start_background_traffic(net, background_traffic)

            self._log(f"(5) baseline connectivity: {src_host} -> {baseline_dst_ip}")
            baseline_ok, baseline_msg = self._ping_check(net, src_host, baseline_dst_ip, expect_reach=True)
            checks_result["baseline_connectivity"] = baseline_ok
            evidence["baseline_msg"] = baseline_msg

            self._log("(6) deploying FlowRule...")
            client.deploy_flow_rules(flowrule)
            for f in flows:
                client.wait_for_flow(
                    device_id=f.get("deviceId", "of:0000000000000001"),
                    priority=f.get("priority", 50000),
                    timeout=15.0,
                )
            # ONOS reporting a flow as ADDED confirms its own bookkeeping, not
            # that OVS has necessarily finished installing it in the dataplane
            # yet -- checking immediately raced ahead of that gap often enough
            # to produce a spurious "blocked" TCP/UDP intent_check result (a
            # live diagnostic confirmed the SYN/RST round-trip was actually
            # fine once given a moment to settle).
            time.sleep(1)

            self._verify_intents(
                net, intent_specs, ip_to_host, host_to_ip, primary_pair,
                checks=checks, min_mbps=min_mbps, custom_data=custom_data,
                checks_result=checks_result, evidence=evidence,
            )

            if "regression" in checks:
                self._verify_regression(
                    net, primary_pair, regression_pair, host_to_ip, checks_result, evidence
                )

            verdict_keys = [k for k in checks_result if not k.startswith("_")]
            all_passed = all(checks_result[k] for k in verdict_keys)
            failed = [k for k in verdict_keys if not checks_result[k]]
            return TwinResult(
                status="passed" if all_passed else "failed",
                reason="all checks passed" if all_passed else f"failed checks: {', '.join(failed)}",
                checks=checks_result,
                evidence=evidence,
            )

        except Exception as exc:
            return TwinResult(
                status="error", reason=f"Digital Twin error: {exc}",
                checks=checks_result, evidence=evidence,
            )

        finally:
            if traffic is not None:
                try:
                    traffic.stop()
                except Exception:
                    pass
            self._log("(rollback) removing deployed FlowRule...")
            try:
                # Roll back every deployed flow's priority, not just the first
                # sub-rule's: a case may bundle extra flows (e.g. E3's forced
                # background-route rule) that intent_specs[0] does not cover, and
                # those would otherwise survive in ONOS after this case ends.
                priorities = {f.get("priority") for f in flows if f.get("priority") is not None}
                if priorities:
                    for priority in priorities:
                        client.delete_flows_by_priority(priority)
                else:
                    client.clear_app_flows()
            except Exception:
                pass
            if net is not None:
                try:
                    net.stop()
                except Exception:
                    pass
            try:
                subprocess.run(["mn", "-c"], capture_output=True, timeout=15)
            except Exception:
                pass
            # mn -c does not reap the ovsdb QoS/Queue rows this case may have
            # created, so drop them here too -- otherwise they pile up for the
            # remaining cases in the run.
            clear_ovs_qos()

    # ── intent extraction / checks ──────────────────────────────────────────

    @staticmethod
    def _extract_intent_specs(flowrule: dict) -> list[tuple]:
        """Return (action, src_ip, dst_ip, proto, port, flow) per sub-rule."""
        is_compound = flowrule.get("intent_action") == "compound"
        sub_rules = flowrule.get("sub_rules", []) if is_compound else [flowrule]
        specs: list[tuple] = []
        for sr in sub_rules:
            sr_flows = sr.get("flows", [])
            sr_flow = sr_flows[0] if sr_flows else {}
            sr_action = sr.get("intent_action", "")
            if not sr_action:
                instructions = sr_flow.get("treatment", {}).get("instructions", []) if sr_flow.get("treatment") else []
                sr_action = "forward" if any(i.get("type") == "OUTPUT" for i in instructions) else "block"
            src = dst = proto = port = None
            for c in sr_flow.get("selector", {}).get("criteria", []):
                if c["type"] == "IPV4_SRC":
                    src = c.get("ip", "").split("/")[0]
                elif c["type"] == "IPV4_DST":
                    dst = c.get("ip", "").split("/")[0]
                elif c["type"] == "IP_PROTO":
                    proto = {6: "tcp", 17: "udp", 1: "icmp"}.get(c.get("protocol"))
                elif c["type"] == "TCP_DST":
                    port = c.get("tcpPort")
                elif c["type"] == "UDP_DST":
                    port = c.get("udpPort")
            if src is not None or dst is not None:
                specs.append((sr_action, src, dst, proto, port, sr_flow))
        return specs

    @staticmethod
    def _egress_port(flow: dict) -> str | int | None:
        """Return the OUTPUT instruction's port from a compiled flow dict."""
        if not flow.get("treatment"):
            return None
        for instr in flow["treatment"].get("instructions", []):
            if instr.get("type") == "OUTPUT":
                return instr.get("port")
        return None

    @staticmethod
    def _ip_to_host(custom_data: dict | None) -> dict[str, str]:
        if custom_data:
            mapping = {h["ip"]: h["id"] for h in custom_data.get("hosts", []) if h.get("ip")}
            if mapping:
                return mapping
        return dict(_DEFAULT_IP_MAP)

    def _verify_intents(
        self, net, intent_specs, ip_to_host, host_to_ip, primary_pair,
        *, checks, min_mbps, custom_data, checks_result, evidence,
    ) -> None:
        for idx, (action, src_ip, dst_ip, proto, port, flow) in enumerate(intent_specs):
            suffix = "" if len(intent_specs) == 1 else f"_{idx}"
            dst_host = ip_to_host.get(dst_ip or "", primary_pair[1])
            if src_ip is not None:
                src_host = ip_to_host.get(src_ip, primary_pair[0])
            else:
                src_host = next((h for h in ip_to_host.values() if h != dst_host), primary_pair[0])
            dst_ip_resolved = dst_ip or host_to_ip.get(primary_pair[1], "10.0.0.4")
            expect_reach = action != "block"

            steered = self._install_steering(net, action, src_ip, dst_ip, src_host, flow, custom_data)
            try:
                if proto in ("tcp", "udp") and port is not None:
                    ok, msg = self._port_check(net, src_host, dst_ip_resolved, proto, port, expect_reach)
                else:
                    ok, msg = self._ping_check(net, src_host, dst_ip_resolved, expect_reach)
                checks_result[f"intent_check{suffix}"] = ok
                evidence[f"intent_msg{suffix}"] = msg
            finally:
                self._remove_steering(net, steered)

            # Bandwidth probe: only for reachable (forward/qos/reroute) intents.
            if "bandwidth" in checks and expect_reach and min_mbps is not None:
                measured = measure_bandwidth(
                    net, src_host, dst_host, dst_ip_resolved,
                    udp=(proto == "udp"),
                )
                met = meets_target(measured, min_mbps)
                checks_result[f"bandwidth{suffix}"] = met
                evidence[f"measured_mbps{suffix}"] = measured
                evidence[f"bandwidth_target_mbps{suffix}"] = min_mbps

    def _install_steering(self, net, action, src_ip, dst_ip, src_host, flow, custom_data) -> list[str]:
        """Force a block intent's traffic through the blocked switch so the fwd
        app cannot route around it. Returns the switches steered (for cleanup)."""
        steered: list[str] = []
        if action != "block" or not custom_data or not (src_ip and dst_ip):
            return steered
        block_sw = _device_id_to_sw_name(flow.get("deviceId", ""), custom_data)
        src_sw = _find_host_switch(src_host, custom_data)
        if not (block_sw and src_sw):
            return steered
        sw_path = _bfs_sw_path(src_sw, block_sw, custom_data)
        if len(sw_path) < 2:
            return steered
        for i in range(len(sw_path) - 1):
            hop, nxt = sw_path[i], sw_path[i + 1]
            out_port = _find_mininet_port(net, hop, nxt)
            if out_port:
                net.get(hop).cmd(
                    f'ovs-ofctl add-flow {hop} '
                    f'"cookie={_STEERING_COOKIE},priority=55000,'
                    f'ip,nw_src={src_ip},nw_dst={dst_ip},actions=output:{out_port}" -O OpenFlow13'
                )
                steered.append(hop)
        if steered:
            time.sleep(1)
        return steered

    @staticmethod
    def _remove_steering(net, steered: list[str]) -> None:
        for hop in steered:
            net.get(hop).cmd(f'ovs-ofctl del-flows {hop} "cookie={_STEERING_COOKIE}/-1" -O OpenFlow13')

    def _verify_regression(
        self, net, primary_pair, regression_pair, host_to_ip, checks_result, evidence
    ) -> None:
        if regression_pair == primary_pair:
            checks_result["regression"] = True
            evidence["regression_msg"] = "skipped -- no independent host pair"
            return
        regression_dst_ip = host_to_ip.get(regression_pair[1], "10.0.0.3")
        ok, msg = self._ping_check(net, regression_pair[0], regression_dst_ip, expect_reach=True)
        checks_result["regression"] = ok
        evidence["regression_msg"] = msg

    # ── low-level probes ────────────────────────────────────────────────────

    def _ping_check(self, net, src_host: str, dst_ip: str, expect_reach: bool) -> tuple[bool, str]:
        """ICMP reachability, retried until a reply gets through or attempts run out.

        Two rules matter here:

        * "Reachable" means *at least one reply got through*, not "zero loss".
          A congested-but-alive link legitimately drops some ICMP; a bandwidth
          shortfall is the bandwidth probe's job to catch, not this check's.
        * A single 3-packet ping is retried, because deploying a rule that pins
          an egress port can redirect traffic onto a path ONOS's reactive `fwd`
          app has not populated downstream yet. That convergence gap was
          observed producing a 100%-loss "blocked" reading for a path that was
          fine moments later (the same case passed in another arm). Any single
          successful round proves reachability, so the retry loop stops at the
          first success and only a fully unreachable path exhausts it.
        """
        try:
            if not re.match(r"^[\d.]+$", dst_ip):
                return False, f"invalid IP: {dst_ip}"
            host = net.get(src_host)
            losses: list[int] = []
            for attempt in range(_REACH_ATTEMPTS):
                host.sendCmd(f"ping -c 3 -W 1 {dst_ip}")
                result = host.waitOutput()
                m = re.search(r"(\d+)% packet loss", result)
                losses.append(int(m.group(1)) if m else 100)
                if losses[-1] < 100:
                    break
                if attempt < _REACH_ATTEMPTS - 1:
                    time.sleep(_REACH_RETRY_DELAY)
            reachable = min(losses) < 100
            if reachable and len(losses) > 1:
                self._log(f"   (note) {src_host}->{dst_ip} needed {len(losses)} ping rounds to converge: {losses}% loss")
            verb = f"reachable ({min(losses)}% loss)" if reachable else "blocked"
            success = reachable if expect_reach else not reachable
            return success, f"{src_host}->{dst_ip} {verb} (expected {'reach' if expect_reach else 'block'})"
        except Exception as exc:
            return False, f"ping error: {exc}"

    def _port_check(
        self, net, src_host: str, dst_ip: str, proto: str, port: int, expect_reach: bool
    ) -> tuple[bool, str]:
        """TCP/UDP reachability via a raw socket connect from ``src_host``.

        Same two rules as ``_ping_check``: a connection is retried across the
        dataplane-convergence gap (ONOS reporting a flow ADDED does not mean OVS
        has finished installing it), and **any** successful attempt proves
        reachability -- so the loop stops at the first success and only a truly
        unreachable target exhausts it. Taking "any success" rather than the
        last attempt also gives security (block) intents the safe reading: if
        anything got through at all, the policy did not block it.
        """
        try:
            if not re.match(r"^[\d.]+$", dst_ip):
                return False, f"invalid IP: {dst_ip}"
            port = int(port)
            host = net.get(src_host)
            cmd = (
                'python3 -c "import socket,errno;'
                "s=socket.socket();s.settimeout(3);"
                f"e=s.connect_ex(('{dst_ip}',{port}));s.close();"
                "print('REACHABLE' if e==0 or e==errno.ECONNREFUSED else 'BLOCKED')\""
            )
            attempts: list[bool] = []
            for attempt in range(_REACH_ATTEMPTS):
                host.sendCmd(cmd)
                attempts.append("REACHABLE" in host.waitOutput())
                if attempts[-1]:
                    break
                if attempt < _REACH_ATTEMPTS - 1:
                    time.sleep(_REACH_RETRY_DELAY)
            reachable = any(attempts)
            if reachable and len(attempts) > 1:
                self._log(f"   (note) {src_host}->{dst_ip}:{port} needed {len(attempts)} attempts to converge")
            success = reachable if expect_reach else not reachable
            verb = "reachable" if reachable else "blocked"
            return success, f"{src_host}->{dst_ip}:{proto.upper()}/{port} {verb} (expected {'reach' if expect_reach else 'block'})"
        except Exception as exc:
            return False, f"port check error: {exc}"

    @staticmethod
    def _check_platform() -> str:
        """Return a skip reason, or "" if Linux + root + Mininet are all present."""
        if sys.platform != "linux":
            return f"platform is not Linux (got {sys.platform})"
        if os.geteuid() != 0:
            return "no root privileges (run with sudo -E)"
        try:
            subprocess.run(["mn", "--version"], capture_output=True, check=True, timeout=5)
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return "Mininet (mn) is not installed"
        return ""
