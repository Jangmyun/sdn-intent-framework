# GOLD-350 데이터셋 구축 및 이중 라벨링 프로토콜

> 목적: 자연어 SDN intent 벤치마크의 gold 라벨을 **독립 이중 라벨링 + adjudication**
> 절차로 확정하고, 그 신뢰성 근거(카테고리 분포, inter-annotator agreement, 불일치
> 해소 과정)를 논문 재현 가능 형태로 문서화한다.
>
> 산출물 위치: `experiments/gold/`. 최종 gold는 `experiments/gold/data/gold.jsonl`
> (350건, `EvaluationCase` 스키마).

---

## 1. 배경과 이전 데이터셋의 한계

E1 데이터셋 카드(`experiments/e1/DATASET_CARD.md`)는 gold 상태를 명시적으로
**provisional**로 표기하고, 체크인된 annotator artifact가 "파이프라인 fixture이지
사람 간 inter-annotator agreement의 증거가 아니다"라고 고지했다. 즉 최종 발표를 위해서는
"두 개의 독립 annotation과 adjudication"이 필요하다는 것이 데이터셋 카드 자체에 적힌
미결 과제였다. 본 프로토콜은 그 미결 과제를 충족하기 위해 설계됐다.

기존 자산의 규모·구성상 한계는 다음과 같았다.

- E1 upstream+authored 벤치마크는 100건이며 카테고리 분포가 불균형했다
  (forwarding 42, security 23, qos 23, compound 2, rejection 10).
- `sdn-xai-pipeline`의 `intents_v2.jsonl`은 100건이지만 그중 50건(sfc 25 + reroute 25)이
  본 저장소 `experiments/e1/data/project_authored_sfc_reroute.jsonl`과 동일 계열이라,
  독립적인 대규모 평가 집합으로 보기 어려웠다.
- compound(다중 정책 절) 케이스가 사실상 부재(2건)하여, 한 지시문이 여러 rule로
  분해되는 상황의 파싱·검증을 평가할 표본이 없었다.

이에 **7개 카테고리 × 50건 = 350건**의 균형 잡힌 후보 집합을 새로 저작하고, 독립
이중 라벨링으로 라벨 신뢰성을 정량화했다.

---

## 2. 고정 토폴로지 규약 (normative)

모든 gold program은 아래 토폴로지를 가정하고 생성됐으며, 이 규약은
`experiments/gold/cases/helpers.py`와 annotation guideline §1에 동일하게 명문화되어
어노테이터와 gold program이 같은 세계 모델을 공유하도록 했다.

```
h1(10.0.0.1), h2(10.0.0.2) ── s1 ──┬── s2 ──┬── s4 ── h3(10.0.0.3), h4(10.0.0.4)
                                    └── s3 ──┘
s1 포트: 1→s2, 2→s3, 3→h1, 4→h2, 9→방화벽(미들박스)
s2 포트: 1→s1, 2→s4   (IDS/DPI/LB/프록시/스크러빙 서비스 노드)
s3 포트: 1→s1, 2→s4   (모니터링/로깅 서비스 노드)
s4 포트: 1→s2, 2→s3, 3→h3, 4→h4
기본 경로: s1 ↔ s2 ↔ s4. 대안 경로: s3 경유.
```

이 포트 맵과 미들박스 규약은 E1 SFC/Reroute 확장 gold
(`experiments/e1/data/project_authored_sfc_reroute.jsonl`)의 관례를 그대로 승계하여,
두 데이터셋 사이의 device·port 의미가 일관되도록 했다.

---

## 3. 후보 350건 저작

### 3.1 카테고리 구성

| 카테고리 | 건수 | 하위 변이(variation) |
|---------|------|--------------------|
| forwarding | 50 | explicit, ip_device, protocol, colloquial, implicit_service |
| security | 50 | deny_pair, deny_service, deny_device, allow_rule, colloquial_deny |
| qos | 50 | bandwidth, latency, queue, combined |
| sfc | 50 | single_switch_bypass, multi_switch_chain, sfc_security |
| reroute | 50 | alt_switch, port_change, failover |
| compound | 50 | exception_default, multi_flow, multi_service, qos_mix, triple |
| ambiguous_unsupported | 50 | ambiguous 15, unknown_entity 15, contradictory 10, unsupported 10 |

각 카테고리는 표층 어휘(explicit host vs IP vs colloquial), 프로토콜/포트 명시 여부,
device/port 고정 여부 등에서 변이를 갖도록 저작하여, 라벨이 특정 키워드에만 의존해
결정되지 않도록 했다.

### 3.2 결정론적 빌더

후보는 손으로 JSON을 쓰는 대신 `experiments/gold/build_candidates.py`가 카테고리별
케이스 모듈(`cases/*.py`)의 선언에서 결정론적으로 생성한다. 빌더는 다음 불변식을
강제하며, 하나라도 위반하면 빌드가 실패한다.

