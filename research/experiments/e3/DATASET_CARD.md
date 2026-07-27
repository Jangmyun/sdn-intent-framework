# E3 Dataset Card — Twin Decision Fidelity (`cases.jsonl`)

## Purpose

Each row is one **twin-fidelity case**: a candidate policy plus how its *true*
behavioral outcome is judged. The dataset feeds Experiment 3, which measures how
well the Digital Twin's automated PASS/FAIL verdict matches the real outcome of
an emulated deployment (see `paper/experiment_protocol/e3_rationale.md`).

## Topology assumed

All cases target the default **diamond** topology built by
`safe_intent_sdn/twin/topology.py::build_network`:

```
h1=10.0.0.1, h2=10.0.0.2 ── s1        s4 ── h3=10.0.0.3, h4=10.0.0.4
                             \  fast  /     s1-s3-s4 @ 10 Mbps
                              s3-----/
                             /  slow  \     s1-s2-s4 @ 1 Mbps
                             s2--------
```

## Schema (`safe_intent_sdn/e3_evaluation.py::E3Case`)

| field | meaning |
| --- | --- |
| `id` | unique case id, e.g. `E3-QOS-003` |
| `intent_category` | `forwarding` \| `security` \| `qos` \| `reroute` \| `compound` |
| `topology_id` | topology the case assumes (`diamond`) |
| `program` | the `IntentProgram`; compiled to ONOS flows by the deterministic compiler and deployed to the twin |
| `background_traffic` | constant-rate flows replayed in every arm to create the load the intent runs under |
| `min_mbps` | bandwidth target for the primary intent pair (QoS only; `null` otherwise) |
| `expected_ground_truth` | `SHOULD_PASS` \| `SHOULD_FAIL` — author-adjudicated anchor cross-checked against the measured ground truth |

## Composition (11 cases)

| category | ids | ground truth | note |
| --- | --- | --- | --- |
| forwarding | E3-FWD-001..002 | SHOULD_PASS | control: reach-only twin is already faithful |
| security | E3-SEC-001..002 | SHOULD_PASS | a deny that correctly blocks is an achieved intent |
| qos (within capacity) | E3-QOS-001..002 | SHOULD_PASS | target ≤ fast link's 10 Mbps ceiling; a real queue reservation can honor it, background load or not |
| qos (over capacity) | E3-QOS-003..005 | **SHOULD_FAIL** | target (12/13/15 Mbps) exceeds the fast link's 10 Mbps physical ceiling — the headline blind spot |
| reroute | E3-RRT-001..002 | SHOULD_PASS | avoid the slow path; reach-only check is faithful |

The over-capacity QoS cases are the ones where a reach-only twin issues a
**dangerous wrong approval** (false positive) and the bandwidth-probing twin
does not: the link stays fully reachable (near-full utilization, no packet
loss), but the requested rate can never be delivered regardless of queue
configuration, so only a real bandwidth measurement reveals the SLA is
infeasible on this topology.

## Why "over capacity", not "congested by shared background load"

An earlier version of this dataset tried to induce the SHOULD_FAIL condition by
racing an unreserved background flow against the QoS flow on the shared fast
path. That design assumed an unprovisioned OpenFlow `QUEUE` action would cause
the two flows to compete unpredictably. In practice, two problems surfaced
running the twin against a real Mininet+ONOS+OVS stack:

1. **The `QUEUE(queueId=0)` action referenced a queue OVS never provisioned**,
   since neither this project's twin nor the `sdn-xai-pipeline` twin it was
   ported from ever created real OVS queues. An unprovisioned queue reference
   is implementation-defined and was observed to cause near-total packet loss
   (measured ~0.25 Mbps), not a fair-share degradation — which also broke the
   reach-only twin's baseline connectivity check, collapsing the very
   distinction ("reachable, but rate not met") the dataset needed to
   demonstrate.
2. Once the twin (`safe_intent_sdn/twin/twin_verifier.py::provision_min_rate_queue`)
   provisions a *real* OVS HTB min-rate queue for the requested target, a
   background flow competing from the *default* (unreserved) queue is exactly
   what a min-rate reservation is designed to survive — so racing it against
   best-effort noise no longer reliably produces a SHOULD_FAIL outcome; it
   tests whether the reservation works, which is the SHOULD_PASS story instead.

## TCP-selector forwarding cases are excluded (known twin/`fwd` limitation)

