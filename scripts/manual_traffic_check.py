"""
manual_traffic_check.py — 트래픽 생성기 + 모니터링 수집기 수동 검증 스크립트

Mininet 토폴로지를 띄우고 트래픽 프리셋을 적용한 뒤, NetworkMonitor로 링크별
처리량/utilization/드롭/큐 백로그를 주기적으로 출력해 눈으로 확인한다.
(계획 문서 LIVE_NETWORK_PRESET_PLAN.md 7장 순서 3, 4)

이건 자동화된 검증기가 아니라 개발 중 눈으로 확인하는 용도다.

실행 조건: Linux + root + Mininet + ONOS 실행 중 (twin_verifier.py와 동일)

사용법:
    sudo -E python3 scripts/manual_traffic_check.py \
        --traffic-preset data/traffic_presets/clos-fabric_core-congestion.json

    sudo -E python3 scripts/manual_traffic_check.py \
        --traffic-preset data/traffic_presets/diamond_slow-path-saturation.json \
        --topology diamond --duration 60 --interval 3
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def _print_samples(samples: list) -> None:
    for s in samples:
        if s.throughput_mbps <= 0.05 and s.dropped_delta == 0 and s.backlog_bytes == 0:
            continue
        print(
            f"  {s.link_id} {s.source}→{s.target}: "
            f"{s.throughput_mbps:.2f}/{s.bw_mbps:.0f}Mbps ({s.util_pct:.0f}%) "
            f"dropped+{s.dropped_delta} backlog={s.backlog_bytes}B"
        )


def _print_flow_samples(flow_samples: list) -> None:
    for f in flow_samples:
        print(
            f"  [{f.flow_id}] {f.src}→{f.dst} ({f.proto}): "
            f"{f.actual_mbps:.2f}/{f.target_mbps:.0f}Mbps (target)"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-preset", required=True, help="트래픽 프리셋 JSON 경로")
    parser.add_argument(
        "--topology", default=None,
        help="토폴로지: 'diamond' 또는 커스텀 토폴로지 JSON 경로 (기본: data/custom_topology.json)",
    )
    parser.add_argument("--duration", type=float, default=30.0, help="관찰 시간(초)")
    parser.add_argument("--interval", type=float, default=5.0, help="모니터링 폴링 간격(초)")
    args = parser.parse_args()

    from xai_pipeline import config
    from xai_pipeline.pipeline.stage4_twin.network_monitor import NetworkMonitor
    from xai_pipeline.pipeline.stage4_twin.onos_client import OnosClient
    from xai_pipeline.pipeline.stage4_twin.topology import (
        build_network, build_network_from_custom, diamond_topology_data,
        get_expected_device_ids, suppress_htb_quantum_warning,
    )
    from xai_pipeline.pipeline.stage4_twin.traffic_generator import start_traffic_preset, stop_traffic_preset
    from xai_pipeline.pipeline.stage4_twin.twin_verifier import TwinVerifier

    skip_reason = TwinVerifier._check_platform()
    if skip_reason:
        print(f"실행 조건 미충족: {skip_reason}", file=sys.stderr)
        return 1

    preset_path = Path(args.traffic_preset)
    preset = json.loads(preset_path.read_text(encoding="utf-8"))
    print(f"[preset] {preset.get('label', preset.get('id'))} — flow {len(preset.get('flows', []))}개")

    topology_arg = args.topology or preset.get("topology_id", "clos-fabric")
    is_diamond = topology_arg == "diamond"
    if is_diamond:
        topo_data = diamond_topology_data()
    else:
        topo_path = Path(topology_arg) if topology_arg.endswith(".json") else config.DATA_DIR / "custom_topology.json"
        topo_data = json.loads(topo_path.read_text(encoding="utf-8"))
    # build_network_from_custom()에는 diamond일 때 None을 넘겨 하드코딩된 build_network()를 타게 한다.
    custom_data = None if is_diamond else topo_data

    client = OnosClient(base_url=config.ONOS_URL, username=config.ONOS_USER, password=config.ONOS_PASSWORD)
    expected_ids = get_expected_device_ids(custom_data)

    net = None
    handles = []
    try:
        print("[1/5] ONOS 준비 대기 중...")
        client.wait_until_ready(timeout=60.0)
        for app in ["org.onosproject.openflow-base", "org.onosproject.openflow", "org.onosproject.fwd"]:
            try:
                client.activate_application(app)
            except Exception:
                pass
        client.clear_app_flows()
        time.sleep(2)

        print("[2/5] Mininet 잔존 인터페이스 정리...")
        subprocess.run(["mn", "-c"], capture_output=True, timeout=15)

        print(f"[3/5] Mininet 토폴로지 시작 ({topology_arg})...")
        with suppress_htb_quantum_warning():
            net = build_network_from_custom(custom_data) \
                if custom_data else build_network()
            net.start()
        client.wait_for_devices(expected_ids, timeout=90.0)
        time.sleep(3)

        print(f"[4/5] 트래픽 프리셋 적용: {len(preset.get('flows', []))}개 flow 기동...")
        handles = start_traffic_preset(net, preset)
        print(f"  ↳ {len(handles)}개 flow 시작됨: "
              f"{[(h.flow_id, h.src_host, h.dst_host) for h in handles]}")

        monitor = NetworkMonitor(net, topo_data, preset)
        monitor.poll()  # 첫 폴링은 baseline만 세팅 (interval 없어 처리량 0)

        print(f"[5/5] {args.duration:.0f}초간 관찰 (간격 {args.interval:.0f}초) — Ctrl+C로 조기 종료 가능")
        elapsed = 0.0
        while elapsed < args.duration:
            time.sleep(args.interval)
            elapsed += args.interval
            print(f"--- t={elapsed:.0f}s ---")
            _print_samples(monitor.poll())
            _print_flow_samples(monitor.flow_samples)

    except KeyboardInterrupt:
        print("\n중단됨 — 정리 중...")
    finally:
        if handles:
            print("트래픽 프리셋 정리 중...")
            stop_traffic_preset(net, handles)
        try:
            client.clear_app_flows()
        except Exception:
            pass
        if net is not None:
            print("Mininet 종료 중...")
            try:
                net.stop()
            except Exception:
                pass
        subprocess.run(["mn", "-c"], capture_output=True, timeout=15)

    return 0


if __name__ == "__main__":
    sys.exit(main())
