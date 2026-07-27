# E1 결과 — RQ1 (2026-07-16 실행, 2026-07-16 정정)

> Gold status: **provisional_gold**. 아래 수치는 독립 이중 annotation과 adjudication이
> 완료되기 전 pipeline-fixture gold로 계산되었다. 최종 논문 수치는 annotation 확정 후
> 재계산해야 한다. 재현: `experiments/e1/score.py`에 아래 20개 로그 파일을 전달하면
> 동일한 `logs/e1/e1_aggregate_full.json`이 생성되고, `--cohort upstream` 플래그를
> 추가하면 §1a의 `logs/e1/e1_aggregate_upstream_only.json`이 생성된다. 실행 환경:
> model `qwen3:8b`(Ollama-compatible, temperature 0.2, num_ctx 4096, `/no_think`),
> 4 treatment × 5 repetition(seed 42–46) × 100 case = 2,000 call.
>
> **정정 이력**: 외부 검토로 (1) E1-A vs IR 비교의 task-equivalence confound,
> (2) E1-A 과잉거절 수치 오류 및 이를 유발한 채점 코드 버그, (3)
> `raw_onos_only_exact_match` 설명 오류, (4) reason별 recall 표본 크기 누락을
> 지적받아 모두 검증 후 반영했다. 채점 버그는 `safe_intent_sdn/e1_evaluation.py`의
> `evaluate_run()`을 수정하고(§3 참고) `logs/e1/e1_aggregate_full.json`을 재생성해
> 아래 표 전체를 갱신했다. E1-B/C/D 수치는 버그의 영향을 받지 않아 이전과 동일하다.

## Table 4. Intent translation 성능 (E1, mean of 5 runs, 100-case 전체)

> **Confound 고지**: 아래 100-case 비교는 project-authored gold(accepted 40건 전원)에
> `enforcement.device`가 없고 그중 28건은 `egress_port`도 없다는 비대칭을 포함한다.
> ONOS FlowRule은 `deviceId`와 OUTPUT 포트가 항상 필수이므로 E1-A는 gold가 요구하지
> 않는 placement 정보를 매번 채워야 하고, 그 슬롯은 구조적으로 mismatch 처리된다.
> **E1-A와 IR(B/C/D)을 통제된 조건에서 비교하려면 §1a의 upstream-only(N=50) 결과를
> 사용해야 한다.**

| Metric | E1-A (direct flow) | E1-B (IR, zero-shot) | E1-C (IR, few-shot) | E1-D (IR, few-shot+grounded) |
| --- | ---: | ---: | ---: | ---: |
| Response schema validity | 0.432 | 0.830 | 0.930 | 0.910 |
| Normalized exact match | 0.020 | 0.200 | 0.218 | **0.368** |
| Normalized rule-count accuracy | 0.013 | 0.778 | 0.844 | 0.822 |
| Normalized type accuracy | 0.400 | 0.895 | 0.901 | 0.911 |
| Required rejection rate (10-case) | 1.000\* | 0.400 | 0.700 | 0.680 |
| Unsupported-only rejection rate (2-case) | 1.000 | 1.000 | 1.000 | 1.000 |
| Hallucinated entity rate | 0.036\* | 0.159 | 0.241 | **0.021** |

\* E1-A의 겉보기 required-rejection/hallucination 수치는 §3에서 설명하듯 실제 능력이
아니라 대량 과잉거절(over-rejection)의 부산물이므로 다른 treatment와 직접 비교할 수
없다.

Run-to-run 표준편차: 위 7개 핵심 집계 지표에서 대부분은 동일하거나 매우 낮은 변동을
보였다. E1-B는 모든 지표에서 `sample_sd=0`, E1-C는 `normalized_exact_match`에서만
작은 변동(sd=0.00447), **E1-D는 `normalized_exact_match`(sd=0.00447)와
`required_rejection_rate`(sd=0.04472, 7개 지표 중 최댓값)에서 변동**을 보였다. E1-A는
이보다 훨씬 큰 변동을 보인다(예: hallucination rate min 0.000–max 0.182). §3–5에서
이 비대칭을 별도로 논의한다.

