"""iperf3 bandwidth measurement for the Digital Twin (E3, new for this repo).

This is the probe the reach-only twin (``twin_nobw`` arm) deliberately omits and
the ``twin_bw`` / ``ground_truth`` arms use. It measures the throughput actually
delivered between two Mininet hosts under whatever background load is present, so
a QoS intent that is *reachable* but cannot meet its target rate under congestion
is detected instead of silently passing.

Uses ``iperf3 -J`` (JSON) and parses the achieved rate from the result, so it does
not depend on scraping human-readable output.
"""
from __future__ import annotations

import json
import re
import subprocess
import time

# Fraction of the target the delivered rate must reach to count as "met". iperf3
# under tc/HTB never quite hits the nominal cap and measurement is noisy, so a
# margin below 1.0 avoids labeling a barely-adequate link as a failure.
DEFAULT_TOLERANCE = 0.85

_SERVER_READY_TIMEOUT = 5.0
_CLIENT_RETRIES = 4
_CLIENT_RETRY_DELAY = 0.7


def _wait_for_server(dst, port: int, timeout: float = _SERVER_READY_TIMEOUT) -> bool:
    """Poll ``dst`` until the one-shot iperf3 server is listening on ``port``.

    Without this, the client can race the server's async ``popen()`` startup and
    fail to connect at all -- and that connection failure was previously
    indistinguishable from "measured throughput is genuinely near zero", since
    ``_parse_mbps`` silently returns 0.0 for either case.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if f":{port} " in dst.cmd(f"ss -ltn 2>/dev/null | grep ':{port} '"):
            return True
        time.sleep(0.1)
    return False


def measure_bandwidth(
    net,
    src_host: str,
    dst_host: str,
    dst_ip: str,
    *,
    duration: int = 4,
    udp: bool = False,
    port: int = 5201,
) -> float:
    """Return throughput delivered from ``src_host`` to ``dst_host`` in Mbps.

    Starts a one-shot iperf3 server on ``dst_host`` and runs an iperf3 client on
    ``src_host``. Returns ``0.0`` if the transfer genuinely fails (e.g. the path
    is blocked), which the caller treats as "target not met" -- but retries the
    client a few times first, since a raw 0.0 from a client-connection failure
    (server not ready, transient error) must not be silently conflated with a
    real zero-throughput measurement.
    """
    if not re.match(r"^[\d.]+$", dst_ip):
        raise ValueError(f"invalid IP: {dst_ip}")

    src = net.get(src_host)
    dst = net.get(dst_host)

    # One-shot server (-1): serves a single client then exits, so no lingering
    # process. Popen handle lets us force-kill on any early return.
    server = dst.popen(
        ["iperf3", "-s", "-1", "-p", str(port), "--json"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_for_server(dst, port):
            print(f"    [Twin] warning: iperf3 server on {dst_host}:{port} never came up in time")

        flags = "-u -b 0" if udp else ""
        for attempt in range(_CLIENT_RETRIES):
            raw = src.cmd(f"iperf3 -c {dst_ip} -p {port} -t {duration} {flags} -J 2>/dev/null")
            mbps, parsed = _parse_mbps(raw, udp=udp)
            if parsed:
                return mbps
            print(f"    [Twin] warning: iperf3 client {src_host}->{dst_ip}:{port} attempt {attempt + 1} produced no parseable result")
            time.sleep(_CLIENT_RETRY_DELAY)
        return 0.0
    finally:
        try:
            server.terminate()
        except Exception:
            pass
        # Belt-and-suspenders: kill any iperf3 the one-shot server left behind.
        dst.cmd("pkill -f 'iperf3 -s' 2>/dev/null")


def _parse_mbps(raw: str, *, udp: bool) -> tuple[float, bool]:
    """Extract achieved Mbps from an iperf3 ``-J`` result blob.

    Returns ``(mbps, parsed)``: ``parsed`` is False when no valid measurement
    could be extracted at all (client error, malformed JSON) -- distinct from a
    successfully parsed but genuinely-zero rate -- so the caller can retry
    instead of silently treating a broken measurement as "target not met".
    """
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return 0.0, False
    try:
        data = json.loads(raw[start : end + 1])
    except (ValueError, TypeError):
        return 0.0, False
    end_block = data.get("end", {})
    if udp:
        summary = end_block.get("sum", {})
    else:
        summary = end_block.get("sum_received") or end_block.get("sum", {})
    bits_per_second = summary.get("bits_per_second")
    if not isinstance(bits_per_second, (int, float)):
        return 0.0, False
    return round(bits_per_second / 1e6, 3), True


def meets_target(measured_mbps: float, target_mbps: float, tolerance: float = DEFAULT_TOLERANCE) -> bool:
    """True if ``measured_mbps`` is within ``tolerance`` of ``target_mbps``."""
    return measured_mbps >= target_mbps * tolerance
