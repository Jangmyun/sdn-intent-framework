"""Aggregate E1 prediction logs into a run-aware evaluation report."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from safe_intent_sdn.e1_evaluation import EvaluationCase, PredictionRecord, aggregate_runs

def load_cases(path: Path) -> list[EvaluationCase]:
    return [EvaluationCase.model_validate_json(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

def load_records(paths: list[Path]) -> list[PredictionRecord]:
    records: list[PredictionRecord] = []
    for path in paths:
        records.extend(PredictionRecord.model_validate_json(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip())
    return records

def build_inventory(topology: dict) -> tuple[dict[str, str], set[str]]:
    aliases: dict[str, str] = {}
    inventory: set[str] = set()
    for entity in topology["entities"]:
        inventory.add(entity["id"])
        for alias in entity["aliases"]:
            aliases[alias] = entity["id"]
    return aliases, inventory

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "experiments/e1/data/intents.jsonl")
    parser.add_argument("--topology", type=Path, default=ROOT / "experiments/e1/data/topology.json")
    parser.add_argument("--cohort", choices=["upstream", "project_authored"], help="restrict scoring to one dataset cohort")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("files", nargs="+", type=Path, help="prediction JSONL files to aggregate")
    args = parser.parse_args()
    cases = load_cases(args.dataset)
    if args.cohort: cases = [c for c in cases if c.cohort == args.cohort]
    case_ids = {c.id for c in cases}
    records = [r for r in load_records(args.files) if r.case_id in case_ids]
    aliases, inventory = build_inventory(json.loads(args.topology.read_text(encoding="utf-8")))
    report = aggregate_runs(cases, records, aliases=aliases, inventory_entities=inventory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)

if __name__ == "__main__":
    main()
