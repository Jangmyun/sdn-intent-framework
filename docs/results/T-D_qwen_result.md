# T-D 실험 결과 보고서 — qwen3:8b × GOLD-350 (rep 1)

> 작성일: 2026-07-23
> Treatment: **T-D** (IntentIR + Few-Shot + Topology Grounding **w/ wiring**)
> 모델: `qwen3:8b` (Ollama, thinking 모드) | Temperature: `0.2` | max_tokens: `8192` | Repetitions: **1**
> 데이터셋: `gold350_eval.jsonl` (**GOLD-350**: 350 cases = accepted 300 / rejected 50, 7카테고리 × 50)
> run_id: `T-D-qwen3-8b-7dcdcd3d` | 채점 리포트: `experiments/eval/reports/T-D_qwen_r1_summary.json`
>
> ⚠️ 이 결과는 기존 `T-D_result.md`(Gemini × 구 60케이스)와 **직접 비교 불가** — 데이터셋(60→350, 배선 의존 gold 포함)과 모델이 모두 다르다. 아래 7장 참조.

---

## 1. 전체 지표 요약

| 지표 | 값 | 해석 |
|------|-----|------|
| schema_validity | **0.871** | 45건 JSON 파싱 실패 — 3장에서 원인 분해 |
| status_match | 0.860 | |
| false_rejection_rate | 0.150 | **주의: 45건 중 44건이 JSON 실패, 모델이 판단으로 거부한 것은 단 1건** (2장) |
| rejection_recall | 0.920 | 거부 케이스 50건 중 46건 정확 감지 |
| rejection_reason_match | 0.957 | 감지한 거부의 사유 분류는 거의 완벽 |
| false_acceptance_rate | 0.060 | 오수락 3건 — 전부 "미묘한" 케이스 (4장) |
| **NEM** (Normalized Exact Match) | **0.514** | |
| hallucinated_entity_rate | **0.002** | 그라운딩의 환각 억제 효과는 소형 모델에서도 유효 |

## 2. false_rejection_rate 0.150의 실체 — 판단 오류가 아니라 형식 오류

gold=accepted 300건에 대한 모델 출력 상태를 분해하면:

| pred 상태 | 건수 |
|---|---|
| accepted (정상 파싱) | 255 |
| **error (JSON 파싱 실패)** | **44** |
| rejected (모델의 명시적 거부) | **1** |

채점기는 error를 "수락하지 못함"으로 집계하므로 표면상 false rejection이 15%지만, **모델의 수락/거부 판단 자체는 유효 출력 기준 255/256 = 99.6% 정확**하다. 유일한 진짜 false rejection은 G-QOS-013 1건("Latency constraints require specific enforcement devices…"라며 ambiguous 거부 — 과잉 신중). 즉 이 모델의 문제는 **판단력이 아니라 출력 형식 준수**다.

## 3. JSON 파싱 실패 45건 원인 분해

| 원인 | 건수 | 상세 |
|---|---|---|
| max_tokens(8192) 한도 도달 | 19 | thinking이 토큰을 소진해 JSON이 잘리거나 시작도 못 함 |
| JSON 대신 영어 산문 출력 | ~26 | "Expecting value: line 1 column 1" 33건 중 다수 — 마크다운 불릿/설명문으로 답변 |

카테고리 분포: **compound 18** > sfc 7 > security 6 > qos 5 = reroute 5 > forwarding 3 > ambiguous 1.
출력이 가장 길고 복잡한 compound에서 집중 발생 — thinking 분량과 형식 붕괴가 비례하는 패턴.

**공정성 이슈**: Gemini 경로는 `response_mime_type="application/json"`으로 JSON을 API 레벨에서 강제하지만, 현재 Ollama 경로(`call_ollama`)는 강제하지 않는다. 모델 간 schema_validity 비교가 구조적으로 qwen에 불리한 상태 — `response_format: json_object` 추가 + rep 1 재실행 여부는 미결정 (8장).

## 4. 오수락 3건 — 전부 능력 경계(capability boundary) 케이스

| Case | Intent | gold 사유 | 분석 |
|---|---|---|---|
| G-AMB-021 | "Drop everything from h1 **and** guarantee h1 to h3 gets 20 Mbps." | contradictory | 절 간 모순(전부 차단 vs 일부 보장) 탐지 실패 — 교차 절 추론 필요 |
| G-AMB-044 | "Limit h2 to h4 to **at most** 1 Mbps." | unsupported | 대역폭 상한(rate limiting)은 미지원 능력 — 하한 보장(qos)으로 오인한 듯 |
| G-AMB-049 | "Block adult content for h2." | unsupported | 콘텐츠 필터링은 미지원 — 일반 block으로 오인한 듯 |

