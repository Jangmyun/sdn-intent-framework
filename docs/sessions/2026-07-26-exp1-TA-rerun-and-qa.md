# Exp-1 T-A 재실행 · 종합 비교 · QA 세션 — 2026-07-26

## 개요

2026-07-24 세션에서 **프롬프트 버전 불일치로 무효 처리**된 T-A를 재실행해 T-A~T-D 4개 treatment
비교를 완성하고, 결과를 문서·발표자료로 정리한 뒤 전체 QA를 수행한 세션.

결론부터: **T-A 재실행 성공(status_match 0.183 → 0.560), 4개 treatment 비교 가능 상태 확보.**
단, QA 과정에서 **T-A vs T-B 비교의 새로운 교란 요인(프롬프트 비대칭)을 발견** — §6-1 참고.

---

## 1. T-A 프롬프트 결함 2차 수정

`run_exp1.py`의 `SYSTEM_DIRECT_FLOW`(T-A 전용 하드코딩 프롬프트)를 프로덕션
`intent_parser.SYSTEM_PROMPT`에 맞추는 작업. 한 번에 끝나지 않고 두 단계로 진행됐다.

| 단계 | run_id | 수정 내용 | status_match |
|---|---|---|---|
| 원본 | `ce969254` | (2026-07-24 무효 판정) 옛 규칙 "forward/block은 src+dst IP 둘 다 필수" | 0.183 |
| 1차 | `44f92b6b` | selector completeness 완화 — 단방향 flow 허용, forward는 dst·egress 둘 다 없을 때만 ambiguous | 0.269 |
| **2차** | **`a26d01cc`** | unknown_entity 판정 기준 명시 | **0.560** |

### 1차 수정만으로 부족했던 이유 (실측 근거)

1차 수정 후 채점했더니 status_match가 0.269에 그쳤다. 오거부 사유를 분류한 결과:

```
accepted-gold 300건 중 오거부 254건의 사유 분포
  unknown_entity : 170건 (57%)   <- 압도적
  ambiguous      :  51건
  unsupported    :  31건
```

`unknown_entity` 오거부 예시 — 모두 **정상 토폴로지 엔티티**를 모른다고 거부한 것:

```
G-CMP-017 "Allow h1 to reach h2 and h3 to reach h4."
  -> "Hosts h1, h2, h3, h4 not found in topology inventory"
G-CMP-014 "On switch 2, drop traffic from 10.0.0.4 but forward other flows."
  -> "switch not in topology"
```

**원인**: T-A는 `grounding=false`라 토폴로지 인벤토리를 프롬프트에 안 준다. 그런데 1차 프롬프트엔
"토폴로지에 없는 엔티티는 거부하라"는 **규칙만 있고 판정 기준이 없었다**. 프로덕션 프롬프트엔
구체적 예시(`h9`, `database-server`, `10.0.0.99`, `switch 99` = unknown)가 있어 무엇이 unknown인지
가늠할 수 있었지만, T-A 프롬프트엔 그게 빠져 있어 모델이 h1~h4조차 신뢰하지 못했다.

**정황 증거**: 동일 조건(grounding 없음)의 T-B는 unknown_entity 오거부가 25건뿐. T-C는 12건.
T-A만 170건 — 프롬프트 차이 외에 설명이 안 된다.

### 2차 수정 내용

`experiments/eval/run_exp1.py` `SYSTEM_DIRECT_FLOW`:

```diff
- - "unknown_entity" : host, IP, or switch not in the topology
+ - "unknown_entity" : references a host, IP, or switch not in the topology
+                      e.g. "h9", "database-server", "10.0.0.99", "switch 99"
+                      (hosts h1-h4 and switches s1-s4/"switch 1".."switch 4" are the
+                       standard names used throughout this network — treat them as known)
```

결과: 오거부 254건 → 152건, status_match 0.269 → 0.560.

> ⚠️ 이 수정의 마지막 괄호 절이 **T-B에는 없는 정보**라는 점이 QA에서 문제로 지적됨 — §6-1.

---

## 2. SFC 구간 프로세스 다운 재발 (4회째)

T-A 재실행 중 **두 번 모두 rep 종료 직전에 프로세스가 죽었다.** 이전 세션(T-A/T-C)까지 합쳐 4회째.

| run_id | 기록된 케이스 | 누락 | 죽기 직전 완료 케이스 |
|---|---|---|---|
| `44f92b6b` | 346/350 | G-CMP-003, G-FWD-042, G-QOS-025, G-SFC-045 | 마지막 5건 전부 SFC |
| `a26d01cc` | 348/350 | G-RRT-031, G-SFC-006 | 마지막 6건 중 5건 SFC |

**진단 근거**:
- 개별 API 호출 실패는 `_call_openai_compatible`이 전부 잡아 `error_kind`로 기록한다
  (실제로 schema_invalid는 정상 기록됨). 누락 4건/2건은 **에러 레코드조차 없음**
  → 개별 호출 실패가 아니라 **프로세스 자체가 죽은 것**.
