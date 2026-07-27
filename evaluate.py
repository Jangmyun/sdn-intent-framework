"""레포 루트 진입점 — 실제 구현은 src/xai_pipeline/evaluate.py에 있다.

uv run python evaluate.py [--limit N] [--skip-llm] [--category sfc]
"""
from xai_pipeline.evaluate import main

if __name__ == "__main__":
    raise SystemExit(main())
