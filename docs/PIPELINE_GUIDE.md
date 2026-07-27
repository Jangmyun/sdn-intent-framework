# SDN XAI Pipeline

자연어 네트워크 인텐트를 ONOS FlowRule로 안전하게 변환하는 End-to-End 파이프라인.
LLM/RAG 기반 인텐트 해석부터 정적 검증, Digital Twin 시뮬레이션, XAI 설명, ONOS 배포까지 6단계로 처리한다.

> 이 파이프라인은 `sdn_intent-framework` 레포 루트에 위치한다. 연구/논문용 재현
> 실험 트랙은 `research/` 아래에 별도로 분리되어 있다. 두 트랙 모두 uv로 관리하되
> 프로젝트는 분리되어 있다 — 파이프라인은 루트 `pyproject.toml`, 연구는
> `research/pyproject.toml`이며 각자 자기 lockfile과 `.venv`를 가진다.

---

## 파이프라인 구조

```
자연어 인텐트
     │
     ▼
[Stage 1] LLM/RAG → Intent IR          (자연어 파싱 + 환각 억제)
     │
     ▼
[Stage 2] Deterministic Compiler        (IntentIR → ONOS FlowRule JSON)
     │
     ▼
[Stage 3] Static Validator              (스키마 검증 + 충돌 탐지 5종)
     │ FAIL ──────────────────────────┐
     │ PASS                           │
     ▼                                │
[Stage 4] Digital Twin 검증            │  (Mininet+ONOS 임시 배포 → rollback)
     │ FAIL ──────────────────────────┤
     │ PASS                           │
     ▼                                │
[Stage 5] XAI 설명 생성               │
     │                                │
     ▼                                ▼
[Stage 6] ONOS 배포              REJECT / 운영자 확인
```

---

## 주요 기여

| 기여 | 설명 | 구현 위치 |
|------|------|-----------|
| **Intent IR** | LLM과 컨트롤러를 분리하는 중간 표현 — 재현성 보장 | `src/xai_pipeline/models/intent_ir.py` |
| **결정론적 컴파일러** | 동일 IR → 항상 동일 FlowRule, LLM 환각 원천 차단 | `src/xai_pipeline/pipeline/stage2_flowrule/compiler.py` |
| **정적 검증** | Shadowing·Redundancy 등 5종 충돌을 LLM 없이 탐지 | `src/xai_pipeline/pipeline/stage3_static/` |
| **Digital Twin 루프** | 임시 배포 → 검증 → rollback으로 안전성 확인 | `src/xai_pipeline/pipeline/stage4_twin/` |
| **Evidence-grounded XAI** | 설명 근거를 실제 stage 출력 데이터에 연결 | `src/xai_pipeline/pipeline/stage5_xai/explainer.py` |

---

## 디렉토리 구조 (레포 루트 기준)

코드는 전부 `src/xai_pipeline/` 아래에 있는 진짜 파이썬 패키지다 (`uv sync`가
editable install). `sys.path` 조작이 전혀 없고, 내부 어디서나 `from xai_pipeline...`
형태로 임포트한다.

```
sdn_intent-framework/
├── main.py                    # 얇은 진입점 — from xai_pipeline.main import main
├── evaluate.py                 # 얇은 진입점 — from xai_pipeline.evaluate import main
├── pyproject.toml              # uv 프로젝트 + hatchling 빌드 설정
├── src/xai_pipeline/           # 실제 코드 (editable install 대상)
│   ├── __init__.py
│   ├── api.py                  # FastAPI 서버 — uv run uvicorn xai_pipeline.api:app
│   ├── config.py                # 전역 설정. BASE_DIR = Path.cwd() (레포 루트에서 실행 전제)
│   ├── main.py                  # CLI 본체 (main.py는 여기로 위임)
│   ├── evaluate.py              # 평가 스크립트 본체
│   ├── static/                  # Web UI (HTML/JS/CSS) — 패키지와 함께 배포
│   ├── models/
│   │   ├── intent_ir.py         # IntentIR 데이터 모델 (Pydantic)
│   │   └── topology.py          # 네트워크 토폴로지 + 엔티티 검증
│   └── pipeline/
│       ├── flow_state_manager.py
│       ├── repair_utils.py
│       ├── stage1_intent/       # LLM 백엔드, RAG, 자연어 → IntentIR
│       ├── stage2_flowrule/     # IntentIR → ONOS FlowRule
│       ├── stage3_static/       # 스키마 검증 + 충돌 탐지
│       ├── stage4_twin/         # ONOS 클라이언트 + Twin 검증 + rollback
│       ├── stage5_xai/          # XAI 보고서 생성
│       └── stage6_deploy/       # 실제 ONOS 배포
├── data/                        # 토폴로지/인텐트/트래픽 프리셋 데이터 (런타임, config.DATA_DIR)
├── experiments/eval/            # GOLD-350 정량 평가 프레임워크 (Exp-1: T-A~T-D)
├── scripts/                     # generate_dataset.py, validate_dataset.py 등 — 아직 src/ 밖
├── tests/                       # 파이프라인 전용 pytest 스위트 (xai_pipeline.* 바로 임포트)
├── docs/                        # 설계 문서 및 세션 기록
├── logs/                        # 실행 결과 JSON (run_id 기반, .gitignore, config.LOGS_DIR)
└── research/                    # 논문 재현 실험 트랙 (별도 시스템)
```

`scripts/`, `experiments/eval/`, `tests/`는 라이브러리가 아니라 실행 스크립트라
`src/` 밖에 남겨뒀다 — `xai_pipeline` 패키지를 (editable) 설치된 대상으로
임포트해서 쓴다.

