# GOLD-350 실험 착수 전 검증 보고서

> 작성: 2026-07-23
> 대상: `docs/dataset/gold.jsonl` (원본) → `experiments/eval/data/gold350_eval.jsonl` (변환본) + Exp-1 실험 체계(run_exp1.py / score_exp1.py / T-A~D config)
> 방법: 자동 검증 스크립트(구조·값·정합성 전수 검사) + 채점기 시뮬레이션 + 프롬프트 대조

---

## 결론 먼저

> **2026-07-23 업데이트: Blocker 전부 해소 완료 — 실험 실행 가능 상태.**
> 최초 검증에서는 "이대로 실행 불가" 판정이었으나, 아래 조치를 모두 적용·재검증했다.

| # | 등급 | 요약 | 영향 범위 | 조치 결과 |
|---|---|---|---|---|
| F1 | 🔴 Blocker | 채점기가 포트 없는 waypoint를 정규화 못 함 | sfc 23/50 케이스 | ✅ **수정 완료** — `score_exp1.py` `normalize_waypoints()`가 문자열 전체를 alias로 먼저 해석. `of:0000000000000002`/`s2`/`switch 2` 모두 `device:s2`로 수렴 확인. 포트 형식(`s1:9`) 회귀 없음 |
| F2 | 🔴 Blocker | 프롬프트의 "src/dst 필수, 없으면 reject" 규칙이 gold와 충돌 | accepted 30/300 케이스 | ✅ **수정 완료** — 실험 전용 완화가 아니라 **프로덕션 프롬프트 자체를 가이드라인 §2 기준으로 개정** (사용자 결정). 규칙: "매치 기준 1개 이상이면 유효 + compound default 절은 eth_type=ipv4 catch-all + dst·egress 둘 다 없는 단독 forward만 ambiguous 유지". GOLD-350이 자체 스펙이므로 E1식 이중 프롬프트보다 정합 |
| F3 | 🟡 결정 필요 | gold가 텍스트에 없는 배선(wiring) 지식을 요구 | reroute 34, sfc 24+ 케이스 | ✅ **옵션 (c) 채택·완료** (사용자 결정) — `topology_eval.json` v2에 `wiring`/`wiring_notes` 추가, `run_exp1.py` grounding 빌더가 "port -> connected node" 형식으로 주입. **배선 테이블을 gold 전수와 대조해 실제 불일치 0건 확인** (외견상 불일치 7건은 전부 의미 해석상 정상) |
| F7 | 🟡 신규 발견 | `topology_eval.json`이 가이드라인에 없는 유령 포트(s2/s3의 3,4번)를 광고 | grounding 정확성 | ✅ **수정 완료** — s2/s3 포트를 가이드라인 §1 기준 [1,2]로 정정. gold 300케이스 재검사 결과 가이드라인 포트셋 위반 0건(gold는 원래부터 준수) |
| F4 | 🟢 참고 | rejected 케이스가 전부 한 카테고리에 몰림 | 지표 해석 | 조치 불필요 — 논문 표 작성 시 유의 |
| F5 | 🟢 참고 | 소요 시간 — 10 reps 기준 총 ~15.6시간 (15RPM) | 일정 | 첫 treatment 3 reps로 분산 실측 후 reps 확정 권장 |
| F6 | 🟢 참고 | T-B/T-C는 h1→10.0.0.1 매핑을 알 수 없음 (by design) | 해석 | 조치 불필요 — grounding ablation의 본질 |

**조치 후 재검증 결과 (2026-07-23):** `validate_gold.py` 300/300 PASS · self-score NEM 300/300 · 유닛테스트 56/56 통과 · T-D dry-run 정상(시스템 프롬프트 ~2393 tokens, 배선 추가로 +369). 남은 참고사항은 F5(첫 실행에서 분산 실측)와 Large 트랙 진행 시 L-SEC-R01 라벨 충돌 1건 처리뿐이다.

---

## 1. 통과한 검증 항목 ✅