- `transport` 에러 0건, 429 에러 0건 → 레이트리밋/네트워크 문제 아님.
- SFC/compound가 가장 긴 thinking을 유발(최대 184초, 12K+ 출력 토큰). `concurrency=20`이라
  데이터셋 뒷부분(느린 SFC 편중)에 도달할 때 in-flight 요청이 몰린 상태에서 죽음.

**해석**: "SFC 케이스에서 죽는다"기보다 **"가장 느린 케이스들이 아직 안 끝난 시점에 죽어서
SFC/CMP가 누락으로 보이는"** 현상일 가능성이 높다. **근본 원인은 여전히 미규명**(OOM, 절전,
터미널 종료 등 외부 kill 추정).

**대응**: 누락 케이스만 별도 호출해 기존 JSONL에 append (전체 재실행 안 함).
프롬프트 출처 검증 완료 — `run_exp1.py` mtime 15:13:13 < 본 실행 15:15:42 < 보강 15:33:07,
그 사이 파일 변경 없음 → **350건 전부 동일 프롬프트로 생성됨 확인**.

---

## 3. 최종 채점 결과

run_id: `T-A-qwen-qwen3-8b-a26d01cc` (350/350, 중복 0)

| 지표 | T-A | T-B | T-C | T-D |
|---|---|---|---|---|
| schema_validity | 0.971 | 0.954 | 0.983 | **0.989** |
| status_match | 0.560 | 0.743 | 0.809 | **0.949** |
| false_rejection_rate ↓ | 0.507 | 0.267 | 0.173 | **0.047** |
| rejection_recall | 0.960 | 0.800 | 0.700 | 0.920 |
| false_acceptance_rate ↓ | **0.040** | 0.180 | 0.300 | 0.060 |
| NEM | N/A | 0.164 | 0.149 | **0.692** |

핵심 발견 3가지는 `docs/results/TA-TD_openrouter_comparison.md`에 정리.
요약: **IR은 오거부를 줄이고(+0.183), grounding은 슬롯 정확도를 올린다(NEM +0.543).
few-shot은 형식 준수엔 기여하지만 사실 정확도엔 기여하지 못하고 오히려 false_acceptance를 올린다.**

---

## 4. 새로 확인된 실패 유형 — T-A의 구조적 오거부

T-A 오거부 152건을 분류한 결과, 상당수가 **모델 능력 문제가 아니라 출력 형식이 강제하는
조기 확정(premature commitment)** 때문이었다.

| 인텐트 (gold = accepted) | T-A 거부 사유 | 근본 원인 |
|---|---|---|
| "Set up forwarding from h3 to h2." | Egress port not specified for forwarding action | FlowRule OUTPUT은 포트 번호 정수 필수 |
| "Give h1 to h3 at least 10 Mbps." | Bandwidth guarantee cannot be enforced; requires queueId | FlowRule QoS는 queueId 정수 필수 |

QoS 카테고리에서 가장 극단적: **T-A status_match 0.080 vs T-B 0.720.**
QoS 인텐트는 대역폭/지연만 말하고 큐 번호를 말하지 않기 때문.

IntentIR은 `egress_port: null`, `device: null`을 허용하고 물리 자원 확정을 Stage 2 결정론적
컴파일러로 미루므로 같은 인텐트를 수락할 수 있다 — 파이프라인 설계 논지를 지지하는 실측 근거.

---

## 5. 산출물

| 파일 | 내용 |
|---|---|
| `docs/results/TA-TD_openrouter_comparison.md` | 종합 비교 분석 (개정판 — T-A 재실행 반영) |
| `docs/results/Exp1_TA-TD_Comparison.pptx` | 발표자료 13슬라이드 |
| `scripts/make_exp1_pptx.py` | PPT 재생성 스크립트 (기존 PPT엔 생성 경로 없었음) |
| `experiments/eval/reports/T-A_openrouter_r1_summary.json` | T-A 채점 결과 (재실행분) |
| `experiments/eval/run_exp1.py` | `SYSTEM_DIRECT_FLOW` 프롬프트 수정 |

---

## 6. QA 결과

### 통과 항목

| 항목 | 결과 |
|---|---|
| 문서·PPT 수치 ↔ 원본 JSON 대조 | **109개 값 전부 일치** (집계 8×4, 환각 4, 슬롯 9×3, 카테고리 status_match 7×4, NEM 6×3) |
| 로그 무결성 (4개 run) | 350/350, 중복 0, 누락 0, 초과 0, run_id 각 1개, 레코드 스키마 동일 |
| 보강 레코드 프롬프트 출처 | mtime 검증으로 본 실행과 동일 프롬프트 확인 |
| 채점 재현성 | 동일 입력 재채점 → aggregate 완전 일치 |
| 채점 안전장치 | run_id 혼재 시 `score_exp1.py`가 SystemExit(1)로 거부하는 것 확인 |
| 단위 테스트 | pytest **56 passed** |

### 6-1. ⚠️ [High] T-A vs T-B 프롬프트 비대칭 — 논문 핵심 비교의 교란 요인

