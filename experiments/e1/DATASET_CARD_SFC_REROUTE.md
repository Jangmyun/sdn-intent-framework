# E1-SFC/Reroute Extension Dataset Card

This is a **separate 100-case extension benchmark** (`experiments/e1/data/intents_sfc_reroute.jsonl`),
built by `experiments/e1/build_sfc_reroute_dataset.py`. It is not a replacement for,
and never merges numbers with, the pinned 100-case `experiments/e1/data/intents.jsonl`
benchmark described in `DATASET_CARD.md`.

## Composition

| category | cases | source |
|---|---:|---|
| forwarding | 15 | reused as-is from `project_authored.jsonl` |
| security | 15 | reused as-is from `project_authored.jsonl` |
| qos | 10 | reused as-is from `project_authored.jsonl` |
| ambiguous_unsupported | 10 | reused as-is from `project_authored.jsonl` |
| sfc | 25 | new, `project_authored_sfc_reroute.jsonl` |
| reroute | 25 | new, `project_authored_sfc_reroute.jsonl` |

The build script asserts the first 50 rows are byte-for-byte the same 50 rows in
`project_authored.jsonl`, so this benchmark's forwarding/security/qos/rejection
results remain directly comparable to the original benchmark's `project_authored`
cohort. The upstream NetIntent cohort is not part of this extension at all.

## Why a separate topology fixture

`sfc`/`reroute` cases assume a diamond topology (`s1` ports 1-4 with port 9 as a
firewall waypoint; `s4` ports 1-4 with port 3/4 as host-facing ports for h3/h4). The
pinned `experiments/e1/data/topology.json` (SHA-256-checked, shared by the original
E1 100-case and E2 48-case benchmarks) only allows `s4` ports `[1,2,5]` and does not
model this. Rather than edit that pinned fixture or the two affected gold cases
(`SFC-B05`, `SFC-B09`), this extension uses its own
`experiments/e1/data/topology_diamond.json`. The original topology and its dependent
benchmarks are untouched.

## New IR fields

`sfc` rules carry `sfc_role: "ingress"|"transit"|"egress"`; an accepted program
containing an `sfc` rule additionally carries a top-level `sfc_chain: list[str]`
naming the waypoints between rules as `"device[:port]"` tokens, one per hop. `reroute`
rules reuse the forwarding selector/enforcement shape; `enforcement.avoid_device` is
available (unused by any gold case here) for cases that must express a path
constraint. See `safe_intent_sdn/validator.py`'s `path` finding category for the
corresponding static checks.

## Gold status and known limitation

Gold status: **provisional**, same caveat as the base benchmark — these are
pipeline-fixture annotations, not independently adjudicated labels. The
`SYSTEM_IR` prompt in `experiments/e1/run_experiment.py` only describes `sfc`/`reroute`
semantics when `translation_experiment.dataset_path` points at
`intents_sfc_reroute.jsonl` (see `SFC_REROUTE_ADDENDUM`), so the original benchmark's
prompt text — and therefore its existing collected logs' reproducibility — is
unaffected by this extension.