| 검증 | 결과 |
|---|---|
| case_id 유일성 | 350/350 유일, 중복 0 |
| 카테고리 균형 | 7카테고리 × 정확히 50개 |
| status 분포 | accepted 300 / rejected 50 (레이블 명세와 일치) |
| instruction 텍스트 중복 | 0건 |
| action 값이 파이프라인 enum(forward/block/qos/sfc/reroute) 내인가 | 위반 0건 |
| host↔IP 역채움 정합성 (h1=10.0.0.1 …) | 불일치 0건 |
| enforcement.device가 인벤토리 내인가 | 위반 0건 |
| egress_port가 해당 스위치 유효 포트 내인가 | 위반 0건 |
| accepted 케이스에 인벤토리 밖 엔티티 언급 없는가 | 위반 0건 |
| rejected(unknown_entity) 케이스에 실제 미지 엔티티가 있는가 | 15건 전부 확인 (9건 숫자형 h5/h9/switch 7/172.16.x 등, 6건 이름형 "database server"/"printer-01"/"port 7 on s3" 등 — 모두 의도된 설계) |
| Stage1 IR 구성 + Stage2 컴파일 (validate_gold.py) | accepted 300/300 PASS |
| score_exp1.py 자기 자신 채점(self-score) | 300/300 NEM=1.0 |
| run_exp1.py 350케이스 로드 (dry-run, T-A/T-D 양쪽) | 정상 |

데이터셋의 **내적 품질에는 문제가 없다.** 아래 발견 사항은 전부 "이 데이터셋 ↔ 기존 실험 체계"의 접합부에서 나온 것이다.

---

## 2. F1 (Blocker) — 포트 없는 waypoint 채점 불가

**증상**: GOLD-350의 sfc 케이스 중 23개는 `sfc_chain`이 포트 없는 디바이스만으로 표현된다(예: `"of:0000000000000002"` — "IDS on switch 2"류, 서비스가 스위치 자체에 붙어 있어 포트 특정이 불필요). 그런데 `score_exp1.py`의 `normalize_waypoints()`는 마지막 콜론 기준으로 device:port를 쪼개기 때문에, `of:0000000000000002`를 "`of`라는 디바이스의 `0000000000000002`번 포트"로 잘못 해석한다.

**채점 시뮬레이션 결과** (gold=`["of:0000000000000002"]`):

| LLM이 낼 법한 출력 | 정규화 결과 | 매칭 |
|---|---|---|
| `["s2"]` | `s2` | ❌ |
| `["switch 2"]` | `switch 2` | ❌ |
| `["s2:1"]` | `device:s2:1` | ❌ |
| `["of:0000000000000002"]` (완전 동일 문자열일 때만) | 그대로 | ✅ |

즉 **모델이 의미상 정답을 내도 문자열이 정확히 `of:...` 형식이 아니면 무조건 오답 처리**된다. sfc 카테고리 waypoints 슬롯 정확도가 최대 27/50으로 상한이 깎인 채 시작하는 셈이다.

**권장 수정** (score_exp1.py, ~5줄): `normalize_waypoints()`에서 각 항목을 쪼개기 전에 **문자열 전체가 alias로 해석되는지 먼저 확인**하고, 되면 canonical ID로 통일한다. `of:0000000000000002`·`s2`·`switch 2`가 모두 `device:s2`로 수렴하므로 문제가 사라진다. 포트 있는 `s1:9` 형식은 기존 로직 그대로 탄다. (변환기 쪽에서 고치는 방법도 있지만, 채점기를 고치는 쪽이 예측 측 표기 다양성까지 함께 해결한다.)

---

## 3. F2 (Blocker) — 프롬프트 ↔ gold 수락 철학 충돌

**증상**: T-B/C/D가 쓰는 시스템 프롬프트(`intent_parser.SYSTEM_PROMPT`)에는 다음 규칙이 있다:

> "For action=block and action=forward: BOTH source.ip AND destination.ip must be specified. If either is missing, reject with reason 'ambiguous'. … Do NOT infer or guess IPs from context. If not stated, reject."

그런데 GOLD-350은 ANNOTATION_GUIDELINE §2("unidirectional flows between inventory endpoints" — 단방향/한쪽 엔드포인트 flow도 컴파일 가능)에 따라 **한쪽 엔드포인트만 있는 forward/block을 accepted로 라벨링**했다. 전수 확인 결과 충돌 케이스 30개:

| 카테고리 | 건수 | 예시 |
|---|---|---|
| forwarding | 9 | G-FWD-011 "On switch 1, forward traffic destined for 10.0.0.2 out port 4." (src 없음) |
| security | 9 | G-SEC-021 "On switch 1, drop all traffic from 10.0.0.1." (dst 없음) |
| compound | 12 | G-CMP-001 "Drop all traffic from h2 … and forward everything else normally." (rule2는 src·dst 둘 다 없음) |

