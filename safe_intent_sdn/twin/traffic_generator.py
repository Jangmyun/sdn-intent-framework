"""Background traffic replay for the Digital Twin (E3, new for this repo).

The E3 experiment replays the same background load in every arm so that
congestion is present when the twin makes its decision. This keeps the fidelity
gap attributable to the twin's *check* (reach-only vs reach+bandwidth), not to
the twin lacking the production load. Only constant-rate flows are generated;
each iperf3 process is tracked so it is always torn down.

Every process is a Mininet ``host.popen`` handle: ``stop()`` terminates each
handle and then ``pkill``s any stray iperf3 per host, and the caller (TwinVerifier)
additionally runs ``mn -c`` in its ``finally`` block, so a failed run cannot leave
iperf3 or interfaces behind for the next case.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field


@dataclass
class TrafficHandles:
    """Live background-traffic processes to be torn down after a case."""

    procs: list = field(default_factory=list)          # list[Popen]
    hosts: set[str] = field(default_factory=set)       # host names touched
    _net: object = None

    def stop(self) -> None:
        for proc in self.procs:
            try:
                proc.terminate()
            except Exception:
                pass
        # Force-kill anything that ignored SIGTERM, per host we started on.
        if self._net is not None:
            for host_name in self.hosts:
                try:
                    self._net.get(host_name).cmd("pkill -9 iperf3 2>/dev/null")
                except Exception:
                    pass
        self.procs.clear()


def start_background_traffic(net, flows: list[dict], *, base_port: int = 5301) -> TrafficHandles:
    """Start constant-rate iperf3 flows described by ``flows``.

    Each flow dict: ``{"src": "h2", "dst": "h3", "dst_ip": "10.0.0.3",
    "mbps": 6, "proto": "udp"|"tcp", "duration": <sec>}``. UDP is preferred for
    background load because it offers a fixed offered rate regardless of loss,
    producing stable congestion on the shared bottleneck.
    """
    handles = TrafficHandles(_net=net)
    for offset, flow in enumerate(flows):
        src = net.get(flow["src"])
        dst = net.get(flow["dst"])
        port = base_port + offset
        proto = flow.get("proto", "udp")
        udp_flag = "-u" if proto == "udp" else ""
        mbps = flow["mbps"]
        duration = int(flow.get("duration", 30))

        server = dst.popen(
            ["iperf3", "-s", "-p", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        handles.procs.append(server)
        handles.hosts.update({flow["src"], flow["dst"]})

    # Give servers a moment to bind before clients connect.
    time.sleep(1)

    for offset, flow in enumerate(flows):
        src = net.get(flow["src"])
        port = base_port + offset
        proto = flow.get("proto", "udp")
        udp_flag = "-u" if proto == "udp" else ""
        mbps = flow["mbps"]
        duration = int(flow.get("duration", 30))
        client = src.popen(
            f"iperf3 -c {flow['dst_ip']} -p {port} {udp_flag} -b {mbps}M "
            f"-t {duration} >/dev/null 2>&1",
            shell=True,
        )
        handles.procs.append(client)

    # Let the offered load ramp up before the caller measures the intent flow.
    time.sleep(1)
    return handles
