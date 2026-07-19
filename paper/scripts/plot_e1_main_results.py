"""Figure: E1 Table 4 metrics (schema validity / exact match / rule-count /
type accuracy / hallucination rate) across the four translation treatments.

Data source (ground truth, not transcribed): `logs/e1/e1_aggregate_full.json`,
the same file `paper/result_tables/e1_results.md` Table 4 (lines 27-35) was
computed from. Error bars are the run-to-run `sample_sd` across the 5 paired
repetitions (see `e1_results.md` lines 41-46 on run-to-run variation).

Usage: uv run --group plots python paper/scripts/plot_e1_main_results.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from plotstyle import TREATMENT_COLOR, TREATMENT_LABEL, apply_paper_style

ROOT = Path(__file__).resolve().parents[2]
AGGREGATE_PATH = ROOT / "logs/e1/e1_aggregate_full.json"
OUT_STEM = ROOT / "paper/figures/e1_table4_metrics"

METRICS = [
    ("response_schema_validity", "Schema\nvalidity"),
    ("normalized_exact_match", "Exact\nmatch"),
    ("normalized_rule_count_accuracy", "Rule-count\naccuracy"),
    ("normalized_type_accuracy", "Type\naccuracy"),
    ("hallucinated_entity_rate", "Hallucinated\nentity rate"),
]
TREATMENTS = ["E1-A", "E1-B", "E1-C", "E1-D"]


def main() -> None:
    if not AGGREGATE_PATH.exists():
        raise SystemExit(
            f"{AGGREGATE_PATH} not found — regenerate it first with "
            "`experiments/e1/score.py` (see paper/result_tables/e1_results.md line 5-9)."
        )
    data = json.loads(AGGREGATE_PATH.read_text())["treatments"]

    apply_paper_style()
    fig, ax = plt.subplots(figsize=(9, 4.5))

    n_treatments = len(TREATMENTS)
    n_metrics = len(METRICS)
    group_width = 0.8
    bar_width = group_width / n_treatments
    x = np.arange(n_metrics)

    for i, treatment in enumerate(TREATMENTS):
        means = [data[treatment][key]["mean"] for key, _ in METRICS]
        sds = [data[treatment][key]["sample_sd"] for key, _ in METRICS]
        offset = (i - (n_treatments - 1) / 2) * bar_width
        bars = ax.bar(
            x + offset,
            means,
            bar_width * 0.9,
            yerr=sds,
            capsize=3,
            color=TREATMENT_COLOR[treatment],
            label=TREATMENT_LABEL[treatment],
        )
        if treatment == "E1-A":
            for bar in bars:
                bar.set_hatch("///")
                bar.set_edgecolor("white")

    ax.set_xticks(x)
    ax.set_xticklabels([label for _, label in METRICS])
    ax.set_ylabel("Score (mean of 5 runs)")
    ax.set_ylim(0, 1.05)
    ax.set_title("E1: intent-translation metrics by treatment (100-case benchmark)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=4, frameon=False)
    ax.annotate(
        "A = direct ONOS output; hatched bars are not directly comparable\n"
        "to B/C/D due to a task-equivalence confound (e1_results.md:20-25)",
        xy=(0.5, 1.0),
        xycoords="axes fraction",
        xytext=(0, 22),
        textcoords="offset points",
        ha="center",
        fontsize=8,
        color="#555555",
    )

    fig.tight_layout()
    fig.savefig(OUT_STEM.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(OUT_STEM.with_suffix(".png"), bbox_inches="tight")
    print(f"wrote {OUT_STEM}.pdf and .png")


if __name__ == "__main__":
    main()