`E3-FWD-002` originally used a TCP `destination_port=80` selector. It failed its
`intent_check` ("h1->10.0.0.3:TCP/80 blocked") identically in all three arms
while plain ICMP to the same host passed, so it was investigated live
(`experiments/e3/diagnose_fwd002.py`). The capture showed the SYN reaching h3 and
h3's RST returning correctly *in isolation* -- the round trip itself is fine --
but `ovs-ofctl dump-flows` revealed the real conflict:

- The compiled forwarding rule pins `h1->h3` out of `s1`'s **fast-path** port
  (`s1-eth2`, toward s3), because the case sets `enforcement.egress_port`.
- ONOS's reactive `fwd` app had independently learned `h1->h3` over the
  **slow path** (`s1-eth1`, toward s2), and installs paths *per direction*
  (asymmetric), so downstream switches only hold rules matching the path `fwd`
  chose.

A high-priority static rule that redirects a flow onto a different path than the
one `fwd` populated downstream leaves the round trip dependent on which rules
`fwd` happens to have installed at that moment. ICMP tolerates this (the check
sends 3 packets over ~3s and needs only one through), but a TCP connect needs a
full round trip inside its 3s timeout, so it fails intermittently-to-consistently.

Both forwarding cases therefore use ICMP. This is a limitation of the ported
twin's interaction with reactive forwarding, **not** something E3 sets out to
measure. Restoring TCP coverage here would require either aligning
`enforcement.egress_port` with the path `fwd` actually selects, or extending the
twin's OVS steering logic (`_install_steering`, currently block-intent-only and
inactive for the built-in diamond topology since it requires `custom_data`) to
forward intents as well.

## Two more issues found on the first full 11-case run (fixed)

- **`E3-QOS-005`'s target (originally 11 Mbps) was too close to the achievable
  near-line-rate ceiling.** Measured throughput on a fully-available fast link
  is ~9.3-9.4 Mbps (protocol overhead below the nominal 10 Mbps HTB cap), and
  `11 * DEFAULT_TOLERANCE(0.85) = 9.35` sits right at that ceiling — the
  measured ground truth PASSED by measurement noise alone, contradicting the
  authored `SHOULD_FAIL` label (caught by `score.py`'s
  `ground_truth_label_mismatch` guard, exactly as designed). Fixed by raising
  the target to 13 Mbps (`13*0.85=11.05`, safely above ~9.4).
- **The background flow's destination collided with the fixed regression
  pair.** The diamond topology's regression pair is `(h2, h3)`
  (`safe_intent_sdn/twin/topology.py::get_test_host_pairs`). `E3-QOS-002`'s
  background flow was originally also `h2->h3` -- meaning the "independent
  pair stays unaffected" regression check was evaluated on exactly the pair
  the case deliberately loaded, which is self-contradictory (of course a pair
  is affected when it *is* the background load). This surfaced as the
  regression check reporting `"h2->10.0.0.3 blocked"` even though the
  bandwidth target itself was met. Fixed by routing the background flow to
  `h4` instead (`h2->h4`): still crosses the same shared s1-s4 link, but no
  longer collides with either the regression pair `(h2,h3)` or the primary
  intent pair `(h1,h4)`'s source.

The over-capacity design sidesteps both problems: it doesn't depend on ONOS's
reactive-forwarding path choice for a second, unrelated flow (which was
non-deterministic in practice — see the "why forced routing" note in
`build_dataset.py`), and it stays a genuine SHOULD_FAIL under real queue
provisioning, since no reservation can exceed the physical link.

## Construction & limitations

- Built by `experiments/e3/build_dataset.py`, which constructs every case through
  the pydantic models and asserts each `program` compiles — so the file cannot
  drift into an invalid or non-compilable state. Regenerate with:
  `uv run python experiments/e3/build_dataset.py`.
- `min_mbps` for the "over capacity" cases is compared against
  `safe_intent_sdn.twin.topology.DIAMOND_FAST_LINK_MBPS` (10.0) by
  `tests/test_e3_dataset.py`; if the diamond topology's fast-link bandwidth ever
  changes, update both.
- `experiments/e3/score.py` still cross-checks the *measured* ground truth
  against each case's `expected_ground_truth` and reports any
  `ground_truth_label_mismatch` — kept as a fail-closed guard even though the
  over-capacity design no longer depends on routing nondeterminism.
- This is a small, hand-authored benchmark (like the E2 fixtures), sized to
  exercise the fidelity contrast per category, not a large sampled corpus.
