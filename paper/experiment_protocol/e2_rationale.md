# E2 실험 설계 근거 (RQ2)

## RQ2

**정적 검증은 hallucinated entity, rule conflict 및 실행 불가능한 정책을 얼마나 조기에
차단할 수 있는가?**

> **범위 고지 (필독)**: 아래에서 쓰는 B1/B2는 논문 전체 파이프라인의 B1(LLM+IR+compiler)/
> B2(B1+Static Validator)가 **아니라**, 그중 compiler↔validator 경계만 떼어 낸
> component-level 평가다. 실행은 `experiments/e2/run_validation.py`가 담당하며, 입력은
> LLM 산출물이 아니라 고정된 gold/authored Intent IR fixture다. 즉 이 실험이 직접
> 입증하는 것은 "B1′(compiler only, 고정 IR 입력)" 대 "B2′(validator+compiler, 동일
> 고정 IR 입력)"이며, "LLM+IR 전체 시스템의 recall이 0.12에서 1.0으로 개선됐다"는
> 식의 서술은 과장이다. 이 문서와 `experiments/e2/score.py`의 출력에는 이 구분을
> 명시한다.

## 1. 왜 검증 단계를 컴파일 단계와 독립적으로 측정해야 하는가

E1은 자연어→Intent IR 번역 단계의 기저 오류 분포를 측정했다. `safe_intent_sdn/compiler.py`는
그 IR을 ONOS flow로 결정론적으로 낮추는 단계이며, IR 자체가 내적으로 표현 가능한지
(`enforcement.device` 존재 여부, IP family 일치, ARP/ICMPv6 충돌 등)만 검사한다. 그러나
compiler는 실제 topology를 전혀 참조하지 않는다 — 존재하지 않는 device 문자열도,
범위를 벗어난 egress_port도, 서로 모순되는 두 rule도 지금은 아무 제지 없이 통과한다.
RQ2가 요구하는 세 가지 실패 유형(hallucinated entity, rule conflict, infeasible
policy)은 모두 topology 지식이나 rule 간 비교가 있어야만 검출 가능하며, 이는 compiler의
설계 범위 밖이다. 따라서 이 gap을 메우는 Static Validator를 compiler와 별도 계층으로
설계하고, 그 증분 효과를 고정 IR 입력 기준 B1′ 대 B2′ 비교로 측정하는 것이 E2의
목적이다. 전체 파이프라인(LLM 산출물 입력) 기준 B1/B2 비교는 별도 실험으로 필요하며,
아래 §9에서 다시 다룬다.

## 2. 왜 LLM 호출 없이도 이 실험이 가능한가

E1은 LLM 출력의 확률적 변동을 통제하기 위해 조건별 5회 반복과 paired seed를 사용했다.
E2의 대상(`validate_program`, `compile_prediction`)은 순수 결정론적 함수이므로, 동일한
입력에 대해 항상 동일한 출력을 낸다 — 반복 실행은 증거를 추가하지 않고 단지 동일한
결과를 복제할 뿐이다. 이 때문에 E2는 새로운 LLM 호출이나 반복/seed 설계 없이, 이미
존재하는 IR fixture(수용된 E1 gold `IntentPrediction` 89건 중 20건 재사용 + 새로 저작한
authored fixture 28건)에 대해 각 treatment당 단 한 번의 결정론적 pass만 수행한다. 이는
E1 대비 방법론적 차이이지, 통제를 생략한 것이 아니다.

## 3. 데이터셋 구성: 정확한 분포

`PLAN.md` §3.2의 60-case 목표 표는 이 단계에 "Conflict/Invalid: 10"이라는 한 줄만
할당하지만, §4.3의 일별 작업(7/29 reference, 7/30 conflict, 7/31 feasibility)은 세
검증 계층을 모두 별도로 구현하도록 요구한다. 이 문서는 "10"을 세 실패 유형의 우산
표현으로 해석했다.

`experiments/e2/data/defective_authored.jsonl`에 새로 저작한 **authored fixture는
28건**이며, 그 구성은 다음과 같다.

- 단일 결함 22건: reference 8, conflict 6, feasibility 8
- 복합 결함(2개 카테고리 동시) 3건
- conflict hard negative 3건 (`expected_findings=[]`) — §4의 방향성 검증용

즉 conflict category로 분류된 9건 중 **6건만 실제 양성**이고 3건은 "flag되면 안 되는"
true negative다. 여기에 `experiments/e2/build_dataset.py`가 E1 gold accepted case
89건(N039 제외, §3.1)에서 forwarding 7·security 6·qos 6·compound 1 = **clean
true-negative 20건**을 재사용해 더하면 총 48건이 된다.

