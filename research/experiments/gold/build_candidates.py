"""Build the GOLD-350 candidate dataset.

Outputs:
    data/candidates.jsonl        350 cases with author-intended labels and gold programs.
    data/blind/instructions.jsonl  blind_id + instruction only, deterministically shuffled,
                                   for independent annotators (no category leakage).
    data/blind/id_map.json       blind_id -> case id (adjudication key; not for annotators).
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from safe_intent_sdn.e1_evaluation import EvaluationCase

from cases import compound, forwarding, qos_cases, rejected, reroute_cases, security, sfc

DATA = Path(__file__).parent / "data"
SHUFFLE_SEED = 20260723
EXPECTED = Counter({
    "forwarding": 50, "security": 50, "qos": 50, "sfc": 50,
    "reroute": 50, "compound": 50, "ambiguous_unsupported": 50,
})


def build() -> list[dict]:
    cases = (forwarding.CASES + security.CASES + qos_cases.CASES + sfc.CASES
             + reroute_cases.CASES + compound.CASES + rejected.CASES)
    for case in cases:
        EvaluationCase.model_validate(case)

    ids = [c["id"] for c in cases]
    if len(set(ids)) != len(cases):
        raise ValueError("case IDs must be unique")
    instructions = [c["instruction"] for c in cases]
    duplicates = [text for text, n in Counter(instructions).items() if n > 1]
    if duplicates:
        raise ValueError(f"duplicate instructions: {duplicates}")

    distribution = Counter(c["category"] for c in cases)
    if distribution != EXPECTED:
        raise ValueError(f"category distribution mismatch: {distribution}")

    for case in cases:
        if case["category"] == "compound" and len(case["expected"]["program"]["rules"]) < 2:
            raise ValueError(f"{case['id']}: compound case must have >= 2 rules")
        if case["category"] not in ("compound", "sfc") and case["expected"]["status"] == "accepted":
            if len(case["expected"]["program"]["rules"]) != 1:
                raise ValueError(f"{case['id']}: single-policy case must have exactly 1 rule")
    return cases


def main() -> None:
    cases = build()
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "blind").mkdir(exist_ok=True)

    target = DATA / "candidates.jsonl"
    target.write_text(
        "".join(json.dumps(c, separators=(",", ":"), ensure_ascii=False) + "\n" for c in cases),
        encoding="utf-8",
    )

    shuffled = list(cases)
    random.Random(SHUFFLE_SEED).shuffle(shuffled)
    blind_rows = [{"blind_id": f"B{i:03d}", "instruction": c["instruction"]}
                  for i, c in enumerate(shuffled, start=1)]
    id_map = {row["blind_id"]: c["id"] for row, c in zip(blind_rows, shuffled)}

    (DATA / "blind" / "instructions.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in blind_rows), encoding="utf-8")
    (DATA / "blind" / "id_map.json").write_text(
        json.dumps(id_map, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {target} ({len(cases)} cases)")
    print(f"wrote {DATA / 'blind' / 'instructions.jsonl'} ({len(blind_rows)} rows)")


if __name__ == "__main__":
    main()
