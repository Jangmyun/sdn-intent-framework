"""GOLD-350 ambiguous/unsupported cases (50, all rejected)."""
from __future__ import annotations

from .helpers import number, reject

ENTRIES = [
    # ambiguous (15)
    ("ambiguous", "Make the network faster.", reject("ambiguous")),
    ("ambiguous", "Fix the connectivity problems.", reject("ambiguous")),
    ("ambiguous", "Improve security across the fabric.", reject("ambiguous")),
    ("ambiguous", "Optimize traffic flow.", reject("ambiguous")),
    ("ambiguous", "Set things up like last time.", reject("ambiguous")),
    ("ambiguous", "Handle h2's traffic appropriately.", reject("ambiguous")),
    ("ambiguous", "Make sure everything works smoothly.", reject("ambiguous")),
    ("ambiguous", "Reduce congestion.", reject("ambiguous")),
    ("ambiguous", "Prioritize the important traffic.", reject("ambiguous")),
    ("ambiguous", "Block the suspicious traffic.", reject("ambiguous")),
    ("ambiguous", "Route traffic more efficiently.", reject("ambiguous")),
    ("ambiguous", "Give better service to the users.", reject("ambiguous")),
    ("ambiguous", "Do something about the latency.", reject("ambiguous")),
    ("ambiguous", "Tighten up the network policies.", reject("ambiguous")),
    ("ambiguous", "Send the traffic the right way.", reject("ambiguous")),
    # contradictory (10)
    ("contradictory", "Allow h2 to reach h3 and block h2 from reaching h3.", reject("contradictory")),
    ("contradictory", "Forward ICMP from h1 to h4 and drop ICMP from h1 to h4.", reject("contradictory")),
    ("contradictory", "Route h1 to h4 through switch 2 and make sure it never touches switch 2.",
     reject("contradictory")),
    ("contradictory", "Deny all traffic from h4 to h1 and also forward all traffic from h4 to h1.",
     reject("contradictory")),
    ("contradictory", "Put h2 to h3 traffic in queue 1 and in queue 5 at the same time.",
     reject("contradictory")),
    ("contradictory", "Drop everything from h1 and guarantee h1 to h3 gets 20 Mbps.",
     reject("contradictory")),
    ("contradictory", "Send h3 to h1 traffic out port 1 and port 2 of switch 4 simultaneously.",
     reject("contradictory")),
    ("contradictory", "Block ping from h2 to h4 but ensure h2 can ping h4.", reject("contradictory")),
    ("contradictory", "Whitelist SSH from h1 to h2 and blacklist SSH from h1 to h2.",
     reject("contradictory")),
    ("contradictory", "Keep h2 to h4 latency under 5 ms and above 50 ms.", reject("contradictory")),
    # unknown entity (15)
    ("unknown_entity", "Let h9 reach h2.", reject("unknown_entity")),
    ("unknown_entity", "Forward traffic from h5 to h1.", reject("unknown_entity")),
    ("unknown_entity", "Block 10.0.0.99 from reaching h3.", reject("unknown_entity")),
    ("unknown_entity", "Route HTTP from 10.0.1.7 to 10.0.0.2.", reject("unknown_entity")),
    ("unknown_entity", "On switch 7, forward traffic to 10.0.0.3 via port 2.", reject("unknown_entity")),
    ("unknown_entity", "Deny all traffic from the database server.", reject("unknown_entity")),
    ("unknown_entity", "Prioritize traffic from the backup NAS to h1 on queue 2.", reject("unknown_entity")),
    ("unknown_entity", "Send h2's traffic through the firewall on switch 6.", reject("unknown_entity")),
    ("unknown_entity", "Give h8 to h1 at least 10 Mbps.", reject("unknown_entity")),
    ("unknown_entity", "Drop packets from printer-01 to h4.", reject("unknown_entity")),
    ("unknown_entity", "Reroute h1 to h4 traffic via switch 5.", reject("unknown_entity")),
    ("unknown_entity", "Forward DNS from h3 to the guest subnet.", reject("unknown_entity")),
    ("unknown_entity", "Block traffic from 172.16.0.4 to h2.", reject("unknown_entity")),
    ("unknown_entity", "On switch 3, forward traffic for h3 out port 7.", reject("unknown_entity")),
    ("unknown_entity", "Allow camera-2 to stream to h4.", reject("unknown_entity")),
    # unsupported (10)
    ("unsupported", "Set up a VPN tunnel from h1 to h4.", reject("unsupported")),
    ("unsupported", "Apply NAT to h2's outbound traffic.", reject("unsupported")),
    ("unsupported", "Encrypt all traffic between h1 and h3.", reject("unsupported")),
    ("unsupported", "Limit h2 to h4 to at most 1 Mbps.", reject("unsupported")),
    ("unsupported", "Allow h1 to reach h3 only during business hours.", reject("unsupported")),
    ("unsupported", "Mirror all of h2's traffic to h4 for analysis.", reject("unsupported")),
    ("unsupported", "Load-balance h1's flows across all available paths dynamically.", reject("unsupported")),
    ("unsupported", "Cache web content for h2 at the edge.", reject("unsupported")),
    ("unsupported", "Block adult content for h2.", reject("unsupported")),
    ("unsupported", "Translate h3's IPv4 traffic to IPv6.", reject("unsupported")),
]

CASES = number("G-AMB", "ambiguous_unsupported", ENTRIES)
