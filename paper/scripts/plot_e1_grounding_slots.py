"""Figure: slot-level accuracy (E1-B/C/D) showing that topology grounding's
effect concentrates almost entirely on the `device` slot.

Data source: `paper/result_tables/e1_results.md` lines 110-116 (Table in
"2. Slot-level 분해"). That per-slot breakdown is a one-off diagnostic pass
over the same E1 logs and is not persisted in `logs/e1/e1_aggregate_full.json`,
so the numbers are transcribed here rather than recomputed — if the slot
breakdown is ever turned into a committed script output, point this file at
that JSON instead of the literal dict below.

Usage: uv run --group plots python paper/scripts/plot_e1_grounding_slots.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from plotstyle import TREATMENT_COLOR, TREATMENT_LABEL, apply_paper_style

ROOT = Path(__file__).resolve().parents[2]
OUT_STEM = ROOT / "paper/figures/e1_grounding_slots"

# transcribed from paper/result_tables/e1_results.md:110-116
SLOT_ACCURACY = {
    "device": {"E1-B": 0.382, "E1-C": 0.481, "E1-D": 0.924},
    "eth_type": {"E1-B": 0.526, "E1-C": 0.657, "E1-D": 0.582},
    "action": {"E1-B": 0.882, "E1-C": 0.877, "E1-D": 0.899},
    "egress_port": {"E1-B": 0.868, "E1-C": 0.963, "E1-D": 0.962},
}
TREATMENTS = ["E1-B", "E1-C", "E1-D"]


def main() -> None:
    apply_paper_style()
    fig, ax = plt.subplots(figsize=(8, 4.5))

    slots = list(SLOT_ACCURACY.keys())
    n_treatments = len(TREATMENTS)
    group_width = 0.8
    bar_width = group_width / n_treatments
    x = np.arange(len(slots))

    for i, treatment in enumerate(TREATMENTS):
        means = [SLOT_ACCURACY[slot][treatment] for slot in slots]
        offset = (i - (n_treatments - 1) / 2) * bar_width
        ax.bar(
            x + offset,
            means,
            bar_width * 0.9,
            color=TREATMENT_COLOR[treatment],
            label=TREATMENT_LABEL[treatment],
        )

    ax.set_xticks(x)
    ax.set_xticklabels(slots)
    ax.set_ylabel("Slot accuracy (100-case benchmark)")
    ax.set_ylim(0, 1.05)
    ax.set_title("E1: topology grounding's effect is concentrated in the `device` slot")
    ax.annotate(
        "device: 0.481 -> 0.924 (C -> D); other slots barely move\n"
        "(paper/result_tables/e1_results.md:118-120)",
        xy=(0.18, 0.93),
        xycoords="axes fraction",
        fontsize=8,
        color="#555555",
    )
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, frameon=False)

    fig.tight_layout()
    fig.savefig(OUT_STEM.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(OUT_STEM.with_suffix(".png"), bbox_inches="tight")
    print(f"wrote {OUT_STEM}.pdf and .png")


if __name__ == "__main__":
    main()
