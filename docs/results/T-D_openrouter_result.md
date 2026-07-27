# T-D 실험 결과 보고서 — qwen3-8b (OpenRouter) × GOLD-350 (rep 1)

> 작성일: 2026-07-24
> Treatment: **T-D** (IntentIR + Few-Shot + Topology Grounding)
> 모델: `qwen/qwen3-8b` (**OpenRouter** 호스팅, thinking 모드) | Temperature: `0.2` | max_tokens: `8192` | reasoning 예산 제한 없음 | Repetitions: **1**
> 실행: `--concurrency 20` (동시 요청 20개)
> 데이터셋: `gold350_eval.jsonl` (GOLD-350: 350 cases = accepted 300 / rejected 50, 7카테고리 × 50)
> run_id: `T-D-qwen-qwen3-8b-ede0ac95` | 채점 리포트: `experiments/eval/reports/T-D_openrouter_r1_summary.json`
>
> ⚠️ 같은 모델(qwen3-8b)이지만 **호스팅 경로가 다르다** — 기존 `T-D_qwen_result.md`는 자체 호스팅 Ollama, 이 보고서는 OpenRouter(서드파티 라우팅, 백엔드 provider/양자화 방식이 다를 수 있음). 완전히 동일한 조건 비교가 아니라는 점을 유의할 것 (7장 참고).

---

## 1. 전체 지표 요약

| 지표 | 값 | Ollama qwen 대비 | 해석 |
|------|-----|---|------|
| schema_validity | **0.989** | 0.871 → 0.989 (+0.118) | JSON 파싱 실패가 45건 → 4건으로 급감 |
| status_match | **0.949** | 0.860 → 0.949 | |
| false_rejection_rate | 0.047 | 0.150 → 0.047 | **주의: 이번엔 형식오류가 아니라 진짜 판단오류가 다수** (2장) |
| rejection_recall | 0.920 | 0.920 (동일) | 거부 케이스 50건 중 46건 정확 감지 — 이전과 완전히 동일 |
| rejection_reason_match | 0.957 | 0.957 (동일) | |
| false_acceptance_rate | 0.060 | 0.060 (동일) | 오수락 3건 — 세부 케이스는 달라짐 (4장) |
| **NEM** (Normalized Exact Match) | **0.692** | 0.514 → 0.692 (+0.178) | 큰 폭 개선 |
| hallucinated_entity_rate | **0.000** | 0.002 → 0.000 | 환각 완전 제거 |

rejection_recall·rejection_reason_match·false_acceptance_rate 세 지표가 Ollama 실행과 **숫자까지 완전히 동일**한 점이 눈에 띈다 — 같은 모델 가중치가 ambiguous_unsupported 카테고리(50건)에서 거의 같은 판단 패턴으로 수렴한 것으로 보이나, 실제 오답 케이스 구성은 달라졌다(4장).

---

## 2. false_rejection_rate 0.047의 실체 — 이번엔 형식오류가 아니라 진짜 판단오류가 주력

gold=accepted 300건에 대한 모델 출력 상태 분해:

| pred 상태 | 건수 |
|---|---|
| accepted (정상 파싱) | 286 |
| rejected (모델의 명시적 거부, 유효 JSON) | **11** |
| error (JSON 파싱 실패) | 3 |

Ollama 실행 때는 정반대였다 — 44/45가 형식 실패, 진짜 오판단은 1건뿐. 이번엔 형식은 거의 완벽(3건만 실패)해진 대신, **11건이 진짜로 잘못 거부됐다.**

### 핵심 패턴: QoS 계열 "enforcement device 미명시" 오판단 (11건 중 7건)

