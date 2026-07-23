"""Compute inter-annotator agreement for the GOLD-350 labeling.

Usage:
    python compute_agreement.py annotations/annotator_a.jsonl annotations/annotator_b.jsonl

Prints Cohen's kappa for category (7-way), status (2-way), and rejection
reason (over cases both annotators rejected), plus raw agreement, the
confusion matrix, and writes disagreements to annotations/disagreements.json.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

CATEGORIES = ("forwarding", "security", "qos", "sfc", "reroute", "compound", "ambiguous_unsupported")
REASONS = ("ambiguous", "contradictory", "unknown_entity", "unsupported")


def load(path: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    out = {}
    for row in rows:
        if row["category"] not in CATEGORIES:
            raise ValueError(f"{path}: invalid category {row['category']!r} for {row['blind_id']}")
        rejected = row["category"] == "ambiguous_unsupported"
        if (row["status"] == "rejected") != rejected:
            raise ValueError(f"{path}: status/category mismatch for {row['blind_id']}")
        if rejected and row.get("rejection_reason") not in REASONS:
            raise ValueError(f"{path}: invalid reason for {row['blind_id']}")
        out[row["blind_id"]] = row
    return out


def cohen_kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    if n == 0:
        return float("nan")
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def main() -> None:
    path_a, path_b = Path(sys.argv[1]), Path(sys.argv[2])
    a, b = load(path_a), load(path_b)
    if set(a) != set(b):
        raise ValueError(f"blind_id sets differ: only_a={sorted(set(a) - set(b))[:5]} only_b={sorted(set(b) - set(a))[:5]}")
    ids = sorted(a)

    cat_pairs = [(a[i]["category"], b[i]["category"]) for i in ids]
    status_pairs = [(a[i]["status"], b[i]["status"]) for i in ids]
    reason_pairs = [(a[i]["rejection_reason"], b[i]["rejection_reason"]) for i in ids
                    if a[i]["status"] == "rejected" and b[i]["status"] == "rejected"]

    agree = sum(1 for x, y in cat_pairs if x == y)
    print(f"cases: {len(ids)}")
    print(f"category raw agreement: {agree}/{len(ids)} = {agree / len(ids):.4f}")
    print(f"category Cohen's kappa: {cohen_kappa(cat_pairs):.4f}")
    print(f"status Cohen's kappa:   {cohen_kappa(status_pairs):.4f}")
    print(f"reason Cohen's kappa (both rejected, n={len(reason_pairs)}): {cohen_kappa(reason_pairs):.4f}")

    confusion = Counter(cat_pairs)
    print("\nconfusion (A x B), disagreements only:")
    for (ka, kb), n in confusion.most_common():
        if ka != kb:
            print(f"  A={ka:<22} B={kb:<22} {n}")

    disagreements = [
        {"blind_id": i, "a": {k: a[i][k] for k in ("category", "status", "rejection_reason", "rationale")},
         "b": {k: b[i][k] for k in ("category", "status", "rejection_reason", "rationale")}}
        for i in ids
        if a[i]["category"] != b[i]["category"]
        or a[i]["status"] != b[i]["status"]
        or (a[i]["status"] == "rejected" and b[i]["status"] == "rejected"
            and a[i]["rejection_reason"] != b[i]["rejection_reason"])
    ]
    out = path_a.parent / "disagreements.json"
    out.write_text(json.dumps(disagreements, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {out} ({len(disagreements)} disagreement cases)")


if __name__ == "__main__":
    main()
