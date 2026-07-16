"""Build the E2 case dataset: E1 gold accepted programs (clean) plus hand-authored
defective cases (reference/conflict/feasibility/multi). Fails closed on any drift
in the expected category distribution or duplicate case ids.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from safe_intent_sdn.e2_evaluation import E2Case

# First N accepted E1 gold cases per category, in dataset file order -- a fixed,
# reproducible selection rather than a hand-picked id list. compound is capped at 1
# (not 2) because E1's own documentation (experiments/e1/README.md) flags N039 as an
# incomplete upstream label (missing forwarding clause); it is excluded below so it
# doesn't masquerade as a true-negative fixture, leaving only N045 as a real compound
# accepted case. forwarding absorbs the one extra slot to keep the clean total at 20.
CLEAN_PER_CATEGORY = {"forwarding": 7, "security": 6, "qos": 6, "compound": 1}
KNOWN_INCOMPLETE_GOLD_IDS = {"N039"}
EXPECTED_DISTRIBUTION = Counter(
    {"clean": sum(CLEAN_PER_CATEGORY.values()), "reference": 8, "conflict": 9, "feasibility": 8, "multi": 3}
)


def select_clean_cases(intents_path: Path) -> list[E2Case]:
    rows = [json.loads(line) for line in intents_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    remaining = dict(CLEAN_PER_CATEGORY)
    selected: list[E2Case] = []
    for row in rows:
        category = row["category"]
        if row["id"] in KNOWN_INCOMPLETE_GOLD_IDS:
            continue
        if row["expected"]["status"] != "accepted" or remaining.get(category, 0) <= 0:
            continue
        remaining[category] -= 1
        selected.append(
            E2Case(
                id=f"clean-{row['id']}",
                category="clean",
                program=row["expected"]["program"],
            )
        )
    if any(remaining.values()):
        raise ValueError(f"could not fill clean quota: still need {remaining}")
    return selected


def load_defective_cases(path: Path) -> list[E2Case]:
    return [E2Case.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    e1_intents = ROOT / "experiments/e1/data/intents.jsonl"
    defective_path = ROOT / "experiments/e2/data/defective_authored.jsonl"
    output_path = ROOT / "experiments/e2/data/cases.jsonl"

    cases = select_clean_cases(e1_intents) + load_defective_cases(defective_path)

    distribution = Counter(c.category for c in cases)
    if distribution != EXPECTED_DISTRIBUTION:
        raise ValueError(f"unexpected category distribution: {dict(distribution)} != {dict(EXPECTED_DISTRIBUTION)}")
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case id")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(case.model_dump_json() + "\n")
    print(f"wrote {len(cases)} cases to {output_path}")


if __name__ == "__main__":
    main()
