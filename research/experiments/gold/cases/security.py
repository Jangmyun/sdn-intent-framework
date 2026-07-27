"""GOLD-350 security cases (50)."""
from __future__ import annotations

from .helpers import allow, deny, number

ENTRIES = [
    # deny host pair (10)
    ("deny_pair", "Block all traffic from h1 to h2.", deny("h1", "h2")),
    ("deny_pair", "Deny h3 access to h4.", deny("h3", "h4")),
    ("deny_pair", "Drop packets from h2 to h1.", deny("h2", "h1")),
    ("deny_pair", "Do not let h4 reach h3.", deny("h4", "h3")),
    ("deny_pair", "Prevent h1 from contacting h4.", deny("h1", "h4")),
    ("deny_pair", "Block h2 to h3 completely.", deny("h2", "h3")),
    ("deny_pair", "Deny all traffic from 10.0.0.3 to 10.0.0.2.", deny("10.0.0.3", "10.0.0.2", eth="ipv4")),
    ("deny_pair", "Drop everything from 10.0.0.4 to 10.0.0.1.", deny("10.0.0.4", "10.0.0.1", eth="ipv4")),
    ("deny_pair", "h1 must not reach h3.", deny("h1", "h3")),
    ("deny_pair", "Cut off traffic from h3 to h1.", deny("h3", "h1")),
    # deny service (10)
    ("deny_service", "Block SSH from h2 to h4.", deny("h2", "h4", proto="tcp", dport=22)),
    ("deny_service", "Deny HTTP from h1 to h4.", deny("h1", "h4", proto="tcp", dport=80)),
    ("deny_service", "Drop ICMP from h3 to h2.", deny("h3", "h2", proto="icmp")),
    ("deny_service", "Block DNS queries from h4 to h1.", deny("h4", "h1", proto="udp", dport=53)),
    ("deny_service", "Prevent FTP from h2 to h3.", deny("h2", "h3", proto="tcp", dport=21)),
    ("deny_service", "Deny HTTPS from h4 to h2.", deny("h4", "h2", proto="tcp", dport=443)),
    ("deny_service", "Block ping from h1 to h2.", deny("h1", "h2", proto="icmp")),
    ("deny_service", "Stop mail traffic from h3 to h4.", deny("h3", "h4", proto="tcp", dport=25)),
    ("deny_service", "Deny UDP port 69 from h1 to h3.", deny("h1", "h3", proto="udp", dport=69)),
    ("deny_service", "Block TCP port 23 from h2 to h1.", deny("h2", "h1", proto="tcp", dport=23)),
    # deny with ip / device scope (10)
    ("deny_device", "On switch 1, drop all traffic from 10.0.0.1.", deny(src="10.0.0.1", eth="ipv4", device=1)),
    ("deny_device", "Block traffic destined for 10.0.0.4 on switch 4.", deny(dst="10.0.0.4", eth="ipv4", device=4)),
    ("deny_device", "Switch 2: deny packets from 10.0.0.2.", deny(src="10.0.0.2", eth="ipv4", device=2)),
    ("deny_device", "Drop UDP from 10.0.0.3 on switch 4.", deny(src="10.0.0.3", eth="ipv4", proto="udp", device=4)),
    ("deny_device", "On switch 3, block everything going to 10.0.0.1.", deny(dst="10.0.0.1", eth="ipv4", device=3)),
    ("deny_device", "Deny ICMP destined for 10.0.0.2 on switch 1.", deny(dst="10.0.0.2", eth="ipv4", proto="icmp", device=1)),
    ("deny_device", "Block TCP port 445 from 10.0.0.1 on switch 1.",
     deny(src="10.0.0.1", eth="ipv4", proto="tcp", dport=445, device=1)),
    ("deny_device", "On switch 4, drop traffic from 10.0.0.4 to 10.0.0.2.",
     deny("10.0.0.4", "10.0.0.2", eth="ipv4", device=4)),
    ("deny_device", "Deny all IPv4 from 10.0.0.2 on switch 2.", deny(src="10.0.0.2", eth="ipv4", device=2)),
    ("deny_device", "Drop packets arriving on port 3 of switch 1.", deny(inport=3, device=1)),
    # explicit allow / whitelist (10)
    ("allow_rule", "Add an allow rule for traffic from h1 to h3.", allow("h1", "h3")),
    ("allow_rule", "Whitelist h2 to h4 traffic.", allow("h2", "h4")),
    ("allow_rule", "Add a permit rule for SSH from h1 to h4.", allow("h1", "h4", proto="tcp", dport=22)),
    ("allow_rule", "Whitelist DNS from h3 to h2.", allow("h3", "h2", proto="udp", dport=53)),
    ("allow_rule", "Insert an accept rule for ICMP from h2 to h1.", allow("h2", "h1", proto="icmp")),
    ("allow_rule", "Add an allow entry for 10.0.0.1 to 10.0.0.4 on switch 1.",
     allow("10.0.0.1", "10.0.0.4", eth="ipv4", device=1)),
    ("allow_rule", "Whitelist HTTPS from h4 to h1.", allow("h4", "h1", proto="tcp", dport=443)),
    ("allow_rule", "Add a security exception permitting h3 to h1.", allow("h3", "h1")),
    ("allow_rule", "Create an ACL entry allowing TCP port 8443 from h2 to h3.",
     allow("h2", "h3", proto="tcp", dport=8443)),
    ("allow_rule", "Whitelist web traffic from h1 to h2.", allow("h1", "h2", proto="tcp", dport=80)),
    # colloquial deny (10)
    ("colloquial_deny", "Shut down any traffic from h4 to h2.", deny("h4", "h2")),
    ("colloquial_deny", "Keep h1 away from h2.", deny("h1", "h2")),
    ("colloquial_deny", "Don't allow h3 to talk to h2.", deny("h3", "h2")),
    ("colloquial_deny", "No SSH into h3 from h1.", deny("h1", "h3", proto="tcp", dport=22)),
    ("colloquial_deny", "Kill the h2 to h4 flow.", deny("h2", "h4")),
    ("colloquial_deny", "h4 shouldn't be able to ping h1.", deny("h4", "h1", proto="icmp")),
    ("colloquial_deny", "Make sure h1 never reaches h2.", deny("h1", "h2")),
    ("colloquial_deny", "Firewall off h1 from h4.", deny("h1", "h4")),
    ("colloquial_deny", "Blackhole traffic from 10.0.0.2 to 10.0.0.4.", deny("10.0.0.2", "10.0.0.4", eth="ipv4")),
    ("colloquial_deny", "Deny everything h3 sends to h2.", deny("h3", "h2")),
]

CASES = number("G-SEC", "security", ENTRIES)
