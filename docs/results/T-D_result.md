# T-D 실험 결과 보고서

> 작성일: 2026-07-22  
> Treatment: **T-D** (IntentIR + Few-Shot + Topology Grounding)  
> 모델: `gemini-3.1-flash-lite` | Temperature: `0.2` | Repetitions: **10**  
> 데이터셋: `intents_eval.jsonl` (60 cases: accepted 54 / rejected 6)

---

## 1. 전체 지표 요약

| 지표 | 값 (mean ± std) | 해석 |
|------|-----------------|------|
| schema_validity | **1.000 ± 0.000** | JSON 파싱 오류 0건 |
| status_match | **1.000 ± 0.000** | accept/reject 판별 완벽 |
| false_rejection_rate | **0.000 ± 0.000** | 허위 거부 없음 |
| rejection_recall | **1.000 ± 0.000** | 거부 케이스(6개) 전부 정확 감지 |
| rejection_reason_match | **1.000 ± 0.000** | 거부 사유 분류까지 정확 |
| false_acceptance_rate | **0.000 ± 0.000** | 허위 수락 없음 |
| hallucinated_entity_rate | **0.000 ± 0.000** | 환각 엔티티 0건 |
| **NEM** (Normalized Exact Match) | **0.944 ± 0.000** | 54개 중 51개 완전 일치 |

> **std = 0.000** — 모든 10 rep에서 동일한 결과. 모델이 Temperature=0.2 환경에서도 완전 결정론적으로 동작함.

---

## 2. 슬롯 정확도

| 슬롯 | 정확도 | 비고 |
|------|--------|------|
| action | 0.944 | reroute 케이스 3건 오분류 |
| source_ip | 1.000 | |
| destination_ip | 1.000 | |
| protocol | 1.000 | |
| dst_port | 1.000 | |
| device | 1.000 | |
| egress_port | 1.000 | |
| alt_egress_port | 1.000 | |
| queue | 1.000 | |
| min_bandwidth_mbps | 1.000 | |
| max_latency_ms | 1.000 | |
| waypoints | 1.000 | |
| **via_device** | **0.500** | reroute 오분류 케이스에서 routing 필드 누락 |
| avoid_device | 1.000 | |

---

## 3. 카테고리별 성능

| 카테고리 | n (×10 reps) | status_match | NEM |
|----------|--------------|--------------|-----|
| forwarding | 100 | 1.000 | 1.000 |
| qos | 100 | 1.000 | 1.000 |
| security | 100 | 1.000 | 1.000 |
| compound | 100 | 1.000 | 1.000 |
| sfc | 100 | 1.000 | 1.000 |
| **reroute** | **100** | **1.000** | **0.667** |

reroute 카테고리는 status_match는 완벽하나, NEM이 0.667로 유일한 실패 지점.

---

## 4. 실패 케이스 분석

### 실패한 케이스 (3건: RRT-03, RRT-05, RRT-07)

| Case | Intent | Gold action | Pred action | 추가 오류 |
|------|--------|-------------|-------------|-----------|
| RRT-03 | `Route all traffic from 10.0.0.4 to 10.0.0.1 through switch 2.` | reroute | **forward** | — (via_device는 s2로 정확) |
| RRT-05 | `Force all traffic from h1 to h4 through switch 3 out port 4.` | reroute | **forward** | routing 필드 전체 누락 |
| RRT-07 | `Route all traffic from h3 to h4 through switch 4, egress port 3.` | reroute | **forward** | routing 필드 전체 누락 |

### 성공/실패 패턴 비교

reroute 케이스 9개를 via_device 유무와 intent 동사 기준으로 분류하면:

| Case | Intent 동사 | via_device | 결과 |
|------|-------------|-----------|------|
| RRT-01 | **Reroute** | switch 2 | 성공 |
| RRT-02 | Avoid | None | 성공 |
| RRT-03 | Route | switch 2 | **실패** |
| RRT-04 | Bypass | None | 성공 |
| RRT-05 | Force | switch 3 | **실패** |
| RRT-06 | Avoid | None | 성공 |
| RRT-07 | Route | switch 4 | **실패** |
| RRT-08 | Avoid | None | 성공 |
| RRT-09 | Bypass | None | 성공 |

### 핵심 원인

**모델이 "reroute" 동의어 표현을 추론하지 못함.**

- `via_device=None` 케이스 (avoid/bypass): 모두 성공 — "avoid", "bypass" 키워드가 명확히 거부/우회 의미를 전달
- `via_device≠None` 케이스 4건 중:
  - RRT-01 성공 — intent에 **"Reroute"** 단어가 명시되어 있음
  - RRT-03/05/07 실패 — "Route", "Force" 등 reroute를 *암묵적으로* 내포하는 동사 사용

즉, **intent_text에 "reroute" 단어가 없는데 via_device 지정이 있는 경우**, 모델이 이를 경로 변경(reroute)이 아닌 단순 전달(forward)로 해석한다.

---

## 5. 총평

T-D는 Topology Grounding이 포함된 최고 tier treatment로, 대부분의 지표에서 **완벽한 성능**을 기록했다.

**강점:**
- 환각 완전 제거 (hallucinated_entity_rate=0.000)
- 거부 판별 및 사유 분류 완벽
- forwarding, qos, security, compound, sfc 5개 카테고리 100% 정확

**한계:**
- `reroute` 카테고리 NEM=0.667 — "reroute" 단어가 없는 경유 지정 intent에서 action 오분류
- via_device 슬롯 정확도 0.500 — action 오분류 케이스에서 routing 필드 연쇄 누락

**이후 비교 포인트:**
T-C (Few-Shot, No Grounding), T-B (Zero-Shot), T-A (Direct FlowRule)와 비교 시 reroute NEM이 핵심 변별 지점이 될 것으로 예상.
