"""레포 루트 진입점 — 실제 구현은 src/xai_pipeline/main.py에 있다.

uv run python main.py --intent "..."
"""
from xai_pipeline.main import main

if __name__ == "__main__":
    raise SystemExit(main())
