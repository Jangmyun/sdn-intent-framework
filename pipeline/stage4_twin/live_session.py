"""
stage4_twin/live_session.py — 네트워크 프리셋 지속 세션 관리자

TwinVerifier.verify()의 "시작→검증→항상 rollback+net.stop()" 1회성 생명주기와는
완전히 분리된 별도 생명주기다: 프리셋 적용 → 계속 실행 → 명시적 stop()까지 지속.
(LIVE_NETWORK_PRESET_PLAN.md 5장)

세션은 프로세스당 단일 인스턴스만 지원한다 — 동시 다중 세션은 다루지 않는다.
start()/stop()은 모두 블로킹 호출이므로 (Mininet 기동/종료에 수십 초 소요),
호출하는 쪽(API 레이어)에서 별도 스레드/executor로 실행해야 한다.
"""
from __future__ import annotations

import subprocess
import threading
import time
from typing import Optional

from stage4_twin.network_monitor import NetworkMonitor
from stage4_twin.onos_client import OnosClient
from stage4_twin.topology import (
    build_network,
    build_network_from_custom,
    get_expected_device_ids,
    suppress_htb_quantum_warning,
)
from stage4_twin.traffic_generator import (
    TrafficFlowHandle,
    start_traffic_preset,
    stop_traffic_preset,
)

# manual_traffic_check.py로 실측 확정한 폴링 주기 (LIVE_NETWORK_PRESET_PLAN.md 8장 열린 질문)
MONITOR_POLL_INTERVAL_SEC = 5.0


class LiveNetworkSession:
    """프리셋 적용 → 계속 실행 → 명시적 종료. TwinVerifier와 별개의 생명주기."""

    def __init__(self) -> None:
        self.net = None
        self.client: Optional[OnosClient] = None
        self.monitor: Optional[NetworkMonitor] = None
        self.traffic_handles: list[TrafficFlowHandle] = []
        self.topology_id: str = ""
        self.topo_data: Optional[dict] = None
        self.traffic_preset_id: str = ""
        self.status: str = "idle"  # idle | starting | running | stopping | error
        self.error: str = ""
        self.started_at: Optional[float] = None

        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._start_stop_lock = threading.Lock()
        self._samples_lock = threading.Lock()
        self._latest_samples: list = []
        self._latest_flow_samples: list = []

    def is_active(self) -> bool:
        return self.status in ("starting", "running")

    def start(self, topology_id: str, topo_data: dict, traffic_preset: Optional[dict]) -> None:
        """토폴로지 기동 + ONOS 연결 대기 + (있으면) 배경 트래픽 시작 + 모니터링 루프 시작.

        net.stop()을 호출하지 않는다 — stop()이 명시적으로 불릴 때까지 계속 실행된다.
        블로킹 호출이며 실패 시 예외를 그대로 올린다 (status는 "error"로 남는다).
        """
        with self._start_stop_lock:
            if self.is_active():
                raise RuntimeError("이미 실행 중인 세션이 있습니다 (단일 세션만 지원)")
            self.status = "starting"
            self.error = ""

        try:
            is_diamond = topology_id == "diamond"
            custom_data = None if is_diamond else topo_data
            expected_ids = get_expected_device_ids(custom_data)

            self.client = OnosClient()
            self.client.wait_until_ready(timeout=60.0)
            for app_name in (
                "org.onosproject.openflow-base",
                "org.onosproject.openflow",
                "org.onosproject.fwd",
            ):
                try:
                    self.client.activate_application(app_name)
                except Exception:
                    pass
            self.client.clear_app_flows()
            time.sleep(2)

            subprocess.run(["mn", "-c"], capture_output=True, timeout=15)

            with suppress_htb_quantum_warning():
                self.net = (
                    build_network_from_custom(custom_data)
                    if custom_data else build_network()
                )
                self.net.start()
            self.client.wait_for_devices(expected_ids, timeout=90.0)
            time.sleep(3)

            if traffic_preset and traffic_preset.get("flows"):
                self.traffic_handles = start_traffic_preset(self.net, traffic_preset)

            self.monitor = NetworkMonitor(self.net, topo_data, traffic_preset)
            self.topology_id = topology_id
            # api.py가 세션 실행 중 Digital Twin을 이 네트워크에 그대로 검증하려면
            # 그때 썼던 topo_data(커스텀 토폴로지 dict)가 필요하다 — diamond는
            # topology.py의 하드코딩된 값을 쓰므로 None으로 남겨둔다(기존 None 의미와 동일).
            self.topo_data = None if topology_id == "diamond" else topo_data
            self.traffic_preset_id = (traffic_preset or {}).get("id", "")
            self.started_at = time.time()

            self._stop_event.clear()
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()

            self.status = "running"
        except Exception as exc:
            self.status = "error"
            self.error = str(exc)
            self._cleanup_best_effort()
            raise

    def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                samples = self.monitor.poll()
                flow_samples = self.monitor.flow_samples
                with self._samples_lock:
                    self._latest_samples = samples
                    self._latest_flow_samples = flow_samples
            except Exception:
                pass
            self._stop_event.wait(MONITOR_POLL_INTERVAL_SEC)

    def snapshot(self) -> dict:
        """현재 링크별 utilization/드롭/백로그 + flow별 실측 대역폭 스냅샷
        (모니터링 루프가 채움)."""
        with self._samples_lock:
            samples = list(self._latest_samples)
            flow_samples = list(self._latest_flow_samples)
        return {
            "status": self.status,
            "topology_id": self.topology_id,
            "traffic_preset_id": self.traffic_preset_id,
            "started_at": self.started_at,
            "error": self.error,
            "links": [
                {
                    "id": s.link_id,
                    "source": s.source,
                    "target": s.target,
                    "bw_mbps": s.bw_mbps,
                    "throughput_mbps": s.throughput_mbps,
                    "util_pct": s.util_pct,
                    "dropped_delta": s.dropped_delta,
                    "backlog_bytes": s.backlog_bytes,
                }
                for s in samples
            ],
            "flows": [
                {
                    "id": f.flow_id,
                    "src": f.src,
                    "dst": f.dst,
                    "proto": f.proto,
                    "target_mbps": f.target_mbps,
                    "actual_mbps": f.actual_mbps,
                }
                for f in flow_samples
            ],
        }

    def stop(self) -> None:
        """배경 트래픽 정리 → 모니터링 루프 중단 → net.stop() → mn -c."""
        with self._start_stop_lock:
            if self.status not in ("running", "error", "starting"):
                return
            self.status = "stopping"

        self._stop_event.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=MONITOR_POLL_INTERVAL_SEC + 5)
        self._cleanup_best_effort()

        with self._samples_lock:
            self._latest_samples = []
            self._latest_flow_samples = []
        self.topology_id = ""
        self.topo_data = None
        self.traffic_preset_id = ""
        self.started_at = None
        self.error = ""
        self.status = "idle"

    def _cleanup_best_effort(self) -> None:
        if self.traffic_handles and self.net is not None:
            try:
                stop_traffic_preset(self.net, self.traffic_handles)
            except Exception:
                pass
        self.traffic_handles = []

        if self.client is not None:
            try:
                self.client.clear_app_flows()
            except Exception:
                pass

        if self.net is not None:
            try:
                self.net.stop()
            except Exception:
                pass
        self.net = None
        self.monitor = None

        try:
            subprocess.run(["mn", "-c"], capture_output=True, timeout=15)
        except Exception:
            pass