| Case | 카테고리 | 모델 거부 사유 | intent |
|---|---|---|---|
| G-QOS-013 | qos | "Enforcement device not specified" | "Keep h1 to h4 latency below 10 ms." |
| G-QOS-022 | qos | 상동 | "Bound the h4 to h2 delay at 50 ms." |
| G-QOS-024 | qos | 상동 | "Hold latency from h1 to h3 under 18 ms." |
| G-QOS-025 | qos | 상동 | "Prioritize h1 to h3 traffic on queue 1." |
| G-QOS-026 | qos | 상동 | "Put h2 to h4 traffic in queue 2." |
| G-QOS-044 | qos | 상동 | "Backup transfers from h3 to h1 need at least 60 Mbps." |
| G-CMP-007 | compound | 상동(forward 서브룰) | "Forward h2 to h3 traffic but drop its UDP." |

전부 "호스트 이름만 언급되고 스위치가 명시되지 않았다"는 이유로 ambiguous 거부다. 그런데 grounding 프롬프트(`topology_eval.json`)의 `wiring_notes`에는 "h1, h2 attach to s1; h3, h4 attach to s4."가 명시돼 있다 — 즉 **모델에게 host→switch 매핑 정보가 주어졌는데도 QoS류 인텐트에서는 이를 활용해 device를 추론하지 않고 그냥 거부**한다. forwarding/security 카테고리에서는 이런 패턴이 거의 없었던 것으로 보아(카테고리별 표 참고), 시스템 프롬프트의 완결성 규칙이 action별로 일관되게 적용되지 않고 있을 가능성이 있다 — QoS 인텐트에 대해서만 device 명시를 유난히 엄격하게 요구하는 것으로 보인다.

### 두 번째 패턴: SFC "IDS on switch 2" 미지 엔티티 오판단 (2건) — 실제로는 grounding 데이터 자체의 결함일 가능성

| Case | intent | 모델 거부 사유 |
|---|---|---|
| G-SFC-026 | "Traffic from h3 to h1 must transit the IDS on switch 2." | "topology does not specify a port for the IDS service" |
| G-SFC-040 | "Route database traffic on TCP 5432 from h2 to h4 through the IDS on switch 2." | "IDS on switch 2 is not a valid entity in the topology" |

`topology_eval.json`을 직접 확인한 결과 — `wiring_notes`엔 "s2 hosts IDS/DPI/LB/proxy/scrubbing services"라고 **서비스 존재는 알려주지만**, s1의 firewall/IDS(포트 9로 명시)와 달리 **s2의 IDS에는 포트 번호가 전혀 부여돼 있지 않다** (`ports["of:...002"]`는 `[1, 2]`뿐). 즉 모델이 "포트가 없어서 유효 엔티티가 아니다"라고 판단한 건 **주어진 grounding 정보를 있는 그대로 정직하게 읽은 결과**에 가깝다 — 모델의 환각이나 오독이 아니라, **topology_eval.json의 s2 IDS 그라운딩이 s1 대비 불완전하게 작성되어 있다는 실측 증거**다. gold가 이를 accepted로 기대한다면, 그라운딩 프롬프트에 "포트 없는 device-attached 서비스는 device 자체를 enforcement 대상으로 써도 된다"는 명시적 규칙을 추가해야 할 것으로 보인다.

---

## 3. JSON 파싱 실패 4건 — 이번엔 원인이 다르다: max_tokens 초과가 아니라 리즌닝이 max_tokens를 무시함

| Case | 카테고리 | output_tokens | latency | 원인 |
|---|---|---|---|---|
| G-AMB-013 | ambiguous_unsupported | 450 | 9.5s | 중첩 괄호 등 소규모 포맷 오류 |
| G-CMP-034 | compound | 8,706 | 85.5s | 긴 thinking 후 JSON 형태는 맞으나 파싱 실패 |
| G-CMP-037 | compound | 8,837 | 83.6s | 상동 |
| G-CMP-023 | compound | 12,110 | 136.3s | 상동 |

