"""Shared matplotlib style for paper figures.

Colorblind-safe qualitative palette (Okabe-Ito). Keep every figure script
importing from here so treatment colors stay consistent across the paper.

Every figure is rendered in both English (default) and Korean (`_ko` file
suffix, `lang="ko"`) so the plotting scripts double as the source of the
Korean-labeled versions used in lab-meeting slides. Korean rendering needs a
Hangul-capable font, which most CI/base images lack, so this module bundles
`fonts/NanumGothic-Regular.ttf` (SIL OFL-1.1, `fonts/OFL.txt`) rather than
depending on whatever happens to be installed on the machine running the
script.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

TREATMENT_COLOR = {
    "E1-A": "#999999",  # grey: direct ONOS output, not a valid comparator (see caveats)
    "E1-B": "#56B4E9",  # sky blue: IR, zero-shot
    "E1-C": "#009E73",  # green: IR, few-shot
    "E1-D": "#D55E00",  # vermillion: IR, few-shot + topology grounding
}

TREATMENT_LABEL = {
    "en": {
        "E1-A": "A: direct flow",
        "E1-B": "B: IR (zero-shot)",
        "E1-C": "C: IR (few-shot)",
        "E1-D": "D: IR (few-shot+grounded)",
    },
    "ko": {
        "E1-A": "A: 직접 생성",
        "E1-B": "B: IR (zero-shot)",
        "E1-C": "C: IR (few-shot)",
        "E1-D": "D: IR (few-shot+topology)",
    },
}

BASELINE_COLOR = "#999999"  # compiler-only (B1')
VALIDATOR_COLOR = "#0072B2"  # validator+compiler (B2')

FIGURE_DPI = 300

_FONTS_DIR = Path(__file__).resolve().parent / "fonts"
_KOREAN_FONT_PATH = _FONTS_DIR / "NanumGothic-Regular.ttf"
_KOREAN_FONT_REGISTERED = False


def _korean_font_family() -> str:
    global _KOREAN_FONT_REGISTERED
    if not _KOREAN_FONT_REGISTERED:
        fm.fontManager.addfont(str(_KOREAN_FONT_PATH))
        _KOREAN_FONT_REGISTERED = True
    return fm.FontProperties(fname=str(_KOREAN_FONT_PATH)).get_name()


def apply_paper_style(lang: str = "en") -> None:
    """Reset rcParams for one figure. Call once per figure, per language."""
    plt.rcParams.update(plt.rcParamsDefault)
    rc = {
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
    if lang == "ko":
        rc["font.family"] = _korean_font_family()
        rc["axes.unicode_minus"] = False
    elif lang != "en":
        raise ValueError(f"unknown lang {lang!r}, expected 'en' or 'ko'")
    plt.rcParams.update(rc)
