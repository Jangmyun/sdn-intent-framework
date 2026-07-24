# E3 Results — Twin Decision Fidelity (RQ3)

Measured on Ubuntu 24.04 (Linux 6.8, 4 vCPU / 7.5 GiB) with Mininet + Open
vSwitch 3.3.4 and ONOS 2.7.0, over the 11-case `experiments/e3/data/cases.jsonl`
benchmark on the built-in diamond topology. Source of record:
`logs/e3/e3_fidelity.json` (produced by `./scripts/e3_run_all.sh`; the twin arms
require Linux + root and cannot run in CI).

**Run integrity:** `ground_truth_label_mismatch` was empty — all 11 measured
ground-truth outcomes agreed with the authored `expected_ground_truth` labels —
and every failed check in the run was a genuine `bandwidth` shortfall, with no
reachability-probe failures. See "Reproducibility notes" below.

## Table E3a — false positive rate (dangerous wrong approvals)

`fpr` = fraction of policies that fail in the emulated deployment
(`ground_truth = FAIL`) that the twin nevertheless approves. Lower is safer.
Categories with no `SHOULD_FAIL` case have an undefined `fpr` (—).

| intent category | `twin_nobw` fpr | `twin_bw` fpr | Δ (bw − nobw) |
| --- | --- | --- | --- |
| forwarding | — | — | — |
| security | — | — | — |
| qos | **1.00** | **0.00** | **−1.00** |
| reroute | — | — | — |
| **overall** | **1.00** | **0.00** | **−1.00** |

## Table E3b — agreement with ground truth (accuracy)

| intent category | `twin_nobw` | `twin_bw` | Δ (bw − nobw) |
| --- | --- | --- | --- |
| forwarding | 1.00 | 1.00 | 0.00 |
| security | 1.00 | 1.00 | 0.00 |
| qos | 0.40 | 1.00 | +0.60 |
| reroute | 1.00 | 1.00 | 0.00 |
| **overall** | **0.727** | **1.000** | **+0.273** |

Confusion counts (positive class = "policy should be approved"):

| arm | scope | tp | fp | fn | tn |
| --- | --- | --- | --- | --- | --- |
| `twin_nobw` | overall | 8 | **3** | 0 | 0 |
| `twin_bw` | overall | 8 | 0 | 0 | 3 |
| `twin_nobw` | qos | 2 | **3** | 0 | 0 |
| `twin_bw` | qos | 2 | 0 | 0 | 3 |

## Claim

The reach-only twin (`twin_nobw`) is perfectly faithful on forwarding, security
and reroute intents (accuracy 1.00 in each) but has a **total QoS blind spot**:
it approved **all three** QoS policies whose requested rate exceeds the fast
link's 10 Mbps physical capacity — `fpr = 1.00`. Those policies are genuinely
reachable (0% packet loss, near-full link utilization at ~9.39 Mbps measured),
so a reachability check cannot distinguish them from a policy that meets its SLA;
only a real bandwidth measurement reveals that the target can never be delivered
by any queue reservation.

Adding the iperf3 bandwidth probe (`twin_bw`) eliminated every one of those wrong
approvals (`qos` `fpr` 1.00 → 0.00) and raised overall twin fidelity from 0.727
to 1.000, **without changing any category the reach-only twin already handled**
(forwarding/security/reroute stay at 1.00). This both validates the Digital Twin
as a decision instrument and quantifies precisely the condition under which it
must probe bandwidth to remain valid.

## Scope

Component-level twin decision-fidelity over emulated diamond-topology
deployments. Validates the twin as a *decision instrument*, **not** the fidelity
of Mininet emulation to physical hardware. Ground truth is the comprehensively
measured emulated deployment, not a physical network. The benchmark is a small
hand-authored fixture set (11 cases, like the E2 fixtures), so the reported rates
characterise this benchmark rather than a sampled population — in particular
`fpr = 1.00` means "all three over-capacity QoS cases were wrongly approved", not
a population estimate. See `paper/experiment_protocol/e3_rationale.md` for the
full caveat and the `ground_truth_label_mismatch` guard.

## Reproducibility notes

Reaching a clean run required fixing three emulation-level confounds, each found
by the guard rails rather than by inspection (details in
`experiments/e3/DATASET_CARD.md`):

1. **Unprovisioned OVS queues.** A compiled `QUEUE(queueId=0)` action had no real
   queue behind it, causing near-total packet loss instead of a reservation.
   `safe_intent_sdn/twin/twin_verifier.py::provision_min_rate_queue` now creates a
   real `linux-htb` min-rate queue (capped at 90% of link capacity so best-effort
   traffic is not starved).
2. **Orphaned ovsdb records.** `mn -c` does not reap QoS/Queue rows, so they
   accumulated across all 33 case-runs and eventually broke unrelated
   reachability checks. `clear_ovs_qos()` now runs before start and after
   teardown.
3. **Host discovery never happening.** The topologies build with
   `autoStaticArp=True`, so hosts never emit ARP and ONOS — which places hosts
   from packet-ins — could not install paths, making even the *pre-deployment*
   baseline check intermittently read "blocked". A warm-up `pingAll` after
   network start fixed this; notably ONOS's own host table often still reports
   0–1 of 4 hosts, so priming the dataplane, not host registration, is the
   effective readiness condition.

## Figure

`paper/figures/e3_fpr_nobw_vs_bw.{pdf,png}` (English) and `..._ko.{pdf,png}`
(Korean), rendered by `paper/scripts/plot_e3_fidelity.py`. Panel (a) is
per-category accuracy (all categories); panel (b) is `fpr` (only categories with
a `SHOULD_FAIL` case).