**주목할 점**: `max_tokens=8192`로 설정했음에도 **10건**의 케이스가 8,192 토큰을 넘겨 출력했다(최대 G-SEC-049 12,545 토큰). 이는 OpenRouter가 이 모델의 `max_tokens`를 최종 답변에만 적용하고 **thinking(reasoning) 토큰은 별도로 취급**한다는 뜻으로 보인다 — Ollama 로컬 실행에선 `max_tokens`가 thinking을 포함한 전체 출력을 제한했던 것과 다른 동작이다. `reasoning: {"max_tokens": N}` 같은 별도 파라미터로 thinking 예산을 명시적으로 잡아주지 않는 한, compound처럼 복잡한 케이스는 무제한으로 길어질 수 있다는 것이 이번 실행으로 실측 확인됐다(단, 4장 전 대화에서 이 파라미터를 실제로 켜봤을 때 정확도가 떨어지는 트레이드오프가 확인되어 이번 실행에서는 의도적으로 끄고 진행함).

---

## 4. 오수락 3건 — 케이스 구성이 Ollama 실행과 다르다 (표본 변동성)

| Case | Intent | gold 사유 | 비고 |
|---|---|---|---|
| G-AMB-021 | "Drop everything from h1 and guarantee h1 to h3 gets 20 Mbps." | contradictory | Ollama 실행에서도 오수락 — 재현된 실패 |
| G-AMB-046 | "Mirror all of h2's traffic to h4 for analysis." | unsupported (트래픽 미러링 미지원) | 신규 |
| G-AMB-048 | "Cache web content for h2 at the edge." | unsupported (엣지 캐싱 미지원) | 신규 |

Ollama 실행의 오수락 3건(G-AMB-021, **G-AMB-044**, **G-AMB-049**)과 겹치는 건 G-AMB-021 하나뿐이다. G-AMB-044·049는 이번 실행에서 정확히 거부됐고, 대신 G-AMB-046·048에서 새로 틀렸다. false_acceptance_rate 자체는 우연히 3/50(0.060)으로 동일하지만, **어떤 케이스를 틀리는지는 실행마다 달라진다** — 이는 4장(reasoning_max_tokens 실험)에서 이미 확인했던 대로 이 모델의 능력 경계 판단이 샘플링에 따라 흔들린다는 뜻이다. **n=1 rep 결과에서 "이 모델은 G-AMB-021을 못 푼다"처럼 케이스 단위로 단정하는 것은 위험** — 여러 rep을 돌려야 어떤 실패가 안정적 패턴인지, 어떤 게 노이즈인지 구분할 수 있다.

---

## 5. 슬롯 정확도

| 슬롯 | 정확도 | Ollama 대비 | 비고 |
|------|--------|---|------|
| protocol / queue / min_bw / max_latency | 1.000 | 동일 | |
| action | 0.965 | 0.953 → 0.965 | |
| dst_port | 0.968 | 0.911 → 0.968 | |
| device | 0.819 | 0.800 → 0.819 | |
| egress_port | 0.835 | 0.697 → 0.835 | 큰 개선 |
| source_ip / destination_ip | 0.908 / 0.908 | 0.736 / 0.728 → 0.908 / 0.908 | 큰 개선 — 파싱 성공률 상승의 파급 효과로 보임 |
| waypoints | 0.542 | 0.628 → **0.542 (하락)** | schema_validity 개선에도 불구하고 오히려 하락 — SFC 카테고리 자체 난이도 문제(2장의 s2 그라운딩 결함과 연결) |
| **alt_egress_port** | **0.292** | 0.233 → 0.292 | 소폭 개선했지만 **여전히 최약 슬롯** |

대부분의 슬롯이 schema_validity 상승(더 많은 유효 케이스가 채점에 포함됨)의 파급 효과로 개선됐지만, waypoints는 오히려 하락했다 — SFC 카테고리 자체의 난이도(특히 s2 IDS 그라운딩 결함)가 형식 문제와는 독립적인 병목임을 시사한다.

---

## 6. 카테고리별 성능

