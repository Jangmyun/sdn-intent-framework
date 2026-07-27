"""
stage4_twin/topology.py — Mininet 토폴로지 빌더

두 가지 모드를 지원한다:
  1. build_network()            — 하드코딩된 다이아몬드 4-스위치 토폴로지 (기본값)
  2. build_network_from_custom() — data/custom_topology.json 기반 동적 토폴로지

Mininet 임포트는 이 파일을 임포트하는 순간이 아닌
각 build_* 함수 내부에서만 수행한다 (Linux 환경 체크 후 호출).

Mininet은 apt로 설치된 순수 파이썬 패키지로, 시스템 Python의 site-packages
(``/usr/lib/python3/dist-packages``)에 들어간다 — 이 프로젝트의 uv 관리 venv는
완전히 격리된 인터프리터 빌드라 시스템 site-packages를 보지 못한다. 그래서
``mn --version``은 되는데 ``import mininet``은 여기서 실패한다. Mininet에는
컴파일된 확장이 없으므로, 경로만 찾아서 sys.path에 추가하면 다른(호환되는)
Python 3.x 런타임에서도 문제없이 임포트할 수 있다 — ``_import_mininet()`` 참고.
"""
from __future__ import annotations

import contextlib
import subprocess
import sys
from typing import Optional

_SYSTEM_PYTHON3 = "/usr/bin/python3"  # research/safe_intent_sdn/twin/topology.py와 동일


