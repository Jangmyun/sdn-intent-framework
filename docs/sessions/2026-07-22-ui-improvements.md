# UI/UX 개선 & 버그 수정 세션 — 2026-07-22

## 개요

XAI-SDN Pipeline 웹 UI 전반에 걸친 품질 개선 작업.  
QA 이슈 수정, 애니메이션 개선, 레이아웃 개편, 스테이지 카드 UI 고도화 등을 포함한다.

---

## 1. 프로젝트 QA 수정

### 1-1. config.py
- `CORS_ORIGINS` 설정 추가
- `API_KEY` 필드 추가
- `DATASET_PATH` 폴백을 `data/intents_v2.jsonl`로 수정
- `validate_config()` 함수 추가: ONOS 기본 비밀번호, API 키 미설정, wildcard CORS 경고 출력

### 1-2. pipeline/repair_utils.py (신규)
- `MAX_REPAIR_ATTEMPTS = 3` 상수
- `build_repair_feedback()` 함수
- `api.py`와 `main.py`에서 공유 사용

### 1-3. api.py
- CORS를 `config.CORS_ORIGINS`에서 읽도록 변경
- `POST /api/run`에 `_require_api_key` FastAPI 의존성 추가
- 토폴로지 로딩 순서: custom → ONOS → diamond (기존: custom → diamond)
- SSE 스트림 종료 시 "done" 이벤트 미수신 시 error + done 강제 발행
- 의도 입력 길이 제한 1000자 (`validate_intent()`)

### 1-4. pipeline/stage2_flowrule/compiler.py
- `extract_device_id()`: `(?:switch(?:es)?|sw|s|node)\s*(\d+)` 패턴을 bare digit 폴백보다 먼저 시도
- "switches 10 and 2" → 10 (기존에는 2로 잘못 추출)

### 1-5. 테스트 추가
- `tests/test_compiler.py`: 35개 pytest 단위 테스트 (extract_device_id, block/forward/reroute/sfc compile)
- `tests/test_conflict_detector.py`: 21개 pytest 단위 테스트 (충돌 탐지, validate())
  - `test_redundancy_is_warning_not_conflict`: Redundancy는 `conflicts`가 아닌 `warnings`에 기록됨을 검증

---

## 2. Mininet HTB Quantum 경고 억제

**문제**: TCLink로 대역폭 제한 링크 설정 시 Linux TC(HTB qdisc)가  
`sch_htb: quantum of class X is big` 커널 경고를 발생시킴.

**해결**: `pipeline/stage4_twin/topology.py`에 `suppress_htb_quantum_warning()` 컨텍스트 매니저 추가.  
`mininet.log.error`를 임시로 패치하여 해당 메시지만 필터링.  
`twin_verifier.py`의 `net.start()` 호출을 이 컨텍스트 매니저로 감쌈.

---

## 3. 웹 UI — Intent 번역 제거

**변경 범위**: intent 입력 번역 표시만 제거. 툴팁/타이틀 한국어는 유지.

- `static/index.html`: `<div id="intent-translation">` 제거, `.preset-item`의 `data-kr` 속성 제거
- `static/app.js`:
  - `bwLabelsVisible = false` (기본값 off)
  - `fillIntent(text, kr)` → `fillIntent(text)`로 kr 파라미터 제거
  - `showIntentTranslation()` / `hideIntentTranslation()` 함수 삭제
  - intent input 이벤트 리스너에서 `hideIntentTranslation()` 호출 제거 (ReferenceError 방지)

---

## 4. 트래픽 패킷 애니메이션 개선

### 4-1. 줌/팬 추적 수정
**문제**: 패킷이 `topoSvg`(루트 SVG)에 생성되어 줌/팬 시 따라가지 않음.  
**해결**: `getTwinLayer()`를 `topoZoomLayer`를 반환하도록 변경.

### 4-2. 노드 드래그 시 애니메이션 깨짐 수정
**문제**: `spawnPacket`이 실행 시점의 좌표를 고정값으로 D3 transition에 설정.  
노드 드래그로 위치가 바뀌어도 패킷은 원래 좌표를 향해 이동.

**해결**: D3 `.attr('cx'/.cy')` transition → `.tween('pos', ...)` 방식으로 교체.  
각 animation frame마다 `nodePositions` Map을 실시간으로 읽어 보간.

```javascript
t = t.transition().duration(segMs).ease(d3.easeLinear)
     .tween('pos', () => (tv) => {
       const from = nodePositions.get(fromId);
       const to   = nodePositions.get(toId);
       if (!from || !to) return;
       dot.attr('cx', from.x + (to.x - from.x) * tv)
          .attr('cy', from.y + (to.y - from.y) * tv);
     });
```

