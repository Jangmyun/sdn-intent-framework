# E2-Path 확장 실험 설계 근거 (addendum to `e2_rationale.md`)

> **범위 고지**: 이 문서는 `e2_rationale.md`가 다루는 원본 48-case E2 벤치마크를
> 대체하지 않는다. 여기서 설명하는 65-case 확장 데이터셋
> (`experiments/e2/data/cases_sfc_reroute.jsonl`)과 그 B1′/B2′ 결과는 별도로
> 보고하며, 원본 48-case 결과와 합산하거나 같은 표에 병기하지 않는다. `e2_rationale.md`
> §1-§9의 범위 고지, conformance-vs-일반화 caveat, B1′/B2′ 명명 규칙은 이 확장에도
> 동일하게 적용된다.

## 1. 왜 별도 확장인가

`experiments/e1/data/intents_sfc_reroute.jsonl`(신규 sfc/reroute 100-case E1 확장
벤치마크)의 gold accepted case들은 원본 E2의 `clean` 쿼터에 들어갈 수 없다 — 원본
E2는 `experiments/e1/data/topology.json`(업스트림 NetIntent 토폴로지)을 기준으로
구축되었고, sfc/reroute 케이스는 별도의 diamond 토폴로지
(`experiments/e1/data/topology_diamond.json`)를 전제하기 때문이다. 또한 sfc/reroute의
실패 유형(끊어진 chain, waypoint 순서 오류, avoid_device 충돌)은 원본 E2의
reference/conflict/feasibility 세 카테고리 중 어디에도 깔끔히 들어가지 않는다.
따라서 새 `path` finding category(`safe_intent_sdn/validator.py`)와 별도의 65-case
데이터셋을 구축했다.

## 2. 데이터셋 구성

| 구분 | 건수 |
|---|---:|
| clean (sfc/reroute gold accepted 전체 재사용) | 50 |
| path (결함 7 + hard negative 1) | 8 |
| feasibility | 3 |
| conflict (결함 1 + hard negative 1) | 2 |
| reference | 1 |
| multi | 1 |
| **합계** | **65** |

`experiments/e2/build_sfc_reroute_dataset.py`가 이 분포를 fail-closed로 강제한다.

### 2.1 왜 clean은 quota가 아니라 50건 전부인가

원본 E2(`e2_rationale.md` §3.1)는 compound quota를 1로 제한하는 등 category별 quota를
쓴다. 이 확장에서는 quota를 두지 않고 sfc/reroute gold accepted case 50건을 전부
재사용했다 — `validate_program`/`compile_prediction`은 순수 결정론적 함수로 sub-
millisecond 비용이므로(`e2_rationale.md` §2/§7), 표본을 줄일 비용상의 이유가 없고
quota를 도입하려면 그 자체로 근거 있는 예외 규칙(N039 같은)을 새로 만들어야 하기
때문이다. 전부 재사용하는 편이 conformance 커버리지를 공짜로 최대화한다.

### 2.2 `path` finding category

`FindingCategory`에 `"path"`를 추가했다(`reference`/`conflict`/`feasibility`에 접어
넣지 않음). 이 카테고리는 "실현된 rule 시퀀스/배치가 선언된 라우팅/체이닝 메타데이터를
만족하는가"를 다루며, entity 존재(reference), pairwise shadowing(conflict), 단일
rule 포트 범위(feasibility) 중 어디에도 속하지 않는다. `safe_intent_sdn/e2_evaluation.py`의
`by_category`는 `get_args(FindingCategory)`로 순회하도록 바꿔, 새 카테고리가 하드코딩
튜플을 다시 고치지 않아도 자동으로 반영된다 — 원본 48-case 리포트에는 `path: {tp=0,
fp=0, fn=0, tn=48}`가 추가될 뿐, 기존 수치는 전혀 바뀌지 않는다(직접 diff로 확인).

`_check_path_constraints`는 세 개의 하위 점검으로 구성된다.

