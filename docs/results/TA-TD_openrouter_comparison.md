# Exp-1 T-A~D 종합 비교 보고서 — qwen3-8b (OpenRouter) × GOLD-350 (rep 1)

> 최초 작성: 2026-07-24 / **개정: 2026-07-26 (T-A 프롬프트 결함 수정 후 재실행 반영)**
> 모델: `qwen/qwen3-8b` (OpenRouter) | Temperature: `0.2` | max_tokens: `8192` | reasoning 예산 제한 없음
> 실행: `--concurrency 20`
> 데이터셋: `gold350_eval.jsonl` (GOLD-350: 350 cases = accepted 300 / rejected 50, 7카테고리 × 50)
> Repetitions: **1** (treatment당) — 단일 rep 결과이므로 수치 변동 가능성 감안할 것 (§8)

| Treatment | run_id | 채점 리포트 |
|---|---|---|
| T-A | `T-A-qwen-qwen3-8b-a26d01cc` ⭐재실행 | `reports/T-A_openrouter_r1_summary.json` |
| T-B | `T-B-qwen-qwen3-8b-d6df6194` | `reports/T-B_openrouter_r1_summary.json` |
| T-C | `T-C-qwen-qwen3-8b-423b2838` | `reports/T-C_openrouter_r1_summary.json` |
| T-D | `T-D-qwen-qwen3-8b-ede0ac95` | `reports/T-D_openrouter_r1_summary.json` |

---

## 0. 결론 먼저

4개 treatment 모두 정상 비교 가능한 상태가 되었다 (T-A는 2026-07-26 프롬프트 수정 후 재실행, §1 참고).

| 비교 | 측정하는 효과 | 결과 |
|---|---|---|
| **T-A vs T-B** | **IR + 결정론적 컴파일러의 기여** (프롬프트 비대칭 있음 — §8 한계 3) | **status_match +0.183 (0.560→0.743), false_rejection −0.240 (0.507→0.267)** |
| T-B vs T-C | Few-shot 단독 기여 | status_match +0.066, 그러나 NEM은 오히려 −0.015 (0.164→0.149) |
| **T-C vs T-D** | **Grounding 단독 기여** | **NEM +0.543 (0.149→0.692)** — 압도적. IP 슬롯이 0.09~0.14대 → 0.91대로 도약 |

한 줄 요약: **IR은 "수락 가능한 인텐트를 거부하지 않게" 만들고, grounding은 "슬롯 값을 정확히 채우게" 만든다. 둘은 서로 다른 실패 모드를 해결하며 대체 관계가 아니다.**

---

## 1. T-A 재실행 이력 (2026-07-26) — 프롬프트 버전 정합성 확보

초기 T-A run(`ce969254`)은 **프롬프트 버전 불일치라는 실험 설계 결함**으로 무효 처리됐다. `run_exp1.py`에 하드코딩된 T-A 전용 프롬프트 `SYSTEM_DIRECT_FLOW`가, T-B/C/D가 쓰는 프로덕션 프롬프트(`intent_parser.SYSTEM_PROMPT`)의 2026-07-23 개정을 반영하지 못한 채 방치돼 있었다. 두 차례에 걸쳐 수정 후 재실행했다.

| 수정 | 내용 | 효과 (status_match) |
|---|---|---|
| 원본 (`ce969254`) | 옛 규칙: "forward/block은 src+dst IP 둘 다 필수" | 0.183 |
| 1차 (`44f92b6b`) | selector completeness 완화 — 단방향 flow 허용, forward는 dst·egress 둘 다 없을 때만 ambiguous | 0.269 |
| **2차 (`a26d01cc`)** ⭐ | unknown_entity 판정 기준 명시 — h1~h4 / s1~s4는 이 네트워크의 표준 이름임을 프롬프트에 기술 | **0.560** |

**2차 수정의 근거**: 1차 수정 후에도 accepted-gold 300건 중 170건(57%)이 `unknown_entity`로 거부됐다. T-A는 `grounding=false`라 토폴로지 인벤토리를 안 주는데, 프롬프트에 "토폴로지에 없는 엔티티는 거부하라"는 규칙만 있고 프로덕션 프롬프트에 있던 구체적 예시(`h9`, `database-server`, `switch 99` = unknown)가 빠져 있어 모델이 h1~h4조차 신뢰하지 못하고 과잉 거부했다. 동일 조건(grounding 없음)의 T-B는 unknown_entity 거부가 25건뿐이었던 것이 정황 증거다. 예시 문구를 프로덕션과 동등하게 보강하자 오거부가 170건 → 절반 수준으로 감소했다.

