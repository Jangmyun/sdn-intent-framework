# Exp-1 & Exp-2: 정량 평가 프레임워크

> 브랜치: `exp/eval-framework`  
> 상세 계획: `docs/EVAL_PLAN.md`  
> 모델: `gemini-3.1-flash-lite` / Temperature: `0.2` / Repetitions: `10`

---

## 디렉토리 구조

```
experiments/eval/
├── data/
│   ├── intents_eval.jsonl          ✅ Small 데이터셋 (60케이스, 9:1, h1–h4, s1–s4)
│   ├── intents_eval_large.jsonl    ✅ Large 데이터셋 (60케이스, 9:1, h1–h16, s1–s8)
│   ├── topology_eval.json          ✅ Small 토폴로지 alias 인벤토리
│   ├── topology_large.json         ✅ Large 토폴로지 alias 인벤토리
│   ├── demonstrations.json         ✅ 정적 few-shot 5개 (phantom 엔티티)
│   └── DATASET_PLAN.md             ✅ 데이터셋 설계 문서
├── config/
│   ├── T-A.toml                    ✅ Direct FlowRule (Small)
│   ├── T-B.toml                    ✅ IR Zero-Shot (Small)
│   ├── T-C.toml                    ✅ IR + Few-Shot (Small)
│   ├── T-D.toml                    ✅ IR + Few-Shot + Grounding (Small)
│   ├── T-A-large.toml              ✅ Direct FlowRule (Large)
│   ├── T-B-large.toml              ✅ IR Zero-Shot (Large)
│   ├── T-C-large.toml              ✅ IR + Few-Shot (Large)
│   └── T-D-large.toml              ✅ IR + Few-Shot + Grounding (Large)
├── logs/                           — 실행 결과 JSONL (gitignore 권장)
├── reports/                        — 채점 결과 JSON
├── run_exp1.py                     ✅ 구현 완료 — Gemini API 배치 실행
├── score_exp1.py                   ✅ 구현 완료 — 채점 엔진
├── validate_gold.py                ✅ 구현 완료 — Gold 검증
├── run_exp2.py                     🔲 미구현 — Stage 1→2→3 파이프라인 평가
└── score_exp2.py                   🔲 미구현 — Exp-2 채점
```

---

## 진행 현황 (2026-07-22 기준)

### Gold Validation
- Small (`intents_eval.jsonl`): **54/54 PASS** ✅
- Large (`intents_eval_large.jsonl`): **54/54 PASS** ✅

### Exp-1 실행 현황 (Small)

| Treatment | 완료 reps | 상태 |
|---|---|---|
| **T-D** | 7 / 10 | 🔄 진행 중 (3 reps 남음) |
| **T-C** | 0 / 10 | 🔲 대기 |
| **T-B** | 0 / 10 | 🔲 대기 |
| **T-A** | 0 / 10 | 🔲 대기 |

- 모델: `gemini-3.1-flash-lite`, temperature `0.2`
- 완료된 로그: `logs/T-D-gemini-31-flash-lite-67f49bee-r01~r07.jsonl`

---

## Treatment 요약

| Treatment | 출력 형식 | Few-Shot | Grounding | 역할 |
|---|---|---|---|---|
| **T-A** | ONOS FlowRule JSON | ❌ | ❌ | 핵심 베이스라인 — IR 없이 LLM 직접 생성 |
| **T-B** | IntentIR | ❌ | ❌ | IR 효과만 분리 |
| **T-C** | IntentIR | ✅ | ❌ | Few-shot 효과 분리 |
| **T-D** | IntentIR | ✅ | ✅ | 현재 파이프라인 설정 (최상) |

비교 포인트:
- **T-A vs T-B**: IR + 컴파일러의 순수 기여 (논문 핵심 주장 검증)
- **T-B vs T-C**: Few-shot 효과
- **T-C vs T-D**: Grounding 효과
- **T-B vs T-D**: 두 기법 결합 효과

---

## 데이터셋 구조

### 공통 설계 원칙
- 파이프라인 IntentIR 스키마 직접 사용 (정규화 레이어 없음)
- accepted : rejected = **9 : 1**
- 6개 카테고리 균형: forwarding / security / qos / sfc / reroute / compound

### Small 토폴로지 (`intents_eval.jsonl`)
- **총 60케이스** = 6 카테고리 × (accepted 9 + rejected 1)
- 토폴로지: 4 hosts (h1–h4), 4 switches (s1–s4), IDS at s1:9

| 카테고리 | rejected 이유 |
|---|---|
| forwarding | ambiguous |
| security | unknown_entity |
| qos | unsupported |
| sfc | ambiguous |
| reroute | contradictory |
| compound | unknown_entity |