## 1. RQ1에 대한 직접 답변

> **RQ1. LLM/RAG는 자연어 네트워크 intent를 얼마나 정확하고 일관된 Intent IR로
> 변환할 수 있는가?**

Controller-neutral Intent IR로 출력을 제한하는 것은 direct ONOS flow 생성 대비
구조적 정확성을 뚜렷하게 개선한다: 구조적으로 파싱 가능한 응답 비율이 43.2%에서
83–93%로 오르고(E1-A vs E1-B/C/D), rule-count·type accuracy도 큰 폭으로 개선된다.
다만 §1a에서 확인하듯 위 100-case 비교에는 project-authored gold의
task-equivalence confound가 섞여 있어, **exact-match 기준의 배수 비교("N배
개선")는 신뢰할 수 있는 수치가 아니다** — 이 부분은 §1a의 통제 비교로 대신한다.

IR 형식 채택 자체는 hallucination을 해결하지 못하며, 여기에 예시 기반
prompting(few-shot)을 더하면 형식 안정성과 거절 판단은 개선되지만 hallucination은
오히려 악화된다(0.159 → 0.241, E1-B→E1-C). Hallucination을 실제로 억제하는 것은
few-shot이 아니라 topology 상태를 prompt에 주입하는 state-grounding이며, grounding을
추가한 E1-D에서 hallucination rate가 0.021로 급락하고 exact match도 0.368로 4개
조건 중 최고치를 기록한다.

종합하면, 현재 데이터는 "LLM/RAG가 정확하고 일관된 IR 변환을 **달성했다**"는 강한
주장을 뒷받침하지 않는다. 대신 뒷받침되는 것은 (a) IR 형식이 direct output 대비
**상대적으로 개선**된 구조적 신뢰성을 준다는 것, (b) 이 개선이 단일 개입이 아니라
IR 형식(구조적 정확성)과 state-grounding(entity 정확성)의 결합에서 온다는 것, (c)
그럼에도 unknown-entity 거절(§4)처럼 grounding으로도 해결되지 않는 오류 유형이
남아 있어 **독립적인 후속 validator가 필요하다는 것**이다. RQ1의 답은 "달성"이
아니라 "상대적 개선과 후속 검증 단계의 필요성 확인"으로 요약한다.

## 1a. Upstream-only 통제 비교 (task-equivalence confound 제거)

Upstream cohort(N001–N050, NetIntent 원본)는 50건 전부 accepted이고 gold에 device
누락 0건, egress_port 누락 1건뿐이라 E1-A(ONOS FlowRule 직접 생성)와 E1-B/C/D(IR
생성)를 **동일한 표현력 요구 수준에서** 비교할 수 있다. 동일 로그를 `--cohort
upstream`으로 재채점한 결과:

| Metric | E1-A | E1-B | E1-C | E1-D |
| --- | ---: | ---: | ---: | ---: |
| Response schema validity | 0.148 | 0.680 | 0.880 | 0.840 |
| Normalized exact match | 0.000 | 0.000 | 0.000 | **0.280** |
| Normalized rule-count accuracy | 0.024 | 0.640 | 0.820 | 0.760 |
| Normalized type accuracy | 0.067 | 0.944 | 0.952 | 0.975 |
| Hallucinated entity rate | 0.050 | 0.289 | 0.486 | **0.042** |

세 가지가 확인된다.

1. **Exact-match 배수 비교는 confound로 부풀려져 있었다는 지적이 맞다.**
   통제 비교에서 E1-A/B/C의 exact match는 모두 0.000이다 — 100-case 비교의
   "10–18배" 프레이밍은 이 confound 없이는 성립하지 않았을 수치다.
2. **그러나 IR의 구조적 우위는 confound와 무관하게 유지된다.** Schema
   validity(0.148 vs 0.680–0.880), rule-count accuracy(0.024 vs 0.640–0.820),
   type accuracy(0.067 vs 0.944–0.975) 모두 통제 비교에서도 direct output이
   압도적으로 불리하다.
3. **State-grounding의 효과는 통제 비교에서 오히려 더 뚜렷하다.** 4개 조건 중
   E1-D만 upstream cohort에서 0이 아닌 exact match(0.280)를 낸다. Few-shot
   단독(E1-C)의 hallucination rate는 project-authored cohort보다 upstream에서
   더 나쁘다(0.241→0.486) — 실제 ONOS 배치 정보가 정확히 요구되는 상황일수록
   grounding 없이는 hallucination이 심해진다는 뜻이다. Grounding을 더한 E1-D만
   0.042로 낮게 유지된다.

## 2. Slot-level 분해: grounding이 정확히 무엇을 고치는가

(100-case 전체 기준. E1-B/C/D는 채점 버그의 영향을 받지 않는다.)

| Slot | E1-B | E1-C | E1-D |
| --- | ---: | ---: | ---: |
| device | 0.382 | 0.481 | **0.924** |
| eth_type | 0.526 | 0.657 | 0.582 |
| action | 0.882 | 0.877 | 0.899 |
| source/destination | 0.882–0.961 | 0.926–0.951 | 0.962–0.975 |
| egress_port | 0.868 | 0.963 | 0.962 |

`device` slot 정확도만 E1-C→E1-D에서 0.481→0.924로 거의 두 배 뛰고, 다른 slot은
E1-C 대비 큰 변화가 없다. 이는 hallucinated_entity_rate 급락(0.241→0.021)이
전반적 능력 향상이 아니라 **device 참조 하나에 집중된 효과**임을 보여준다.
대표 사례(`N001`, instruction: *"In switch 1, any PING request destined for
10.0.0.1 should go through port 3."*)에서 E1-C는 `"device": "switch 1"`처럼
instruction 문구를 그대로 복사해 미등록 entity로 처리되지만, E1-D는 topology
inventory에 등록된 canonical alias `"device": "s1"`을 사용한다. Few-shot 예시에는
canonical device alias 사용 사례가 포함되어 있지 않으므로, 이 개선은 예시 모방이
아니라 prompt에 주입된 topology inventory를 실제로 참조한 결과로 해석하는 것이
타당하다. 이 결과는 §1a에서 upstream-only 통제 비교로도 재확인된다.

## 3. E1-A의 실패 양상: 정확도 붕괴가 아니라 회피 (버그 수정 반영)

E1-A의 겉보기 required-rejection 100%는 좋은 신호가 아니다. Run 단위로 원시 출력을
확인하면 100개 중 45개(run별 45/47/45/45/45)가 `output == {}`였지만, 그중
**실제로 모델이 선택한 genuine rejection은 run당 39/42/42/41/42건뿐**이었다(정답은
10개만 거절 대상이므로 이마저 대량 과잉거절이다). 나머지 3~6건은 `output`이 아니라
`error` 필드를 함께 보면 원인이 다르다: `run_experiment.py`의 `call()` 자체가 JSON
파싱 실패 등으로 예외를 던져 응답 내용을 전혀 받지 못했고, `output`이 초기값 `{}`로
남아있을 뿐이다.

**발견 및 수정한 채점 버그**: E1-A에서는 `{}`가 "유효한 거절 sentinel"로 특별
취급되기 때문에, 이런 leftover-default 레코드가 `safe_intent_sdn/e1_evaluation.py`의
`evaluate_run()`을 그대로 통과해 **실패가 아니라 성공적인 거절로 조용히 채점되고
있었다**(E1-B/C/D는 `{}`가 유효 sentinel이 아니므로 원래부터 정상적으로
`schema_invalid_cases`에 잡혔음). `rec.error is not None and rec.output == {}`
조건을 추가해 이런 레코드를 `schema_invalid_cases`로 분리하도록 수정하고 전체를
재집계했다. 그 결과 E1-A의 `response_schema_validity`는 0.474 → **0.432**로
낮아졌다(Table 4에 반영됨). `required_rejection_rate`는 이번 5회 실행에서는
leftover-default 레코드가 우연히 필수거절 10-case와 겹치지 않아 1.000으로
변화가 없었다.

나머지 시도(성공적으로 응답을 받았지만 스키마 검증에 실패한 경우) 중에서도 상당수가
프로젝트 스키마가 정의한 필드명(`ip`, `protocol`, `port`) 대신 실제 ONOS REST API
필드명(`ipv4Dst`, `ipProto`, `outputPort`)을 사용한 것이 원인이었다. 이는 사전
설계 문서(`paper/experiment_protocol/e1_rationale.md` §2)에서 예상한 "direct
output은 controller-specific 세부사항에 취약하다"는 가설을 뒷받침하는 구체적
실패 사례다.

E1-B는 반대 극단을 보인다: 100개 중 4개만 거절해 필수거절 10개 중 6개를 놓쳤다
(under-rejection). E1-A(과잉 회피)와 E1-B(과잉 확신) 사이의 이 비대칭은, 출력
형식을 바꾸는 것만으로 정확도와 안전 판단이 함께 개선되지 않고 서로 다른 실패
극단을 오간다는 것을 보여준다.

## 4. Rejection-reason별 분해와 남은 한계

Gold 표본 크기: ambiguous(n=3), contradictory(n=2), unknown_entity(n=3),
unsupported(n=2), 합계 10 (`DATASET_CARD.md`와 일치). 표본이 매우 작으므로 아래
recall은 통계적 추론이 아니라 탐색적(descriptive) 관찰로만 다룬다.

| Reason (n) | E1-B | E1-C | E1-D |
| --- | ---: | ---: | ---: |
| ambiguous (3) | 0.333 | 0.667 | 0.667 |
| contradictory (2) | 0.000 | 1.000 | 0.900 |
| unknown_entity (3) | 0.333 | 0.333 | 0.333 |
| unsupported (2) | 1.000 | 1.000 | 1.000 |

Ambiguous·contradictory recall이 E1-B→E1-C에서 크게 뛴 것(0.333→0.667,
0.000→1.000)이 few-shot 예시를 그대로 모방한 결과처럼 보일 수 있지만, 실제로
`experiments/e1/data/demonstrations.json`의 5개 예시 중 거절 예시는 단 1개뿐이고
그 reason도 `unsupported`다 — ambiguous나 contradictory 예시는 few-shot에
전혀 포함되어 있지 않다. 따라서 이 개선은 특정 reason의 패턴 암기가 아니라,
"거절도 유효한 답"이라는 것을 예시가 일반적으로 보여줌으로써 모델이 애매하거나
모순된 요청 앞에서 더 적극적으로 거절 형태의 출력을 시도하게 된, 보다 일반적인
few-shot 효과로 해석하는 것이 데이터와 부합한다. Contradictory는 n=2뿐이므로
이 해석도 사례 수준 관찰로 제한한다.

E1-D의 required_rejection_rate(0.68)가 E1-C(0.70)보다 근소하게 낮은 것도 이
reason-level 분해로 설명된다: E1-D의 5회 반복 중 1회에서만 contradictory 사례
하나(n=2 중 1건)가 뒤집혀 recall이 1.0→0.5로 떨어졌고(해당 run의
`required_rejection_rate`도 0.7→0.6으로 하락), 나머지 4회는 E1-C와 동일했다.
Table 4에서 이미 밝혔듯 이는 E1-D가 7개 핵심 지표 중 유일하게 두 지표
(`normalized_exact_match`, `required_rejection_rate`)에서 작은 run-to-run
변동을 보인 사례다.

**unknown_entity recall = 0.333(3건 중 1건)**은 few-shot과 grounding 어느
쪽으로도 개선되지 않는다는 점에서 탐색적으로 주목할 만하다. 표본이 3건뿐이라
강한 일반화는 어렵지만, §2의 slot-level 결과와 함께 읽으면 하나의 가설을
세울 수 있다: topology grounding은 모델이 "answer를 낼 때 올바른 entity를
참조하는 능력"은 크게 높이지만, "이 entity가 애초에 inventory에 없다는 것을
알아채고 거절하는 능력"은 높이지 못할 수 있다. 이는 LLM 자체의 self-check만으로는
불완전할 수 있음을 시사하며, 독립적인 reference validator의 필요성(다음 실험
단계인 Static Validator, RQ2)과 방향이 일치하는 관찰이다.

## 5. Threats to validity

- **Task-equivalence confound (High)**: §1a에서 다루듯, 100-case 비교의
  project-authored cohort는 gold IR에 device/egress_port가 없어 E1-A에 불리한
  비대칭 과제를 부여한다. Exact-match 기준 배수 비교는 이 confound 때문에
  신뢰할 수 없으며, 통제된 결론은 반드시 §1a(upstream-only)를 근거로 삼아야
  한다. 근본적 해결(project-authored gold에 placement 정보를 새로 주석)은
  현재 범위에서 보류했다 — provisional gold의 독립 이중 annotation이 아직
  완료되지 않은 상태에서 gold 구조를 추가로 확장하면 annotation QA 파이프라인
  부담이 커지기 때문이다.
- **채점 버그 발견 및 수정 이력**: 문서 검토 과정에서 E1-A의 leftover-default
  `{}`가 성공적 거절로 오분류되던 채점 버그를 발견해 `e1_evaluation.py`를
  수정하고 전체를 재집계했다(§3). 회귀 테스트를
  `tests/test_e1_evaluation.py::test_e1a_call_failure_leftover_default_is_not_scored_as_successful_rejection`에
  추가했다.
- **Provisional gold**: gold annotation은 아직 독립 이중 annotator agreement가
  완료되지 않았다.
- **Run-to-run 변동**: E1-B는 7개 핵심 지표 전체에서 `sample_sd=0`이다. E1-C는
  `normalized_exact_match`에서만(sd=0.00447), E1-D는 `normalized_exact_match`와
  `required_rejection_rate`(sd=0.04472, 전체 중 최댓값)에서 작은 변동을 보였다.
  Paired 5-run 설계는 재현성 확인에는 성공했지만, treatment 간 차이가 표본 변동
  대비 유의한지를 검정할 통계적 검정력은 사실상 제공하지 못한다 — 관찰된 차이는
  서술적(descriptive) 비교로 취급해야 하며, `exploratory_ci_95`를 강한 추론
  근거로 인용해서는 안 된다. 반대로 E1-A는 동일 설정에서도 훨씬 큰 변동을
  보였는데, 이는 과제가 어려울수록(direct flow 생성) 출력이 덜 결정론적이라는
  부가적 관찰이다.
- **Compound bucket n=2**: rule-count/순서 관련 지표에서 compound category는
  2건뿐으로 사례 연구 수준이며 통계적 추론 대상이 아니다.
- **Rule 순서 매칭**: 현재 비교는 rule count 일치 후 위치 기반으로 slot을
  비교한다. Gold와 예측이 같은 rule을 다른 순서로 냈다면 실제로는 맞은 예측이
  mismatch로 집계될 수 있다(`tmp/plan_review.md` §A에서 이미 지적된 미해결
  구조적 이슈). 향후 type+action 기반 최적 매칭 도입이 필요하다.
- **모델 단일성**: 전체 결과는 `qwen3:8b` 1개 모델, 1개 온도(0.2) 설정에서만
  얻어졌다. 모델·설정에 따라 few-shot/grounding의 상대적 기여가 달라질 수 있다.

부가 진단: `raw_onos_only_exact_match`는 "byte-level JSON 일치율"이 아니라
`safe_intent_sdn/e1_evaluation.py:123`의 `rec.output == case.upstream_output`,
즉 **파싱된 Python 객체(dict) 간 구조적 동등성 비교**다(key 순서·whitespace
무관). E1-A는 upstream cohort 50건 전체에서 5회 모두 **0.0**을 기록한다. 이
지표는 채점 관용도가 전혀 없는 진단용 수치이므로 0.0 자체가 문제라기보다는,
본 연구가 채택한 normalized 비교(정렬·alias 정규화 후 semantic 비교)가 raw
structured-object exact match보다 훨씬 관대하고 의미 있는 채점 기준이라는
것을 재확인해 준다.
