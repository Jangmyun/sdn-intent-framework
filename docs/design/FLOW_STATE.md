# Flow State 관리 — 구현 설명서

> Phase 1(백엔드)·Phase 2(UI)는 구현 완료, Phase 3(Twin 검증 확장)은 미구현 — §10 참조.

## 1. 해결하는 문제

Digital Twin은 매 파이프라인 실행마다 Mininet을 새로 시작하므로 근본적으로 stateless다.
기존 검증 흐름은 `Mininet 시작 → 기존 ONOS flow 전체 삭제 → 새 rule만 설치 → 검증`이었다.

실제 운영 ONOS에는 이전에 배포된 rule들이 쌓여 있으므로, "새 rule만 있는 이상적 환경"을
검증하는 것은 실제 환경과 괴리가 있다.

```
운영 ONOS 상태: [block s1(h1→h4)] + [forward s2(h2→h3)] + 새 rule [block s3(h1→h3)]
기존 Twin:      새 rule [block s3(h1→h3)] 만 설치 후 검증
개선된 Twin:    3개 rule 모두 설치 후 검증 (기존 rule과의 간섭도 확인)
```

**설계 결정 — Mininet 재시작은 유지한다.** Mininet 프로세스를 유지·재사용하는 방향도
이론상 가능하지만 ONOS 컨트롤러 연결 상태 관리 복잡도가 매우 높고, 이전 테스트 잔여
상태와 혼합될 위험이 있다. 대신 **시작 시 이전 state를 재현하는 방식**으로 해결했다.

---

## 2. 핵심 설계: FlowRule 캐시 + 사용자 명시적 로드

캐시 로드를 파이프라인 내부에서 자동으로 하지 않는다.
**사용자가 "Load State"로 명시적으로 불러온 뒤 파이프라인을 실행한다.**

```
┌─────────────────────────────────────────────┐
│  파이프라인 성공 (APPROVE + Deploy 완료)      │
│  → 새 FlowRule을 토폴로지별 캐시에 누적 저장  │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
        data/flow_state/{topology_id}.json
                       │
          사용자가 "Load State" 버튼 클릭
                       │
                       ▼
        state.preloadedFlows (프론트엔드 메모리)
                       │
          Run Pipeline 클릭 → /api/run body에 포함
                       │
                       ▼
┌─────────────────────────────────────────────┐
│  Stage 4 (Digital Twin)                     │
│  preloaded_flows + new_flows 모두 설치       │
│  → 검증 대상은 new_flows만                   │
│     (preloaded는 배경 환경 구성 용도)         │
└─────────────────────────────────────────────┘
```

**핵심 원칙:**
- 파이프라인(Stage 1~6)은 항상 **새 rule 하나만** 처리한다
- 캐시 state는 Twin의 "배경 환경"을 구성하는 용도다
- 사용자가 명시적으로 Load 해야만 적용된다 → 의도치 않은 state 누적 방지

---

## 3. 토폴로지 ID 체계

토폴로지마다 독립적인 state를 유지하기 위해 안정적인 ID를 사용한다.

| 토폴로지 종류 | ID 결정 방식 | 예시 |
|---|---|---|
| 프리셋 | 프리셋 키 그대로 | `"diamond"`, `"clos-fabric"` |
| 커스텀 | 파일명 고정 | `"custom"` |

`RunRequest.topology_id`로 프론트엔드가 현재 선택된 토폴로지를 전달한다.

```
data/flow_state/
├── diamond.json
├── clos-fabric.json
└── custom.json
```

---

## 4. `pipeline/flow_state_manager.py`

토폴로지별 FlowRule 상태를 `data/flow_state/`에 JSON으로 관리한다.

### 공개 API

| 함수 | 역할 |
|---|---|
| `load_state(topology_id, topo_hash=None)` | 저장된 flow 목록 반환. 해시 불일치 시 `[]` |
| `save_flows(topology_id, new_flows, intent_summary, topo_hash=None)` | 기존 state에 누적 저장 |
| `remove_flow(topology_id, flow_index)` | 특정 인덱스 flow 제거, 제거된 flow 반환 |
| `clear_state(topology_id)` | state 파일 삭제 |
| `list_states()` | 모든 토폴로지 요약 `{id: {count, updated_at}}` |
| `get_state_detail(topology_id)` | 특정 토폴로지 전체 state |
| `compute_topo_hash(custom_data)` | 커스텀 토폴로지 구조 해시 |
| `strip_meta_for_deploy(flows)` | ONOS 배포 전 `_meta` 제거 |

### 저장 형식