모델이 프롬프트를 **충실히 따를수록** 이 30건을 reject하고, gold는 accept이므로 → `false_rejection_rate`가 최대 10%p까지 인위적으로 올라간다. 반대로 모델이 프롬프트를 무시해야 점수가 나오는 구조는 실험으로서 자기모순이다.

**선례**: 같은 문제를 E1 재현 실험 때 이미 겪었고, 그때의 해법이 [EXPERIMENT_PLAN.md](../plan/EXPERIMENT_PLAN.md) §2-3에 기록되어 있다 — *"실험 전용 system prompt를 별도로 작성하여 src_ip 미필수 조건으로 완화한다. (현재 파이프라인의 프로덕션 프롬프트는 변경하지 않는다.)"*

**권장 수정**: 동일한 방식. `run_exp1.py`에 실험 전용 완화 프롬프트(해당 단락만 "한쪽 엔드포인트만 명시된 경우 그대로 파싱하라"로 교체)를 정의해 T-B/C/D가 그걸 쓰도록 한다. **프로덕션 `intent_parser.py`는 건드리지 않는다.**

---

## 4. F3 (결정 필요) — gold가 요구하는 "배선 지식"은 텍스트·프롬프트 어디에도 없음

**증상**: GOLD-350의 reroute/sfc gold는 팀원이 고정 토폴로지의 **링크 배선**(s1-s2는 s1 포트 1, s1-s3는 s1 포트 2, h1은 s1에 접속 등)을 알고 작성한 "컴파일 결과에 가까운" 값이다. 그런데 이 배선 정보는 인텐트 텍스트에도 없고, **T-D의 grounding 프롬프트에도 없다**(topology_eval.json에는 포트 *목록*만 있고 링크 연결 관계가 없음). 전수 확인 결과:

- **reroute 34/50**: gold `enforcement.device`가 텍스트에 언급 안 된 스위치. 예) G-RRT-001 "Reroute h1 to h4 traffic **via switch 3** instead of switch 2." → gold device=**s1**(h1의 접속 스위치), egress_port=**2**(s1→s3 방향 포트). 텍스트가 언급하는 스위치는 2·3뿐. 모델은 s1도 포트 2도 알아낼 방법이 없다.
- **reroute 18/50**: gold `egress_port` 숫자가 텍스트에 등장하지 않음 (위와 중복 다수).
- **sfc 24/50**: gold `enforcement.device`(ingress 스위치)가 텍스트 언급 스위치와 불일치. sfc 38/50은 egress/alt_egress 포트가 텍스트에 없음.

참고로 **기존 60케이스 데이터셋은 이 문제가 없도록 텍스트에 포트를 명시**했다(예: SFC-01 "…on switch 1 **port 9**, then forward out **port 2**"). 두 데이터셋의 gold 철학이 다른 것: 기존 것은 "텍스트에서 파싱 가능한 것"만 gold로 삼았고, GOLD-350은 "정확한 컴파일에 필요한 것"을 gold로 삼았다. **Exp-1은 Stage 1(파싱) 능력을 측정하는 실험이므로**, 텍스트에서 원리적으로 유도 불가능한 슬롯은 파싱 능력이 아니라 우연을 측정한다.

**옵션 3가지 (사용자 결정 필요):**

| 옵션 | 내용 | 장단점 |
|---|---|---|
| **(a) 그대로 진행** | 배선 의존 슬롯 실패를 그냥 받아들임 | 조치 없음. 단, reroute/sfc의 슬롯 정확도·NEM은 4개 treatment 모두 바닥에 깔려 변별력 상실. 논문 표에서 "왜 이 카테고리만 0에 가까운가"를 설명해야 함 |
| **(b) 채점 시 배선 의존 슬롯 제외** | 변환기에서 reroute/sfc의 텍스트-유도-불가 슬롯(device/egress_port/alt_egress_port 중 텍스트에 없는 것)을 null 처리 → score_exp1.py가 자동으로 채점 제외 | Exp-1의 측정 목적("파싱 정확도")과 정합. 기존 60케이스 철학과도 일치. gold 원본은 손대지 않고 변환기만 수정 |
| **(c) grounding 프롬프트에 링크 배선 추가** | topology_eval.json에 links 섹션을 추가하고 T-D 프롬프트에 주입 | T-D만 이 슬롯을 맞출 수 있게 됨 → "배선까지 아는 grounding"의 효과를 보여주는 확장 실험이 됨. 단, T-B/C는 여전히 원리적으로 불가능해 treatment 간 비교가 이 슬롯들에서 불공정. 프롬프트 토큰도 증가 |

