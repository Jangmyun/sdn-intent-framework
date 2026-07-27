# An Explainable LLM-RAG Framework for Intent-Driven SDN Automation with Digital Twin Validation

> **Digital Twin 검증을 활용한 설명가능한 LLM 및 RAG 기반 Intent-Driven SDN 자동화 프레임워크**

자연어 네트워크 운영 의도를 검증된 SDN 정책으로 변환하고, 실제 네트워크에 배포하기 전에 Digital Twin 환경에서 안전성을 사전 검증하는 폐루프형 SDN 자동화 프레임워크입니다.

## Repository Layout

이 레포는 서로 독립적인 두 시스템을 담고 있습니다.

| | 파이프라인 앱 (레포 루트) | 논문 재현 트랙 (`research/`) |
|---|---|---|
| 역할 | 자연어 인텐트 → ONOS FlowRule End-to-End 변환·배포 (LLM/RAG, Digital Twin, XAI, Web UI) | E1~E3 및 gold 데이터셋 실험, 논문 figure/table 생성 |
| 진입점 | `main.py` (CLI), `api.py` (FastAPI) | `research/main.py` |
| 의존성 | `requirements.txt` (pip) | `research/pyproject.toml` (uv) |
| 테스트 | `pytest` (루트 `tests/`) | `cd research && uv run pytest -q` |
| 문서 | [Pipeline Guide](docs/PIPELINE_GUIDE.md) | [`research/AGENTS.md`](research/AGENTS.md) |

두 시스템은 레포 루트의 `.env` 하나를 공유합니다 (파이프라인은 `LLM_*`/`ONOS_*`,
연구 트랙은 `SAFE_SDN_*` 접두사 사용). 템플릿은 [`.env.example`](.env.example) 참고.

## Quickstart — 파이프라인 앱

```bash
pip install -r requirements.txt
cp .env.example .env        # 값 채우기
uvicorn api:app --reload --port 8000
```

자세한 사용법은 [Pipeline Guide](docs/PIPELINE_GUIDE.md)를 참고하세요.

## Quickstart — 논문 재현 트랙

```bash
cd research
uv sync --locked
./scripts/installation/setup.sh
./scripts/installation/doctor.sh
./scripts/smoke_test.sh
```

자세한 설치 및 환경 관리 방법은
[Installation Guide](research/scripts/installation/README.md)를 참고하세요.