> **재현성 주의**: T-A의 프롬프트는 `run_exp1.py`에 하드코딩돼 있어 프로덕션 프롬프트 개정 시 자동으로 따라가지 않는다. 향후 `intent_parser.SYSTEM_PROMPT`를 고칠 때마다 `SYSTEM_DIRECT_FLOW`의 대응 규칙도 함께 점검해야 한다.

---

## 2. 전체 지표 비교

| 지표 | T-A | T-B | T-C | T-D |
|---|---|---|---|---|
| schema_validity | 0.971 | 0.954 | 0.983 | **0.989** |
| status_match | 0.560 | 0.743 | 0.809 | **0.949** |
| false_rejection_rate | 0.507 | 0.267 | 0.173 | **0.047** |
| rejection_recall | 0.960 | 0.800 | 0.700 | 0.920 |
| rejection_reason_match | 0.917 | 0.850 | 0.914 | **0.957** |
| false_acceptance_rate | **0.040** | 0.180 | 0.300 | 0.060 |
| **NEM** | N/A (포맷 상이) | 0.164 | 0.149 | **0.692** |
| hallucinated_entity_rate | N/A | 0.005 | 0.001 | **0.000** |
| rule_count_match | N/A | 0.926 | 1.000 | 0.956 |

**T-A의 NEM은 구조적으로 N/A다** — T-A는 IntentIR이 아니라 raw ONOS FlowRule JSON을 출력하므로 IR 슬롯 단위 채점이 적용되지 않는다(EVAL_PLAN §2-1이 명시한 설계). T-A의 비교 지표는 `schema_validity` / `status_match` / `false_rejection_rate`다.

**주목할 트레이드오프**: T-A는 false_acceptance_rate가 0.040으로 가장 낮고 rejection_recall이 0.960으로 가장 높다. 즉 T-A는 "거부해야 할 걸 잘 거부"하지만, 그 대가로 "수락해야 할 것의 절반을 거부"(false_rejection 0.507)한다. 보수적으로 치우친 것이지 판별력이 좋은 게 아니다.

---

## 3. T-A vs T-B — IR의 기여 (논문 핵심 주장)

T-A와 T-B는 few-shot·grounding이 **둘 다 꺼진** 조건에서의 비교이며, 주된 차이는 출력 형식(ONOS FlowRule 직접 생성 vs IntentIR)이다. 단, 두 프롬프트는 출력 형식 외에도 정보량이 달라 **완전한 단일 변수 조작은 아니다** — 자세한 내용과 그 영향 방향은 §8 한계 3 참고.

| 지표 | T-A (Direct FlowRule) | T-B (IntentIR) | Δ |
|---|---|---|---|
| status_match | 0.560 | 0.743 | **+0.183** |
| false_rejection_rate | 0.507 | 0.267 | **−0.240** |
| schema_validity | 0.971 | 0.954 | −0.017 |

**왜 T-A가 오거부하는가 — 형식이 강제하는 조기 확정(premature commitment).** T-A 오거부 152건의 사유를 분류하면:

| 사유 유형 | 예시 인텐트 | 모델의 거부 사유 |
|---|---|---|
| egress port 미확정 | "Set up forwarding from h3 to h2." | "Egress port not specified for forwarding action" |
| queueId 미확정 | "Give h1 to h3 at least 10 Mbps." | "Bandwidth guarantee cannot be enforced; requires queueId" |

ONOS FlowRule 스키마는 `OUTPUT` instruction에 **포트 번호 정수**를, QoS엔 **queueId 정수**를 반드시 요구한다. 인텐트에 그 값이 없으면 LLM은 지어내거나(환각) 거부할 수밖에 없고, qwen3-8b는 정직하게 거부를 택했다. 반면 IntentIR은 `egress_port: null`, `device: null`을 허용하고 **물리 자원 확정을 Stage 2 결정론적 컴파일러로 미룬다** — 그래서 같은 인텐트를 수락할 수 있다.

이것이 카테고리별로 가장 극단적으로 드러나는 곳이 **QoS**다: T-A status_match **0.080** vs T-B 0.720. QoS 인텐트는 대부분 대역폭/지연만 말하고 큐 번호를 말하지 않기 때문이다.

> **해석 주의**: 이 결과는 "LLM이 FlowRule을 못 만든다"가 아니라 **"IR 없는 구조는 LLM에게 알 수 없는 값을 강제로 확정하게 만들고, 그 압력이 오거부(또는 환각)로 배출된다"**는 것이다. 파이프라인이 IR + 결정론적 컴파일러로 관심사를 분리한 설계 근거를 실측으로 뒷받침한다.

---

## 4. T-B vs T-C — Few-shot의 기여 (제한적)

