# Paper Figures

이 디렉터리의 PNG/PDF는 `paper/scripts/`의 스크립트로 재생성 가능합니다. 이미지 자체는 논문
제출물이므로 커밋하지만, 원본 실행 로그(`logs/e1/`, `logs/e2/`)는 재현 가능한 대용량
artifact이므로 계속 Git에서 무시합니다.

각 스크립트는 영문 그림과 함께 `_ko` 접미사가 붙은 한글 라벨 버전도 같은 실행에서 함께
생성합니다(예: `e1_table4_metrics.png` + `e1_table4_metrics_ko.png`). 한글 렌더링은
`paper/scripts/fonts/NanumGothic-Regular.ttf`(SIL OFL-1.1, 같은 폴더의 `OFL.txt` 참고)를
번들로 포함해 사용하므로, 로컬에 한글 폰트가 없어도 동일하게 재현됩니다.

## 재생성

```bash
uv run --group plots python paper/scripts/plot_e1_main_results.py
uv run --group plots python paper/scripts/plot_e1_grounding_slots.py
uv run --group plots python paper/scripts/plot_e1_sfc_reroute_category.py
uv run --group plots python paper/scripts/plot_e2_precision_recall.py
```

`plot_e1_main_results.py`와 `plot_e2_precision_recall.py`는 `logs/e1/e1_aggregate_full.json`,
`logs/e2/20260717T120019/*.json`을 직접 읽으므로 해당 로그가 로컬에 있어야 합니다(각각
`experiments/e1/score.py`, `experiments/e2/run_validation.py` + `score.py`로 재생성).
`plot_e1_grounding_slots.py`와 `plot_e1_sfc_reroute_category.py`는 slot/category별 재채점이
아직 별도 스크립트로 커밋되어 있지 않아, `paper/result_tables/e1_results.md`와
`paper/experiment_protocol/e1_rationale_sfc_reroute_addendum.md`의 해당 표 값을 코드
주석에 출처를 남기고 transcribe한 것입니다 — 그 재채점 로직이 커밋되면 JSON을 직접 읽도록
바꿔야 합니다.

## Files

(`_ko` 접미사 버전은 아래 각 항목과 동일한 데이터의 한글 라벨 버전이라 표에서 생략)

| 파일 | 내용 | 근거 |
| --- | --- | --- |
| `e1_table4_metrics.*` | E1 Table 4: treatment별 5개 핵심 지표(오차막대=run-to-run sample_sd) | `logs/e1/e1_aggregate_full.json` |
| `e1_grounding_slots.*` | grounding이 `device` slot에 집중되는 효과 | `paper/result_tables/e1_results.md:110-120` |
| `e1_sfc_reroute_category_collapse.*` | SFC/reroute 확장에서 sfc만 전 조건 0%로 붕괴 | `paper/experiment_protocol/e1_rationale_sfc_reroute_addendum.md:64-69` |
| `e2_recall_b1_vs_b2.*` | E2/E2-Path에서 compiler-only 대비 validator recall | `logs/e2/20260717T120019/original_report.json`, `sfc_reroute_report.json` |
