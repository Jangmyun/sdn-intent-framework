"""Mininet topology builders for the Digital Twin (E3).

Ported from ``sdn-xai-pipeline/pipeline/stage4_twin/topology.py``. Two modes:

  1. ``build_network()``             -- hard-coded diamond (4 switches, asymmetric
                                        TCLink bandwidth: slow s1-s2-s4 path at
                                        1 Mbps, fast s1-s3-s4 path at 10 Mbps).
  2. ``build_network_from_custom()`` -- a dynamic topology from a dict shaped like
                                        {"switches": [...], "hosts": [...], "links": [...]}.

Mininet is imported inside each builder (not at module import) so this module is
importable on any platform; only calling a builder requires Mininet.

Mininet's Python package is a pure-Python, apt-installed package that lives in
the *system* Python's site-packages (``/usr/lib/python3/dist-packages``), not in
this project's uv-managed virtual environment, which is a fully isolated
interpreter build with no visibility into system site-packages. So a plain
``import mininet`` fails here even though ``mn --version`` succeeds. Since
Mininet has no compiled extensions, it is safe to import from a different-but-
compatible Python 3.x runtime once its directory is added to ``sys.path`` --
see ``_import_mininet()``.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Optional

# Matches the s1-s3-s4 TCLink bw in build_network(): the physical ceiling any
# QoS reservation on that path can ever deliver, regardless of queue config.
DIAMOND_FAST_LINK_MBPS = 10.0

EXPECTED_DEVICE_IDS: set[str] = {
    "of:0000000000000001",
    "of:0000000000000002",
    "of:0000000000000003",
    "of:0000000000000004",
}


def get_expected_device_ids(custom_data: Optional[dict] = None) -> set[str]:
    """Return the set of ONOS device ids the topology should register."""
    if custom_data is None:
        return EXPECTED_DEVICE_IDS
    return {f"of:{sw.get('dpid', '0' * 16)}" for sw in custom_data.get("switches", [])}


def get_test_host_pairs(
    custom_data: Optional[dict] = None,
) -> tuple[tuple[str, str], tuple[str, str]]:
    """Return ``(primary_pair, regression_pair)`` host names.

    ``primary_pair`` is the intent-under-test src/dst; ``regression_pair`` is an
    independent pair that must stay unaffected. For the default diamond this is
    ``(("h1","h4"), ("h2","h3"))``.
    """
    if custom_data is None:
        return ("h1", "h4"), ("h2", "h3")

    ids = [h["id"] for h in custom_data.get("hosts", [])]
    if len(ids) >= 4:
        return (ids[0], ids[-1]), (ids[1], ids[2])
    if len(ids) == 2:
        return (ids[0], ids[1]), (ids[0], ids[1])
    if len(ids) >= 1:
        return (ids[0], ids[0]), (ids[0], ids[0])
    return ("h1", "h4"), ("h2", "h3")


_SYSTEM_PYTHON3 = "/usr/bin/python3"  # matches this repo's Ubuntu-24.04-only scope


def _system_mininet_site_dir() -> Optional[str]:
    """Ask the system ``python3`` where its Mininet package lives.

    Must use an absolute path, not the bare ``python3`` name: when this runs
    under ``uv run``, PATH has ``.venv/bin`` prepended, so an unqualified
    ``python3`` would resolve back to the very (mininet-less) venv interpreter
    we are trying to work around.

    Returns the directory to add to ``sys.path`` (Mininet's parent directory),
    or ``None`` if the system interpreter doesn't have Mininet either.
    """
    try:
        result = subprocess.run(
            [_SYSTEM_PYTHON3, "-c", "import mininet, os; print(os.path.dirname(os.path.dirname(mininet.__file__)))"],
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

    # This interpreter can't see Mininet -- likely the uv-managed venv, which is
    # isolated from the system Python where `apt install mininet` put it. Ask the
    # system python3 for its location and retry once before giving up.
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
            "Mininet is not installed. Install with: "
            "sudo apt-get install mininet openvswitch-switch"
        ) from exc
    return TCLink, Mininet, OVSSwitch, RemoteController, Topo


def build_network_from_custom(
    custom_data: dict,
    controller_ip: str = "127.0.0.1",
    controller_port: int = 6653,
):
    """Build a Mininet network from a ``{switches, hosts, links}`` dict.

    Each link may carry a ``bw`` (Mbps); present bandwidth is enforced with
    ``TCLink`` so shared links can be saturated to create real congestion.
    """
    TCLink, Mininet, OVSSwitch, RemoteController, Topo = _import_mininet()

    sw_ids = {sw["id"] for sw in custom_data.get("switches", [])}
    host_ids = {h["id"] for h in custom_data.get("hosts", [])}

    class CustomTopo(Topo):
        def build(self):
            for sw in custom_data.get("switches", []):
                self.addSwitch(sw["id"], dpid=sw.get("dpid", "0" * 16), protocols="OpenFlow13")
            for h in custom_data.get("hosts", []):
                self.addHost(h["id"], ip=f"{h.get('ip', '10.0.0.1')}/24", mac=h.get("mac", ""))
            for lnk in custom_data.get("links", []):
                src, dst = lnk["source"], lnk["target"]
                if src not in sw_ids | host_ids or dst not in sw_ids | host_ids:
                    continue
                bw = lnk.get("bw")
                if bw:
                    self.addLink(src, dst, cls=TCLink, bw=bw)
                else:
                    self.addLink(src, dst)

    controller = RemoteController("c0", ip=controller_ip, port=controller_port, protocols="tcp")
    return Mininet(
        topo=CustomTopo(),
        controller=controller,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
    )


def build_network(controller_ip: str = "127.0.0.1", controller_port: int = 6653):
    """Build the default diamond topology (4 switches, 4 hosts).

    Slow path s1-s2-s4 is capped at 1 Mbps and the fast path s1-s3-s4 at 10 Mbps,
    so QoS/reroute behavior differs measurably by path.
    """
    TCLink, Mininet, OVSSwitch, RemoteController, Topo = _import_mininet()

    class DiamondTopo(Topo):
        def build(self):
            h1 = self.addHost("h1", ip="10.0.0.1/24")
            h2 = self.addHost("h2", ip="10.0.0.2/24")
            h3 = self.addHost("h3", ip="10.0.0.3/24")
            h4 = self.addHost("h4", ip="10.0.0.4/24")

            s1 = self.addSwitch("s1", dpid="0000000000000001", protocols="OpenFlow13")
            s2 = self.addSwitch("s2", dpid="0000000000000002", protocols="OpenFlow13")
            s3 = self.addSwitch("s3", dpid="0000000000000003", protocols="OpenFlow13")
            s4 = self.addSwitch("s4", dpid="0000000000000004", protocols="OpenFlow13")

            self.addLink(h1, s1, port2=3)
            self.addLink(h2, s1, port2=4)
            self.addLink(h3, s4, port2=3)
            self.addLink(h4, s4, port2=4)

            # slow path s1-s2-s4 (1 Mbps) vs fast path s1-s3-s4 (10 Mbps)
            self.addLink(s1, s2, port1=1, port2=1, cls=TCLink, bw=1)
            self.addLink(s2, s4, port1=2, port2=1, cls=TCLink, bw=1)
            self.addLink(s1, s3, port1=2, port2=1, cls=TCLink, bw=10)
            self.addLink(s3, s4, port1=2, port2=2, cls=TCLink, bw=10)

    controller = RemoteController("c0", ip=controller_ip, port=controller_port, protocols="tcp")
    return Mininet(
        topo=DiamondTopo(),
        controller=controller,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
    )