**권장**: **(b)** — Exp-1의 목적에 맞고 수정 범위가 변환기 한 곳이다. (c)는 나중에 T-D 전용 추가 분석으로 얹을 수 있다(상호 배타적이지 않음).

---

## 5. 참고 사항 (조치 불필요, 해석 주의)

**F4 — rejected 분포 변화**: 기존 60케이스는 rejected가 6개 카테고리에 1개씩 분산됐지만, GOLD-350은 50개 전부 `ambiguous_unsupported` 단일 카테고리다. `rejection_recall`은 문제없이 계산되지만, **카테고리별 지표 표에서 rejected 관련 수치는 이 카테고리에만 나타난다**. 논문 표 구성 시 유의.

**F5 — 소요 시간**: 350케이스 기준 실측 필요. 15RPM(프리 티어) 가정 시:

| reps | treatment당 | 4 treatments 총 |
|---|---|---|
| 10 | ~3.9h | **~15.6h** |
| 5 | ~1.9h | ~7.8h |
| 3 | ~1.2h | ~4.7h |

n=350이면 rep당 케이스 수가 커서 **reps를 10 → 5로 줄여도 통계적 안정성은 오히려 기존(60케이스×10reps)보다 낫다**(케이스 수가 분산의 지배 요인). 마감(D-32) 감안 시 5 reps 권장. 단, 기존 T-D가 std=0.000(완전 결정론적)이었던 점을 고려하면 3 reps로도 충분할 가능성이 높다 — 첫 treatment를 3 reps 돌려 rep 간 분산을 실측한 뒤 결정하는 것도 방법.

**F6 — T-B/T-C의 엔드포인트 IP**: GOLD-350 instruction 대부분이 호스트 이름(h1)만 언급하고 gold에는 IP(10.0.0.1)가 채워져 있다(변환기가 인벤토리로 역채움 — 기존 60케이스도 동일한 구조였음). grounding이 없는 T-B/T-C는 h1→10.0.0.1 매핑을 "추측"해야 하며, 이는 **의도된 설계다**(grounding 효과 측정이 실험 목적). 다만 h(N)→10.0.0.(N)은 Mininet 표준 관례라 LLM이 맞힐 가능성이 높다는 점은 해석 시 염두에 둘 것.

---

## 6. 조치 이력 (전부 완료)

1. ✅ **F1** — `score_exp1.py` `normalize_waypoints()` alias 우선 해석 적용, 동치/회귀 시뮬레이션 통과
2. ✅ **F2** — 계획 변경(사용자 결정): 실험 전용 완화 프롬프트 대신 **프로덕션 `intent_parser.SYSTEM_PROMPT`의 "src/dst IP requirements" 절을 "Selector completeness requirements"로 개정**. GOLD-350 가이드라인 §2를 시스템의 규범 스펙으로 채택한 것. 부작용: Large 트랙(구 철학)의 L-SEC-R01("Block all traffic from 10.0.0.5" = 구 gold rejected)이 새 규칙에선 정당한 accept → **Large 보조 실험 전 이 1건 라벨 수정 필요**
3. ✅ **F3(c) + F7** — `topology_eval.json` v2 (wiring 추가 + 유령 포트 제거), `run_exp1.py` grounding 빌더 확장. 배선 테이블-gold 전수 대조로 불일치 0건 확인
4. ✅ 재검증 — validate_gold 300/300, self-score 300/300, pytest 56/56, dry-run 정상
5. ⏭ 다음: 첫 treatment 3 reps 실행 → rep 간 분산 실측 → 최종 reps 확정(F5) → 전체 실행

---

## 부록 — 재현 방법

```bash
# 구조/값/정합성 전수 검사 + 채점 시뮬레이션 (이 보고서의 근거)
# 스크립트: (세션 scratchpad) verify_gold350.py — 필요 시 experiments/eval/로 승격 가능

# gold 컴파일 검증
python experiments/eval/validate_gold.py --dataset experiments/eval/data/gold350_eval.jsonl

# dry-run 로드 확인
python experiments/eval/run_exp1.py --config experiments/eval/config/T-D.toml --repetitions 1 --dry-run
```
