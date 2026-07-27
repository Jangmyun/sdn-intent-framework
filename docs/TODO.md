# 미해결 과제

> 문서 정리(2026-07-27) 시 `GOLD350_VERIFICATION.md`와 `PIPELINE_HEALTH_REVIEW_2026_07_23.md`를
> 제거하면서, 그 문서들에만 기록되어 있던 **아직 처리되지 않은 항목**을 옮겨 담은 목록이다.
> 이미 해소된 항목(GOLD-350 F1/F2/F3/F7 등)은 옮기지 않았다.
>
> Exp-1 실험 관련 과제는 [`plan/EVAL_PLAN.md`](plan/EVAL_PLAN.md) §16에 따로 있다.

## High

### H1. RAG 인덱스를 매 요청마다 재구축

`main.py`와 `api.py` 둘 다 요청이 들어올 때마다 `rag.build_index()`를 호출한다.
이 함수는 데이터셋 전체를 **한 줄씩 임베딩 API 호출**한 뒤 FAISS 인덱스를 새로 만든다.
캐싱이나 영속화가 전혀 없어, 인텐트 파싱을 시작하기도 전에 최대 수백 번의 네트워크
임베딩 호출이 발생한다. 웹 서버 경로(`api.py`)에서 특히 체감이 크다.

→ 프로세스 시작 시 1회 구축 후 캐싱하거나, 임베딩 결과를 디스크에 저장해 재사용.

### H2. 핵심 안전 로직에 테스트가 없음

`tests/`는 `test_compiler.py`, `test_conflict_detector.py` 2개뿐이다.
정작 이 시스템이 내세우는 "환각 억제"와 "정적 검증"의 정확성을 보증하는 코드가
회귀 테스트로 보호받지 못하고 있다.

테스트 0인 모듈: `intent_parser.py`, `schema_validator.py`,
`models/topology.py`(`validate_switch`/`check_intent` — 환각 방어 핵심),
`flow_state_manager.py`, `twin_verifier.py`의 순수 헬퍼, `api.py` 엔드포인트.

→ 우선순위: `models/topology.py`와 `schema_validator.py`. 둘 다 순수 함수라 비용이 낮고
회귀 방지 효과가 크다.

## Medium

### M1. `main.py`와 `api.py`의 오케스트레이션 로직 중복

`repair_utils.py`로 공통 상수/피드백 빌더는 분리했지만, Repair Loop 구조 자체
(Stage1→2→3 순회, 재시도 조건, 로그 필드 조립)는 양쪽에 따로 구현되어 있다.
이미 갈라졌는지 diff 확인부터 필요.

### M2. `evaluate.py`와 `research/experiments/eval/`의 평가 프레임워크 이원화

`evaluate.py`는 `data/intents_v2.jsonl`(100케이스) 기반 구식 배치 평가이고,
현재 기준은 `research/experiments/eval/`(GOLD-350 350케이스)다.
**GOLD-350만 사용하기로 결정(2026-07-27)했으므로**, `evaluate.py`와 `intents_v2.jsonl`,
`scripts/generate_dataset.py`, `scripts/validate_dataset.py`의 처리 방향을 정해야 한다.

### M3. `device` 미지정 시 조용히 `"switch 1"`로 폴백

`models/intent_ir.py`에서 LLM이 device를 명시하지 않으면 명시적 오류 없이 스위치 1로
암묵 배정된다. `selector` 쪽은 "at least ONE concrete match criterion" 규칙으로 모호성을
적극 거부하는데 `enforcement.device`는 동일한 엄격함이 없다 — 비대칭.

### M4. compound 내부 충돌 검사가 외부 충돌 탐지보다 헐거움

외부 충돌 탐지(`conflict_detector.py`)는 CIDR subset/overlap까지 고려하지만
(`ip_overlaps`, `ip_is_subset`), compound sub-rule끼리는 criteria 값이 완전히 같은
경우만 검사한다(`c1[t] == c2[t]`). 겹치지만 동일하지 않은 CIDR을 쓰는 두 sub-rule 간
shadowing을 놓칠 수 있다.

### M5. Large 트랙 `L-SEC-R01` 라벨 충돌 (미처리)

프로덕션 프롬프트를 GOLD-350 가이드라인 §2 기준으로 개정하면서
`research/experiments/eval/data/intents_eval_large.jsonl`의 `L-SEC-R01`
("Block all traffic from 10.0.0.5.")이 구 기준으로는 `rejected/ambiguous`였으나
새 규칙에서는 정당한 accept가 된다. **현재 파일은 여전히 `rejected`로 남아 있다.**

→ Large 보조 실험을 진행하기 전에 이 1건의 라벨을 수정해야 한다.

## Low

### L1. 로그 회전/용량 상한 없음

`logs/{run_id}.json`이 무한 누적된다. gitignore되어 레포 오염은 없지만 디스크 관리 이슈.

### L2. `twin_verifier.py`의 셸 명령 f-string 조립

`_block_rule_check`/steering 로직이 `ovs-ofctl add-flow` 등을 f-string으로 조립한다.
`sw_name`/IP는 상위에서 검증되지만(정규식 `^[\d.]+$`, 토폴로지 기반 이름),
파라미터화 대신 문자열 삽입이라 향후 입력 경로가 늘면 주의 필요.

### L3. Twin 검증 확장 3종 미구현

경로 추적(`ovs-appctl ofproto/trace`), 동시 간섭 테스트, iperf3 임계값 판정.
특히 **iperf가 측정만 하고 판정을 안 해서 QoS 인텐트의 대역폭 보장이 현재 검증되지 않는다.**
자세한 내용은 [`design/FLOW_STATE.md`](design/FLOW_STATE.md) §10.

### L4. 라이브 세션 타임아웃 자동 종료 없음

`LiveNetworkSession`이 오래 방치되면 iperf3 프로세스가 계속 돈다.
서버 재시작 없이는 회수되지 않는다. → [`design/LIVE_NETWORK.md`](design/LIVE_NETWORK.md) §10.
