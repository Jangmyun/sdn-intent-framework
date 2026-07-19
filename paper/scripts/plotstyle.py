"""Shared matplotlib style for paper figures.

Colorblind-safe qualitative palette (Okabe-Ito). Keep every figure script
importing from here so treatment colors stay consistent across the paper.
"""
from __future__ import annotations

import matplotlib.pyplot as plt

TREATMENT_COLOR = {
    "E1-A": "#999999",  # grey: direct ONOS output, not a valid comparator (see caveats)
    "E1-B": "#56B4E9",  # sky blue: IR, zero-shot
    "E1-C": "#009E73",  # green: IR, few-shot
    "E1-D": "#D55E00",  # vermillion: IR, few-shot + topology grounding
}

TREATMENT_LABEL = {
    "E1-A": "A: direct flow",
    "E1-B": "B: IR (zero-shot)",
    "E1-C": "C: IR (few-shot)",
    "E1-D": "D: IR (few-shot+grounded)",
}

BASELINE_COLOR = "#999999"  # compiler-only (B1')
VALIDATOR_COLOR = "#0072B2"  # validator+compiler (B2')

FIGURE_DPI = 300


def apply_paper_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": FIGURE_DPI,
            "savefig.dpi": FIGURE_DPI,
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.alpha": 0.3,
            "axes.axisbelow": True,
        }
    )
