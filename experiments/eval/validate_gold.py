"""
experiments/eval/validate_gold.py - Gold Validation

Gold JSON for accepted cases is passed through Stage 2 (FlowRule compiler)
to verify the gold itself is correct.

Usage:
    python experiments/eval/validate_gold.py
    python experiments/eval/validate_gold.py --dataset experiments/eval/data/intents_eval_large.jsonl
    python experiments/eval/validate_gold.py --large
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

from models.intent_ir import IntentIR, CompoundIntentIR
from stage2_flowrule.compiler import compile_flowrule, compile_compound, CompileError


def gold_to_ir(gold: dict) -> IntentIR | CompoundIntentIR:
    """
    gold dict -> IntentIR or CompoundIntentIR.

    Single rule: pass gold directly to IntentIR.from_llm_output().
    Compound rule: convert each element of gold["rules"] to IntentIR,
                   then build CompoundIntentIR.
    """
    if "rules" in gold:
        rules = [IntentIR.from_llm_output(r) for r in gold["rules"]]
        return CompoundIntentIR(rules=rules, description="gold-validation")
    else:
        return IntentIR.from_llm_output(gold)


def compile_ir(ir: IntentIR | CompoundIntentIR) -> dict:
    """Compile IR to FlowRule (dispatches single vs compound)"""
    if isinstance(ir, CompoundIntentIR):
        return compile_compound(ir)
    return compile_flowrule(ir)


def _flow_summary(flowrule: dict) -> str:
    """Brief summary of compiled FlowRule (device, flow count)"""
    flows = flowrule.get("flows", [])
    if not flows:
        return "(no flows)"
    devices = list({f.get("deviceId", "?") for f in flows})
    return f"{len(flows)} flow(s) on {devices}"


def validate(dataset_path: Path) -> list[dict]:
    cases = [json.loads(l) for l in dataset_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    accepted = [c for c in cases if c["gold"]["status"] == "accepted"]

    results = []
    for case in accepted:
        cid      = case["case_id"]
        category = case["category"]
        gold     = case["gold"]
        action   = gold.get("action") or "compound"

        try:
            ir       = gold_to_ir(gold)
            flowrule = compile_ir(ir)
            results.append({
                "case_id":  cid,
                "category": category,
                "action":   action,
                "status":   "PASS",
                "detail":   _flow_summary(flowrule),
                "error":    None,
            })
        except Exception as exc:
            results.append({
                "case_id":  cid,
                "category": category,
                "action":   action,
                "status":   "FAIL",
                "detail":   None,
                "error":    str(exc),
            })

    return results


def print_report(results: list[dict], dataset_path: Path) -> None:
    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] == "FAIL"]

    print(f"\n{'='*65}")
    print(f"  Gold Validation - {dataset_path.name}")
    print(f"  Accepted cases: {len(results)}  |  PASS: {len(passed)}  |  FAIL: {len(failed)}")
    print(f"{'='*65}")

    if failed:
        print("\n[FAIL cases]")
        for r in failed:
            print(f"  FAIL  {r['case_id']:<12} ({r['category']:<10} / {r['action']:<8})  {r['error']}")

    print("\n[PASS cases]")
    for r in passed:
        print(f"  PASS  {r['case_id']:<12} ({r['category']:<10} / {r['action']:<8})  {r['detail']}")

    from collections import Counter
    cat_fail = Counter(r["category"] for r in failed)
    print(f"\n[Category summary]")
    cats = sorted({r["category"] for r in results})
    for cat in cats:
        cat_results = [r for r in results if r["category"] == cat]
        n_pass = sum(1 for r in cat_results if r["status"] == "PASS")
        n_fail = sum(1 for r in cat_results if r["status"] == "FAIL")
        bar = "O" * n_pass + "X" * n_fail
        print(f"  {cat:<12}  {n_pass}/{n_pass+n_fail}  [{bar}]")

    print(f"\n{'='*65}")
    if failed:
        print(f"  Result: {len(failed)} FAIL(s) - gold needs fixing")
        sys.exit(1)
    else:
        print(f"  Result: ALL PASS - gold validation complete")
    print(f"{'='*65}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gold Validation - Stage 2 compile check")
    parser.add_argument(
        "--dataset",
        default="experiments/eval/data/intents_eval.jsonl",
        help="Dataset JSONL path (default: Small)",
    )
    parser.add_argument(
        "--large",
        action="store_true",
        help="Validate Large dataset (shortcut for --dataset)",
    )
    args = parser.parse_args()

    if args.large:
        dataset_path = ROOT / "experiments/eval/data/intents_eval_large.jsonl"
    else:
        dataset_path = ROOT / args.dataset

    if not dataset_path.exists():
        print(f"ERROR: File not found: {dataset_path}")
        sys.exit(1)

    results = validate(dataset_path)
    print_report(results, dataset_path)


if __name__ == "__main__":
    main()
