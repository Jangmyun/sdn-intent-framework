"""Build the E1-SFC/Reroute extension dataset: the existing 50 project-authored
forwarding/security/qos/ambiguous_unsupported cases (reused directly, not
re-vendored, so their equality with ``project_authored.jsonl`` is structural rather
than an assertion that could rot) plus 25 sfc and 25 reroute cases authored for this
extension. This is a separate benchmark from ``experiments/e1/data/intents.jsonl``
(the pinned 100-case upstream+authored benchmark) and never replaces it -- see
``experiments/e1/DATASET_CARD_SFC_REROUTE.md``.
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from safe_intent_sdn.e1_evaluation import EvaluationCase

DATA = Path(__file__).parent / "data"
BASE = DATA / "project_authored.jsonl"
EXTENSION = DATA / "project_authored_sfc_reroute.jsonl"
TARGET = DATA / "intents_sfc_reroute.jsonl"
EXPECTED = Counter({"forwarding": 15, "security": 15, "qos": 10, "ambiguous_unsupported": 10, "sfc": 25, "reroute": 25})


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def build() -> list[dict]:
    base = _jsonl(BASE)
    if len(base) != 50:
        raise ValueError("base project-authored cohort must contain 50 rows")
    extension = _jsonl(EXTENSION)
    if len(extension) != 50:
        raise ValueError("sfc/reroute extension cohort must contain 50 rows")

    cases = base + extension
    for case in cases:
        EvaluationCase.model_validate(case)

    ids = [c["id"] for c in cases]
    if len(set(ids)) != 100:
        raise ValueError("case IDs must be unique")

    distribution = Counter(c["category"] for c in cases)
    if distribution != EXPECTED:
        raise ValueError(f"category distribution mismatch: {distribution}")
    return cases


def main() -> None:
    TARGET.write_text(
        "".join(json.dumps(c, separators=(",", ":"), ensure_ascii=False) + "\n" for c in build()),
        encoding="utf-8",
    )
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
