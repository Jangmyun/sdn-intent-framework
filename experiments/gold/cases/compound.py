"""GOLD-350 compound cases (50).

Ordering convention (documented in the annotation guideline and protocol):
the exception / more-specific clause comes first in ``rules`` (highest policy
priority first, per IntentProgram semantics); independent non-overlapping
clauses keep instruction order.
"""
from __future__ import annotations

from .helpers import accept, enf, number, qc, rule, sel


def r_fwd(src=None, dst=None, eth=None, proto=None, dport=None, device=None, port=None):
    return rule("forwarding", "forward", sel(src, dst, eth, proto, dport=dport),
                enforcement=enf(device, port))


def r_deny(src=None, dst=None, eth=None, proto=None, dport=None, device=None):
    return rule("security", "deny", sel(src, dst, eth, proto, dport=dport),
                enforcement=enf(device))


def r_allow(src=None, dst=None, eth=None, proto=None, dport=None, device=None):
    return rule("security", "allow", sel(src, dst, eth, proto, dport=dport),
                enforcement=enf(device))


def r_qos(src=None, dst=None, eth=None, proto=None, dport=None, bw=None, lat=None, queue=None):
    return rule("qos", "prioritize", sel(src, dst, eth, proto, dport=dport), qos=qc(bw, lat, queue))


