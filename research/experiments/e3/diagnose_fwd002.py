"""One-off live diagnostic for the E3-FWD-002 TCP/dport=80 return-path failure.

E3-FWD-002 (h1->h3, TCP, dport=80, forwarded via s1's fast egress) fails its
intent_check ("h1->10.0.0.3:TCP/80 blocked") identically across all three E3
arms and across independent Mininet bring-ups, while plain ICMP baseline and
regression checks on the same hosts pass -- so this isn't run-to-run flakiness.

Working theory: the compiled flow is a high-priority STATIC rule that ONLY
matches the forward direction (src=h1,dst=h3,tcp,dport=80). It intercepts the
SYN before ONOS's reactive `fwd` app ever sees it, so `fwd` never learns this
conversation. h3's TCP stack should reply with a RST (nothing listens on port
80), but that RST (src=h3,dst=h1, tcp sport=80) matches no explicit flow and
depends entirely on `fwd`'s reactive handling for the return leg -- which may
not correctly route it back, leaving h1's connect() to time out.

This script deploys the *exact* compiled flow for this case, then -- instead of
rolling back immediately like the normal twin does -- dumps live evidence to
confirm or refute that theory before cleaning up:

  1. `ovs-ofctl dump-flows` on s1 (h1's switch) and s4 (h3's switch): is our
     static rule installed? Did `fwd` install ANYTHING, in either direction?
  2. tcpdump on h3 during a fresh connection attempt: does the SYN even arrive
     at h3? Does h3 send anything back?
  3. A repeat port check with a much longer timeout (8s instead of 3s), to
     distinguish "needs more time to converge" from "never resolves".
  4. ARP tables on h1/h3, to rule out address-resolution as the cause.

Requires Linux + root + Mininet + a running ONOS (./scripts/onos.sh start).
Run with: sudo /home/chu2739/.local/bin/uv run python experiments/e3/diagnose_fwd002.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from safe_intent_sdn.compiler import compile_prediction
from safe_intent_sdn.e3_evaluation import E3Case
from safe_intent_sdn.intent_ir import IntentPrediction
from safe_intent_sdn.twin.onos_client import OnosClient
from safe_intent_sdn.twin.topology import build_network, get_expected_device_ids

HOST_IPS = {"h1": "10.0.0.1", "h2": "10.0.0.2", "h3": "10.0.0.3", "h4": "10.0.0.4"}


def load_case(case_id: str) -> E3Case:
    for line in (ROOT / "experiments/e3/data/cases.jsonl").read_text().splitlines():
        case = E3Case.model_validate_json(line)
        if case.id == case_id:
            return case
    raise SystemExit(f"case {case_id} not found")


def section(title: str) -> None:
    print(f"\n{'=' * 10} {title} {'=' * 10}")


def main() -> None:
    if sys.platform != "linux":
        raise SystemExit("Linux only")
    import os
    if os.geteuid() != 0:
        raise SystemExit("root required (run with sudo)")

    case = load_case("E3-FWD-002")
    flow_set = compile_prediction(
        IntentPrediction(status="accepted", program=case.program), endpoint_ips=HOST_IPS
    )
    flowrule = flow_set.model_dump(mode="json")
    print("Compiled flow:")
    print(json.dumps(flowrule, indent=2))

    client = OnosClient()
    net = None
    try:
        print("\nWaiting for ONOS, activating apps, clearing flows...")
        client.wait_until_ready(timeout=60.0)
        for app in ("org.onosproject.openflow-base", "org.onosproject.openflow", "org.onosproject.fwd"):
            try:
                client.activate_application(app)
            except Exception:
                pass
        time.sleep(2)
        client.clear_app_flows()
        time.sleep(1)

        subprocess.run(["mn", "-c"], capture_output=True, timeout=15)
        print("Starting Mininet (diamond topology)...")
        net = build_network()
        net.start()
        client.wait_for_devices(get_expected_device_ids(), timeout=90.0)
        time.sleep(3)

        h1, h3 = net.get("h1"), net.get("h3")

        section("ARP tables BEFORE any traffic")
        print("h1:", h1.cmd("arp -n"))
        print("h3:", h3.cmd("arp -n"))

        section("Baseline ping h1 -> h3 (establishes ARP/fwd learning like the twin does)")
        h1.sendCmd("ping -c 3 -W 1 10.0.0.3")
        print(h1.waitOutput())

        section("Deploying the compiled FlowRule")
        client.deploy_flow_rules(flowrule)
        for f in flowrule["flows"]:
            client.wait_for_flow(device_id=f["deviceId"], priority=f["priority"], timeout=15.0)
        time.sleep(1)

        section("ovs-ofctl dump-flows s1 (h1's switch) -- is our static rule here?")
        print(net.get("s1").cmd("ovs-ofctl dump-flows s1 -O OpenFlow13"))

        section("ovs-ofctl dump-flows s4 (h3's switch) -- did fwd install anything, either direction?")
        print(net.get("s4").cmd("ovs-ofctl dump-flows s4 -O OpenFlow13"))

        section("tcpdump on h3 (5s) while h1 attempts a TCP connect to port 80")
        h3.cmd("timeout 5 tcpdump -ni h3-eth0 'tcp port 80 or icmp' -c 20 > /tmp/h3_dump.txt 2>&1 &")
        time.sleep(1)
        h1.sendCmd(
            "python3 -c \"import socket,errno;"
            "s=socket.socket();s.settimeout(3);"
            "e=s.connect_ex(('10.0.0.3',80));s.close();"
            "print('connect_ex errno:', e, '(0=open,111=ECONNREFUSED,110=ETIMEDOUT)')\""
        )
        print(h1.waitOutput())
        time.sleep(4)  # let the 5s tcpdump window finish
        print("h3 tcpdump capture:")
        print(h3.cmd("cat /tmp/h3_dump.txt"))

        section("Repeat port check with a longer timeout (8s) -- times out, or just slow to converge?")
        h1.sendCmd(
            "python3 -c \"import socket,errno,time;"
            "t0=time.time();"
            "s=socket.socket();s.settimeout(8);"
            "e=s.connect_ex(('10.0.0.3',80));s.close();"
            "print('connect_ex errno:', e, 'elapsed:', round(time.time()-t0,2))\""
        )
        print(h1.waitOutput())

        section("ovs-ofctl dump-flows s1 AFTER the connection attempts")
        print(net.get("s1").cmd("ovs-ofctl dump-flows s1 -O OpenFlow13"))
        section("ovs-ofctl dump-flows s4 AFTER the connection attempts")
        print(net.get("s4").cmd("ovs-ofctl dump-flows s4 -O OpenFlow13"))

        section("ARP tables AFTER traffic")
        print("h1:", h1.cmd("arp -n"))
        print("h3:", h3.cmd("arp -n"))

    finally:
        print("\nCleaning up...")
        try:
            client.clear_app_flows()
        except Exception:
            pass
        if net is not None:
            try:
                net.stop()
            except Exception:
                pass
        subprocess.run(["mn", "-c"], capture_output=True, timeout=15)


if __name__ == "__main__":
    main()
