"""Figure: exact-match rate by request category on the SFC/reroute extension
benchmark, showing that `sfc` collapses to 0% across every treatment while
the four base categories improve the same way they did in the original E1.

Data source: `paper/experiment_protocol/e1_rationale_sfc_reroute_addendum.md`
lines 64-69 (Table in "3. 카테고리별 분해"). Like the slot-level breakdown,
this category-level rescoring is a one-off diagnostic pass not persisted in
`logs/e1/e1_sfc_reroute_aggregate_full.json`, so it is transcribed here.

Renders both an English figure (`e1_sfc_reroute_category_collapse.*`) and a
Korean-labeled one (`e1_sfc_reroute_category_collapse_ko.*`).

Usage: uv run --group plots python paper/scripts/plot_e1_sfc_reroute_category.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from plotstyle import TREATMENT_COLOR, TREATMENT_LABEL, apply_paper_style

ROOT = Path(__file__).resolve().parents[2]
OUT_STEM = ROOT / "paper/figures/e1_sfc_reroute_category_collapse"

# transcribed from paper/experiment_protocol/e1_rationale_sfc_reroute_addendum.md:64-69
# (exact-match column of each "schema/exact" cell)
CATEGORY_EXACT_MATCH = {
    "en": {
        "forwarding (15)": {"E1-B": 0.120, "E1-C": 0.333, "E1-D": 0.320},
        "security (15)": {"E1-B": 0.253, "E1-C": 0.667, "E1-D": 0.613},
        "qos (10)": {"E1-B": 0.300, "E1-C": 0.400, "E1-D": 0.300},
        "sfc (25)": {"E1-B": 0.000, "E1-C": 0.000, "E1-D": 0.000},
        "reroute (25)": {"E1-B": 0.000, "E1-C": 0.000, "E1-D": 0.080},
    },
    "ko": {
        "단순 전달 (15)": {"E1-B": 0.120, "E1-C": 0.333, "E1-D": 0.320},
        "보안 (15)": {"E1-B": 0.253, "E1-C": 0.667, "E1-D": 0.613},
        "QoS (10)": {"E1-B": 0.300, "E1-C": 0.400, "E1-D": 0.300},
        "SFC (25)": {"E1-B": 0.000, "E1-C": 0.000, "E1-D": 0.000},
        "우회 경로 (25)": {"E1-B": 0.000, "E1-C": 0.000, "E1-D": 0.080},
    },
}
HIGHLIGHTED_PREFIXES = {
    "en": ("sfc", "reroute"),
    "ko": ("SFC", "우회"),
}
TREATMENTS = ["E1-B", "E1-C", "E1-D"]

TEXT = {
    "en": {
        "ylabel": "Normalized exact match",
        "title": "SFC/reroute extension: base categories improve, sfc collapses to 0%",
    },
    "ko": {
        "ylabel": "정규화된 완전 일치율",
        "title": "SFC/우회 확장: 기존 카테고리는 개선되지만 SFC는 0%로 붕괴",
    },
}


def render(lang: str) -> None:
    apply_paper_style(lang)
    fig, ax = plt.subplots(figsize=(9, 4.5))

    categories = list(CATEGORY_EXACT_MATCH[lang].keys())
    n_treatments = len(TREATMENTS)
    group_width = 0.8
    bar_width = group_width / n_treatments
    x = np.arange(len(categories))

    for i, treatment in enumerate(TREATMENTS):
        means = [CATEGORY_EXACT_MATCH[lang][cat][treatment] for cat in categories]
        offset = (i - (n_treatments - 1) / 2) * bar_width
        ax.bar(
            x + offset,
            means,
            bar_width * 0.9,
            color=TREATMENT_COLOR[treatment],
            label=TREATMENT_LABEL[lang][treatment],
        )

    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=15, ha="right")
    ax.set_ylabel(TEXT[lang]["ylabel"])
    ax.set_ylim(0, 0.75)
    ax.set_title(TEXT[lang]["title"])
    for i, cat in enumerate(categories):
        if cat.startswith(HIGHLIGHTED_PREFIXES[lang]):
            ax.axvspan(i - 0.4, i + 0.4, color="#D55E00", alpha=0.06, zorder=0)
    ax.legend(loc="upper left", frameon=False)

    fig.tight_layout()
    stem = OUT_STEM if lang == "en" else OUT_STEM.with_name(OUT_STEM.name + "_ko")
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".png"), bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {stem}.pdf and .png")


def main() -> None:
    render("en")
    render("ko")


if __name__ == "__main__":
    main()