def _system_mininet_site_dir() -> Optional[str]:
    """시스템 python3에게 Mininet 패키지 위치를 물어본다.

    반드시 절대경로를 써야 한다 — ``uv run`` 아래에서는 PATH 맨 앞에
    ``.venv/bin``이 붙어서, qualify 안 된 ``python3``는 우리가 우회하려는
    그 (mininet 없는) venv 인터프리터로 다시 돌아가 버린다.

    sys.path에 추가할 디렉터리(Mininet의 부모 디렉터리)를 반환하거나,
    시스템 인터프리터에도 Mininet이 없으면 None을 반환한다.
    """
    try:
        result = subprocess.run(
            [_SYSTEM_PYTHON3, "-c",
             "import mininet, os; print(os.path.dirname(os.path.dirname(mininet.__file__)))"],
            capture_output=True, text=True, timeout=5, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    path = result.stdout.strip()
    return path or None


def _import_mininet():
    try:
        from mininet.link import TCLink
        from mininet.net import Mininet
        from mininet.node import OVSSwitch, RemoteController
        from mininet.topo import Topo
        return TCLink, Mininet, OVSSwitch, RemoteController, Topo
    except ImportError:
        pass

    # 이 인터프리터에서는 Mininet이 안 보인다 — uv venv일 가능성이 높다.
    # 시스템 python3에게 위치를 물어서 한 번 더 시도한다.
    system_dir = _system_mininet_site_dir()
    if system_dir and system_dir not in sys.path:
        sys.path.append(system_dir)

    try:
        from mininet.link import TCLink
        from mininet.net import Mininet
        from mininet.node import OVSSwitch, RemoteController
        from mininet.topo import Topo
    except ImportError as exc:
        raise RuntimeError(
            "Mininet이 설치되지 않았습니다. "
            "설치: sudo apt-get install mininet openvswitch-switch"
        ) from exc
    return TCLink, Mininet, OVSSwitch, RemoteController, Topo


@contextlib.contextmanager
def suppress_htb_quantum_warning():
    """
    sch_htb 'quantum of class X is big' 경고를 Mininet 로그에서 억제하는
    컨텍스트 매니저.

    원인: Mininet이 TCLink로 대역폭 제한 링크를 설정할 때 Linux TC(HTB qdisc)가
    quantum 값이 크다는 커널 경고를 발생시킨다. 이는 TC의 r2q 기본값(10)이
    높은 대역폭 설정과 맞지 않아 생기는 benign warning으로, 실제 네트워크
    동작에는 영향을 미치지 않는다.

    억제 방법: mininet.log.error를 일시적으로 패치하여 해당 메시지만 필터링.
    """
    try:
        _import_mininet()  # sys.path에 mininet 위치를 보장한 뒤 아래에서 로그 모듈을 가져온다
        import mininet.log as _mn_log
        _orig_error = _mn_log.error

        def _filtered_error(*args, **kwargs):
            msg = "".join(str(a) for a in args)
            if "quantum of class" in msg and "is big" in msg:
                return  # benign 경고 억제
            _orig_error(*args, **kwargs)

        _mn_log.error = _filtered_error
        yield
    except (ImportError, RuntimeError):
        yield  # Mininet 미설치 환경에서는 아무것도 하지 않음
    finally:
        try:
            _mn_log.error = _orig_error
        except Exception:
            pass

EXPECTED_DEVICE_IDS: set[str] = {
    "of:0000000000000001",
    "of:0000000000000002",
    "of:0000000000000003",
    "of:0000000000000004",
}


def get_expected_device_ids(custom_data: Optional[dict] = None) -> set[str]:
    """토폴로지 데이터에서 예상 ONOS device ID 집합 반환."""
    if custom_data is None:
        return EXPECTED_DEVICE_IDS
    return {
        f"of:{sw.get('dpid', '0' * 16)}"
        for sw in custom_data.get("switches", [])
    }


def diamond_topology_data() -> dict:
    """다이아몬드 토폴로지의 custom_topology.json 호환 표현.

    build_network()은 다이아몬드를 하드코딩된 Topo 서브클래스로 직접 만들지만,
    network_monitor.py 등 custom_data 형식(switches/hosts/links)을 요구하는
    코드에서 재사용하기 위해 별도로 노출한다.
    """
    return {
        "switches": [
            {"id": "s1", "dpid": "0000000000000001"},
            {"id": "s2", "dpid": "0000000000000002"},
            {"id": "s3", "dpid": "0000000000000003"},
            {"id": "s4", "dpid": "0000000000000004"},
        ],
        "hosts": [
            {"id": "h1", "ip": "10.0.0.1"},
            {"id": "h2", "ip": "10.0.0.2"},
            {"id": "h3", "ip": "10.0.0.3"},
            {"id": "h4", "ip": "10.0.0.4"},
        ],
        "links": [
            {"id": "l1", "source": "s1", "target": "s2", "bw": 1},
            {"id": "l2", "source": "s2", "target": "s4", "bw": 1},
            {"id": "l3", "source": "s1", "target": "s3", "bw": 10},
            {"id": "l4", "source": "s3", "target": "s4", "bw": 10},
        ],
    }


def get_test_host_pairs(custom_data: Optional[dict] = None) -> tuple[tuple[str, str], tuple[str, str]]:
    """
    intent_check 및 regression 테스트에 사용할 호스트 쌍 반환.

    Returns:
        (primary_pair, regression_pair)
        primary_pair:    intent 검증 대상 (src, dst)
        regression_pair: 영향 없어야 할 쌍 (src, dst)
    """
    if custom_data is None:
        return ("h1", "h4"), ("h2", "h3")

    hosts = custom_data.get("hosts", [])
    ids = [h["id"] for h in hosts]

    if len(ids) >= 4:
        return (ids[0], ids[-1]), (ids[1], ids[2])
    if len(ids) == 2:
        return (ids[0], ids[1]), (ids[0], ids[1])
    if len(ids) >= 1:
        return (ids[0], ids[0]), (ids[0], ids[0])
    return ("h1", "h4"), ("h2", "h3")


def build_network_from_custom(
    custom_data: dict,
    controller_ip: Optional[str] = None,
    controller_port: Optional[int] = None,
):
    """
    UI 에디터에서 저장한 커스텀 토폴로지 JSON → Mininet 네트워크.

    Args:
        custom_data: custom_topology.json 내용 dict
        controller_ip: ONOS 컨트롤러 IP (기본: config.ONOS_CONTROLLER_IP)
        controller_port: OpenFlow 포트 (기본: config.ONOS_CONTROLLER_PORT)

    Returns:
        Mininet 객체 (net.start() 호출 전)
    """
    from xai_pipeline import config
    controller_ip = controller_ip or config.ONOS_CONTROLLER_IP
    controller_port = controller_port or config.ONOS_CONTROLLER_PORT

    TCLink, Mininet, OVSSwitch, RemoteController, Topo = _import_mininet()

    sw_ids  = {sw["id"] for sw in custom_data.get("switches", [])}
    host_ids = {h["id"] for h in custom_data.get("hosts", [])}

    class CustomTopo(Topo):
        def build(self):
            # 스위치
            for sw in custom_data.get("switches", []):
                self.addSwitch(
                    sw["id"],
                    dpid=sw.get("dpid", "0" * 16),
                    protocols="OpenFlow13",
                )
            # 호스트
            for h in custom_data.get("hosts", []):
                self.addHost(
                    h["id"],
                    ip=f"{h.get('ip', '10.0.0.1')}/24",
                    mac=h.get("mac", ""),
                )
            # 링크 (포트 번호는 Mininet이 자동 부여)
            port_counter: dict[str, int] = {}
            for lnk in custom_data.get("links", []):
                src, dst = lnk["source"], lnk["target"]
                if src not in sw_ids | host_ids or dst not in sw_ids | host_ids:
                    continue
                bw = lnk.get("bw")
                if bw:
                    self.addLink(src, dst, cls=TCLink, bw=bw)
                else:
                    self.addLink(src, dst)

    controller = RemoteController(
        "c0", ip=controller_ip, port=controller_port, protocols="tcp"
    )
    return Mininet(
        topo=CustomTopo(),
        controller=controller,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
    )


def build_network(controller_ip: Optional[str] = None, controller_port: Optional[int] = None):
    """
    Mininet 다이아몬드 토폴로지를 생성하고 반환한다.

    Args:
        controller_ip: ONOS 컨트롤러 IP (기본: config.ONOS_CONTROLLER_IP)
        controller_port: OpenFlow 포트 (기본: config.ONOS_CONTROLLER_PORT)

    Returns:
        Mininet 객체 (net.start() 호출 전)

    Raises:
        RuntimeError: Mininet이 설치되지 않은 경우
    """
    from xai_pipeline import config
    controller_ip = controller_ip or config.ONOS_CONTROLLER_IP
    controller_port = controller_port or config.ONOS_CONTROLLER_PORT

    TCLink, Mininet, OVSSwitch, RemoteController, Topo = _import_mininet()

    class DiamondTopo(Topo):
        def build(self):
            # 호스트 추가
            h1 = self.addHost("h1", ip="10.0.0.1/24")
            h2 = self.addHost("h2", ip="10.0.0.2/24")
            h3 = self.addHost("h3", ip="10.0.0.3/24")
            h4 = self.addHost("h4", ip="10.0.0.4/24")

            # 스위치 추가 (OpenFlow 1.3)
            s1 = self.addSwitch("s1", dpid="0000000000000001", protocols="OpenFlow13")
            s2 = self.addSwitch("s2", dpid="0000000000000002", protocols="OpenFlow13")
            s3 = self.addSwitch("s3", dpid="0000000000000003", protocols="OpenFlow13")
            s4 = self.addSwitch("s4", dpid="0000000000000004", protocols="OpenFlow13")

            # 호스트-스위치 연결
            self.addLink(h1, s1, port2=3)
            self.addLink(h2, s1, port2=4)
            self.addLink(h3, s4, port2=3)
            self.addLink(h4, s4, port2=4)

            # 스위치간 연결 (저속: s1-s2-s4 / 고속: s1-s3-s4)
            self.addLink(s1, s2, port1=1, port2=1, cls=TCLink, bw=1)
            self.addLink(s2, s4, port1=2, port2=1, cls=TCLink, bw=1)
            self.addLink(s1, s3, port1=2, port2=1, cls=TCLink, bw=10)
            self.addLink(s3, s4, port1=2, port2=2, cls=TCLink, bw=10)

    controller = RemoteController(
        "c0", ip=controller_ip, port=controller_port, protocols="tcp"
    )

    return Mininet(
        topo=DiamondTopo(),
        controller=controller,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
    )