| 지표 | T-B | T-C | Δ |
|---|---|---|---|
| status_match | 0.743 | 0.809 | +0.066 |
| false_rejection_rate | 0.267 | 0.173 | −0.094 |
| false_acceptance_rate | 0.180 | 0.300 | **+0.120** ⚠️ |
| NEM | 0.164 | 0.149 | **−0.015** |
| dst_port 슬롯 | 0.636 | 0.951 | +0.315 |
| source_ip 슬롯 | 0.107 | 0.094 | −0.013 |

Few-shot은 **출력 형식 준수**(schema_validity +0.029, dst_port +0.315)와 **수락 판정**에는 도움이 되지만, **슬롯 값의 사실 정확도는 개선하지 못한다**(NEM 소폭 하락). 게다가 rejection_recall이 0.800 → 0.700으로 떨어지고 false_acceptance가 0.180 → 0.300으로 올랐다 — few-shot 데모 5개가 전부 accepted 예시이다 보니 모델이 "일단 수락" 쪽으로 편향된 것으로 보인다.

**핵심**: few-shot 예시 몇 개로는 host↔IP 매핑을 일반화해서 배우지 못한다. source_ip는 0.107 → 0.094로 사실상 그대로다.

---

## 5. T-C vs T-D — Grounding의 기여 (지배적)

| 슬롯 | T-B | T-C | T-D | Grounding 효과 (T-D−T-C) |
|---|---|---|---|---|
| protocol | 1.000 | 0.967 | 1.000 | +0.033 |
| action | 0.932 | 0.935 | 0.965 | +0.030 |
| dst_port | 0.636 | 0.951 | 0.968 | +0.017 |
| queue / min_bw / max_latency | ~1.000 | ~0.99 | 1.000 | ~0 |
| device | 0.552 | 0.595 | 0.819 | **+0.224** |
| egress_port | 0.430 | 0.469 | 0.835 | **+0.366** |
| **source_ip** | 0.107 | 0.094 | 0.908 | **+0.814** |
| **destination_ip** | 0.150 | 0.137 | 0.908 | **+0.771** |
| alt_egress_port | 0.000 | 0.027 | 0.292 | +0.265 |
| waypoints | 0.500 | 0.595 | 0.542 | −0.053 |

**Grounding은 IP 슬롯을 사실상 전담 해결한다.** grounding 인벤토리에 `h1 = 10.0.0.1` alias 테이블이 들어가니 당연한 결과이기도 하지만, 중요한 건 **few-shot으로는 이게 안 됐다는 대조**다(§4). 명시적 그라운딩 인벤토리가 있어야만 해결되는 문제 유형이 존재한다는 뜻이다.

`waypoints`만 유일하게 소폭 하락(−0.053)했는데, 이는 `topology_eval.json`의 그라운딩 결함 때문으로 확인됐다 — s1의 firewall은 포트 9가 명시돼 있는데 s2의 IDS는 포트 정보가 아예 없어서, 모델이 "포트를 모르니 유효 엔티티가 아니다"라고 판단한 케이스가 있다(자세한 내용은 `T-D_openrouter_result.md` §5).

---

## 6. 카테고리별 비교

### status_match (전 treatment)

| 카테고리 | T-A | T-B | T-C | T-D |
|---|---|---|---|---|
| forwarding | 0.660 | 0.620 | 0.780 | 0.980 |
| security | 0.540 | 0.600 | 1.000 | 1.000 |
| **qos** | **0.080** | 0.720 | 0.640 | 0.880 |
| sfc | 0.580 | 0.920 | 0.740 | 0.960 |
| reroute | 0.620 | 1.000 | 1.000 | 1.000 |
| compound | 0.480 | 0.540 | 0.800 | 0.900 |
| ambiguous_unsupported | 0.960 | 0.800 | 0.700 | 0.920 |

### NEM (T-B/C/D — T-A는 IR 슬롯 없음)

| 카테고리 | T-B | T-C | T-D |
|---|---|---|---|
| security | 0.400 | 0.280 | **0.900** |
| compound | 0.148 | 0.100 | **0.844** |
| qos | 0.111 | 0.062 | **0.841** |
| forwarding | 0.290 | 0.256 | **0.837** |
| reroute | 0.140 | 0.140 | 0.580 |
| **sfc** | 0.000 | 0.000 | **0.167** |

모든 카테고리에서 grounding 도입(T-C→T-D) 시점에 큰 폭으로 뛴다. **sfc는 T-B/T-C에서 0.000** — grounding 없이는 단 한 건도 완전히 맞히지 못했다. T-D에서도 0.167로 여전히 최저이며, 이는 SFC가 (a) waypoint 포트 확정, (b) 왕복 경로의 alt_egress_port 추론이라는 다단계 토폴로지 추론을 요구하기 때문이다. 8B 모델은 배선표를 줘도 이 추론을 잘 못한다 — **컴파일러가 포트 계산을 담당해야 한다는 파이프라인 논지를 지지하는 실측 근거**.

---

## 7. 실행 비용 및 안정성

