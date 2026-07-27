# Research Track — 논문 재현 실험

`An Explainable LLM-RAG Framework for Intent-Driven SDN Automation with Digital Twin
Validation` 논문의 실험(E1~E3, gold 데이터셋)을 재현하기 위한 코드입니다.

레포 루트의 파이프라인 애플리케이션과는 **독립적인 시스템**이며, 의존성·설정·테스트가
모두 분리되어 있습니다. 파이프라인 앱은 [Pipeline Guide](../docs/PIPELINE_GUIDE.md)를
참고하세요.

## 구성

| 경로 | 역할 |
|---|---|
| `safe_intent_sdn/` | 핵심 라이브러리 (config, run_context, compiler, validator, twin) |
| `config/` | 재현용 기본값(`default.toml`) 및 실험별 override(`experiments/`) |
| `experiments/{e1,e2,e3,gold}/` | 실험별 데이터셋 빌드·실행·채점 스크립트 |
| `paper/` | 실험 프로토콜 문서, 결과 표, figure 생성 스크립트 |
| `schemas/` | 커밋된 JSON Schema (`safe_intent_sdn.schema`로 생성) |
| `scripts/` | ONOS/Mininet 운영 및 설치 스크립트 |
| `tests/` | pytest 스위트 |
| `logs/` | 런타임 산출물 (`.gitignore`) |

## 시작하기

```bash
cd research
uv sync --locked
uv run pytest -q
```

SDN 실험 환경 준비는 [Installation Guide](scripts/installation/README.md),
실행 순서는 [Scripts Guide](scripts/README.md)를 참고하세요.

## 설정과 비밀값

재현 가능한 비밀이 아닌 값은 `config/*.toml`에 두고, 비밀값은 `SAFE_SDN_*` 환경변수로
관리합니다. `.env`는 `research/.env`를 먼저 찾고 없으면 레포 루트의 `.env`를 사용하므로,
두 시스템이 루트 `.env` 하나를 공유할 수 있습니다.

기여 가이드는 [AGENTS.md](AGENTS.md)를 참고하세요.