- 350건 전부가 `safe_intent_sdn.e1_evaluation.EvaluationCase` 스키마 검증 통과.
- ID 유일성, **지시문 문자열 유일성**(표층 중복 금지).
- 카테고리 분포가 정확히 50/50/.../50.
- 카테고리별 rule 수 규약: compound ≥ 2 rule, sfc ≥ 2 rule + `sfc_chain` 존재,
  나머지 accepted 카테고리는 정확히 1 rule.

### 3.3 blind split (라벨 유출 차단)

어노테이터에게는 카테고리·gold program이 제거된 **blind 파일만** 제공한다.
`build_candidates.py`는 고정 시드(`SHUFFLE_SEED=20260723`)로 케이스 순서를 섞어
`data/blind/instructions.jsonl`(필드: `blind_id`, `instruction`만)을 만들고,
`blind_id → case id` 매핑은 adjudication 전용 키 `data/blind/id_map.json`에 분리 저장한다.
셔플은 카테고리가 파일 내에서 블록으로 뭉치지 않게 하여(테스트가 최장 동일-카테고리
연속 < 10을 강제) 제시 순서에서 라벨을 추론할 수 없도록 한다.

---

## 4. 독립 이중 라벨링

### 4.1 어노테이터 지침

라벨링 규칙은 `experiments/gold/ANNOTATION_GUIDELINE.md`(v1.0)에 자기완결적으로
규정했다. 핵심은 **순서형 결정 절차(§4)**로, 다음 우선순위로 적용된다.

1. unknown entity(인벤토리 밖 엔티티) → reject/`unknown_entity`
2. contradiction(동일 flow에 양립 불가한 요구) → reject/`contradictory`
3. unsupported(capability 목록 밖 기능: rate-cap, NAT, VPN, 암호화, 미러링, 시간조건,
   동적 LB 등) → reject/`unsupported`
4. 과도한 모호성(식별 가능한 flow/action 없음) → reject/`ambiguous`
5. 정책 절 개수 세기 — 2개 이상이면 `compound` (단, 서비스 체인·체인 후속 처리·경로
   변경의 실패 조건·한 flow의 복수 QoS 제약은 단일 절)
6. 미들박스 waypoint 경유 → `sfc` (서비스 명사가 경로 동사보다 우선)
7. 경로/포트 변경 → `reroute`
8. 성능 보장 → `qos`
9. 차단 또는 명시적 allow-rule → `security`
10. 그 외 단일 flow 전달 → `forwarding`

가이드라인은 경계 사례를 위한 hard-case 표(§6)를 포함한다. 예: "firewall off A from B"
= security(경유 없음), "redirect through the IDS on s2" = sfc(서비스 역할 발동),
"reroute via s3 instead of s2" = reroute(순수 경로 변경), "allow h2 to reach h4" =
forwarding(연결 동사) vs "whitelist h2 to h4" = security(ACL 프레이밍).

### 4.2 독립성 통제

두 어노테이터(A, B)는 **별개의 에이전트 세션**으로 실행됐고, 각 세션은 오직 두 파일
(가이드라인, blind 지시문)만 읽도록 제한됐다 — 후보 원본, 케이스 모듈, 상대 어노테이터의
출력, 여타 데이터셋 접근을 명시적으로 금지했다. 제시 순서 편향을 줄이기 위해 B는
판단을 역순(B350→B001)으로 수행한 뒤 파일만 오름차순으로 기록했다. 각자 산출물은
`experiments/gold/annotations/annotator_a.jsonl`, `annotator_b.jsonl`.

---

## 5. Agreement 측정

`experiments/gold/compute_agreement.py`가 Cohen's kappa를 계산한다. 결과:

| 지표 | 값 |
|------|-----|
| 카테고리 raw agreement | 350/350 = 1.000 |
| 카테고리 Cohen's κ (7-way) | **1.000** |
| status Cohen's κ (accept/reject) | 1.000 |
| rejection reason Cohen's κ (양측 reject n=50) | 1.000 |
| 어노테이터 간 불일치 건수 | **0** |

두 독립 어노테이터가 350건 전부에서 카테고리·status·reject 사유까지 동일하게
판정했다(κ=1.0). 이는 순서형 결정 절차와 hard-case 표가 경계 사례를 충분히 규정해,
독립 판단이 완전히 수렴했음을 의미한다. 실제로 양측이 보고한 "genuinely borderline"
목록도 상당 부분 겹쳤으며(예: "switch 2 then switch 4" 계열, "from now on" egress 변경,
"permit/allow" 연결 동사 대 ACL 프레이밍), 겹치는 경계 사례를 놓고도 최종 라벨이
동일했다.

> **해석 주의**: κ=1.0은 라벨링 난이도가 낮음이 아니라 **가이드라인의 결정성**을
> 반영한다. 두 어노테이터는 동일한 상세 지침을 공유했으므로 이 값은 "잘 규정된 지침
> 하에서의 재현성"을 입증하며, 지침 없이 상식만으로 라벨링할 때의 난이도를 뜻하지
> 않는다. 이 한계를 데이터셋 카드에도 명시한다.

---

## 6. Adjudication