| Treatment | 평균 지연 | 최대 지연 | 평균 입력 토큰 | 평균 출력 토큰 | schema_invalid |
|---|---|---|---|---|---|
| T-A | 38.2s | 184s | 946 | 2,667 | 10 |
| T-B | 35.2s | 132s | 1,660 | 2,315 | 16 |
| T-C | 31.7s | 138s | 2,523 | 1,852 | 6 |
| T-D | 38.9s | 145s | 2,894 | 2,190 | 4 |

- **transport 에러는 4개 run 통틀어 0건.** 실패는 전부 JSON 파싱 실패(schema_invalid).
- Grounding은 입력 토큰을 늘리지만(+371 vs T-C) 출력 토큰과 실패율을 함께 낮춘다 — 프롬프트 비용 대비 이득이 명확하다.
- **프로세스 중단 이슈**: T-A/T-C에서 rep 종료 직전 프로세스가 죽는 현상이 4회 관측됐다(누락 1~4건). 매번 죽기 직전 완료 케이스가 SFC 카테고리에 편중돼 있는데, SFC/compound가 가장 긴 thinking(최대 184초, 12K+ 토큰)을 유발하는 것과 관련 있어 보인다. 누락 케이스는 별도 호출로 보강해 4개 run 모두 350/350 확보했다. **근본 원인은 미규명 — §8 참고.**

---

## 8. 한계 및 다음 단계

### 한계

1. **n=1 rep.** 모든 수치가 단일 실행 결과다. 특히 T-B vs T-C의 NEM 역전(0.164→0.149)은 크기가 작아 샘플링 노이즈와 구분되지 않는다. 최소 3 rep 확보 필요.
2. **T-A vs T-B는 지표 일부만 비교 가능.** 출력 포맷이 달라 NEM/슬롯 정확도는 T-A에 적용 불가. `status_match`·`false_rejection_rate`만으로 논지를 세워야 한다.
3. **⚠️ T-A vs T-B는 단일 변수 조작이 아니다 — 프롬프트 비대칭 (가장 중요한 한계).**
   `SYSTEM_DIRECT_FLOW`(T-A, 3,362자)와 `SYSTEM_PROMPT`(T-B/C/D, 6,089자)는 출력 형식 외에도 정보량이 다르며, 교란이 **양방향**으로 존재한다.

   | 방향 | 항목 |
   |---|---|
   | T-A에만 있음 (T-A에 유리) | `hosts h1-h4 / switches s1-s4는 표준 이름` 화이트리스트 — **사실상 부분적 토폴로지 정보**이며 T-B는 못 받음 |
   | T-B/C/D에만 있음 (T-B에 유리) | `## Compound intents` 섹션 + 워크드 예시 2개, `## action / intent_type mapping` 표, `## Field rules` 상세 |

   **결론의 방향성은 보존된다**: T-A는 엔티티 화이트리스트라는 이점을 받고도 T-B보다 낮았으므로(0.560 vs 0.743), 측정된 IR 효과 **+0.183은 보수적 추정**일 가능성이 높다. 다만 "IR의 순수 기여"라는 표현은 엄밀하지 않으며, 논문에는 **"IR 기반 프롬프트 패키지 vs 직접 생성 패키지의 비교"**로 기술하거나 엄격 패리티 재실행이 필요하다.

   완전한 패리티는 출력 형식이 다른 이상 원리적으로 달성 불가능하다는 점도 함께 명시해야 한다.
4. **Ollama vs OpenRouter 서빙 차이.** 동일 qwen3-8b라도 서빙 스택이 다르면 결과가 달라진다(이전 Ollama run: schema 0.871 / NEM 0.514 vs OpenRouter 0.989 / 0.692). 본 보고서의 4개 run은 모두 OpenRouter라 내부 비교는 유효하다.

### 다음 단계

1. **rep 수 확대 (최우선)** — 4 treatment × 3 rep 이상. T-B/T-C NEM 역전의 실체 확인.
2. **SFC 구간 프로세스 다운 원인 조사** — 4회 재현된 패턴. concurrency를 낮춰(예: 10) 재현 여부 확인, 장시간 thinking 케이스의 자원 사용 계측.
3. **`topology_eval.json` s2 IDS 그라운딩 보강** — s1 firewall과 달리 포트 정보가 없어 SFC waypoints 정확도를 구조적으로 깎고 있음.
4. **QoS 완결성 규칙 검토** — T-D에서도 QoS false rejection이 "enforcement device 미명시" 사유로 남아 있음(`T-D_openrouter_result.md` §4).
5. **few-shot 데모 구성 재검토** — 현재 5개 전부 accepted 예시라 T-C의 false_acceptance 상승(0.180→0.300)을 유발했을 가능성. rejected 예시 포함 버전과 비교.