### 4-3. Block 애니메이션 점 고착 버그 수정
**원인**: `positions` → `initialPositions` 리네임 시 burst 체크 라인(1981)을 누락.  
`ReferenceError`로 `.remove()`가 호출되지 않아 점들이 목적지에 겹쳐 쌓임.  
**해결**: `positions.length` → `initialPositions.length`로 수정.

---

## 5. Digital Twin 카드 자동 닫힘

**문제**: 파이프라인 완료 후 Stage 4 카드가 열린 채로 남음.

**해결**: stage 4의 종료 분기(`else`)에 `s.expanded = false` 추가.

---

## 6. 파이프라인 진행 헤더 바

스테이지 카드 위에 전체 파이프라인 진행 상황을 시각화하는 헤더를 추가.

**구성요소**:
- 상단: 현재 단계명 (running=파란색, done=초록색, error=빨간색) + `3 / 6 · 50%` 카운터
- 중간: 6개 세그먼트 진행 바 — 단계별 상태에 따라 색상 전환, running 세그먼트는 shimmer 애니메이션
- 하단: `NLP | Flow | Validate | Twin | XAI | Deploy` 라벨

**파일 변경**:
- `static/index.html`: `#pipeline-progress` 블록 추가
- `static/style.css`: `#pipeline-progress`, `.pp-seg`, `.pp-step` 등 스타일 추가
- `static/app.js`: `renderPipelineProgress()` 함수 추가, `handleSSEEvent` 스테이지 이벤트에서 호출

---

## 7. 스테이지 카드 전환 부드럽게

**문제**: Stage 1/2/3 처리가 너무 빠르면 running 상태가 순식간에 지나가 보이지 않음.

**해결**: `MIN_STAGE_VISIBLE_MS = 700` 상수 도입.  
`running` 이벤트 수신 시 타임스탬프 기록 (`_stageRunningAt`).  
`done`/`error`/`skipped` 이벤트는 실제 경과 시간을 계산해 부족한 만큼 지연 후 렌더링.

**추가 개선**:
- `.stage-card` transition에 `border-color 0.4s ease` 추가
- `stage-card-enter` 애니메이션을 single RAF → double RAF로 변경 (브라우저가 초기 상태를 페인트한 후 transition 시작 보장)

---

## 8. Clos Fabric 토폴로지 프리셋 저장

사용자가 직접 구성한 커스텀 토폴로지를 `TOPO_PRESETS`에 저장.

**구조**: 5계층 Clos Fabric
```
Ingress(s1) → Access(s5, s2) → Distribution(s8,s6,s3,s7)
→ Core(s9,s4,s10,s11) → Aggregation(s12,s13) → Egress(s14)
```

- 14 switches, 10 hosts
- Distribution↔Core: 4×4 full bipartite (16 링크)
- 듀얼홈 호스트: h4·h5 (s7+s11), h8·h9 (s8+s9)
- 키: `'clos-fabric'`, 메뉴: **Research > ⬡ Clos Fabric (14SW · 10H)**

---

## 9. 입력창 / 파이프라인 영역 분리

**문제**: 스테이지 카드가 많아지면 입력창이 스크롤 아래로 밀려 보이지 않음.

**해결**: `#main`을 두 영역으로 분리.

```
#main (overflow: hidden)
├── #pipeline-area   ← flex: 1, overflow-y: auto (스크롤 가능)
│   ├── #pipeline-progress
│   ├── #stages-section
│   └── #decision-banner
└── #intent-section  ← flex-shrink: 0, border-top (항상 고정)
    ├── textarea
    ├── Presets 버튼
    └── Run Pipeline 버튼
```

---

## 10. 스테이지 카드 상세 뷰 고도화

기존 raw JSON 출력 → 스테이지별 전용 포맷 렌더링으로 교체.

| 스테이지 | 표시 내용 |
|---|---|
| **① Intent Parsing** | Action 배지 + 파싱 필드 표 (Src/Dst IP, Device, Protocol, Port 등) / Compound 시 서브룰별 분리 |
| **② FlowRule Compile** | 플로우 룰 카드 — Match 기준표 + Action(DROP ⛔ / → Port N) 나란히, 디바이스 ID·우선순위 헤더 |
| **③ Static Validation** | Pass/Fail 배지 + 충돌 테이블 (Type, Reason) + 경고 목록 (노란 배경) |
| **④ Digital Twin** | 상태 배지 + Verification Checks (✓ PASS / ✗ FAIL) + Evidence 표 |
| **⑤ XAI Explanation** | 결정 배지 + Overall Confidence 바 + 단계별 신뢰도 미니바 + Evidence 목록 |
| **⑥ ONOS Deploy** | 배포 성공/실패 배지 + 설치된 Flow ID 목록 |

**신규 함수**: `renderStageDetail(s)`, `renderSD1~6()`, `irTable()`, `flowCard()`  
**신규 CSS 클래스**: `.sd-section`, `.sd-badge`, `.sd-table`, `.sd-flow-card`, `.sd-check-row`, `.sd-conf-row`, `.sd-conf-bar-*`, `.sd-evidence-item` 등

