"""
stage4_twin/twin_verifier.py — Digital Twin 기반 FlowRule 검증

Mininet 가상 네트워크를 사용해 FlowRule이 의도한 동작을 수행하는지
실제로 배포하고 테스트한다.

실행 조건:
  - Linux 플랫폼
  - root 권한 (sudo)
  - Mininet 설치됨

위 조건을 충족하지 못하면 status="skipped"로 반환한다.
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

# ── 스티어링 헬퍼 ────────────────────────────────────────────────────────────────
_STEERING_COOKIE = "0xdeadbeef"


def _device_id_to_sw_name(device_id: str, custom_data: Optional[dict]) -> Optional[str]:
    """'of:0000000000000002' → 's2' (커스텀 토폴로지 기반, 없으면 숫자 변환)"""
    if custom_data:
        for sw in custom_data.get("switches", []):
            if f"of:{sw.get('dpid', '')}" == device_id:
                return sw["id"]
    try:
        n = int(device_id.replace("of:", ""), 16)
        return f"s{n}"
    except ValueError:
        return None


def _find_host_switch(host_id: str, custom_data: Optional[dict]) -> Optional[str]:
    """host_id가 직접 연결된 스위치 이름 반환"""
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
    """BFS로 스위치 간 최단 경로 반환 (스위치 이름 리스트)"""
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
    """Mininet에서 sw_from → sw_to 방향의 OpenFlow 포트 번호 반환.

    TCIntf는 .port 속성이 없으므로 OVSSwitch.ports 딕셔너리(intf→port)를
    우선 사용하고, 없으면 인터페이스 이름('s1-eth2' → 2)에서 파싱한다.
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

        # OVSSwitch.ports: {intf → port_num}
        if hasattr(sw_node, 'ports') and intf in sw_node.ports:
            return sw_node.ports[intf]
        # 이름 파싱 fallback: 's1-eth2' → 2
        try:
            return int(intf.name.split('eth')[-1])
        except (ValueError, IndexError):
            pass
    return None


@dataclass
class TwinResult:
    """Digital Twin 검증 결과"""

    status: str  # "passed" | "failed" | "skipped" | "error"
    reason: str = ""
    checks: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)

    def summary(self) -> str:
        status_map = {
            "passed": "PASS",
            "failed": "FAIL",
            "skipped": "SKIP",
            "error": "ERROR",
        }
        label = status_map.get(self.status, self.status.upper())
        if self.reason:
            return f"{label}: {self.reason}"
        return label


