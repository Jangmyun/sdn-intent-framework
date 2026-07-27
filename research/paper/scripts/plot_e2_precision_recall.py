"""Figure: compiler-only (B1') vs validator+compiler (B2') recall on the two
E2 component-level conformance benchmarks (original 48-case and the 65-case
SFC/reroute "E2-Path" extension). Precision is 1.00 for both treatments in
both benchmarks whenever it is defined (see the reports' `precision: null`
for B1' on E2-Path, where B1' rejects nothing), so this figure plots recall,
which is where the validator's incremental value actually shows up.

Data source (ground truth, not transcribed):
`logs/e2/20260717T120019/original_report.json` and
`logs/e2/20260717T120019/sfc_reroute_report.json`.

Renders both an English figure (`e2_recall_b1_vs_b2.*`) and a Korean-labeled
one (`e2_recall_b1_vs_b2_ko.*`) from the same data.

Usage: uv run --group plots python paper/scripts/plot_e2_precision_recall.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from plotstyle import BASELINE_COLOR, VALIDATOR_COLOR, apply_paper_style

ROOT = Path(__file__).resolve().parents[2]
E2_REPORT = ROOT / "logs/e2/20260717T120019/original_report.json"
E2_PATH_REPORT = ROOT / "logs/e2/20260717T120019/sfc_reroute_report.json"
OUT_STEM = ROOT / "paper/figures/e2_recall_b1_vs_b2"

TEXT = {
    "en": {
        "benchmarks": ["E2\n(48 fixtures)", "E2-Path\n(65 fixtures)"],
        "b1_label": "B1' (compiler only)",
        "b2_label": "B2' (validator + compiler)",
        "ylabel": "Case-level recall on defect-positive fixtures",
        "title": (
            "Static validator recall vs. compiler-only baseline\n"
            "(component-level conformance, not end-to-end LLM eval)"
        ),
    },
    "ko": {
        "benchmarks": ["E2\n(48개 fixture)", "E2-Path\n(65개 fixture)"],
        "b1_label": "B1′ (Compiler만)",
        "b2_label": "B2′ (Validator + Compiler)",
        "ylabel": "결함 양성(defect-positive) 사례에 대한 case-level recall",
        "title": (
            "정적 Validator recall vs compiler-only baseline\n"
            "(구성요소 단위 적합성 평가이며 전체 LLM 파이프라인 평가가 아님)"
        ),
    },
}


def render(lang: str, b1_recall: list[float], b2_recall: list[float]) -> None:
    text = TEXT[lang]
    apply_paper_style(lang)
    fig, ax = plt.subplots(figsize=(6, 4.5))
    x = np.arange(len(text["benchmarks"]))
    bar_width = 0.32

    bars1 = ax.bar(x - bar_width / 2, b1_recall, bar_width, color=BASELINE_COLOR, label=text["b1_label"])
    bars2 = ax.bar(x + bar_width / 2, b2_recall, bar_width, color=VALIDATOR_COLOR, label=text["b2_label"])

    for bars in (bars1, bars2):
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height:.2f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                fontsize=9,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(text["benchmarks"])
    ax.set_ylabel(text["ylabel"])
    ax.set_ylim(0, 1.15)
    ax.set_title(text["title"])
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=False)

    fig.tight_layout()
    stem = OUT_STEM if lang == "en" else OUT_STEM.with_name(OUT_STEM.name + "_ko")
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".png"), bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {stem}.pdf and .png")


def main() -> None:
    for path in (E2_REPORT, E2_PATH_REPORT):
        if not path.exists():
            raise SystemExit(
                f"{path} not found — regenerate it first with "
                "`experiments/e2/run_validation.py` + `experiments/e2/score.py` "
                "(see paper/experiment_protocol/e2_rationale.md)."
            )

    e2 = json.loads(E2_REPORT.read_text())
    e2_path = json.loads(E2_PATH_REPORT.read_text())
    b1_recall = [e2["B1"]["any_defect"]["recall"], e2_path["B1"]["any_defect"]["recall"]]
    b2_recall = [e2["B2"]["any_defect"]["recall"], e2_path["B2"]["any_defect"]["recall"]]

    render("en", b1_recall, b2_recall)
    render("ko", b1_recall, b2_recall)


if __name__ == "__main__":
    main()
