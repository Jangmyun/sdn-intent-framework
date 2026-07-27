"""
stage4_twin/traffic_generator.py — 배경 트래픽 생성기

LiveNetworkSession이 살아있는 동안 계속 도는 iperf3 기반 백그라운드 부하를
Mininet 호스트에서 기동/정리한다.

twin_verifier.py의 `_iperf_check()`는 "1회 측정 후 종료"(foreground, blocking)가
목적이라 이것과 다르다 — 여기서는 세션 종료까지 지속되는 백그라운드 부하가 필요하므로
별도 모듈로 분리했다.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional

_IPERF3_SERVER_PORT_BASE = 5201  # flow마다 겹치지 않도록 인덱스만큼 오프셋


@dataclass
class TrafficFlowHandle:
    """실행 중인 트래픽 flow 하나의 정리(cleanup)용 핸들."""

    flow_id: str
    src_host: str
    dst_host: str
    port: int
    server_pid: Optional[str] = None
    client_pid: Optional[str] = None


def _valid_host_name(name: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9_-]+$", name or ""))


def _start_bg(node, cmd: str) -> Optional[str]:
    """node에서 cmd를 백그라운드로 실행하고 PID를 반환한다 (실패 시 None).

    Mininet host.cmd()로 그냥 '... &'만 실행하면 PID를 못 잃어 나중에
    확실히 kill할 수 없으므로 '& echo $!'로 PID를 받아온다.
    """
    out = node.cmd(f"{cmd} > /dev/null 2>&1 & echo $!")
    m = re.search(r"(\d+)", out)
    return m.group(1) if m else None


def _kill(node, pid: Optional[str]) -> None:
    if pid:
        node.cmd(f"kill -9 {pid} 2>/dev/null")


def _iperf_t_flag(duration_sec: Optional[float]) -> str:
    """duration_sec이 None(무기한)이면 iperf3 -t 0(무제한), 아니면 그 값(초)."""
    return "0" if duration_sec is None else str(int(duration_sec))


def _build_client_cmd(
    dst_ip: str,
    port: int,
    proto: str,
    pattern: str,
    flow: dict,
    duration_sec: Optional[float],
) -> Optional[str]:
    """패턴별 클라이언트 실행 커맨드 문자열을 만든다. 지원하지 않는 패턴이면 None."""
    udp_flag = "-u " if proto == "udp" else ""

    if pattern == "constant":
        target_mbps = flow.get("target_mbps", 1)
        t_flag = _iperf_t_flag(duration_sec)
        return f"iperf3 -c {dst_ip} -p {port} {udp_flag}-b {target_mbps}M -t {t_flag}"

    if pattern == "bursty":
        target_mbps = flow.get("target_mbps", 1)
        on_sec = int(flow.get("on_sec", 10))
        off_sec = int(flow.get("off_sec", 5))
        loop = (
            f"while true; do "
            f"iperf3 -c {dst_ip} -p {port} {udp_flag}-b {target_mbps}M -t {on_sec}; "
            f"sleep {off_sec}; "
            f"done"
        )
        return _wrap_loop(loop, duration_sec)

    if pattern == "ramp":
        start_mbps = float(flow.get("start_mbps", 0))
        end_mbps = float(flow.get("end_mbps", 10))
        ramp_duration = float(flow.get("ramp_duration_sec", 60))
        step_sec = float(flow.get("step_sec", 5))
        steps = max(1, int(ramp_duration / step_sec))
        stages = []
        for i in range(steps):
            frac = i / (steps - 1) if steps > 1 else 1.0
            mbps = start_mbps + (end_mbps - start_mbps) * frac
            stages.append(
                f"iperf3 -c {dst_ip} -p {port} {udp_flag}-b {mbps:.2f}M -t {step_sec:.0f}"
            )
        # ramp 완료 후에는 end_mbps로 무기한 유지 (세션 종료 시 stop_traffic_preset이 정리)
        tail = f"while true; do iperf3 -c {dst_ip} -p {port} {udp_flag}-b {end_mbps:.2f}M -t {step_sec:.0f}; done"
        loop = "; ".join(stages) + "; " + tail
        return _wrap_loop(loop, duration_sec)

    return None


def _wrap_loop(loop: str, duration_sec: Optional[float]) -> str:
    """무기한 셸 루프를 bash -c로 감싼다. duration_sec이 있으면 timeout으로 자동 종료."""
    if duration_sec is not None:
        return f"timeout {int(duration_sec)}s bash -c '{loop}'"
    return f"bash -c '{loop}'"


def start_traffic_preset(net, preset: dict) -> list[TrafficFlowHandle]:
    """
    preset["flows"] 각각에 대해:
      1. dst_host에서 iperf3 서버를 백그라운드로 기동
      2. start_offset_sec만큼 대기 후 src_host에서 패턴에 맞는 클라이언트를 기동
      3. TrafficFlowHandle 리스트 반환 (stop_traffic_preset 정리용)

    호스트 이름이 net에 없거나 유효하지 않은 flow는 건너뛴다.
    """
    handles: list[TrafficFlowHandle] = []

    for idx, flow in enumerate(preset.get("flows", [])):
        src_name = flow.get("src", "")
        dst_name = flow.get("dst", "")
        if not (_valid_host_name(src_name) and _valid_host_name(dst_name)):
            continue

        try:
            src_node = net.get(src_name)
            dst_node = net.get(dst_name)
        except Exception:
            continue
        if src_node is None or dst_node is None:
            continue

        port = _IPERF3_SERVER_PORT_BASE + idx
        proto = flow.get("proto", "tcp")
        pattern = flow.get("pattern", "constant")
        start_offset = float(flow.get("start_offset_sec", 0) or 0)
        duration_sec = flow.get("duration_sec")

        dst_node.cmd(f"pkill -9 -f 'iperf3 -s -p {port}' 2>/dev/null")
        server_pid = _start_bg(dst_node, f"iperf3 -s -p {port}")
        time.sleep(0.3)  # 서버가 listen 시작할 시간

        if start_offset > 0:
            time.sleep(start_offset)

        client_cmd = _build_client_cmd(dst_node.IP(), port, proto, pattern, flow, duration_sec)
        client_pid = _start_bg(src_node, client_cmd) if client_cmd else None

        handles.append(
            TrafficFlowHandle(
                flow_id=flow.get("id", f"f{idx}"),
                src_host=src_name,
                dst_host=dst_name,
                port=port,
                server_pid=server_pid,
                client_pid=client_pid,
            )
        )

    return handles


def stop_traffic_preset(net, handles: list[TrafficFlowHandle]) -> None:
    """각 flow의 src/dst 호스트에서 클라이언트/서버 프로세스를 정리한다.

    PID kill과 포트 기준 pkill을 함께 사용한다 — bursty/ramp 패턴은
    bash 루프 안에서 iperf3 자식 프로세스를 반복 기동하므로 루프 PID만
    죽여선 이미 떠 있는 iperf3가 잔류할 수 있기 때문이다.
    """
    for handle in handles:
        src_node = dst_node = None
        try:
            src_node = net.get(handle.src_host)
        except Exception:
            pass
        try:
            dst_node = net.get(handle.dst_host)
        except Exception:
            pass

        if src_node is not None:
            _kill(src_node, handle.client_pid)
            src_node.cmd(f"pkill -9 -f 'iperf3 -c .* -p {handle.port} ' 2>/dev/null")
        if dst_node is not None:
            _kill(dst_node, handle.server_pid)
            dst_node.cmd(f"pkill -9 -f 'iperf3 -s -p {handle.port}' 2>/dev/null")