| 카테고리 | status_match | NEM | Ollama NEM 대비 |
|---|---|---|---|
| security | 1.000 | 0.900 | 0.795 → 0.900 |
| compound | 0.900 | 0.844 | 0.594 → 0.844 |
| qos | 0.880 | 0.841 | 0.682 → 0.841 |
| forwarding | 0.980 | 0.837 | 0.681 → 0.837 |
| reroute | 1.000 | 0.580 | 0.267 → 0.580 |
| **sfc** | 0.960 | **0.167** | 0.070 → 0.167 |
| ambiguous_unsupported | 0.920 | N/A | 0.920 → 0.920 (동일) |

**모든 카테고리가 개선됐다.** 그러나 순위는 그대로다 — sfc가 압도적 최하위, reroute가 그 다음. 절대 수치는 크게 올랐지만(sfc 0.070→0.167, 2.4배), 다른 카테고리(0.8~0.9대)와의 격차는 여전히 크다. **배선/다단계 토폴로지 추론이 여전히 핵심 병목이라는 지난 보고서의 결론은 이번에도 유지된다** — 오히려 2장에서 확인한 s2 그라운딩 결함처럼, 문제가 "모델의 추론력"뿐 아니라 "그라운딩 데이터 자체의 완결성"에도 있다는 새로운 단서가 추가됐다.

---

## 7. 세 실행 비교 (참고용 — 직접 비교 불가)

| | Gemini flash-lite × 구 60케이스 | qwen3-8b (Ollama) × GOLD-350 | qwen3-8b (**OpenRouter**) × GOLD-350 |
|---|---|---|---|
| schema_validity | 1.000 | 0.871 | **0.989** |
| status_match | 1.000 | 0.860 | **0.949** |
| NEM | 0.944 | 0.514 | **0.692** |
| hallucination | 0.000 | 0.002 | **0.000** |

세 실행 모두 데이터셋·모델·호스팅 경로 중 하나 이상이 다르다. 특히 Ollama vs OpenRouter는 **같은 모델 가중치라고 알려져 있지만 실제로는 provider/양자화/서빙 스택이 다를 수 있어** 완전한 통제 비교가 아니다 — schema_validity가 0.871→0.989로 급등한 것도 모델이 똑똑해진 게 아니라 **서빙 스택이 더 안정적으로 JSON을 뱉는다**는 인프라적 차이일 가능성이 크다. 이 두 경로를 "같은 모델의 신뢰할 수 있는 재현"으로 논문에 쓰려면, 두 경로 모두 동일 조건(같은 quantization, 같은 시스템 프롬프트, 여러 rep)에서 재현되는지 확인이 필요하다.

---

## 8. 실행 통계 및 다음 단계

- **동시성**: `--concurrency 20`으로 실행, 429(rate limit) 에러 0건
- **latency**: 평균 38.9초/케이스, 중앙값은 더 짧지만 compound/sfc/security 카테고리의 긴 꼬리(최대 145초, G-SEC-049)가 평균을 끌어올림
- **토큰**: 평균 출력 2,190 토큰(thinking 포함), 10건이 max_tokens(8192) 설정을 초과 출력 — 3장 참고

**다음 세션에서 결정할 사항:**
1. QoS류 "enforcement device 미명시" 거부 패턴(7건) — 시스템 프롬프트의 완결성 규칙을 action 타입 전반에 일관되게 loosen할지 검토 (프로덕션 `intent_parser.SYSTEM_PROMPT` F2 개정과 같은 종류의 조치가 QoS에도 필요할 수 있음)
2. `topology_eval.json`의 s2 IDS 그라운딩에 포트 정보 추가 또는 "포트 없는 서비스는 device 자체로 참조 가능" 규칙 명시
3. rep 수를 늘려(최소 3) 이번 실행에서 본 오수락/오거부 케이스가 안정적 패턴인지 샘플링 노이즈인지 구분
4. Ollama vs OpenRouter 서빙 경로 차이가 실제로 결과에 영향을 주는지 별도로 통제된 비교 실행 필요 여부 판단
5. 아직 실행 안 된 T-A/B/C(OpenRouter)를 언제, 몇 rep으로 돌릴지
