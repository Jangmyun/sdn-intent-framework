# 파이프라인 코드베이스 점검 (2026-07-23)

전체 6-stage 파이프라인(`main.py`/`api.py` → Stage1~6)을 처음부터 다시 읽고 정리한 현황 평가.
목적: "지금 구현이 괜찮은가"에 대한 근거 있는 답과, 다음에 손볼 곳의 우선순위.

**결론 먼저**: 아키텍처 설계는 견고하다 (LLM을 파싱에만 국한하고 결정론적 컴파일러 +
정적 검증 + 실제 Digital Twin으로 안전성을 확보하는 구조). 다만 **테스트 커버리지가
컴파일러/충돌탐지 두 모듈에만 몰려 있고**, **RAG 인덱스를 매 요청마다 재구축**하는 등
운영 관점에서 짚어야 할 이슈가 몇 개 있다.

---

## 1. 아키텍처 평가

```
자연어 → [1 LLM/RAG] → IntentIR → [2 결정론적 컴파일러] → FlowRule
       → [3 정적검증] → (실패 시 최대 3회 Repair Loop로 1로 복귀)
       → [4 Digital Twin] → [5 XAI] → [6 배포]
```

**잘 된 설계 판단들:**

- **LLM은 파싱에만 쓰고 이후 전부 결정론적.** `stage2_flowrule/compiler.py`는 순수 함수이고,
  동일 `IntentIR` → 항상 동일 `FlowRule` (`compile_flowrule`, `compile_compound`). LLM
  환각이 배포까지 이어질 수 있는 경로를 구조적으로 차단한다는 README의 주장이 코드로
  실제 뒷받침된다.
- **환각 방어가 여러 층에 나뉘어 있다**: (a) `models/intent_ir.py:309-322`
  `_validate_raw_ip`가 LLM이 반환한 잘못된 IP(`999.999.999.999` 등)를 조용히 버리지 않고
  명시적으로 거부, (b) `models/topology.py:194-230` `check_intent`가 토폴로지에 없는
  호스트/스위치 참조를 `unknown_entity`로 거부, (c) `schema_validator.py:75-98`
  `_Criterion._validate_value_fields`가 Stage2 출력 자체도 다시 한번 IP/포트 범위를
  검증. 방어가 중복되는 게 아니라 서로 다른 실패 모드(LLM 출력 오류 vs 컴파일러 버그)를
  잡도록 계층화되어 있다.
- **Repair Loop** (`main.py:167-297`, `pipeline/repair_utils.py`)가 정적 검증 실패를
  LLM에게 자연어 피드백으로 돌려주고 최대 3회 재시도한다 — 단순하지만 효과적인
  self-correction.
- **충돌 탐지기 5종** (`conflict_detector.py`)이 priority 기반 override를 올바르게
  처리한다: 새 룰이 기존 룰보다 우선순위가 높고 기존 룰의 match를 완전히 덮으면
  Shadowing(진짜 충돌)이지만, 부분 겹침이면 "정상 override"로 분류해 false positive를
  피한다 (`conflict_detector.py:220-248`). Redundancy/Generalization은 경고로만 처리하고
  REJECT 사유에서 제외하는 판단(`static_validator.py:141-159`)도 합리적이다.
- **Digital Twin이 실제로 검증한다.** Mock이 아니라 Mininet+OVS에 실제 배포하고
  ping/TCP-SYN/iperf3로 확인한 뒤 `(deviceId, priority)` 조합으로 정밀 rollback한다
  (`twin_verifier.py:594-612`) — 배경에 깔린 `preloaded_flows`와 priority가 겹쳐도
  collateral delete가 안 나도록 신경 쓴 흔적이 있다.
- **확신도(confidence) 계산이 투명하다** — `static×0.5 + twin×0.5`의 명시적 가중합
  (`explainer.py:153-201`), 블랙박스 LLM 점수가 아니다. XAI라는 이름에 맞게 결정 근거가
  각 스테이지 데이터에 실제로 연결되어 있다(`evidence` 리스트).
- **동시성 안전장치**: `flow_state_manager.py`가 임시파일+`os.replace()`로 원자적 쓰기,
  전역 락으로 프로세스 내 동시 요청 보호, `topo_hash`로 커스텀 토폴로지 구조 변경 시
  캐시 자동 무효화(`flow_state_manager.py:70-105`) — 단일 프로세스 배포라는 전제를
  명시하고 그 안에서 정확하게 처리했다.