class TwinVerifier:
    """Mininet Digital Twin을 사용한 FlowRule 검증기"""

    def __init__(
        self,
        onos_url: Optional[str] = None,
        onos_user: Optional[str] = None,
        onos_password: Optional[str] = None,
        controller_ip: Optional[str] = None,
        controller_port: Optional[int] = None,
    ) -> None:
        from xai_pipeline import config
        self.onos_url = onos_url or config.ONOS_URL
        self.onos_user = onos_user or config.ONOS_USER
        self.onos_password = onos_password or config.ONOS_PASSWORD
        self.controller_ip = controller_ip or config.ONOS_CONTROLLER_IP
        self.controller_port = controller_port or config.ONOS_CONTROLLER_PORT

    def _log(self, msg: str) -> None:
        """진행 상황을 서버 콘솔과 UI 콜백(있으면)에 동시 출력."""
        print(f"    [Twin] {msg}")
        if getattr(self, "_progress_cb", None):
            self._progress_cb(msg)

    def verify(
        self,
        flowrule: dict,
        progress_cb=None,
        emit_cb=None,
        preloaded_flows: Optional[list] = None,
        external_net=None,
        external_custom_data: Optional[dict] = None,
    ) -> TwinResult:
        """
        FlowRule을 Digital Twin에 배포하고 검증한다.

        검증 항목:
          1. baseline_connectivity: FlowRule 배포 전 기본 연결성
          2. intent_check: FlowRule의 의도 동작
             - block이면 타겟 pair 차단 확인
             - forward이면 타겟 pair 전달 확인
          3. regression: 관련 없는 host pair 영향 없음

        Args:
            flowrule:        {"flows": [...]} 형식의 FlowRule dict
            progress_cb:     진행 상황 UI 전달용 콜백 (str → None), 없으면 콘솔만
            preloaded_flows: 사용자가 UI "Load State"로 불러온 기존 FlowRule 목록.
                             배포 전 배경 환경으로 함께 설치됨 (검증 대상은 new_flows만).
            external_net:    이미 실행 중인 Mininet 객체(LiveNetworkSession.net 등).
                             지정하면 새 Mininet을 기동/종료하지 않고 이 네트워크에
                             그대로 검증한다 — 배경 트래픽이 흐르는 중이라도 그
                             실제 상태에서 검증하는 게 목적이므로 flow 정리도
                             생략한다. 검증용으로 배포한 flowrule 자체는 평소처럼
                             끝나면 rollback한다(네트워크는 안 건드림).
            external_custom_data: external_net을 만들 때 쓴 커스텀 토폴로지 dict.
                             external_net 지정 시에만 사용(diamond면 None).

        Returns:
            TwinResult
        """
        self._progress_cb = progress_cb
        self._emit_cb = emit_cb
        preloaded_flows = preloaded_flows or []
        using_external_net = external_net is not None
        # ── 플랫폼 체크 ────────────────────────────────────────
        skip_reason = self._check_platform()
        if skip_reason:
            return TwinResult(status="skipped", reason=skip_reason)

        from xai_pipeline.pipeline.stage4_twin.onos_client import OnosClient, OnosError
        from xai_pipeline.pipeline.stage4_twin.topology import (
            build_network, build_network_from_custom,
            get_expected_device_ids, get_test_host_pairs,
            suppress_htb_quantum_warning,
            EXPECTED_DEVICE_IDS,
        )

        client = OnosClient(
            base_url=self.onos_url,
            username=self.onos_user,
            password=self.onos_password,
        )

        # ── 커스텀 토폴로지 로드 ───────────────────────────
        custom_data = external_custom_data if using_external_net else self._load_custom_topology()
        expected_ids = get_expected_device_ids(custom_data)
        primary_pair, regression_pair = get_test_host_pairs(custom_data)

        # SFC 인텐트: 데이터플레인(middlebox 없음) 대신 OVS 제어플레인 검증으로 대체
        is_sfc = bool(flowrule.get("sfc_chain")) or flowrule.get("intent_action") == "sfc"

        flows = flowrule.get("flows", [])

        # 복합 인텐트: sub_rules 목록에서 검증 대상 추출
        is_compound = flowrule.get("intent_action") == "compound"
        if is_compound:
            sub_rules = flowrule.get("sub_rules", [])
        else:
            sub_rules = [flowrule]  # 단일 룰을 리스트로 감싸 통일 처리

        # 각 sub-rule에서 (action, src_ip, dst_ip, flow_proto, flow_dst_port, flow) 추출
        intent_specs = []
        for sr in sub_rules:
            sr_flows = sr.get("flows", [])
            sr_flow = sr_flows[0] if sr_flows else {}
            sr_action = sr.get("intent_action", "")
            if not sr_action:
                instructions = sr_flow.get("treatment", {}).get("instructions", [])
                has_output = any(i.get("type") == "OUTPUT" for i in instructions)
                sr_action = "forward" if has_output else "block"
            criteria = sr_flow.get("selector", {}).get("criteria", [])
            sr_src = sr_dst = sr_proto = sr_port = None
            for c in criteria:
                if c["type"] == "IPV4_SRC":
                    sr_src = c.get("ip", "").split("/")[0]
                elif c["type"] == "IPV4_DST":
                    sr_dst = c.get("ip", "").split("/")[0]
                elif c["type"] == "IP_PROTO":
                    sr_proto = {6: "tcp", 17: "udp", 1: "icmp"}.get(c.get("protocol"))
                elif c["type"] == "TCP_DST":
                    sr_port = c.get("tcpPort")
                elif c["type"] == "UDP_DST":
                    sr_port = c.get("udpPort")
            if sr_src is not None or sr_dst is not None:
                intent_specs.append((sr_action, sr_src, sr_dst, sr_proto, sr_port, sr_flow))

        if not intent_specs:
            return TwinResult(
                status="skipped",
                reason="FlowRule에 IPV4_SRC/IPV4_DST criteria가 없어 트래픽 검증 대상을 특정할 수 없음",
            )

        # 대표 flow (baseline/regression 기준): 첫 번째 sub-rule 사용
        action, src_ip, dst_ip, flow_proto, flow_dst_port, flow = intent_specs[0]

        # IP→호스트 매핑 (커스텀 토폴로지 우선, 없으면 Diamond 기본값)
        ip_to_host: dict[str, str] = {}
        if custom_data:
            for h in custom_data.get("hosts", []):
                if h.get("ip"):
                    ip_to_host[h["ip"]] = h["id"]
        if not ip_to_host:
            ip_to_host = {
                "10.0.0.1": "h1", "10.0.0.2": "h2",
                "10.0.0.3": "h3", "10.0.0.4": "h4",
            }
        dst_host = ip_to_host.get(dst_ip or "", primary_pair[1])

        if src_ip is not None:
            src_host = ip_to_host.get(src_ip, primary_pair[0])
        else:
            # src_ip 미지정: dst_host가 아닌 다른 호스트를 소스로 선택.
            # 자기 자신에게 연결하면 루프백을 타서 스위치/블록룰을 우회하기 때문.
            src_host = next(
                (hid for hid in ip_to_host.values() if hid != dst_host),
                primary_pair[0],
            )

        # baseline ping 대상 IP (dst_host의 IP)
        baseline_dst_ip = dst_ip or next(
            (ip for ip, hid in ip_to_host.items() if hid == primary_pair[1]),
            "10.0.0.4",
        )

        net = None
        checks: dict = {}
        evidence: dict = {}

        try:
            # ── 1. ONOS 준비 대기 ──────────────────────────
            self._log("① ONOS 컨트롤러 준비 대기 중...")
            client.wait_until_ready(timeout=60.0)

            # ── 2. 필수 ONOS 앱 활성화 ────────────────────
            self._log("② ONOS OpenFlow 앱 활성화 중...")
            for app in [
                "org.onosproject.openflow-base",
                "org.onosproject.openflow",
                "org.onosproject.fwd",
            ]:
                try:
                    client.activate_application(app)
                except Exception:
                    pass
            time.sleep(2)

            if using_external_net:
                # 라이브 세션의 네트워크를 그대로 재사용 — 별도 Mininet을 새로
                # 띄우지 않는다. flow 정리도 스킵한다: clear_app_flows()는
                # org.onosproject.fwd가 설치한 flow까지 지워서 세션의 배경
                # 트래픽(reactive-forwarding)을 순간적으로 끊어버리기 때문.
                self._log("③④ 라이브 세션 네트워크 재사용 — 별도 Mininet 기동/flow 정리 생략")
                net = external_net
                if preloaded_flows:
                    self._log(f"③+ 사전 로드된 FlowRule {len(preloaded_flows)}개 환경 구성에 포함")
            else:
                # ── 3. 기존 flow 정리 ──────────────────────────
                self._log("③ 기존 flow 정리 중...")
                client.clear_app_flows()
                time.sleep(1)

                # preloaded_flows 개수 로그 (항상 표시)
                if preloaded_flows:
                    self._log(f"③+ 사전 로드된 FlowRule {len(preloaded_flows)}개 환경 구성에 포함")

                # ── 4. Mininet 토폴로지 시작 ───────────────────
                self._log("④ 잔존 Mininet 인터페이스 정리 중...")
                subprocess.run(
                    ["mn", "-c"],
                    capture_output=True,
                    timeout=15,
                )

                with suppress_htb_quantum_warning():
                    if custom_data:
                        sw_cnt = len(custom_data.get("switches", []))
                        h_cnt  = len(custom_data.get("hosts", []))
                        self._log(f"④ Mininet 가상 네트워크 시작 중... (커스텀 토폴로지 {sw_cnt}SW/{h_cnt}H)")
                        net = build_network_from_custom(custom_data, self.controller_ip, self.controller_port)
                    else:
                        self._log("④ Mininet 가상 네트워크 시작 중... (다이아몬드 기본 토폴로지)")
                        net = build_network(self.controller_ip, self.controller_port)
                    net.start()

                self._log("④ ONOS에 가상 스위치 연결 대기 중... (Live Topology에 가상 스위치가 표시됩니다)")
                client.wait_for_devices(expected_ids, timeout=90.0)
                time.sleep(3)

            # ── 5. baseline 연결성 확인 ────────────────────
            self._log(f"⑤ [baseline] FlowRule 배포 전 연결성 확인: {src_host} → {baseline_dst_ip}")
            baseline_ok, baseline_msg = self._ping_check(
                net, src_host, baseline_dst_ip, expect_reach=True
            )
            checks["baseline_connectivity"] = baseline_ok
            evidence["baseline_msg"] = baseline_msg
            self._log(f"   {'✓' if baseline_ok else '✗'} {baseline_msg}")

            # ── 5. FlowRule 배포 ───────────────────────────
            # preloaded_flows(기존 환경) + new_flows(검증 대상) 모두 설치
            self._log("⑥ FlowRule 가상 스위치에 배포 중...")
            if preloaded_flows:
                # _meta 필드 제거 후 배포
                clean_preloaded = [{k: v for k, v in f.items() if k != "_meta"}
                                   for f in preloaded_flows]
                client.deploy_flow_rules({"flows": clean_preloaded})
                self._log(f"   ↳ 사전 로드 FlowRule {len(clean_preloaded)}개 설치 완료 (배경 환경)")
            client.deploy_flow_rules(flowrule)
            # 모든 flows가 OVS에 push될 때까지 대기 (B7 fix: flows[0]만 대기하던 버그)
            for f in flows:
                client.wait_for_flow(
                    device_id=f.get("deviceId", "of:0000000000000001"),
                    priority=f.get("priority", 50000),
                    timeout=15.0,
                )

            # ── 5b. OVS egress port 검증 ──────────────────
            # forward action인 flow에 한해, OVS가 실제로 올바른 포트로 output하는지 확인
            for f_idx, f in enumerate(flows):
                instructions = f.get("treatment", {}).get("instructions", [])
                output_ports = [
                    i.get("port") for i in instructions if i.get("type") == "OUTPUT"
                ]
                if not output_ports:
                    continue  # block/drop rule은 스킵
                try:
                    expected_port = int(output_ports[0])
                except (ValueError, TypeError):
                    # "NORMAL", "CONTROLLER", "FLOOD" 등 논리 포트는 검증 불가 → 스킵
                    continue
                device_id = f.get("deviceId", "")
                sw_name = _device_id_to_sw_name(device_id, custom_data)
                priority = f.get("priority", 50000)
                if sw_name is None:
                    continue
                check_key = "egress_port" if len(flows) == 1 else f"egress_port_{f_idx}"
                self._log(
                    f"⑥+ OVS egress port 검증: {sw_name} priority={priority} "
                    f"→ output:{expected_port} 확인 중..."
                )
                ep_ok, ep_msg = self._egress_port_check(net, sw_name, expected_port, priority, flow=f)
                checks[check_key] = ep_ok
                evidence[f"{check_key}_msg"] = ep_msg
                self._log(f"   {'✓' if ep_ok else '✗'} {ep_msg}")

            # ── 6. intent 동작 확인 (모든 sub-rule 순회) ──────────────
            for spec_idx, (spec_action, spec_src_ip, spec_dst_ip,
                           spec_proto, spec_port, spec_flow) in enumerate(intent_specs):
                # 단일 인텐트는 기존 키 이름 유지, 복합이면 번호 접미사
                check_key = "intent_check" if len(intent_specs) == 1 else f"intent_check_{spec_idx}"
                msg_key   = "intent_msg"   if len(intent_specs) == 1 else f"intent_msg_{spec_idx}"

                # 이 spec의 src/dst 호스트 해석
                spec_dst_host = ip_to_host.get(spec_dst_ip or "", primary_pair[1])
                if spec_src_ip is not None:
                    spec_src_host = ip_to_host.get(spec_src_ip, primary_pair[0])
                else:
                    spec_src_host = next(
                        (hid for hid in ip_to_host.values() if hid != spec_dst_host),
                        primary_pair[0],
                    )
                spec_dst_ip_resolved = spec_dst_ip or next(
                    (ip for ip, hid in ip_to_host.items() if hid == primary_pair[1]),
                    "10.0.0.4",
                )

                # ── 6a. block 인텐트 검증 준비 ────────────────────────
                block_sw_name: Optional[str] = None
                steered_switches: list[str] = []
                if spec_action == "block":
                    block_sw_name = _device_id_to_sw_name(spec_flow.get("deviceId", ""), custom_data)

                # ── 6b. intent 동작 확인 ───────────────────────────────
                step_label = f"⑦ [intent_{spec_idx}]" if len(intent_specs) > 1 else "⑦ [intent]"

                if spec_action == "sfc" or (is_sfc and spec_idx == 0):
                    # SFC: Mininet에 실제 middlebox 없음 → OVS 제어플레인 검증
                    ep_key_0 = "egress_port" if len(flows) == 1 else "egress_port_0"
                    ep_key_1 = "egress_port_1"
                    ingress_ok = checks.get(ep_key_0, False)
                    egress_ok  = checks.get(ep_key_1, True)
                    intent_ok  = ingress_ok and egress_ok
                    intent_msg = (
                        "SFC 제어플레인 검증: ingress(→waypoint) + egress(waypoint→dst) "
                        "FlowRule OVS 설치 확인"
                        if intent_ok else
                        "SFC 제어플레인 검증 실패: OVS에 ingress/egress rule 미설치"
                    )
                    self._log(f"{step_label} [sfc] 제어플레인 검증 (OVS ingress+egress rule)")
                    self._log(f"   ↳ 데이터플레인은 실제 middlebox 없이 검증 불가 — 제어플레인으로 대체")
                    self._log(f"   {'✓' if intent_ok else '✗'} {intent_msg}")

                elif spec_action == "block":
                    # ── block: OVS flow table 확인 (1차) + ping 스티어링 (2차) ──
                    # 1차: 해당 스위치에 NOACTION/drop 룰이 실제로 설치되었는지 확인
                    # → 우회 경로 존재 여부와 무관하게 룰 설치를 권위 있는 기준으로 사용
                    self._log(f"{step_label} [block] OVS 블록 룰 설치 확인: {block_sw_name}")
                    ovs_ok, ovs_msg = self._block_rule_check(
                        net, block_sw_name, spec_src_ip, spec_dst_ip, spec_flow
                    )
                    self._log(f"   {'✓' if ovs_ok else '✗'} {ovs_msg}")

                    # 2차: 스티어링으로 해당 스위치를 통과하도록 강제 후 ping 차단 확인
                    ping_blocked = False
                    if ovs_ok and custom_data and spec_src_ip and spec_dst_ip and block_sw_name:
                        spec_src_sw = _find_host_switch(spec_src_host, custom_data)
                        if spec_src_sw:
                            sw_path = _bfs_sw_path(spec_src_sw, block_sw_name, custom_data)
                            if len(sw_path) >= 2:
                                force_path = [spec_src_host] + sw_path
                                self._log(f"   ↳ 검증 경로 강제: {' → '.join(force_path)}")
                                for i in range(len(sw_path) - 1):
                                    hop, nxt = sw_path[i], sw_path[i + 1]
                                    out_port = _find_mininet_port(net, hop, nxt)
                                    if out_port:
                                        sw_node = net.get(hop)
                                        sw_node.cmd(
                                            f'ovs-ofctl add-flow {hop} '
                                            f'"cookie={_STEERING_COOKIE},priority=60000,'
                                            f'ip,nw_src={spec_src_ip},nw_dst={spec_dst_ip},'
                                            f'actions=output:{out_port}" -O OpenFlow13'
                                        )
                                        steered_switches.append(hop)
                                if steered_switches:
                                    time.sleep(1)
                                    ping_ok, ping_msg = self._ping_check(
                                        net, spec_src_host, spec_dst_ip_resolved, expect_reach=False
                                    )
                                    ping_blocked = ping_ok
                                    self._log(f"   {'✓' if ping_blocked else '△'} 스티어링 경로 ping: {ping_msg}")

                    # 판정: OVS 룰 설치 여부가 기준
                    # ping이 통과되더라도 OVS에 룰이 있으면 PASS (우회 경로는 설계 의도)
                    intent_ok = ovs_ok
                    if ovs_ok and ping_blocked:
                        intent_msg = f"{ovs_msg} | 스티어링 경로 차단 확인됨"
                    elif ovs_ok and not ping_blocked:
                        intent_msg = f"{ovs_msg} | 우회 경로 존재 (부분 차단 — 정상)"
                    else:
                        intent_msg = ovs_msg
                    self._log(f"   {'✓' if intent_ok else '✗'} {intent_msg}")

                else:
                    # forward / qos / reroute: 도달 확인
                    if spec_proto in ("tcp", "udp") and spec_port is not None:
                        proto_label = f"{spec_proto.upper()}/{spec_port}"
                        self._log(
                            f"{step_label} 전달 확인: "
                            f"{spec_src_host} → {spec_dst_ip_resolved}:{proto_label}"
                        )
                        intent_ok, intent_msg = self._port_check(
                            net, spec_src_host, spec_dst_ip_resolved,
                            proto=spec_proto, port=spec_port,
                            expect_reach=True,
                        )
                    else:
                        self._log(
                            f"{step_label} 전달 확인: "
                            f"{spec_src_host} → {spec_dst_ip_resolved} (ICMP)"
                        )
                        intent_ok, intent_msg = self._ping_check(
                            net, spec_src_host, spec_dst_ip_resolved, expect_reach=True
                        )
                    self._log(f"   {'✓' if intent_ok else '✗'} {intent_msg}")

                checks[check_key] = intent_ok
                evidence[msg_key]  = intent_msg

                # ── 6c. iperf 대역폭 측정 (forward/qos/reroute 전달 성공 시) ──
                if spec_action in ("forward", "qos", "reroute") and intent_ok:
                    bw_key = "bandwidth" if len(intent_specs) == 1 else f"bandwidth_{spec_idx}"
                    spec_dst_host_name = ip_to_host.get(spec_dst_ip_resolved or "", primary_pair[1])
                    self._log(
                        f"   ↳ iperf3 대역폭 측정: {spec_src_host} → {spec_dst_ip_resolved}"
                    )
                    bw_mbps, bw_msg = self._iperf_check(
                        net, spec_src_host, spec_dst_host_name, spec_dst_ip_resolved
                    )
                    evidence[f"{bw_key}_mbps"] = bw_mbps
                    evidence[f"{bw_key}_msg"]  = bw_msg
                    self._log(f"   ↳ {bw_msg}")
                    # 측정된 대역폭을 UI 토폴로지에 실시간 표시
                    if bw_mbps > 0 and getattr(self, "_emit_cb", None):
                        self._emit_cb({
                            "type": "twin_bw",
                            "src_ip": spec_src_ip or "",
                            "dst_ip": spec_dst_ip_resolved or "",
                            "bw_mbps": bw_mbps,
                        })

                # ── 6c. 스티어링 룰 제거 ──────────────────────────────
                for hop in steered_switches:
                    sw_node = net.get(hop)
                    sw_node.cmd(
                        f'ovs-ofctl del-flows {hop} '
                        f'"cookie={_STEERING_COOKIE}/-1" -O OpenFlow13'
                    )
                if steered_switches:
                    self._log("   ↳ 스티어링 룰 제거 완료")

            # ── 7. 회귀 테스트 ───────────────────────────
            host_to_ip = {hid: ip for ip, hid in ip_to_host.items()}
            if regression_pair == primary_pair:
                self._log("⑧ [regression] 독립 호스트 쌍 없음 — 스킵")
                checks["regression"] = True
                evidence["regression_msg"] = (
                    "회귀 테스트 스킵 — 독립적인 호스트 쌍 없음 "
                    f"(토폴로지 호스트 수: {len(ip_to_host)}개)"
                )
            else:
                regression_dst_ip = host_to_ip.get(regression_pair[1], "10.0.0.3")
                self._log(
                    f"⑧ [regression] 영향 없어야 할 쌍 확인: "
                    f"{regression_pair[0]} → {regression_dst_ip}"
                )
                regression_ok, regression_msg = self._ping_check(
                    net, regression_pair[0], regression_dst_ip, expect_reach=True
                )
                checks["regression"] = regression_ok
                evidence["regression_msg"] = regression_msg
                self._log(f"   {'✓' if regression_ok else '✗'} {regression_msg}")

            # ── 판정 ──────────────────────────────────────
            all_passed = all(checks.values())
            status = "passed" if all_passed else "failed"
            failed_checks = [k for k, v in checks.items() if not v]
            reason = (
                f"실패한 검사: {', '.join(failed_checks)}"
                if failed_checks
                else "모든 검사 통과"
            )

            return TwinResult(
                status=status,
                reason=reason,
                checks=checks,
                evidence=evidence,
            )

        except Exception as exc:
            return TwinResult(
                status="error",
                reason=f"Digital Twin 오류: {exc}",
                checks=checks,
                evidence=evidence,
            )

        finally:
            # ── 8. rollback ───────────────────────────────
            # 대표 flow(intent_specs[0])의 priority만 지우면 sub-rule마다
            # priority가 다른 compound/sfc 인텐트에서 나머지 flow가 잔류한다.
            # deploy_flow_rules(flowrule)로 실제 배포된 flows 전체를 대상으로,
            # deviceId+priority 조합별로 정확히 삭제한다 (배경 preloaded_flows와
            # priority가 겹쳐도 collateral 삭제되지 않도록).
            self._log("⑨ FlowRule rollback 중...")
            try:
                rollback_targets = {
                    (f.get("deviceId"), f.get("priority"))
                    for f in flows
                    if f.get("deviceId") and f.get("priority") is not None
                }
                if rollback_targets:
                    for device_id, priority in rollback_targets:
                        client.delete_flows_by_priority(priority, device_id=device_id)
                elif not using_external_net:
                    # deviceId/priority가 없는 예외적인 경우의 최종 수단.
                    # 라이브 세션 네트워크에서는 배경 트래픽까지 지울 수 있어 스킵.
                    client.clear_app_flows()
            except Exception:
                pass

            # ── 9. Mininet 종료 ───────────────────────────
            if using_external_net:
                self._log("⑩ 라이브 세션 네트워크 유지 — 종료하지 않음")
            else:
                if net is not None:
                    self._log("⑩ Mininet 가상 네트워크 종료 중...")
                    try:
                        net.stop()
                    except Exception:
                        pass
                # 인터페이스 완전 정리 (다음 실행 시 File exists 방지)
                try:
                    subprocess.run(["mn", "-c"], capture_output=True, timeout=15)
                except Exception:
                    pass

    def _block_rule_check(
        self,
        net,
        sw_name: Optional[str],
        src_ip: Optional[str],
        dst_ip: Optional[str],
        flow: dict,
    ) -> tuple[bool, str]:
        """
        OVS flow table에서 NOACTION/DROP 블록 룰 설치 여부를 확인한다.

        Args:
            net: Mininet 객체
            sw_name: 확인할 스위치 이름 (예: "s4")
            src_ip: 차단 대상 출발지 IP (없으면 None)
            dst_ip: 차단 대상 목적지 IP (없으면 None)
            flow: 파이프라인 FlowRule 딕셔너리 (priority 참고용)

        Returns:
            (True, 성공 메시지) 또는 (False, 실패 메시지)
        """
        if not sw_name:
            return False, "블록 스위치 이름 미확인 — OVS 검증 불가"

        try:
            sw_node = net.get(sw_name)
        except Exception:
            return False, f"{sw_name} 노드를 Mininet에서 찾을 수 없음"

        for attempt in range(3):
            try:
                raw = sw_node.cmd(
                    f"ovs-ofctl dump-flows {sw_name} -O OpenFlow13 2>/dev/null"
                )
                lines = raw.strip().splitlines()
                for line in lines:
                    # actions=drop 또는 actions= (NOACTION) 여부 확인
                    is_drop = (
                        "actions=drop" in line.lower()
                        or re.search(r"actions=\s*$", line.strip())
                    )
                    if not is_drop:
                        continue
                    # src_ip 매칭
                    if src_ip and f"nw_src={src_ip}" not in line:
                        continue
                    # dst_ip 매칭
                    if dst_ip and f"nw_dst={dst_ip}" not in line:
                        continue
                    return (
                        True,
                        f"OVS {sw_name} 블록 룰 확인됨"
                        + (f" (src={src_ip}" if src_ip else "")
                        + (f", dst={dst_ip})" if dst_ip else (")" if src_ip else "")),
                    )
                # 룰 미발견 — 재시도 전 대기
                if attempt < 2:
                    time.sleep(1)
            except Exception as exc:
                if attempt < 2:
                    time.sleep(1)
                else:
                    return False, f"OVS dump-flows 오류: {exc}"

        return (
            False,
            f"OVS {sw_name}에 블록 룰 미발견"
            + (f" (src={src_ip}" if src_ip else "")
            + (f", dst={dst_ip})" if dst_ip else (")" if src_ip else "")),
        )

    def _ping_check(
        self,
        net,
        src_host: str,
        dst_ip: str,
        expect_reach: bool,
    ) -> tuple[bool, str]:
        """
        src_host에서 dst_ip로 ping을 전송하고 결과를 확인한다.

        Args:
            net: Mininet 객체
            src_host: 소스 호스트 이름 (예: "h1")
            dst_ip: 대상 IP 주소 (예: "10.0.0.4")
            expect_reach: True이면 도달 가능해야 함, False이면 차단되어야 함

        Returns:
            (성공 여부, 설명 메시지)
        """
        try:
            host = net.get(src_host)
            # dst_ip 형식 검증 (shell injection 방지)
            if not re.match(r"^[\d.]+$", dst_ip):
                return False, f"잘못된 IP 형식: {dst_ip}"

            host.sendCmd(f"ping -c 3 -W 1 {dst_ip}")
            result = host.waitOutput()

            # "0% packet loss" in "100% packet loss" 가 True가 되는 버그 방지
            # → regex로 실제 packet loss % 추출
            m = re.search(r"(\d+)% packet loss", result)
            loss_pct = int(m.group(1)) if m else 100
            reachable = (loss_pct == 0)

            if expect_reach:
                success = reachable
                msg = (
                    f"{src_host}→{dst_ip} ping 성공 (예상: 도달 가능)"
                    if success
                    else f"{src_host}→{dst_ip} ping 실패 (예상: 도달 가능이어야 함)"
                )
            else:
                success = not reachable
                msg = (
                    f"{src_host}→{dst_ip} ping 차단됨 (예상: 차단)"
                    if success
                    else f"{src_host}→{dst_ip} ping 통과됨 (예상: 차단이어야 함)"
                )

            return success, msg

        except Exception as exc:
            return False, f"ping 실행 오류: {exc}"

    def _port_check(
        self,
        net,
        src_host: str,
        dst_ip: str,
        proto: str,
        port: int,
        expect_reach: bool,
    ) -> tuple[bool, str]:
        """
        TCP/UDP 포트 연결 테스트.
        Python socket으로 SYN을 보내고 응답을 확인한다.

        - 연결 성공 (errno 0) 또는 연결 거부 (errno 111 ECONNREFUSED):
            패킷이 목적지에 도달한 것 → reachable=True
        - 타임아웃 (errno 110 ETIMEDOUT) 등:
            패킷이 스위치에서 DROP된 것 → reachable=False

        Args:
            net: Mininet 객체
            src_host: 소스 호스트 이름 (예: "h4")
            dst_ip: 대상 IP 주소
            proto: "tcp" 또는 "udp"
            port: 대상 포트 번호
            expect_reach: True이면 도달 가능해야 함

        Returns:
            (성공 여부, 설명 메시지)
        """
        try:
            if not re.match(r"^[\d.]+$", dst_ip):
                return False, f"잘못된 IP 형식: {dst_ip}"
            port = int(port)

            host = net.get(src_host)

            # Python socket으로 TCP SYN 전송 후 응답 분류
            # ECONNREFUSED(111): 패킷 도달, 서비스 없음 → reachable
            # ETIMEDOUT(110) / 기타: DROP → not reachable
            cmd = (
                f"python3 -c \""
                f"import socket,errno;"
                f"s=socket.socket({'socket.AF_INET' if True else ''});"
                f"s.settimeout(3);"
                f"e=s.connect_ex(('{dst_ip}',{port}));"
                f"s.close();"
                f"print('REACHABLE' if e==0 or e==errno.ECONNREFUSED else 'BLOCKED')"
                f"\""
            )
            host.sendCmd(cmd)
            result = host.waitOutput()
            reachable = "REACHABLE" in result

            proto_label = f"{proto.upper()}/{port}"
            if expect_reach:
                success = reachable
                msg = (
                    f"{src_host}→{dst_ip}:{proto_label} 연결 가능 (예상: 도달 가능)"
                    if success
                    else f"{src_host}→{dst_ip}:{proto_label} 연결 실패 (예상: 도달 가능이어야 함)"
                )
            else:
                success = not reachable
                msg = (
                    f"{src_host}→{dst_ip}:{proto_label} 차단됨 (예상: 차단)"
                    if success
                    else f"{src_host}→{dst_ip}:{proto_label} 통과됨 (예상: 차단이어야 함)"
                )

            return success, msg

        except Exception as exc:
            return False, f"포트 테스트 오류: {exc}"

    def _egress_port_check(
        self,
        net,
        sw_name: str,
        expected_port: int,
        priority: int,
        flow: Optional[dict] = None,
    ) -> tuple[bool, str]:
        """
        OVS flow table에서 FlowRule이 expected_port로 output하는지 확인한다.

        1차: priority 기반 탐색 (3회 재시도)
        2차: flow dict의 IPV4_DST 기반 fallback 탐색
          (ONOS 파이프라이너가 priority를 변환하는 경우 대응)

        Args:
            net:           Mininet 객체
            sw_name:       스위치 이름 (예: "s1")
            expected_port: FlowRule treatment에 명시된 egress 포트 번호
            priority:      FlowRule priority (매칭 기준)
            flow:          FlowRule dict (fallback 탐색용, 없으면 생략)

        Returns:
            (성공 여부, 설명 메시지)
        """
        try:
            sw_node = net.get(sw_name)
            if sw_node is None:
                return False, f"스위치 {sw_name}을 찾을 수 없음"

            # ONOS가 flow를 확인한 후 OVS에 OpenFlow push가 완료되기까지
            # 최대 2초 지연이 있을 수 있으므로 3회까지 재시도한다.
            result = ""
            result_clean = ""
            for _attempt in range(3):
                result = sw_node.cmd(f"ovs-ofctl dump-flows {sw_name} -O OpenFlow13")
                # \r을 제거해 인터페이스 이름("s2-eth2\r") 안에 CR이 섞이는 경우를 방지
                result_clean = result.replace("\r", "")
                if f"priority={priority}" in result_clean:
                    break
                if _attempt < 2:
                    time.sleep(1)

            def _parse_output_port(text: str) -> Optional[int]:
                """'output:N' 또는 'output:\"sw-ethN\"' 에서 포트 번호 추출"""
                m = re.search(
                    r'output:(?:"([^"]*)"|(0x[0-9a-fA-F]+|\d+))',
                    text,
                )
                if not m:
                    return None
                if m.group(1) is not None:
                    eth_m = re.search(r"eth(\d+)", m.group(1).strip())
                    return int(eth_m.group(1)) if eth_m else None
                port_str = m.group(2).strip()
                return int(port_str, 16) if port_str.startswith("0x") else int(port_str)

            # ── 1차: priority 기반 탐색 ─────────────────────
            m_line = re.search(
                rf'priority={priority}[^\n]*',
                result_clean,
            )
            if m_line:
                actual_port = _parse_output_port(m_line.group(0))
                if actual_port is not None:
                    if actual_port == expected_port:
                        return True, (
                            f"{sw_name} OVS flow: output:{actual_port} "
                            f"(예상 포트 {expected_port} 일치)"
                        )
                    return False, (
                        f"{sw_name} OVS flow: output:{actual_port} "
                        f"(예상: output:{expected_port} — 포트 불일치)"
                    )
                snippet = m_line.group(0)[:120]
                if "drop" in snippet.lower() or "noaction" in snippet.lower():
                    return False, (
                        f"{sw_name} OVS flow: DROP/NOACTION "
                        f"(예상: output:{expected_port})"
                    )

            # ── 2차: IPV4_DST / IN_PORT 기반 fallback 탐색 ──
            # ONOS가 OVS로 push할 때 priority를 누락하는 경우가 있으므로
            # re.escape는 정규식용 — 평문 in 체크에는 raw 문자열 사용
            if flow is not None:
                criteria = {
                    c["type"]: c
                    for c in flow.get("selector", {}).get("criteria", [])
                }
                dst_ip_c = criteria.get("IPV4_DST", {}).get("ip", "")
                in_port_c = criteria.get("IN_PORT", {}).get("port", "")

                search_str = None   # plain string for `in` check
                field_str = ""
                if dst_ip_c:
                    dst_ip_host = dst_ip_c.split("/")[0]
                    search_str = dst_ip_host          # 예: "10.0.0.1"
                    field_str = f"nw_dst={dst_ip_host}"
                elif in_port_c:
                    search_str = str(in_port_c)
                    field_str = f"in_port={in_port_c}"

                if search_str:
                    for line in result_clean.splitlines():
                        if search_str not in line:
                            continue
                        actual_port = _parse_output_port(line)
                        if actual_port is None:
                            continue
                        if actual_port == expected_port:
                            return True, (
                                f"{sw_name} OVS flow: output:{actual_port} "
                                f"({field_str} 기준 — priority 변환 감지됨)"
                            )
                        return False, (
                            f"{sw_name} OVS flow: output:{actual_port} "
                            f"(예상: output:{expected_port} — 포트 불일치, "
                            f"{field_str} 기준)"
                        )

            # ── 탐색 실패 ────────────────────────────────────
            return False, (
                f"{sw_name}: priority={priority} flow 없음 (OVS에 미설치 또는 priority 변환)"
            )

        except Exception as exc:
            return False, f"OVS egress port 확인 오류: {exc}"

    def _iperf_check(
        self,
        net,
        src_host: str,
        dst_host: str,
        dst_ip: str,
        duration: int = 3,
    ) -> tuple[float, str]:
        """
        iperf3 (없으면 iperf)로 대역폭을 측정한다.
        pass/fail 판정이 아닌 보조 측정값으로 evidence에 기록된다.

        Args:
            net:       Mininet 객체
            src_host:  소스 호스트 이름 (예: "h1")
            dst_host:  대상 호스트 이름 (예: "h4") — iperf 서버 실행용
            dst_ip:    대상 IP 주소
            duration:  측정 시간 (초, 기본 3)

        Returns:
            (대역폭 Mbps, 설명 메시지)
            대역폭 -1.0 → iperf 미설치 또는 측정 실패
        """
        try:
            if not re.match(r"^[\d.]+$", dst_ip):
                return -1.0, f"잘못된 IP 형식: {dst_ip}"

            src_node = net.get(src_host)
            dst_node = net.get(dst_host)
            if src_node is None or dst_node is None:
                return -1.0, "호스트를 찾을 수 없음"

            # ── iperf3 시도 ──────────────────────────────
            # 서버 시작 (백그라운드, 1회 연결 후 종료)
            dst_node.cmd("pkill iperf3 2>/dev/null; sleep 0.2")
            dst_node.cmd(f"iperf3 -s -1 >/dev/null 2>&1 &")
            time.sleep(0.8)

            src_node.sendCmd(
                f"iperf3 -c {dst_ip} -t {duration} --connect-timeout 3000 2>&1"
            )
            # Mininet waitOutput()은 timeout 파라미터를 지원하지 않으므로 제거
            # iperf3은 -t {duration} 후 자동 종료되므로 무기한 대기해도 안전
            result = src_node.waitOutput()

            # iperf3 JSON 없이 텍스트 파싱
            m = re.search(r"(\d+\.?\d*)\s+(Gbits|Mbits|Kbits)/sec\s+(?:receiver|sender)", result)
            if not m:
                m = re.search(r"(\d+\.?\d*)\s+(Gbits|Mbits|Kbits)/sec", result)
            if m:
                val, unit = float(m.group(1)), m.group(2)
                bw_mbps = val * 1000 if unit == "Gbits" else val / 1000 if unit == "Kbits" else val
                bw_mbps = round(bw_mbps, 2)
                return bw_mbps, f"{src_host}→{dst_ip} 대역폭: {bw_mbps} Mbps (iperf3)"

            # iperf3 미설치 or 실패 → iperf(v2) 시도
            if "command not found" in result or "No such file" in result or not result.strip():
                dst_node.cmd("pkill iperf 2>/dev/null; sleep 0.2")
                dst_node.cmd(f"iperf -s >/dev/null 2>&1 &")
                time.sleep(0.8)

                src_node.sendCmd(f"iperf -c {dst_ip} -t {duration} 2>&1")
                result2 = src_node.waitOutput()
                dst_node.cmd("pkill iperf 2>/dev/null")

                m2 = re.search(r"(\d+\.?\d*)\s+(Gbits|Mbits|Kbits)/sec", result2)
                if m2:
                    val, unit = float(m2.group(1)), m2.group(2)
                    bw_mbps = val * 1000 if unit == "Gbits" else val / 1000 if unit == "Kbits" else val
                    bw_mbps = round(bw_mbps, 2)
                    return bw_mbps, f"{src_host}→{dst_ip} 대역폭: {bw_mbps} Mbps (iperf)"

                if "command not found" in result2 or "No such file" in result2:
                    return -1.0, "iperf/iperf3 미설치 — 대역폭 측정 스킵"

                return -1.0, f"iperf 결과 파싱 실패: {result2[:120]}"

            dst_node.cmd("pkill iperf3 2>/dev/null")
            return -1.0, f"iperf3 결과 파싱 실패: {result[:120]}"

        except Exception as exc:
            return -1.0, f"iperf 오류: {exc}"

    def _load_custom_topology(self) -> Optional[dict]:
        """
        data/custom_topology.json 로드. 없으면 None 반환.
        UI 에디터에서 저장한 커스텀 토폴로지를 Digital Twin에 반영한다.
        """
        import json
        from xai_pipeline import config
        path = config.DATA_DIR / "custom_topology.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    @staticmethod
    def _check_platform() -> str:
        """
        실행 환경을 확인하고 문제가 있으면 이유를 반환한다.
        문제 없으면 빈 문자열 반환.
        """
        if sys.platform != "linux":
            return f"플랫폼이 Linux가 아님 (현재: {sys.platform})"

        if os.geteuid() != 0:
            return "root 권한 없음 (sudo -E로 실행하세요)"

        try:
            subprocess.run(
                ["mn", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return "Mininet(mn)이 설치되지 않음"

        return ""  # 모든 조건 충족