---

## 11. Digital Twin — 부분 차단 검증 방식 개선

### 11-1. 문제 상황

Clos Fabric 토폴로지에서 h1→h2 트래픽에 대해 8개 스위치(s5, s8, s6, s3, s11, s4, s10, s12)를 블록하되, 의도적으로 일부 경로(h1→s1→s2→s7→s9→s13→s14→h2)를 열어두는 **부분 차단** 인텐트를 실행했을 때 Digital Twin이 FAIL을 반환하는 문제.

**원인**: 기존 검증 방식이 ping 결과를 권위 있는 기준으로 사용.
우회 경로로 ping이 통과되면 "차단 실패"로 판정 → 오탐.

### 11-2. 해결: OVS 제어플레인 기반 검증

`pipeline/stage4_twin/twin_verifier.py`의 block 인텐트 검증 로직을 재구조화.

**변경 전**: 스티어링 룰 설치 → ping 차단 여부 → 이것이 PASS/FAIL 기준  
**변경 후**:
1. `_block_rule_check()` (신규) — OVS flow table에서 DROP/NOACTION 룰 설치 여부 확인 **(1차, 권위 기준)**
2. 스티어링 + ping — 보조 확인, 로그에만 기록 **(2차)**
3. `intent_ok = ovs_ok` — OVS 확인이 판정 기준

```
OVS ✓ + ping 차단됨 → "스티어링 경로 차단 확인됨"     → PASS
OVS ✓ + ping 통과됨 → "우회 경로 존재 (부분 차단 — 정상)" → PASS
OVS ✗              → "OVS sN에 블록 룰 미발견"         → FAIL
```

### 11-3. `_block_rule_check()` 메서드 구현

`TwinVerifier` 클래스에 추가. 동작:
- `ovs-ofctl dump-flows {sw_name} -O OpenFlow13` 실행
- `actions=drop` 또는 `actions=` (NOACTION) 라인에서 `nw_src`, `nw_dst` 매칭 확인
- 최대 3회 재시도 (1초 간격)
- 룰 발견 시 `(True, msg)`, 미발견 시 `(False, msg)` 반환

---

## 12. Clos Fabric DPID 버그 수정

### 문제

`data/custom_topology.json`에서 s10~s14의 DPID가 decimal 표기로 잘못 저장됨.

| 스위치 | 잘못된 DPID | 올바른 DPID |
|---|---|---|
| s10 | `0000000000000010` (=0x10=16) | `000000000000000a` (=10) |
| s11 | `0000000000000011` (=17) | `000000000000000b` |
| s12 | `0000000000000012` (=18) | `000000000000000c` |
| s13 | `0000000000000013` (=19) | `000000000000000d` |
| s14 | `0000000000000014` (=20) | `000000000000000e` |

### 원인 분석

- `compiler.py`: `"s10"` → `f"of:{10:016x}"` = `of:000000000000000a`
- `topology.py`: `addSwitch("s10", dpid="0000000000000010")` → Mininet/ONOS에 `of:0000000000000010` (=16)으로 연결
- 두 값 불일치 → ONOS가 존재하지 않는 디바이스에 룰 푸시 시도 → 설치 실패
- `_block_rule_check`가 s10 OVS에서 룰을 못 찾음 → FAIL

### 해결

`data/custom_topology.json`의 DPID와 h10 MAC을 올바른 hex 값으로 수정.  
h10 MAC도 동일하게 `00:00:00:00:00:10` → `00:00:00:00:00:0a` 수정.

---

## 파일 변경 목록

| 파일 | 변경 내용 |
|---|---|
| `config.py` | CORS, API_KEY, validate_config() |
| `api.py` | API key 인증, 토폴로지 로딩 순서, SSE 에러 처리 |
| `main.py` | 토폴로지 로딩 통일, repair_utils 공유 |
| `pipeline/repair_utils.py` | **신규** — 공유 유틸리티 |
| `pipeline/stage2_flowrule/compiler.py` | extract_device_id 정규식 개선 |
| `pipeline/stage4_twin/topology.py` | suppress_htb_quantum_warning() 추가 |
| `pipeline/stage4_twin/twin_verifier.py` | 부분 차단 OVS 검증 + `_block_rule_check()` 추가 |
| `data/custom_topology.json` | s10~s14 DPID, h10 MAC hex 수정 |
| `tests/test_compiler.py` | **신규** — 35개 단위 테스트 |
| `tests/test_conflict_detector.py` | **신규** — 21개 단위 테스트 |
| `static/index.html` | pipeline-area 분리, pipeline-progress, Clos Fabric 프리셋 |
| `static/style.css` | 레이아웃 개편, 진행 바, 스테이지 디테일 패널 스타일 |
| `static/app.js` | 애니메이션 수정, 진행 바, 최소 표시 시간, 스테이지 렌더러 |