ENTRIES = [
    # deny + default forward (15)
    ("exception_default", "Drop all traffic from h2 on switch 1 and forward everything else normally.",
     accept([r_deny(src="h2", device=1), r_fwd(eth="ipv4", device=1)])),
    ("exception_default", "On switch 4, block traffic to h4 but keep forwarding all other traffic.",
     accept([r_deny(dst="h4", device=4), r_fwd(eth="ipv4", device=4)])),
    ("exception_default", "Block ICMP from h1 to h3 and forward the rest of h1's traffic.",
     accept([r_deny("h1", "h3", proto="icmp"), r_fwd(src="h1")])),
    ("exception_default", "Deny SSH from h2 to h4 while still forwarding other h2 to h4 traffic.",
     accept([r_deny("h2", "h4", proto="tcp", dport=22), r_fwd("h2", "h4")])),
    ("exception_default", "Forward all traffic from h1 to h4 except SSH.",
     accept([r_deny("h1", "h4", proto="tcp", dport=22), r_fwd("h1", "h4")])),
    ("exception_default", "Allow everything from h3 to h1 except ICMP.",
     accept([r_deny("h3", "h1", proto="icmp"), r_fwd("h3", "h1")])),
    ("exception_default", "Forward h2 to h3 traffic but drop its UDP.",
     accept([r_deny("h2", "h3", proto="udp"), r_fwd("h2", "h3")])),
    ("exception_default", "Forward all traffic from h4 to h2 except FTP.",
     accept([r_deny("h4", "h2", proto="tcp", dport=21), r_fwd("h4", "h2")])),
    ("exception_default", "On switch 1, drop packets from 10.0.0.3 and forward all other IPv4 traffic.",
     accept([r_deny(src="10.0.0.3", eth="ipv4", device=1), r_fwd(eth="ipv4", device=1)])),
    ("exception_default", "Block DNS from h1 to h2 but let everything else through.",
     accept([r_deny("h1", "h2", proto="udp", dport=53), r_fwd("h1", "h2")])),
    ("exception_default", "Forward everything from h3 to h4 apart from telnet.",
     accept([r_deny("h3", "h4", proto="tcp", dport=23), r_fwd("h3", "h4")])),
    ("exception_default", "Deny HTTP from h4 to h1 and forward its remaining traffic.",
     accept([r_deny("h4", "h1", proto="tcp", dport=80), r_fwd("h4", "h1")])),
    ("exception_default", "Everything from h1 should reach h3 except HTTPS.",
     accept([r_deny("h1", "h3", proto="tcp", dport=443), r_fwd("h1", "h3")])),
    ("exception_default", "On switch 2, drop traffic from 10.0.0.4 but forward other flows.",
     accept([r_deny(src="10.0.0.4", eth="ipv4", device=2), r_fwd(eth="ipv4", device=2)])),
    ("exception_default", "Let h2 reach h1 fully except for ping.",
     accept([r_deny("h2", "h1", proto="icmp"), r_fwd("h2", "h1")])),
    # two independent flows (10)
    ("multi_flow", "Forward HTTP from h1 to h3 and DNS from h2 to h4.",
     accept([r_fwd("h1", "h3", proto="tcp", dport=80), r_fwd("h2", "h4", proto="udp", dport=53)])),
    ("multi_flow", "Allow h1 to reach h2 and h3 to reach h4.",
     accept([r_fwd("h1", "h2"), r_fwd("h3", "h4")])),
    ("multi_flow", "Forward SSH from h2 to h3 and FTP from h3 to h2.",
     accept([r_fwd("h2", "h3", proto="tcp", dport=22), r_fwd("h3", "h2", proto="tcp", dport=21)])),
    ("multi_flow", "Set up paths from h1 to h4 and from h4 to h1.",
     accept([r_fwd("h1", "h4"), r_fwd("h4", "h1")])),
    ("multi_flow", "Route ICMP from h1 to h2 and UDP from h3 to h1.",
     accept([r_fwd("h1", "h2", proto="icmp"), r_fwd("h3", "h1", proto="udp")])),
    ("multi_flow", "Allow web traffic from h2 to h4 and mail from h4 to h2.",
     accept([r_fwd("h2", "h4", proto="tcp", dport=80), r_fwd("h4", "h2", proto="tcp", dport=25)])),
    ("multi_flow", "Forward h1 to h3 and h2 to h3.",
     accept([r_fwd("h1", "h3"), r_fwd("h2", "h3")])),
    ("multi_flow", "Enable HTTPS from h3 to h1 and HTTP from h3 to h2.",
     accept([r_fwd("h3", "h1", proto="tcp", dport=443), r_fwd("h3", "h2", proto="tcp", dport=80)])),
    ("multi_flow", "Allow DNS from h1 to h4 and DNS from h2 to h4.",
     accept([r_fwd("h1", "h4", proto="udp", dport=53), r_fwd("h2", "h4", proto="udp", dport=53)])),
    ("multi_flow", "Forward TCP from h4 to h3 and ICMP from h4 to h2.",
     accept([r_fwd("h4", "h3", proto="tcp"), r_fwd("h4", "h2", proto="icmp")])),
    # one clause, multiple services (5)
    ("multi_service", "Block SSH and telnet from h2 to h4.",
     accept([r_deny("h2", "h4", proto="tcp", dport=22), r_deny("h2", "h4", proto="tcp", dport=23)])),
    ("multi_service", "Forward HTTP and HTTPS from h1 to h3.",
     accept([r_fwd("h1", "h3", proto="tcp", dport=80), r_fwd("h1", "h3", proto="tcp", dport=443)])),
    ("multi_service", "Deny FTP and SMTP from h3 to h1.",
     accept([r_deny("h3", "h1", proto="tcp", dport=21), r_deny("h3", "h1", proto="tcp", dport=25)])),
    ("multi_service", "Allow DNS and HTTP from h2 to h1.",
     accept([r_fwd("h2", "h1", proto="udp", dport=53), r_fwd("h2", "h1", proto="tcp", dport=80)])),
    ("multi_service", "Drop ICMP and UDP from h4 to h2.",
     accept([r_deny("h4", "h2", proto="icmp"), r_deny("h4", "h2", proto="udp")])),
    # qos mixed with other intents (10)
    ("qos_mix", "Put h1 to h3 traffic in queue 1 and block h4 from reaching h3.",
     accept([r_qos("h1", "h3", queue=1), r_deny("h4", "h3")])),
    ("qos_mix", "Guarantee 20 Mbps for h2 to h4 and forward ICMP from h2 to h1.",
     accept([r_qos("h2", "h4", bw=20), r_fwd("h2", "h1", proto="icmp")])),
    ("qos_mix", "Prioritize DNS from h1 to h2 on queue 2 and drop DNS from h3.",
     accept([r_qos("h1", "h2", proto="udp", dport=53, queue=2), r_deny(src="h3", proto="udp", dport=53)])),
    ("qos_mix", "Keep h1 to h4 latency under 10 ms and block telnet from h1 to h4.",
     accept([r_qos("h1", "h4", lat=10), r_deny("h1", "h4", proto="tcp", dport=23)])),
    ("qos_mix", "Give web traffic from h3 to h1 at least 15 Mbps and deny its FTP.",
     accept([r_qos("h3", "h1", proto="tcp", dport=80, bw=15), r_deny("h3", "h1", proto="tcp", dport=21)])),
    ("qos_mix", "Queue 3 for h4 to h1 and forward h4 to h2.",
     accept([r_qos("h4", "h1", queue=3), r_fwd("h4", "h2")])),
    ("qos_mix", "Reserve 30 Mbps under 25 ms for h2 to h3, and block h2 to h4.",
     accept([r_qos("h2", "h3", bw=30, lat=25), r_deny("h2", "h4")])),
    ("qos_mix", "Prioritize ICMP from h1 to h2 in queue 1 and forward UDP from h1 to h2.",
     accept([r_qos("h1", "h2", proto="icmp", queue=1), r_fwd("h1", "h2", proto="udp")])),
    ("qos_mix", "Ensure 10 Mbps minimum for HTTPS from h4 to h3 and block HTTP from h4 to h3.",
     accept([r_qos("h4", "h3", proto="tcp", dport=443, bw=10), r_deny("h4", "h3", proto="tcp", dport=80)])),
    ("qos_mix", "Latency under 15 ms for h3 to h2, plus forward h3 to h4.",
     accept([r_qos("h3", "h2", lat=15), r_fwd("h3", "h4")])),
    # three-clause and whitelist-style combinations (10)
    ("triple", "Block h2 and h3 from reaching h4, and forward everything else to h4.",
     accept([r_deny("h2", "h4"), r_deny("h3", "h4"), r_fwd(dst="h4")])),
    ("triple", "Drop ICMP from h1 and h2 on switch 1 but forward their other traffic.",
     accept([r_deny(src="h1", proto="icmp", device=1), r_deny(src="h2", proto="icmp", device=1),
             r_fwd(eth="ipv4", device=1)])),
    ("triple", "Whitelist SSH from h1 to h2 and drop all other SSH to h2.",
     accept([r_allow("h1", "h2", proto="tcp", dport=22), r_deny(dst="h2", proto="tcp", dport=22)])),
    ("triple", "On switch 1, forward traffic for 10.0.0.1 out port 3 and traffic for 10.0.0.2 out port 4.",
     accept([r_fwd(dst="10.0.0.1", eth="ipv4", device=1, port="3"),
             r_fwd(dst="10.0.0.2", eth="ipv4", device=1, port="4")])),
    ("triple", "Block h1 to h4 and h4 to h1.",
     accept([r_deny("h1", "h4"), r_deny("h4", "h1")])),
    ("triple", "Forward DNS from h2 to h4 and block all other UDP from h2.",
     accept([r_fwd("h2", "h4", proto="udp", dport=53), r_deny(src="h2", proto="udp")])),
    ("triple", "Give h1 to h3 queue 1, forward h2 to h3, and block h4 to h3.",
     accept([r_qos("h1", "h3", queue=1), r_fwd("h2", "h3"), r_deny("h4", "h3")])),
    ("triple", "Permit only ICMP from h3 to h4 and drop the rest of h3 to h4 traffic.",
     accept([r_allow("h3", "h4", proto="icmp"), r_deny("h3", "h4")])),
    ("triple", "On switch 4, drop everything from 10.0.0.2 except DNS.",
     accept([r_allow(src="10.0.0.2", eth="ipv4", proto="udp", dport=53, device=4),
             r_deny(src="10.0.0.2", eth="ipv4", device=4)])),
    ("triple", "Forward h1 to h2 and h2 to h1, but block ICMP from h1 to h2.",
     accept([r_deny("h1", "h2", proto="icmp"), r_fwd("h1", "h2"), r_fwd("h2", "h1")])),
]

CASES = number("G-CMP", "compound", ENTRIES)
