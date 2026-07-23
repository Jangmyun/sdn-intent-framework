"""Finalize the GOLD-350 dataset from adjudicated labels.

Inputs:
    data/candidates.jsonl               author-intended cases (with gold programs)
    data/blind/id_map.json              blind_id -> case id
    annotations/final_labels.jsonl      adjudicated labels:
        {"blind_id", "category", "status", "rejection_reason", "source"}
        where source is "unanimous" | "reconciled" | "adjudicated".
    annotations/author_overrides.jsonl  (optional) full corrected EvaluationCase rows
        replacing candidates whose adjudicated label contradicted the author label.

Outputs:
    data/gold.jsonl          final gold cases (EvaluationCase schema).
    data/label_conflicts.json  cases where the adjudicated label disagrees with the
                               author label and no override exists (excluded from gold).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from safe_intent_sdn.e1_evaluation import EvaluationCase

ROOT = Path(__file__).parent
DATA = ROOT / "data"
ANN = ROOT / "annotations"


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    cases = {c["id"]: c for c in _jsonl(DATA / "candidates.jsonl")}
    id_map = json.loads((DATA / "blind" / "id_map.json").read_text(encoding="utf-8"))
    finals = {row["blind_id"]: row for row in _jsonl(ANN / "final_labels.jsonl")}
    overrides = {c["id"]: c for c in _jsonl(ANN / "author_overrides.jsonl")}

    if set(finals) != set(id_map):
        raise ValueError("final_labels.jsonl must cover every blind_id exactly once")

    gold: list[dict] = []
    conflicts: list[dict] = []
    sources = Counter()
    for blind_id, case_id in sorted(id_map.items()):
        case = cases[case_id]
        final = finals[blind_id]
        sources[final["source"]] += 1
        if case_id in overrides:
            replacement = overrides[case_id]
            if replacement["category"] != final["category"]:
                raise ValueError(f"override for {case_id} does not match adjudicated label")
            gold.append(replacement)
        elif final["category"] == case["category"]:
            gold.append(case)
        else:
            conflicts.append({
                "case_id": case_id, "blind_id": blind_id,
                "instruction": case["instruction"],
                "author_category": case["category"],
                "adjudicated": final,
            })

    for case in gold:
        EvaluationCase.model_validate(case)
    gold.sort(key=lambda c: c["id"])

    (DATA / "gold.jsonl").write_text(
        "".join(json.dumps(c, separators=(",", ":"), ensure_ascii=False) + "\n" for c in gold),
        encoding="utf-8")
    (DATA / "label_conflicts.json").write_text(
        json.dumps(conflicts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"gold cases: {len(gold)}")
    print(f"label sources: {dict(sources)}")
    print(f"category distribution: {dict(Counter(c['category'] for c in gold))}")
    print(f"unresolved label conflicts: {len(conflicts)} (see data/label_conflicts.json)")


if __name__ == "__main__":
    main()