- **주석에 실제 버그 수정 이력(B2/B6/B7/D2/D10/F1 등)이 남아있다** — 한번 짜고 끝난
  코드가 아니라 QA 사이클을 거친 흔적. `conflict_detector.py`의 SFC 재배포 시 false
  positive 회피 로직(`static_validator.py:144-149`)처럼 실전에서 발견된 엣지케이스가
  반영되어 있다.

---

## 2. 발견한 이슈 (우선순위순)

### High

**H1. RAG 인덱스를 매 요청마다 처음부터 재구축한다.**
`main.py:104-114`와 `api.py:152-192` 둘 다 파이프라인/API 요청이 들어올 때마다
`rag.build_index()`를 호출한다. 이 함수(`stage1_intent/rag.py:16-71`)는 `data/intents_v2.jsonl`
전체(현재 100줄)를 **한 줄씩 임베딩 API 호출**한 뒤 FAISS 인덱스를 새로 만든다. CLI 1회
실행이든 API 요청 1건이든 인텐트 파싱을 시작하기도 전에 최대 100번의 네트워크 임베딩
호출이 발생한다는 뜻이다. 인덱스는 데이터셋이 바뀌지 않는 한 재사용 가능한데 캐싱이나
영속화가 전혀 없다. 데이터셋이 커지면(현재 GOLD-350 실험처럼 350개+) 요청당 지연시간이
선형으로 늘어난다 — 웹 서버 경로(`api.py`)에서는 특히 체감이 크다.
→ 프로세스 시작 시 1회 구축 후 캐싱하거나, 임베딩 결과를 디스크에 저장해 재사용 권장.

**H2. 테스트가 Stage2(컴파일러)/Stage3(충돌탐지)에만 몰려 있다.**
`tests/`에는 `test_compiler.py`(194줄), `test_conflict_detector.py`(156줄) 2개뿐이고
56개 테스트 모두 통과한다. 하지만:
- `intent_parser.py` (LLM 응답 파싱, compound intent 분기, 토폴로지 검증 연동) — 테스트 0
- `schema_validator.py` — 테스트 0 (Pydantic 모델이라 간단히 커버 가능한데도)
- `models/topology.py`의 `validate_switch`/`check_intent` (환각 방어 핵심 로직) — 테스트 0
- `flow_state_manager.py` (원자적 쓰기, topo_hash 무효화) — 테스트 0
- `twin_verifier.py`의 순수 헬퍼(`_bfs_sw_path`, `_parse_output_port`, `_device_id_to_sw_name`) —
  Mininet 없이도 단위테스트 가능한데 테스트 0
- `api.py` 엔드포인트 — 테스트 0

이 시스템이 내세우는 "환각 억제"와 "정적 검증"의 실제 정확성을 보증하는 게 바로 이
테스트 안 된 코드들이다. 컴파일러는 결정론적이라 테스트가 쉽지만, 정작 안전성 주장의
핵심(LLM 출력 검증, 토폴로지 그라운딩)은 현재 회귀 테스트로 보호받지 못한다.

### Medium

**M1. `main.py`와 `api.py`가 파이프라인 오케스트레이션 로직을 거의 통째로 중복한다.**
`repair_utils.py`로 공통 상수/피드백 빌더는 분리했지만, Repair Loop 구조 자체(Stage1→2→3
순회, 재시도 조건, 로그 필드 조립)는 `main.py:167-297`과 `api.py`의 `_run_pipeline`(길이상
비슷한 규모로 추정)에 각각 따로 구현되어 있다. 버그를 고치거나 로직을 바꾸면 두 곳에
반영해야 하고, 실제로 이미 한 번 이렇게 갈라졌을 가능성이 있다(직접 diff 확인 권장).

**M2. 루트의 `evaluate.py`와 `experiments/eval/`가 두 개의 평가 프레임워크로 공존.**
`evaluate.py`는 `data/intents_v2.jsonl` 기반 구식 배치 평가 스크립트이고, 현재 실제로
쓰이는 건 `experiments/eval/run_exp1.py` + `score_exp1.py` (GOLD-350 기반)다. 어느 쪽이
"현재 기준"인지 코드만 봐서는 알기 어렵다 — 신규 기여자가 헷갈릴 수 있는 지점.