정리하면:

| 구분 | 건수 |
| --- | ---: |
| defect-positive (단일 22 + 복합 3) | **25** |
| true-negative (clean 20 + conflict hard negative 3) | **23** |
| **합계** | **48** |

### 3.1 compound quota가 2가 아니라 1인 이유

E1의 accepted compound case는 N039와 N045 두 건뿐인데, `experiments/e1/README.md`가
이미 N039를 "raw output에 forwarding clause가 누락되어 있어 불완전한 upstream
label"로 명시하고 있다. 실제로 N039의 gold IR을 그대로 compiler에 넣으면 `forward
requires enforcement.egress_port`로 컴파일에 실패한다 — 이는 RQ2가 다루는 topology
기반 결함이 아니라 label 자체의 결함이므로, N039를 clean 진짜음성으로 포함하면 B1′과
B2′ 모두에서 근거 없는 false positive가 발생해 precision을 왜곡한다. 따라서
`build_dataset.py`는 N039를 `KNOWN_INCOMPLETE_GOLD_IDS`로 명시적으로 제외하고,
forwarding quota를 6에서 7로 늘려 clean 총량 20을 유지한다.

## 4. Conflict 검증의 방향성: 왜 hard negative가 필수인가

Rule list 순서는 곧 policy 평가 순서(우선순위 내림차순)이므로, "일반적인 규칙이
구체적인 규칙보다 먼저 오고 서로 다른 action을 가지는" 패턴(`deny *` 다음
`allow host X`)은 뒤 규칙이 영원히 발동하지 않는 실제 dead-rule 버그다. 그러나 이
방향을 뒤집은 패턴(`allow host X` 다음 `deny *`)은 표준적이고 의도된 ACL 관용구이며,
**절대 flag되어서는 안 된다**. 이 비대칭을 검증하지 않으면 validator가 이 흔한 패턴에서
소음을 내어 precision을 해칠 수 있으므로, conflict 데이터셋의 hard negative 3건 중
2건은 specific-before-general 순서, 1건은 서로 다른 device에 동일 selector를 배치한
경우로 구성했다(`tests/test_validator.py`의
`test_validate_program_does_not_flag_specific_rule_preceding_general_rule`,
`test_validate_program_does_not_flag_identical_selectors_on_different_devices`가
회귀를 방지한다).

## 5. B1′의 우연한 host 검증을 어떻게 보고하는가

`compile_prediction`은 동작을 위해 host→IP resolver(`endpoint_ips`)를 반드시 필요로
하며, 그 resolver에 없는 host는 이미 `CompilationError`로 거부된다. 이는 설계된
검증 기능이 아니라 컴파일에 resolver가 필요하다는 사실의 부수 효과다. B1′을 공정한
baseline으로 만들려면 resolver에 topology의 모든 실제 host alias를 채워 넣어야 하며(빈
resolver를 주면 hallucination 여부와 무관하게 모든 host 포함 rule을 거부하게 되어 실험
설계 자체가 무너진다), 그 결과 B1′은 unknown host만 부수적으로 잡아낸다 — unknown IP,
unknown device, port 범위, rule 충돌은 전혀 잡지 못한다. `safe_intent_sdn/e2_evaluation.py`의
`score_treatment`는 이를 투명하게 보고한다: `any_defect`(전체 지표)와 별도로
`unknown_host_subset`(정확히 `unknown_host` 하나만 결함인 case들의 부분집합)을 분리해,
B1′의 능력을 과장하지 않으면서도 실제 관측된 데이터를 버리지 않는다.

## 6. Feasibility 범위를 왜 port 존재/범위 검사로 제한했는가

`experiments/e1/data/topology.json`은 device별 유효 port 목록(`ports`)을 이미 갖고
있지만, bandwidth나 queue 개수 같은 수치적 용량 데이터는 어디에도 없다 — NetIntent
upstream 데이터에도, 실제 ONOS/OVS 배포 관측치에도 없다. 이런 수치를 지금 임의로
만들어 검증 기준으로 삼는 것은 근거 없는 가정을 사실처럼 다루는 것이며, 이는 본
프로젝트가 fail-closed 원칙에서 지키려는 태도(가짜 근거로 안전을 주장하지 않는다)와
정면으로 배치된다. 따라서 E2의 feasibility 검사는 오늘 실제로 근거를 댈 수 있는
것 — device 존재 여부와 device별 port 범위 — 로 제한했다. VLAN 범위는 이미 Pydantic
필드 제약(0–4095)으로 다뤄지고 있어 추가 검사를 두지 않았다.

## 7. 채점 파이프라인 자체의 무결성을 어떻게 보장하는가

Precision/recall 수치는 채점기가 완전하고 일관된 로그를 받았다는 전제 위에서만
의미가 있다. 초기 구현은 이 전제를 강제하지 않았다: case에 대응하는 result가 없으면
조용히 건너뛰어 FN으로 세지 않았고, result가 중복되면 마지막 값이 조용히 이전 값을
덮어썼다 — 둘 다 불완전한 실행 로그에서도 precision/recall이 1.0처럼 보이게 만들 수
있는 결함이다. `safe_intent_sdn/e2_evaluation.py`의 `validate_results`는 채점 전에
다음을 fail-closed로 검사하며, `score_treatment`는 항상 이 함수를 먼저 호출한다.

- dataset과 result 로그의 case id가 정확히 1:1로 일치하는가(빠진 case, 여분의 case
  모두 오류)
- dataset·result 각각에 중복 id가 없는가
- 한 result 로그 안에 treatment가 섞여 있지 않은가
- `outcome=="accepted"`인 result가 `rejection_stage`/`findings`/`error`를 함께
  들고 있지 않은가
- `outcome=="rejected"`인 result가 `rejection_stage`를 반드시 갖는가
- B1이 categorized `findings`를 보고하지 않는가(B1은 애초에 그런 정보를 낼 수 없다)
- `rejection_stage=="validator"`인 result가 오직 B2에서만 나오는가

## 8. Category 지표는 case-level이지 finding-level이 아니다

`score_treatment`의 `by_category`는 "이 case에서 category X에 해당하는 finding이
하나라도 보고되었는가"를 기준으로 하는 **case-level** precision/recall이다. 특정
`code`나 `rule_indices`가 정확한지, 같은 category 안에 여러 결함이 있을 때 그중
일부만 찾았는지는 별도로 다루지 않는다. 따라서 "category recall 1.0"은 "이 category의
모든 개별 결함을 정확한 code로 정확히 짚어냈다"는 뜻이 아니라 "이 category가 걸린
case를 놓치지 않았다"는 뜻으로 읽어야 한다. `code_mismatch_cases`는 이를 보완하는
진단용 목록으로, category-level hit은 맞았지만 실제 finding의 `code` 집합이
`expected_codes`와 다른 case를 보고한다(핵심 precision/recall 계산에는 포함되지
않는다) — 논문에 인용하기 전 반드시 이 목록이 비어 있는지 확인한다.

## 9. 결과 해석의 범위: conformance이지 일반화 성능이 아니다

양성 fixture(reference/conflict/feasibility 25건)는 validator가 구현하려는 taxonomy를
직접 겨냥해 저작되었고, 동일한 저자가 validator 구현과 fixture 저작을 모두 수행했으며,
독립적인 두 번째 annotator의 검토나 adjudication 없이 결과를 산출했다. 이 조건에서
B2′의 precision/recall 1.0은 "정의된 taxonomy와 저작 fixture에 대한 구현 conformance"로
읽어야 하며, 독립적인 holdout에서의 일반화 성능이나 실제 LLM 오류 분포에 대한
일반화로 해석해서는 안 된다. 논문의 핵심 성능 주장으로 인용할 때는 다음과 같이
한정된 문장을 권장한다.

> 단일 topology의 48개 고정 fixture를 사용한 결정론적 component-level conformance
> evaluation에서, compiler-only baseline(B1′)은 25개 defect-positive case 중 3개를
> 거부했고(TP=3, FP=0, precision=1.00, recall=0.12) static validator를 추가한
> 구성(B2′)은 25개 모두를 거부했다(TP=25, FP=0, precision=1.00, recall=1.00).
> Case-level recall은 0.12에서 1.00으로 증가했으며, 23개 true-negative fixture에서는
> 거부가 관찰되지 않았다. 이 결과는 독립 holdout에서의 일반화 성능이 아니라 저작
> taxonomy에 대한 탐색적 구현 검증이다.

**precision만 단독 인용 금지**: B1′과 B2′ 모두 precision이 1.00으로 동일하지만 그
의미는 전혀 다르다 — B1′의 1.00은 "25건 중 3건만 시도해서 그 3건을 다 맞혔다"는
뜻이고 B2′의 1.00은 "25건 전부 시도해서 다 맞혔다"는 뜻이다. precision을 인용할
때는 반드시 recall(또는 TP/FP 원값)을 함께 병기해, 표본이 3건뿐인 precision과
25건인 precision을 같은 무게로 읽지 않도록 한다.

성능 주장을 강화하려면 (a) validator 구현과 독립적으로 결함 사례를 저작하거나
검토, (b) 별도 holdout fixture, (c) 두 annotator의 category/code 판정과 adjudication,
(d) 실제 E1 모델 오류나 향후 운영 로그에서 추출한 결함 사례 추가가 필요하다.

## 10. PLAN.md가 요구하는 추가 자료

`PLAN.md` §3.6은 static validator 관련 지표로 정적 단계에서 차단된 정책 수, Twin 실행을
절약한 비율, 검증 처리 시간을 명시한다. `experiments/e2/score.py`는 이제 다음을 함께
보고한다.

- `defect_positive_total`/`rejected_count`: "B1′ 3/25 rejected", "B2′ 25/25 rejected"를
  그대로 노출.
- `B2_minus_B1.incremental_rejections`(=22): B2′가 추가로 거부한 defect-positive case 수.
- `observed_latency_ms`(mean/median/min/max/total, treatment별): 실제 실행된 단계
  전체의 case당 관측 지연시간. **이것은 "static validation overhead"가 아니다** — B2는
  결함을 validator 단계에서 거부하면 compiler를 아예 실행하지 않으므로 B1과 실행 경로
  자체가 다르다. 실제로 재현에서도 B2의 전체 평균이 B1보다 짧게 나왔는데(짧은 경로로
  일찍 끝나는 case가 섞여 있기 때문), 이를 "validator가 있어서 더 빠르다"처럼 인용하면
  안 된다.
- `validator_overhead`(compute_validator_overhead): 위 confound를 제거한 진짜 overhead
  수치. B1과 B2가 **둘 다 compiler까지 실행하는** true-negative 23건만 골라
  `b1_compiler_only_ms`/`b2_validator_ms`/`b2_compiler_ms`/`b2_total_ms`와
  `added_overhead_ms`(mean/median)를 비교한다. `E2Result.validator_duration_ms`/
  `compiler_duration_ms`는 각각 warm-up 1회 후 31회 반복 호출의 median으로 측정한다
  (`experiments/e2/run_validation.py`의 `_timed_ms`) — 서브밀리초 단위 결정론적 함수도
  시스템 잡음의 영향을 받으므로, 기능적 pass/fail 결과는 단일 호출로 충분해도 시간
  측정에는 반복+median이 필요하다. 논문에는 이 `validator_overhead`만 "overhead"로
  인용하고, `observed_latency_ms`는 "관측된 end-to-end case 처리 시간"으로만 인용한다.

**"Twin 실행 절약"에 대한 주의**: `incremental_rejections=22`는 Digital Twin이 아직
구현되지 않은 현재 시점에서 "이만큼의 case가 (아직 만들어지지 않은) Twin 단계에
도달하기 전에 걸러질 잠재적 여지가 있다"는 뜻일 뿐, 실측된 Twin 실행 절약량이 아니다.
E3에서 Twin 실행 비용이 측정된 뒤에만 실제 절감량으로 정량화할 수 있다.

## 11. 한계 (Limitations)

- **Construction bias / conformance vs. 일반화**: §9에서 설명한 대로, 현재 결과는
  독립 holdout에서의 일반화 성능이 아니라 저작 taxonomy에 대한 conformance다.
- **Bandwidth/queue 수치 feasibility 미검증**: §6에서 설명한 대로, 실제 측정된
  용량 데이터가 확보되기 전까지(Digital Twin 실험 E3+ 또는 실제 ONOS queue 설정
  스냅샷 이후) 보류한다.
- **Compound gold의 알려진 결함(N039)**: E2는 이 case를 clean 진짜음성에서 제외했지만,
  이는 gold annotation 자체의 미해결 이슈이며 E1의 provisional gold 상태와 연결된
  한계로 남는다.
- **단일 topology**: E2는 `topology.json`이 정의하는 단일 Topology A(4-host,
  4-device)에서만 검증되었다. `PLAN.md` §3.3의 Topology B/C가 구축되면 재검증이
  필요하다.
- **48-case 규모, 통계적 추론 대상 아님**: 탐색적 벤치마크로 취급해야 한다.
- **B1′/B2′는 component-level 평가**: §범위 고지 및 §1에서 설명한 대로, 이는 논문
  전체 시스템의 B1/B2가 아니라 compiler-validator 경계만의 controlled evaluation이다.
  End-to-end LLM+IR 입력 기준 B1/B2 비교는 아직 수행되지 않았다.
