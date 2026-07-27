# GOLD-350 Dataset Card

350 English SDN intent instructions, balanced at 50 cases across seven
categories: `forwarding`, `security`, `qos`, `sfc`, `reroute`, `compound`,
and `ambiguous_unsupported`. Semantic gold is an ordered `IntentProgram`
(`EvaluationCase` schema), an independent project annotation under the fixed
topology in `paper/experiment_protocol/gold_dataset_protocol.md` §2 — not an
official NetIntent or ONOS label.

## Composition

| category | n | status |
|----------|---|--------|
| forwarding | 50 | accepted |
| security | 50 | accepted |
| qos | 50 | accepted |
| sfc | 50 | accepted (≥2 rules, `sfc_chain` set) |
| reroute | 50 | accepted |
| compound | 50 | accepted (≥2 rules) |
| ambiguous_unsupported | 50 | rejected (ambiguous 15, unknown_entity 15, contradictory 10, unsupported 10) |

## Gold status: **adjudicated (LLM double-annotation)**

Gold labels were fixed by independent double labeling plus adjudication, per
`paper/experiment_protocol/gold_dataset_protocol.md`:

- Two independent annotator sessions labeled a blind split (instruction text
  only, category and program withheld). Cohen's κ = **1.000** on category
  (7-way), status, and rejection reason; **0** inter-annotator disagreements.
- Validation against author-intended labels found 2 divergences (both
  multi-hop SFC cases whose wording failed to invoke a service role). These
  were resolved by revising the instruction text to invoke the service
  function; they are marked `source="adjudicated"` in
  `annotations/final_labels.jsonl` (the other 348 are `unanimous`).

**Known limitation.** Annotators are independent LLM agent sessions sharing
one detailed guideline, not human experts. κ = 1.0 demonstrates reproducibility
under a decisive guideline, not human inter-annotator agreement, and does not
replace it. Gold programs depend on the assumed topology and are not official
upstream labels.

## Files

| path | contents |
|------|----------|
| `data/gold.jsonl` | final 350 gold cases (`EvaluationCase`) |
| `data/candidates.jsonl` | author-intended cases with gold programs |
| `data/blind/instructions.jsonl` | blind_id + instruction only (annotator input) |
| `data/blind/id_map.json` | blind_id → case id (adjudication key) |
| `annotations/annotator_a.jsonl`, `annotator_b.jsonl` | independent labels |
| `annotations/final_labels.jsonl` | adjudicated labels with `source` |
| `annotations/disagreements.json` | inter-annotator disagreements (empty) |
| `ANNOTATION_GUIDELINE.md` | v1.0 labeling rules |

## Reproduce

```bash
.venv/bin/python experiments/gold/build_candidates.py
.venv/bin/python experiments/gold/compute_agreement.py \
    experiments/gold/annotations/annotator_a.jsonl \
    experiments/gold/annotations/annotator_b.jsonl
.venv/bin/python experiments/gold/build_gold.py
.venv/bin/python -m pytest tests/test_gold_dataset.py -q
```