1. **SFC chain 연속성**: chain 길이(`len(sfc_chain) == len(rules)-1`), hop마다 chain
   token의 device가 실제 다음 rule의 device와 일치하는지, 그 device/port가 topology에
   실제로 존재하는지, 동일 device를 지나는 hop(방화벽 우회 등)에서 이전 rule의
   egress_port·다음 rule의 ingress_port·chain token의 port가 모두 일치하는지.
2. **SFC role 순서**: `sfc_role` 부분열이 `ingress`로 시작하고, `ingress`가 중복되지
   않고, `egress`가 있다면 마지막이어야 한다.
3. **reroute `avoid_device`**: `enforcement.avoid_device`가 실제 배치된
   `enforcement.device`와 canonically 같으면 충돌.

### 2.3 "unknown waypoint"가 "reference"와 겹치지 않는 이유

topology에 아예 없는 device 문자열은 chain token과 rule의 device가 일치하는 순간
`_check_references`도 이미 `unknown_device`로 잡는다(둘 다 같은
`inventory.aliases`/`device_ports`를 본다) — 따라서 "완전히 모르는 device"로는
`path`만 단독으로 잡히는 fixture를 만들 수 없다. 이를 격리하기 위해
`topology_diamond.json`에 `device:s5`를 **alias는 등록되어 있지만 `ports`에는 없는**
장치로 추가했다(등록만 되고 아직 배치되지 않은 waypoint라는 현실적 시나리오). 이
경우 `reference` 체크는 통과하지만(`canonical.startswith("device:")`가 참) `path`의
`path_unknown_waypoint`만 단독으로 발생한다. `sfc-unknown-waypoint-device`,
`multi-sfc-unknown-waypoint-and-oor-port` 두 fixture가 이를 사용한다.

### 2.4 hard negative가 왜 필요한가

`e2_rationale.md` §4와 동일한 이유로, "정상적으로 구성된" 케이스를 잘못 flag하지
않는지 검증하는 hard negative가 각 defect 계열에 하나씩 있다: 올바른 3-hop
chain(`sfc-hardneg-valid-two-hop-chain`)과, specific rule이 general rule보다 먼저
오는 표준 ACL 관용구(`reroute-hardneg-specific-then-general-deny`, 원본 E2의
specific-before-general 비대칭 검증과 동일한 발상).

## 3. B1′/B2′ 우연한 검증 능력에 대해

원본 E2 §5와 마찬가지로, B1′(compiler only)은 sfc/reroute 전용 결함
(`path`/`feasibility`/`conflict`/`reference`)에 대한 topology 지식이 전혀 없다.
`compile_prediction`은 IR 자체의 내적 일관성만 보므로, 이 15개 결함 fixture는 모두
컴파일에 성공하며 B1′은 하나도 거부하지 못한다.

## 4. 실측 결과

`experiments/e2/run_validation.py --dataset cases_sfc_reroute.jsonl --topology
topology_diamond.json`으로 B1/B2를 각각 실행하고
`experiments/e2/score.py --scope-note "..."`로 채점한 실측 결과:

> 단일 diamond topology의 65개 고정 fixture를 사용한 결정론적 component-level
> conformance evaluation에서, compiler-only baseline(B1′)은 13개 defect-positive
> case 중 0개를 거부했고(TP=0, FN=13, recall=0.00) static validator를 추가한
> 구성(B2′)은 13개 모두를 거부했다(TP=13, FP=0, precision=1.00, recall=1.00).
> 52개 true-negative fixture(clean 50 + hard negative 2)에서는 거부가 관찰되지
> 않았다. `by_category` case-level recall: reference 1/1, conflict 1/1,
> feasibility 4/4, path 8/8. `code_mismatch_cases`는 비어 있다.

이 결과는 §3.9의 conformance-vs-일반화 caveat 및 §11의 한계(construction bias,
단일 topology, 65-case 규모는 통계적 추론 대상이 아님, component-level 평가)를
그대로 상속한다 — validator 구현자와 fixture 저자가 동일 인물이며, 독립적인 두
번째 annotator의 검토나 adjudication이 없었다.