단순한 미지 엔티티/모호성은 다 잡아내고(recall 0.920), **시스템 능력 목록의 경계선**(상한 vs 하한, 콘텐츠 vs 플로우)에서만 실패. 프롬프트의 capability 목록 강화로 개선 여지 있음.

## 5. 슬롯 정확도

| 슬롯 | 정확도 | 비고 |
|------|--------|------|
| protocol / queue / min_bw / max_latency | 1.000 | |
| action | 0.953 | |
| dst_port | 0.911 | |
| device | 0.800 | |
| source_ip / destination_ip | 0.736 / 0.728 | 호스트명→IP 변환 누락이 일부 존재 (grounding에 매핑이 있음에도) |
| egress_port | 0.697 | |
| waypoints | 0.628 | F1(채점기 alias 수정) 적용 후 수치 — 수정 전이었다면 sfc 23케이스가 전부 오답 처리됐을 것 |
| **alt_egress_port** | **0.233** | 최약 슬롯 — 아래 6장 |

## 6. 핵심 발견 — 배선(wiring) 추론은 그라운딩만으로 해결되지 않는다

카테고리별 NEM: security 0.795 > qos 0.682 ≈ forwarding 0.681 > compound 0.594 > **reroute 0.267** > **sfc 0.070**

reroute/sfc가 바닥인 이유는 공통적으로 **배선 추론 실패**다:

- **sfc**: waypoint 자체(0.628)와 진입 포트(예: 방화벽 s1:9)는 맞추지만, "waypoint 통과 **후** 목적지 방향 포트"(alt_egress_port, 0.233)를 못 채운다. 예: G-SFC-001에서 waypoints·device·egress_port=9 전부 정답, alt_egress_port(정답 1)만 null.
- **reroute**: "via switch 3"에서 `via_device=s3`는 추출하지만, gold가 요구하는 `enforcement.egress_port=2`(s1에서 s3로 가는 포트)를 비우거나 틀린다(G-RRT-003: 3 출력, 정답 2).

이번 실험은 그라운딩 프롬프트에 **전체 배선("s1 ports: 1->s2, 2->s3, 3->h1, …")을 명시적으로 제공한 상태**(topology_eval.json v2)였다. 즉 정보 부족이 아니라, 8B 모델이 "h1은 s1에 붙어 있고, s3 경유라면 s1의 2번 포트로 내보내야 한다"는 **다단계 토폴로지 추론 자체를 못 하는 것**이다.

**논문 관점**: 이 결과는 파이프라인의 핵심 설계 주장 — *"경로/포트 결정 같은 토폴로지 추론은 LLM이 아니라 결정론적 컴파일러(Stage 2)가 담당해야 한다"* — 를 지지하는 실측 근거다. LLM에게 배선을 줘도 못 쓴다는 것을 보여주므로, IR에서 의미(어디를 경유)만 추출하고 포트 계산은 코드가 하는 현재 구조의 정당성이 강화된다.

## 7. Gemini(구 60케이스) 결과와의 관계

| | Gemini flash-lite × 구 60케이스 | qwen3:8b × GOLD-350 |
|---|---|---|
| schema_validity | 1.000 | 0.871 |
| status_match | 1.000 | 0.860 |
| NEM | 0.944 | 0.514 |
| hallucination | 0.000 | 0.002 |

**직접 비교 불가**: 데이터셋 자체가 다르다(60→350케이스, GOLD-350은 배선 의존 gold·one-sided 케이스·능력 경계 거부 케이스 포함 — 난도가 명확히 높음). 공정한 모델 비교를 하려면 **Gemini도 GOLD-350으로 재실행**해야 하며, 그 전까지 위 표는 "참고"로만 볼 것.

## 8. 실행 통계 및 다음 단계

- **소요**: 총 131분/rep (평균 22.4초/케이스, 최대 88초 — thinking이 긴 accepted 케이스가 지배적). 3 reps × 4 treatments 전체 ≈ **26시간** 예상.
- 평균 출력 2,043 토큰(thinking 포함), 한도 도달 19건.

**미결정 사항 (다음 세션에서 결정):**
1. **JSON 강제(response_format) 추가 여부** — 공정성 관점에선 추가가 맞고, 추가 시 rep 1 재실행 필요(~2.2h). 형식 실패 ~26건(산문 출력)이 사라지면 schema_validity가 0.95+로 오를 것으로 예상.
2. max_tokens 8192 → 상향 여부 (한도 도달 19건 구제; 단 latency 증가 트레이드오프).
3. 나머지 treatments(T-A/B/C) 실행 순서 및 reps 수.