`research/` 아래에는 `safe_intent_sdn/`, `config/`, `schemas/`, `experiments/e1~e3`,
`experiments/gold`, `paper/`, `scripts/`(ONOS·Mininet 운영), `tests/`가 들어 있으며
이 파이프라인과는 완전히 별도로 동작한다. `uv`로 관리한다 (`cd research && uv sync --locked`).

---

## 실행 가이드

### 1. 의존성 설치

[uv](https://docs.astral.sh/uv/)로 관리한다. uv가 없다면:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

프로젝트 환경 구성 (Python 3.11을 자동으로 받아온다):

```bash
uv sync                 # 기본 의존성 + dev(pytest)
uv sync --group reports  # 발표자료 생성(python-pptx)까지 필요할 때
```

Digital Twin(Mininet) 사용 시 추가 설치:

```bash
sudo apt update && sudo apt install -y mininet
```

### 2. 환경변수 설정

레포 루트에 `.env` 파일 생성 (이미 `safe_intent_sdn`용 `SAFE_SDN_*` 변수가 있다면 같은 파일에 추가):

```bash
cat >> .env << 'EOF'
LLM_BASE_URL=https://ollama.example.com/v1
LLM_MODEL=qwen3:8b
EMBED_MODEL=nomic-embed-text
LLM_API_KEY=ollama

GOOGLE_API_KEY=your_key_here

ONOS_URL=http://127.0.0.1:8181/onos/v1
ONOS_USER=onos
ONOS_PASSWORD=rocks
EOF
```

### 3. sudo 권한 설정 (Digital Twin 필수)

Mininet은 root 권한이 필요합니다. 매번 비밀번호 입력 없이 실행하려면:

```bash
echo "$USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/$USER
sudo chmod 440 /etc/sudoers.d/$USER
```

### 4. 앱 실행

#### Web UI (HTML/JS + FastAPI)

```bash
# 일반 실행 (Digital Twin 스킵)
uv run uvicorn xai_pipeline.api:app --reload --port 8000

# Digital Twin 사용 시 (root 필요)
# sudo는 uv의 PATH를 못 보므로 venv의 uvicorn 절대경로를 넘긴다
sudo -E $(uv run which uvicorn) xai_pipeline.api:app --port 8000
```

브라우저에서 `http://localhost:8000` 접속

#### CLI

```bash
uv run python main.py --intent "block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1"
```

---

## 사용법 (CLI 옵션)

```bash
# 기본 실행
uv run python main.py --intent "block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1"

# Gemini 모델 사용, Digital Twin 스킵
uv run python main.py --intent "..." --model gemini-2.0-flash --skip-twin

# RAG 예시 수 조정, 상세 출력
uv run python main.py --intent "..." --rag-k 5 --verbose

# 배포까지 스킵 (검증만 수행)
uv run python main.py --intent "..." --skip-twin --skip-deploy

# RAG 없이 LLM 직접 호출
uv run python main.py --intent "..." --no-rag
```

**종료 코드**
| 코드 | 의미 |
|------|------|
| `0` | APPROVE (모든 검증 통과, 배포 완료) |
| `1` | APPROVE_WITHOUT_TWIN (Twin 스킵, 배포 완료) |
| `2` | REJECT (검증 실패 또는 인텐트 거부) |
| `3` | ERROR (파이프라인이 예외로 중단됨 — 승인/거부 판정에 도달하지 못함) |
| `4` | DEPLOY_FAILED (승인 판정까지는 통과했으나 ONOS 배포가 실패함) |

---

## 인텐트 예시

```
# 트래픽 차단
block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1

# 포워딩
forward traffic from 10.0.0.1 to 10.0.0.2 via switch 2

# QoS
prioritize TCP traffic from 10.0.0.1 to 10.0.0.3 on switch 1

# 서비스 체인 (방화벽 경유)
route traffic from h1 to h4 through firewall on switch 1

# 경로 변경
reroute traffic from 10.0.0.1 to 10.0.0.2 via switch 3
```

---

## XAI 출력 예시

```
인텐트: block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1

[인텐트 해석]  action=block(차단) | device=1 | src=10.0.0.1/32 | dst=10.0.0.4/32
[FlowRule]    deviceId=of:0000000000000001 | priority=40000 | criteria=3개 | action=DROP
[정적 검증]   PASS (스키마 OK, 충돌 없음)
[Digital Twin] 검증 통과 (3/3 체크)

최종 결정: APPROVE
판정 근거: 정적 검증 통과 (스키마 OK, 충돌 없음); Digital Twin 검증 통과 (3/3 체크)
```

---

## GOLD-350 정량 평가 (Exp-1)

`experiments/eval/`에 T-A(Direct FlowRule) ~ T-D(IR+Few-Shot+Grounding) 4개
treatment 비교 프레임워크가 있다. 실행 방법은 `experiments/eval/README.md` 참고.

```bash
uv run python experiments/eval/run_exp1.py \
  --config experiments/eval/config/T-D.toml \
  --repetitions 10 \
  --output experiments/eval/logs/

uv run python experiments/eval/score_exp1.py \
  --dataset experiments/eval/data/gold350_eval.jsonl \
  --topology experiments/eval/data/topology_eval.json \
  --logs experiments/eval/logs/ \
  --output experiments/eval/reports/summary_exp1.json
```

---

## 환경

- **LLM**: Ollama (qwen3:8b 기본) / Google Gemini API
- **임베딩**: nomic-embed-text (RAG용)
- **벡터 검색**: FAISS (IndexFlatL2)
- **SDN 컨트롤러**: ONOS 2.7 (Docker)
- **Digital Twin**: Mininet 다이아몬드 토폴로지 (s1–s4, h1–h4)
- **UI**: HTML/JS (FastAPI static 서빙)