```json
{
  "topology_id": "clos-fabric",
  "flows": [
    {
      "deviceId": "of:0000000000000005",
      "priority": 50000,
      "selector": {"criteria": [...]},
      "treatment": {"instructions": [{"type": "NOACTION"}]},
      "_meta": {
        "intent": "block h1→h2 on s5",
        "deployed_at": "2026-07-23T14:30:00+00:00"
      }
    }
  ],
  "updated_at": "2026-07-23T14:30:00+00:00",
  "topo_hash": "a3f8c2d1"
}
```

`_meta`는 UI 표시용이며, ONOS 배포 전에 `_strip_meta()`로 제거된다.

### 동시성 안전장치

FastAPI는 동기 경로 함수를 threadpool에서 실행하므로 동시 요청이 같은 state 파일을
동시에 read-modify-write할 수 있다. 두 가지로 대응한다:

```python
_LOCK = threading.Lock()   # 프로세스 내 동시 접근 차단

def _write_file(topology_id: str, data: dict) -> None:
    """임시 파일에 쓴 뒤 os.replace()로 원자적 교체 — 쓰기 도중 프로세스가
    죽어도 기존 파일이 손상되지 않는다."""
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)
```

> 단일 프로세스 배포를 전제한다. 멀티 프로세스 배포 시에는 파일 락이 별도로 필요하다.

### 커스텀 토폴로지 구조 변경 시 자동 무효화

커스텀 토폴로지가 수정되면 기존 캐시의 `deviceId`가 더 이상 유효하지 않을 수 있다.
`custom.json` state에 토폴로지 구조 해시를 함께 저장하고, 로드 시 비교한다.

```python
def compute_topo_hash(custom_data: dict) -> str:
    """switches(id/dpid) + links(source/target)만 해싱.
    x/y 좌표, label 등 레이아웃 정보는 제외 — 네트워크 구조만 비교."""
    key = {
        "switches": sorted([...], key=lambda x: x["id"]),
        "links": sorted([{"s": min(...), "t": max(...)}], key=...),
    }
    return hashlib.md5(json.dumps(key, sort_keys=True).encode()).hexdigest()[:8]
```

링크는 `min`/`max`로 정규화해 방향에 무관하게 같은 해시를 낸다.
프리셋 토폴로지는 구조가 코드에 고정되어 있으므로 `topo_hash` 없이 호출한다.

---

## 5. `twin_verifier.py` 통합

`verify()`가 `preloaded_flows` 파라미터를 받는다. 파이프라인 내부에서 캐시를 직접
읽지 않고, API 레이어가 요청 body에서 받아 전달한다.

```python
def verify(
    self,
    flowrule: dict,
    progress_cb=None,
    emit_cb=None,
    preloaded_flows: Optional[list] = None,
    external_net=None,
    external_custom_data: Optional[dict] = None,
) -> TwinResult:
```

- `preloaded_flows`: 배포 전 배경 환경으로 함께 설치됨. **검증 대상은 `new_flows`만**
- `external_net`/`external_custom_data`: 라이브 세션 통합용 — [LIVE_NETWORK.md](LIVE_NETWORK.md) 참조

---

## 6. API 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/flow-state` | 전체 토폴로지 state 목록 (count, updated_at) |
| `GET` | `/api/flow-state/{topology_id}` | 특정 토폴로지 flows + `sync_status` |
| `DELETE` | `/api/flow-state/{topology_id}` | 전체 초기화 |
| `DELETE` | `/api/flow-state/{topology_id}/flows/{index}` | 개별 rule 삭제 + ONOS 동시 제거 |

쓰기 엔드포인트에는 `dependencies=[Depends(_require_api_key)]`가 적용된다.

### `sync_status` — ONOS Live와의 불일치 탐지

`GET /api/flow-state/{topology_id}` 응답에 캐시 ↔ ONOS 실제 상태 비교 결과가 포함된다.

```json
{
  "flows": [...],
  "sync_status": {
    "in_cache_not_onos": 2,
    "in_onos_not_cache": 0,
    "matched": 5,
    "onos_available": true
  }
}
```

비교 키는 `deviceId | priority | 정렬된 criteria`다. ONOS가 오프라인이면
`onos_available: false`로 반환하고 비교를 건너뛴다(예외를 삼킴).

| 상황 | UI 메시지 |
|---|---|
| 캐시에는 있는데 ONOS에 없음 | ⚠ `N개 rule이 ONOS에 미설치 상태 (재배포 필요)` |
| ONOS에는 있는데 캐시에 없음 | ℹ `N개 외부 rule 감지 (다른 경로로 설치됨)` |
| 완전 일치 | 배너 없음 |

### 개별 삭제 시 ONOS 동시 제거