어노테이터 간 불일치가 0건이므로 통상적 의미의 "불일치 조정"은 없었다. 그러나 더
엄격한 검증으로 **어노테이터 합의 라벨 vs 저자 의도 라벨**을 대조했고, 여기서 2건이
어긋났다.

| case id | blind id | 저자 의도 | 합의 라벨 | 지시문(수정 전) |
|---------|----------|----------|----------|----------------|
| G-SFC-031 | B329 | sfc | forwarding | "Chain h1 to h4 traffic through switch 2 then switch 4." |
| G-SFC-032 | B320 | sfc | forwarding | "Route SSH from h2 to h3 through switch 2 and then switch 4." |

**진단**: 두 건은 멀티홉 SFC gold program(s1→s2→s4 3-rule 체인 + `sfc_chain`)을
의도했으나, 지시문이 경유 스위치만 나열하고 **서비스 기능(IDS/DPI 등)을 발동하지
않았다**. 가이드라인 §4.6은 sfc가 되려면 서비스 역할이 명시돼야 한다고 규정하므로,
두 어노테이터가 이를 forwarding으로 판정한 것은 **가이드라인상 정확한 판단**이었다.
즉 결함은 라벨이 아니라 지시문 wording에 있었다.

**해소 방식(항목 수정형 adjudication)**: adjudicator는 어노테이터 판단이 옳음을 인정하되,
해당 케이스가 의도한 것은 실제 서비스 체인 컴파일 경로였음을 근거로 **지시문을 서비스
역할이 드러나도록 수정**했다.

- G-SFC-031 → "Chain h1 to h4 traffic through **the IDS on switch 2**, then out via switch 4."
- G-SFC-032 → "Route SSH from h2 to h3 through **the DPI engine on switch 2** and then switch 4."

수정된 지시문은 "through the IDS/DPI on switch 2"라는, 두 어노테이터가 다른 모든
multi_switch_chain 케이스에서 **만장일치로 sfc로 판정한** 것과 동일한 표층 패턴을
가지므로, sfc 라벨과 3-rule gold program이 일관되게 정당화된다. 이 결정으로 카테고리
50/50 균형과 멀티홉 SFC 컴파일 커버리지가 모두 보존됐다.

이 조정은 어노테이터 판단을 뒤집는 것이 아니라 **결함 항목을 수정**하는, adjudication의
표준적 결과다. 두 건은 `final_labels.jsonl`에서 `source="adjudicated"`로 표기되고,
나머지 348건은 `source="unanimous"`다.

---

## 7. Gold 확정

`experiments/gold/build_gold.py`가 수정된 후보 + `final_labels.jsonl`을 병합해 최종
gold를 생성한다. adjudicated 라벨이 후보 카테고리와 불일치하면 저자가 program을 고쳐
쓴 `author_overrides.jsonl` 항목으로만 대체를 허용하며, 미해소 충돌은 gold에서 제외하고
`data/label_conflicts.json`에 격리한다(현재 0건).

최종 결과:

- gold 350건, `EvaluationCase` 스키마 전수 검증 통과.
- 카테고리 분포 50/50/50/50/50/50/50.
- 라벨 출처: unanimous 348, adjudicated 2, unresolved conflict 0.

`tests/test_gold_dataset.py`(6개 테스트)가 스키마·분포·rule 수 규약·blind split
무유출·blind 순서 비블록화·annotator↔final↔gold 정합성을 회귀 방지로 강제한다.

---

## 8. 재현 절차

```bash
# 1. 후보 + blind split 생성
.venv/bin/python experiments/gold/build_candidates.py

# 2. 독립 이중 라벨링 (각 어노테이터는 guideline + blind 파일만 접근)
#    → annotations/annotator_a.jsonl, annotator_b.jsonl

# 3. agreement 측정
.venv/bin/python experiments/gold/compute_agreement.py \
    experiments/gold/annotations/annotator_a.jsonl \
    experiments/gold/annotations/annotator_b.jsonl

# 4. adjudication 반영 후 gold 확정
.venv/bin/python experiments/gold/build_gold.py

# 5. 회귀 테스트
.venv/bin/python -m pytest tests/test_gold_dataset.py -q
```

---

## 9. 한계와 고지

- **어노테이터는 사람이 아니라 독립 LLM 에이전트 세션이다.** κ=1.0은 "동일 가이드라인
  하에서 독립 판단의 재현성"을 입증하지만, 사람 전문가 간 agreement를 대체하지 않는다.
  발표 시 이 점을 데이터셋 카드에 명시하고, 필요 시 사람 어노테이터 표본으로 보강한다.
- gold program(포트·device 배정)은 §2 토폴로지 가정에 종속된 저자 annotation이며,
  공식 ONOS/NetIntent 라벨이 아니다.
- adjudication으로 2건의 지시문을 수정했으므로, 라벨링 라운드의 입력(annotator_a/b.jsonl)은
  수정 전 wording에 대한 기록이고, 최종 blind/candidates/gold는 수정 후 wording을 담는다.
  이 불일치는 의도된 것이며 본 문서 §6에 그 근거가 남는다.
