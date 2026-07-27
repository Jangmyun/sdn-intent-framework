"""
stage4_twin/network_monitor.py — 링크별 처리량/손실/큐 백로그 모니터링 수집기

세 지표(처리량/드롭/백로그) 모두 tc qdisc 카운터 하나에서 뽑는다
(LIVE_NETWORK_PRESET_PLAN.md 6장).

처음엔 계획대로 처리량을 onos_client.port_statistics()로 재려 했으나, 실측 결과
ONOS의 포트 통계 갱신 주기가 우리 폴링 주기(수초)보다 느려 값이 몇 초씩 stale하다가
한꺼번에 튀는 현상이 나왔다(순간 utilization 180%+ 등 물리적으로 불가능한 값).
tc는 커널의 실시간 카운터를 직접 읽으므로 이 지연이 없고, drop/backlog도 같은
명령 한 번으로 같이 얻을 수 있어 소스를 tc 하나로 통일했다.

ping은 쓰지 않는다 — end-to-end 경로 전체를 뭉뚱그려 어느 링크가 병목인지
특정 못 하기 때문. 단, backlog는 엄밀한 RTT가 아니라 "드롭률 + 큐 백로그 기반
지연 근사치"임에 주의.

링크→인터페이스/포트 매핑은 twin_verifier._find_mininet_port()를 그대로 재사용한다.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional

from stage4_twin.twin_verifier import _find_mininet_port

_QDISC_SENT_RE = re.compile(r"Sent (\d+) bytes")
_QDISC_DROPPED_RE = re.compile(r"dropped\s+(\d+)")
_QDISC_BACKLOG_RE = re.compile(r"backlog\s+(\d+)b")


@dataclass
class LinkSample:
    """링크 하나(source→target 방향)의 한 폴링 시점 스냅샷."""

    link_id: str
    source: str
    target: str
    bw_mbps: float
    throughput_mbps: float = 0.0
    util_pct: float = 0.0
    dropped_delta: int = 0     # 이번 폴링 간격 동안 새로 발생한 드롭 (근사)
    backlog_bytes: int = 0     # 폴링 시점의 큐 백로그 (순간값, 델타 아님)


@dataclass
class FlowSample:
    """트래픽 프리셋의 flow 하나(src→dst)에 대한 실측 대역폭 스냅샷.

    src 호스트의 (첫 번째) 인터페이스 송신 바이트 델타로 측정한다 — 같은 호스트에서
    동시에 여러 flow를 보내는 프리셋은 아직 없으므로 호스트 단위 측정으로 충분하다.
    같은 호스트가 소스인 flow가 둘 이상이면 이 값은 그 호스트의 합산 송신량이 된다.
    """

    flow_id: str
    src: str
    dst: str
    proto: str
    target_mbps: float
    actual_mbps: float = 0.0


def _read_host_sent_bytes(host_node) -> int:
    """호스트 (첫 번째) 인터페이스의 누적 송신 바이트. 실패 시 0."""
    try:
        intfs = host_node.intfList()
        if not intfs:
            return 0
        ifname = intfs[0].name
        raw = host_node.cmd(f"cat /sys/class/net/{ifname}/statistics/tx_bytes 2>/dev/null")
        return int(raw.strip() or 0)
    except Exception:
        return 0


def _read_qdisc_stats(sw_node, ifname: str) -> tuple[int, int, int]:
    """(누적 sent_bytes, 누적 dropped, 현재 backlog_bytes) — 조회 실패 시 (0, 0, 0)."""
    try:
        raw = sw_node.cmd(f"tc -s qdisc show dev {ifname} 2>/dev/null")
    except Exception:
        return 0, 0, 0
    sent_m = _QDISC_SENT_RE.search(raw)
    dropped_m = _QDISC_DROPPED_RE.search(raw)
    backlog_m = _QDISC_BACKLOG_RE.search(raw)
    sent = int(sent_m.group(1)) if sent_m else 0
    dropped = int(dropped_m.group(1)) if dropped_m else 0
    backlog = int(backlog_m.group(1)) if backlog_m else 0
    return sent, dropped, backlog


class NetworkMonitor:
    """LiveNetworkSession이 주기적으로 poll()하여 최신 링크 상태를 얻는 수집기.

    스위치-스위치 링크만 대상으로 한다 (호스트 업링크는 토폴로지 정보상
    이미 병목이 아닌 것으로 확인됨 — clos-fabric은 100Mbps 고정).
    """

    def __init__(self, net, custom_data: dict, traffic_preset: Optional[dict] = None):
        self.net = net
        self.custom_data = custom_data
        self._prev_sent: dict[str, int] = {}      # ifname → 누적 sent bytes
        self._prev_dropped: dict[str, int] = {}   # ifname → 누적 dropped
        self._prev_ts: Optional[float] = None

        sw_ids = {sw["id"] for sw in custom_data.get("switches", [])}
        self._sw_links = [
            lnk for lnk in custom_data.get("links", [])
            if lnk.get("source") in sw_ids and lnk.get("target") in sw_ids
        ]

        self._flows = (traffic_preset or {}).get("flows", [])
        self._prev_flow_bytes: dict[str, int] = {}   # flow_id → 누적 송신 바이트
        self.flow_samples: list[FlowSample] = []      # 마지막 poll()이 채움

    def poll(self) -> list[LinkSample]:
        """모든 스위치간 링크의 최신 LinkSample 목록을 반환한다."""
        now = time.monotonic()
        interval = (now - self._prev_ts) if self._prev_ts is not None else None
        self._prev_ts = now

        samples: list[LinkSample] = []
        for lnk in self._sw_links:
            sw_from, sw_to = lnk["source"], lnk["target"]
            bw = float(lnk.get("bw", 0) or 0)
            port = _find_mininet_port(self.net, sw_from, sw_to)

            throughput_mbps = 0.0
            dropped_delta = backlog = 0
            if port is not None:
                ifname = f"{sw_from}-eth{port}"
                try:
                    sw_node = self.net.get(sw_from)
                except Exception:
                    sw_node = None
                if sw_node is not None:
                    sent, total_dropped, backlog = _read_qdisc_stats(sw_node, ifname)

                    if interval:
                        prev_sent = self._prev_sent.get(ifname, sent)
                        throughput_mbps = round(max(0, sent - prev_sent) * 8 / 1e6 / interval, 3)
                    self._prev_sent[ifname] = sent

                    prev_dropped = self._prev_dropped.get(ifname, total_dropped)
                    dropped_delta = max(0, total_dropped - prev_dropped)
                    self._prev_dropped[ifname] = total_dropped

            util_pct = round(throughput_mbps / bw * 100, 1) if bw else 0.0

            samples.append(LinkSample(
                link_id=lnk.get("id", f"{sw_from}-{sw_to}"),
                source=sw_from,
                target=sw_to,
                bw_mbps=bw,
                throughput_mbps=throughput_mbps,
                util_pct=util_pct,
                dropped_delta=dropped_delta,
                backlog_bytes=backlog,
            ))

        self.flow_samples = self._poll_flows(interval)
        return samples

    def _poll_flows(self, interval: Optional[float]) -> list[FlowSample]:
        flow_samples: list[FlowSample] = []
        for flow in self._flows:
            flow_id = flow.get("id", "")
            src_name = flow.get("src", "")
            actual_mbps = 0.0
            try:
                src_node = self.net.get(src_name)
            except Exception:
                src_node = None
            if src_node is not None:
                curr = _read_host_sent_bytes(src_node)
                if interval:
                    prev = self._prev_flow_bytes.get(flow_id, curr)
                    actual_mbps = round(max(0, curr - prev) * 8 / 1e6 / interval, 3)
                self._prev_flow_bytes[flow_id] = curr
            flow_samples.append(FlowSample(
                flow_id=flow_id,
                src=src_name,
                dst=flow.get("dst", ""),
                proto=flow.get("proto", ""),
                target_mbps=float(flow.get("target_mbps", 0) or 0),
                actual_mbps=actual_mbps,
            ))
        return flow_samples