**M3. `models/intent_ir.py:376-377`에서 `device` 미지정 시 조용히 `"switch 1"`로 폴백.**
LLM이 device를 명시하지 않은 인텐트(예: 파싱 누락)가 명시적 오류 없이 스위치 1로
암묵 배정될 수 있다. `selector` 쪽은 "at least ONE concrete match criterion" 규칙으로
모호성을 적극적으로 거부하는데(`intent_parser.py` SYSTEM_PROMPT §Selector completeness),
`enforcement.device` 쪽은 동일한 엄격함이 없다 — 비대칭.

**M4. 복합 인텐트 내부 충돌 검사(`_check_intra_conflicts`, `static_validator.py:46-114`)가
외부 충돌 탐지기(`conflict_detector.py`)보다 헐거운 로직을 쓴다.** 외부 충돌 탐지는
CIDR subset/overlap까지 고려하는데(`ip_overlaps`, `ip_is_subset`), compound 룰끼리는
criteria 값이 완전히 같은 경우만 검사한다(`c1[t] == c2[t]`). 겹치지만 동일하지 않은
CIDR을 쓰는 두 sub-rule 간 shadowing은 놓칠 수 있다.

### Low

**L1.** 로그(`logs/{run_id}.json`)에 회전/용량 상한이 없음 — 장기 운영 시 누적. gitignore
되어 있어 레포 오염은 없지만 디스크 관리 이슈로 남을 수 있음.

**L2.** `twin_verifier.py`의 `_block_rule_check`/steering 로직(`ovs-ofctl add-flow` 등)이
f-string으로 셸 명령을 조립한다. `sw_name`/IP 값이 상위에서 이미 검증되긴 하지만(정규식
`^[\d.]+$` 체크, 토폴로지 기반 이름), 파라미터화 대신 문자열 삽입 방식이라 defense-in-depth
관점에서 향후 입력 경로가 늘어나면 주의가 필요.

**L3.** 보안 기본값(`API_KEY=""`, `ONOS_PASSWORD="rocks"`, `CORS_ORIGINS="*"`)은 이미
`config.py:82-106`에서 시작 시 경고를 출력하고 README에도 운영 가이드가 있어 "알려진 채로
방치된" 상태는 아님 — 새 이슈라기보다 기존에 문서화된 리스크로 재확인.

---

## 3. 정량 스냅샷

| 항목 | 값 |
|---|---|
| Python 소스 파일 수 | 25개 (pipeline/, models/, api.py, main.py 등) |
| 테스트 파일 / 통과 | 2개 파일, 56개 테스트, 전부 통과 |
| 테스트가 없는 핵심 모듈 | intent_parser, schema_validator, topology, flow_state_manager, twin_verifier(순수 헬퍼), api.py |
| Stage4 twin_verifier.py 크기 | 1075줄 (verify() 단일 메서드가 약 450줄) |
| api.py 크기 | 984줄 |
| RAG 재임베딩 비용 | 요청당 최대 100회 임베딩 호출 (intents_v2.jsonl 기준, GOLD-350 사용 시 더 커짐) |

---

## 4. 권장 우선순위

1. **RAG 인덱스 캐싱** (H1) — 웹 서버 경로 지연시간에 직접 영향, 수정 난이도 낮음.
2. **핵심 안전 로직에 최소 단위테스트 추가** (H2) — 특히 `models/topology.py`
   (`validate_switch`, `check_intent`)와 `schema_validator.py`. 둘 다 순수 함수라 비용 낮고
   회귀 방지 효과가 큼.
3. **`main.py`/`api.py` 오케스트레이션 로직 실제 diff 확인** (M1) — 이미 갈라졌는지부터 점검.
4. **`evaluate.py` vs `experiments/eval/` 관계 정리** (M2) — 둘 중 하나를 legacy로 명시하거나
   evaluate.py를 삭제/archive.
5. device_hint 폴백(M3), compound intra-conflict 엄격도(M4)는 급하지 않지만 이번에 함께
   기록해 둠.

---

*이 문서는 2026-07-23 기준 코드 스냅샷(`exp/eval-v2` 브랜치)을 대상으로 함. 현재 GOLD-350
실험(T-D, qwen3:8b) 진행과는 별개로, 파이프라인 본체(main.py/api.py/pipeline/) 코드 품질을
검토한 결과다.*