### Large 토폴로지 (`intents_eval_large.jsonl`)
- **총 60케이스** = 6 카테고리 × (accepted 9 + rejected 1)
- 토폴로지: 16 hosts (h1–h16), 8 switches (s1–s8), IDS at s1:9 & s3:9
- Small과 다른 rejected 이유 분포로 상보적 커버리지

| 카테고리 | rejected 이유 |
|---|---|
| forwarding | unknown_entity |
| security | ambiguous |
| qos | contradictory |
| sfc | unsupported |
| reroute | ambiguous |
| compound | contradictory |

---

## 실험 실행 순서

### 1단계: Gold Validation (run_exp1.py 전에 완료 권장)

수락 케이스 54개 gold JSON을 파이프라인 Stage 1→2에 통과시켜 gold 자체의 정확성 확인.

### 2단계: Exp-1 실행 (Small)

```bash
# T-A ~ T-D × 10회 반복
python experiments/eval/run_exp1.py \
  --config experiments/eval/config/T-D.toml \
  --repetitions 10 \
  --output experiments/eval/logs/
```

**출력 파일:** `logs/T-D-gemini-flash-lite-<uuid>-r1.jsonl` ... `r10.jsonl`

**예측 레코드 형식:**
```json
{
  "case_id": "FWD-01",
  "treatment": "T-D",
  "model": "gemini-3.1-flash-lite",
  "run_id": "T-D-gemini-flash-lite-a3f2b1c0",
  "repetition": 1,
  "output": {"status": "accepted", "action": "forward", ...},
  "raw_content": "...",
  "latency_ms": 1234.5,
  "input_tokens": 850,
  "output_tokens": 130,
  "error_kind": null,
  "error": null
}
```

`error_kind`: `null` | `"transport"` | `"schema_invalid"` | `"timeout"`

### 3단계: 채점 (Exp-1)

```bash
python experiments/eval/score_exp1.py \
  --dataset experiments/eval/data/intents_eval.jsonl \
  --topology experiments/eval/data/topology_eval.json \
  --logs experiments/eval/logs/ \
  --output experiments/eval/reports/summary_exp1.json
```

### 4단계: Small 결과 분석 → 보완 방향 확인

### 5단계: Exp-1 실행 (Large)

```bash
python experiments/eval/run_exp1.py \
  --config experiments/eval/config/T-D-large.toml \
  --repetitions 10 \
  --output experiments/eval/logs/
```

---

## 채점 지표 요약 (Exp-1)

### 공통 지표 (T-A ~ T-D)

| 지표 | 설명 |
|---|---|
| `schema_validity` | LLM 출력 파싱 성공률 |
| `status_match` | accepted/rejected 판별 정확도 |
| `false_rejection_rate` | 수락 케이스 오거부율 |
| `rejection_recall` | 거부 케이스 탐지율 |
| `rejection_reason_match` | rejection_reason 일치율 |

### IntentIR 슬롯 지표 (T-B ~ T-D만)

| 지표 | 설명 |
|---|---|
| `slot_accuracy[action]` | action 필드 정확도 |
| `slot_accuracy[source_ip]` | 출발지 IP 정확도 |
| `slot_accuracy[destination_ip]` | 목적지 IP 정확도 |
| `slot_accuracy[protocol]` | 프로토콜 정확도 |
| `slot_accuracy[dst_port]` | 목적지 포트 정확도 |
| `slot_accuracy[device]` | 스위치 정확도 (alias 정규화) |
| `slot_accuracy[egress_port]` | 출구 포트 정확도 |
| `slot_accuracy[queue]` | QoS queue 정확도 |
| `slot_accuracy[waypoints]` | SFC 웨이포인트 정확도 |
| `hallucinated_entity_rate` | 토폴로지에 없는 엔티티 비율 |
| `normalized_exact_match` | 모든 슬롯 완전 일치율 |

---

## 시드 규칙

Gemini API는 seed 파라미터 미지원. n=10 반복은 temperature=0.2의 자연 분산 측정.  
Bootstrap CI 계산(10,000 재샘플링)에만 seed 사용.

| repetition | bootstrap seed |
|---|---|
| 1 | 42 |
| 2 | 43 |
| 3 | 44 |
| 4 | 45 |
| 5 | 46 |
| 6 | 47 |
| 7 | 48 |
| 8 | 49 |
| 9 | 50 |
| 10 | 51 |

---

## .gitignore 권장

```
experiments/eval/logs/
experiments/eval/reports/
```

결과 파일은 API 비용이 들어간 산출물이므로 별도 관리 권장.