`DELETE /api/flow-state/{topology_id}/flows/{index}`는 state에서 제거한 뒤
ONOS에서도 `delete_flows_by_priority(priority, device_id)`로 삭제를 시도한다.
**ONOS 삭제가 실패해도 state 삭제는 유지**되며, 응답의 `onos_deleted` 필드로 결과를 알린다.

---

## 7. 파이프라인 통합 지점 (`api.py`)

### 요청 파라미터

```python
class RunRequest(BaseModel):
    intent: str
    ...
    preloaded_flows: list = []   # UI "Load State"로 불러온 기존 FlowRule
    topology_id: str = ""        # 현재 선택된 토폴로지 ID (flow state 저장 키)
```

### Stage 4 — 배경 환경으로 설치

```python
twin_result = verifier.verify(
    flowrule,
    progress_cb=lambda msg: progress(4, msg),
    emit_cb=emit,
    preloaded_flows=req.preloaded_flows,
    ...
)
```

### Stage 6 — 배포 성공 시 저장

Twin 검증 통과 + ONOS 실제 배포 성공 시에만 저장한다.
커스텀 토폴로지면 현재 구조 해시를 함께 기록한다.

```python
if req.topology_id:
    if req.topology_id == "custom":
        # 현재 custom_topology.json 해시 계산
        ...
    flow_state_manager.save_flows(
        topology_id=req.topology_id,
        ...
    )
    progress(6, f"Flow state 저장 완료 ({req.topology_id}, {len(new_flows)}개 rule)")
```

---

## 8. UI (`static/app.js`, `index.html`, `style.css`)

### FLOW RULES 섹션 탭 구조

```
FLOW RULES  [ONOS Live] [Saved State ●3]
```

| 탭 | 내용 |
|---|---|
| **ONOS Live** | 현재 ONOS에 설치된 flow (기존 polling 유지) |
| **Saved State** | 캐시 파일의 누적 flow 목록 |

Saved State 탭 구성:
- flow 목록 (Device / Pri / Match / Action / Intent / 날짜)
- 개별 `✕` 삭제 버튼
- 전체 초기화 버튼
- `sync_status` 기반 불일치 배너

### 프론트엔드 상태

```javascript
const state = {
  ...
  preloadedFlows: [],   // Load State로 불러온 FlowRule 목록
};
```

`GET /api/flow-state/{topology_id}` → `state.preloadedFlows`에 저장 →
`renderSavedStateTab(flows, sync_status)` 렌더 → Run Pipeline 시
`/api/run` body의 `preloaded_flows`로 전달.

---

## 9. 엣지 케이스 처리

| 상황 | 처리 방식 |
|---|---|
| 캐시된 flow가 현재 ONOS에 없음 | `sync_status`로 배너 표시, 재배포 여부는 사용자 판단 |
| 캐시 flow + 새 flow 간 충돌 | Stage 3에서 REJECT → Stage 4 미진입 |
| 토폴로지 변경 (preset 전환) | 다른 `topology_id` → 독립 state 파일 |
| 커스텀 토폴로지 구조 변경 | `topo_hash` 불일치 → 캐시 무효화(`[]` 반환) + 경고 로그 |
| 캐시 초기화 후 재실행 | `load_state()` → `[]` → 새 flow만 설치 (기존 동작과 동일) |
| ONOS 배포 skip (toggle on) | state 저장 안 함 (Twin 통과만으로는 저장하지 않음) |

---

## 10. 미구현 — Twin 검증 확장 (계획 Phase 3)

아래 3가지가 원 계획의 Phase 3으로 포함되어 있었으나 **현재 미구현 상태**다.
`twin_verifier.py`에 해당 메서드가 존재하지 않는다.

| 항목 | 계획 내용 | 상태 |
|---|---|---|
| **경로 추적** (`_path_trace_check`) | `ovs-appctl ofproto/trace`로 패킷 처리 경로 확인. reroute/sfc가 실제로 의도한 경로를 타는지 검증 | 🔲 미구현 |
| **동시 간섭 테스트** (`_concurrent_interference_test`) | 설치된 모든 flow pair에 동시 ping → 순차 검증으로는 못 잡는 간섭 탐지 | 🔲 미구현 |
| **iperf3 임계값 판정** | `_iperf_check()`에 `min_bw_mbps` 추가 → QoS "최소 N Mbps 보장"을 PASS/FAIL로 격상 (현재는 측정만) | 🔲 미구현 |

현재 `_iperf_check()`는 Mbps를 측정해 표시하지만 판정 기준이 없어 QoS intent의
대역폭 보장 여부를 검증하지 못한다.