`SYSTEM_DIRECT_FLOW`(T-A)와 `SYSTEM_PROMPT`(T-B/C/D)의 섹션 구성을 대조한 결과,
**두 프롬프트는 출력 형식 외에도 정보량이 크게 다르다** (3,362자 vs 6,089자).

**T-A에만 있는 것 (T-A에 유리):**
- `(hosts h1-h4 and switches s1-s4 ... treat them as known)` — §1의 2차 수정으로 추가한 절.
  **이건 사실상 부분적 토폴로지 정보**이며 T-B는 받지 못한다.

**T-B/C/D에만 있는 것 (T-B에 유리):**
- `## Compound intents` 섹션 + 워크드 예시 2개 (T-A엔 복합 인텐트 가이드가 전혀 없음)
- `## action / intent_type mapping` 표
- `## Field rules` (selector/enforcement 상세)

**함의**: T-A vs T-B는 **"출력 형식만 다른 단일 변수 조작"이 아니다.** 실제로는
"프롬프트 패키지 A vs 패키지 B"의 비교이며, 교란이 양방향으로 존재한다.

**다만 결론의 방향성은 보존된다**: T-A는 엔티티 화이트리스트라는 이점을 받고도 T-B보다
낮았다(0.560 vs 0.743). 즉 측정된 IR 효과 +0.183은 **보수적 추정**일 가능성이 높다.

**권장 조치 (택1)**:
- (a) **엄격 패리티 재실행** — 화이트리스트 절을 빼고 프로덕션과 동일한 예시
  (`h9`/`database-server`/`10.0.0.99`/`switch 99`)만 남긴 뒤 T-A 재실행. 가장 깨끗하지만
  1차 실행(0.269)과 2차(0.560) 사이 어딘가로 떨어질 것으로 예상되며, 그 경우 "IR 효과"에
  프롬프트 정보량 효과가 섞여 있다는 비판을 피하기 어렵다.
- (b) **비대칭을 명시하고 한계로 기술** — 완전한 패리티는 출력 형식이 다른 이상 원리적으로
  불가능하다는 점을 논문에 명시. 현재 문서는 이 방향으로 기술돼 있음.

### 6-2. [Medium] `run_exp1.py`에 T-A 프롬프트 하드코딩 — 재발 위험

`SYSTEM_DIRECT_FLOW`가 실행 스크립트에 하드코딩돼 있어 프로덕션 프롬프트 개정을 자동으로
따라가지 않는다. **이번 세션의 원인이 정확히 이것**이며, 2026-07-24에 이미 한 번 터진 문제다.

**권장**: T-A 프롬프트를 `pipeline/` 또는 `experiments/eval/prompts/`로 분리하고,
프로덕션 프롬프트와의 규칙 대응표를 테스트로 고정(예: 두 프롬프트에서 rejection reason 4종과
selector completeness 문구가 모두 존재하는지 검사하는 pytest).

### 6-3. [Low] 로그 디렉토리에 폐기 run 누적

`experiments/eval/logs/`에 T-A 5개 · T-D 8개 run_id가 혼재. 그중 `T-A-...-78215ce6-r01.jsonl`은
이번 세션에서 사용자가 중단시킨 49건짜리 부분 실행 파일로 **분석 가치가 전혀 없다**.

`score_exp1.py`가 `--run-id` 없이는 거부하므로 **오염 위험은 차단돼 있으나**, 실수 여지와
디렉토리 가독성 문제는 남는다.

**권장**: `logs/archive/` 하위로 폐기 run 이동 (삭제는 비권장 — 이력 보존).

### 6-4. [Low] rep=1 — 모든 수치의 재현성 미확인

특히 T-B vs T-C의 NEM 역전(0.164 → 0.149, Δ=−0.015)은 절대값이 작아 샘플링 노이즈와
구분되지 않는다. 현재 문서·PPT 모두 이 한계를 명시하고 있으나, **논문 주장으로 쓰려면
rep 확대가 선행되어야 한다.**

---

## 7. 다음 단계 (우선순위 순)

1. **rep 확대** — 4 treatment × 3 rep 이상. T-B/T-C NEM 역전의 실체 확인. (최우선)
2. **6-1 결정** — 엄격 패리티 재실행 여부. 논문 핵심 주장의 방어력에 직결.
3. **SFC 구간 프로세스 다운 원인 조사** — `concurrency=10`으로 낮춰 재현 여부 확인,
   장시간 thinking 케이스의 자원 사용 계측.
4. **`topology_eval.json` s2 IDS 그라운딩 보강** — s1 firewall과 달리 포트 정보가 없어
   SFC waypoints 정확도를 구조적으로 깎는 중 (T-D waypoints가 유일하게 grounding 후 하락).
5. **few-shot 데모 구성 재검토** — 현재 5개 전부 accepted 예시. T-C의 false_acceptance
   상승(0.180 → 0.300)의 유력한 원인. rejected 예시 포함 버전과 비교.
6. **6-2 구조 개선** — T-A 프롬프트 분리 + 패리티 검사 테스트 추가.
