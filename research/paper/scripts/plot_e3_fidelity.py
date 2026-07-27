"""Figure: reach-only twin (twin_nobw) vs bandwidth-probing twin (twin_bw) false
positive rate per intent category on the E3 twin-fidelity benchmark.

fpr is the dangerous wrong-approval rate: the fraction of policies that fail in
the (emulated) production deployment that the twin nevertheless approves. The
reach-only twin's blind spot is QoS requests that exceed the link's physical
capacity -- reachable but below target no matter how the queue is configured --
which the bandwidth probe eliminates. Categories with no
defect-positive (SHOULD_FAIL) case have an undefined fpr and are omitted.

Data source (ground truth, not transcribed):
`logs/e3/e3_fidelity.json` (experiments/e3/score.py output).

Renders both an English figure (`e3_fpr_nobw_vs_bw.*`) and a Korean-labeled one
(`e3_fpr_nobw_vs_bw_ko.*`) from the same data.

Usage: uv run --group plots python paper/scripts/plot_e3_fidelity.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from plotstyle import BASELINE_COLOR, VALIDATOR_COLOR, apply_paper_style

ROOT = Path(__file__).resolve().parents[2]
E3_REPORT = ROOT / "logs/e3/e3_fidelity.json"
OUT_STEM = ROOT / "paper/figures/e3_fpr_nobw_vs_bw"

TEXT = {
    "en": {
        "nobw_label": "twin_nobw (reachability only)",
        "bw_label": "twin_bw (+ bandwidth probe)",
        "acc_ylabel": "Agreement with ground truth (accuracy)",
        "fpr_ylabel": "False positive rate (wrong approvals)",
        "acc_title": "(a) Fidelity by intent category",
        "fpr_title": "(b) Wrong-approval rate",
        "overall": "overall",
        "nodefect": "no reject-case",
        "title": (
            "Digital Twin decision fidelity vs emulated ground truth\n"
            "(reachability-only twin vs twin with bandwidth probe)"
        ),
    },
    "ko": {
        "nobw_label": "twin_nobw (도달성만)",
        "bw_label": "twin_bw (+ 대역폭 프로브)",
        "acc_ylabel": "Ground truth 일치율 (정확도)",
        "fpr_ylabel": "거짓 양성률 (잘못된 승인)",
        "acc_title": "(a) 인텐트 카테고리별 충실도",
        "fpr_title": "(b) 오승인율",
        "overall": "전체",
        "nodefect": "거부 사례 없음",
        "title": (
            "에뮬레이트 ground truth 대비 Digital Twin 결정 충실도\n"
            "(도달성만 검사하는 Twin vs 대역폭 프로브를 더한 Twin)"
        ),
    },
}


def _series(report: dict, metric: str, *, defined_only: bool) -> tuple[list[str], list[float], list[float]]:
    """Pull ``metric`` for both arms, overall first then per category.

    ``defined_only`` drops categories where the metric is undefined for both
    arms -- fpr has no meaning in a category with no SHOULD_FAIL case, so those
    are omitted from the fpr panel but kept in the accuracy panel.
    """
    fidelity = report["fidelity"]
    nobw, bw = fidelity["twin_nobw"], fidelity["twin_bw"]
    labels = ["overall"]
    a_vals = [nobw["overall"][metric] or 0.0]
    b_vals = [bw["overall"][metric] or 0.0]
    for category in sorted(nobw["by_category"]):
        a, b = nobw["by_category"][category][metric], bw["by_category"][category][metric]
        if defined_only and a is None and b is None:
            continue
        labels.append(category)
        a_vals.append(a or 0.0)
        b_vals.append(b or 0.0)
    return labels, a_vals, b_vals


def _panel(ax, text, labels, nobw_vals, bw_vals, *, ylabel, title, zero_note=False) -> None:
    display = [text["overall"] if lbl == "overall" else lbl for lbl in labels]
    x = np.arange(len(labels))
    bar_width = 0.36
    bars1 = ax.bar(x - bar_width / 2, nobw_vals, bar_width, color=BASELINE_COLOR, label=text["nobw_label"])
    bars2 = ax.bar(x + bar_width / 2, bw_vals, bar_width, color=VALIDATOR_COLOR, label=text["bw_label"])
    for bars in (bars1, bars2):
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height:.2f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8,
            )
    ax.set_xticks(x)
    ax.set_xticklabels(display, rotation=20, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, 1.18)
    ax.set_title(title, fontsize=11)


def render(lang: str, report: dict) -> None:
    text = TEXT[lang]
    apply_paper_style(lang)
    fig, (ax_acc, ax_fpr) = plt.subplots(1, 2, figsize=(10, 4.6))

    labels_a, nobw_a, bw_a = _series(report, "accuracy", defined_only=False)
    _panel(ax_acc, text, labels_a, nobw_a, bw_a,
           ylabel=text["acc_ylabel"], title=text["acc_title"])

    labels_f, nobw_f, bw_f = _series(report, "fpr", defined_only=True)
    _panel(ax_fpr, text, labels_f, nobw_f, bw_f,
           ylabel=text["fpr_ylabel"], title=text["fpr_title"])
    # Categories without a SHOULD_FAIL case have no fpr and are absent from (b);
    # say so rather than letting a reader think they scored zero.
    dropped = [l for l in labels_a if l not in labels_f]
    if dropped:
        ax_fpr.text(0.5, -0.34, f"{text['nodefect']}: {', '.join(dropped)}",
                    transform=ax_fpr.transAxes, ha="center", fontsize=8, color="#555555")

    handles, plot_labels = ax_acc.get_legend_handles_labels()
    fig.legend(handles, plot_labels, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.04))
    fig.suptitle(text["title"])
    fig.tight_layout(rect=(0, 0.03, 1, 0.99))

    stem = OUT_STEM if lang == "en" else OUT_STEM.with_name(OUT_STEM.name + "_ko")
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".png"), bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {stem}.pdf and .png")


def main() -> None:
    if not E3_REPORT.exists():
        raise SystemExit(
            f"{E3_REPORT} not found -- regenerate it first by running the three arms "
            "(experiments/e3/run_twin_fidelity.py --arm ...) then experiments/e3/score.py "
            "(see paper/experiment_protocol/e3_rationale.md)."
        )
    report = json.loads(E3_REPORT.read_text())
    render("en", report)
    render("ko", report)


if __name__ == "__main__":
    main()
