# 네트워크 프리셋 & 실시간 모니터링 — 구현 설명서

> 계획 단계 대비 두 가지 주요 설계 변경이 있었다 — §6-1(모니터링 소스), §7(파이프라인 통합).

## 1. 목표

**"네트워크 프리셋을 적용하면 특정 상황(예: 코어 링크 혼잡)이 실제로 재현된 네트워크가
그 순간부터 계속 돌아가고, 운영자는 링크별 대역폭·혼잡 위치·드롭률·큐 백로그를 실시간으로
보면서 필요하면 그 자리에서 바로 정책(FlowRule)을 적용할 수 있다."**

기존 파이프라인과 **실행 모델 자체가 다르다**는 점이 핵심이다.

| | 기존 (Stage 1~6) | 네트워크 프리셋 |
|---|---|---|
| 실행 방식 | 요청 1건 → 검증 → 배포 → **즉시 종료** | 프리셋 적용 → **계속 실행**되는 세션 |
| Digital Twin 수명 | `verify()` 안에서 시작→검증→rollback→`net.stop()` (1회성) | 명시적으로 멈출 때까지 지속 |
| 모니터링 | 없음 (Twin 검증 중 iperf 배지만 일시적) | 상시 — 세션이 살아있는 한 계속 |

---

## 2. 토폴로지

**메인: `clos-fabric` 프리셋 재사용.** 실제 오버서브스크립션 지점이 있다 —
Aggregation→Egress (`s12→s14`, `s13→s14`, 각 10Mbps, 합 20Mbps)가 h2(100Mbps 링크)
쪽으로 좁아지는 구조라, 여러 호스트가 동시에 h2로 보내면 진짜 병목이 생긴다.

**보조: `diamond`** — 링크 2개(1Mbps/10Mbps)뿐이라 "혼잡 vs 우회 경로"를 가장 빨리
눈으로 확인할 수 있는 최소 재현 케이스.

---

## 3. 트래픽 프리셋 (`data/traffic_presets/`)

토폴로지 프리셋과 별개 개념이다. **하나의 트래픽 프리셋은 특정 토폴로지 프리셋을 전제로,
그 안에서 동시에 흐를 배경 flow들을 정의한다.**

파일명 규칙: `{topology_id}_{preset_id}.json`

```jsonc
// data/traffic_presets/clos-fabric_core-congestion.json
{
  "id": "clos-fabric_core-congestion",
  "label": "코어 혼잡 — 다수 호스트가 h2로 동시 스트리밍",
  "topology_id": "clos-fabric",
  "flows": [
    { "id": "f1", "src": "h1",  "dst": "h2", "proto": "tcp",
      "target_mbps": 8, "pattern": "constant",
      "start_offset_sec": 0,  "duration_sec": null },   // null = 세션 종료까지
    { "id": "f2", "src": "h7",  "dst": "h2", "proto": "tcp",
      "target_mbps": 8, "pattern": "constant",
      "start_offset_sec": 0,  "duration_sec": null },
    { "id": "f3", "src": "h10", "dst": "h2", "proto": "udp",
      "target_mbps": 6, "pattern": "bursty",
      "start_offset_sec": 10, "duration_sec": null }
  ]
}
```

f1+f2가 8+8=16Mbps로 `s12→s14`/`s13→s14`(합 20Mbps) 용량의 80%를 채우고,
f3가 10초 뒤 추가되면 20Mbps를 넘겨 실제로 드롭이 발생한다.

### 구현된 프리셋 6종

| 파일 | 시나리오 |
|---|---|
| `clos-fabric_idle.json` | 배경 트래픽 없음 — false-positive 혼잡 탐지 방지 베이스라인 |
| `clos-fabric_core-congestion.json` | Aggregation→Egress 포화 (핵심 데모) |
| `clos-fabric_ramping-load.json` | 트래픽 점진 증가 — 혼잡이 서서히 심해지는 그래프 |
| `clos-fabric_bursty-single-link.json` | 한 링크에만 짧은 버스트 반복 — 순간 vs 지속 혼잡 구분 |
| `clos-fabric_dual-homed-failover.json` | dual-homed 호스트 한쪽 업링크만 부하 — 이중화 경로 시나리오 |
| `diamond_slow-path-saturation.json` | 1Mbps 저속 경로를 채우는 최소 재현 케이스 |

---

## 4. 배경 트래픽 생성기 (`stage4_twin/traffic_generator.py`)

기존 `_iperf_check()`는 "1회 측정 후 종료"(foreground, blocking)라 목적이 다르므로
별도 모듈로 분리했다 — 여기서는 "세션이 끝날 때까지 계속 도는 백그라운드 부하"가 필요하다.

```python
@dataclass
class TrafficFlowHandle:
    flow_id: str
    src_host: str
    dst_host: str
    server_pid: Optional[str] = None
    ...

def start_traffic_preset(net, preset: dict) -> list[TrafficFlowHandle]
def stop_traffic_preset(net, handles: list[TrafficFlowHandle]) -> None
```

### 패턴별 클라이언트 명령 조립 (`_build_client_cmd`)

| 패턴 | 구현 |
|---|---|
| `constant` | `iperf3 -c {dst} -b {target}M -t {duration}` 단일 호출 |
| `bursty` | on/off 쉘 루프를 백그라운드로 실행 (`while ...; do iperf3 ...; sleep N; done`) |
| `ramp` | `-b` 값을 단계적으로 올리며 재시작하는 쉘 루프 |

`bursty`/`ramp`는 iperf3 단일 호출로 만들 수 없어 호스트에서 실행할 쉘 루프 스크립트를
백그라운드로 던지는 방식을 쓴다.

### 프로세스 정리

Mininet `host.cmd("... &")`로 백그라운드 실행 시 PID를 추적하지 않으면 좀비가 남는다.
`_start_bg()`가 `cmd(f"... & echo $!")`로 PID를 받아 핸들에 저장하고,
`stop_traffic_preset()`이 `_kill()`로 확실히 정리한다.
`duration_sec: null`인 flow는 무제한 실행 후 세션 종료 시 강제 kill로 처리한다.

---

## 5. 지속 세션 관리자 (`stage4_twin/live_session.py`)

기존 `TwinVerifier.verify()`는 "시작→검증→**항상 rollback+net.stop()**"이 `finally`로
묶여 있다. 이 구조를 건드리지 않고 **별도 세션 관리자**를 새로 만들었다 — 이미 잘 동작하고
테스트된 1회성 검증 로직을 수정할 이유가 없기 때문이다.

```python
class LiveNetworkSession:
    """프리셋 적용 → 계속 실행 → 명시적 종료. TwinVerifier와 별개의 생명주기."""

    def is_active(self) -> bool                                    # starting | running
    def start(self, topology_id, topo_data, traffic_preset) -> None
    def stop(self) -> None
    def snapshot(self) -> dict
```

**프로세스당 단일 세션만 지원한다.** `start()`/`stop()`은 블로킹 호출이므로
(Mininet 기동/종료에 수십 초) API 레이어에서 별도 스레드/executor로 실행한다.

### 상태 전이

```
idle → starting → running → stopping → idle
              ↘ error (실패 시 _cleanup_best_effort() 후 예외 재발생)
```

### `start()` 순서

1. ONOS 준비 대기 (`wait_until_ready`) + OpenFlow 앱 활성화 + 기존 flow 정리
2. `mn -c`로 잔여 인터페이스 정리
3. `suppress_htb_quantum_warning()` 컨텍스트에서 토폴로지 기동 (`net.start()`)
4. 디바이스 연결 대기 (`wait_for_devices`, 90초)
5. 트래픽 프리셋이 있으면 `start_traffic_preset()`
6. `NetworkMonitor` 생성 + 폴링 스레드 기동
7. `status = "running"` — **`net.stop()`을 호출하지 않는다**

### `stop()` — 정리 보장

```
_stop_event.set() → 모니터 스레드 join → _cleanup_best_effort() → 상태 초기화
```

`_cleanup_best_effort()`는 각 단계를 개별 `try/except`로 감싸 하나가 실패해도
나머지가 진행되도록 한다: 트래픽 정리 → ONOS flow 정리 → `net.stop()` → `mn -c`.

---

## 6. 모니터링 수집기 (`stage4_twin/network_monitor.py`)

### 6-1. ⚠ 계획 대비 변경: 측정 소스를 `tc qdisc`로 통일

계획에서는 처리량을 `onos_client.port_statistics()` 폴링으로 재려 했으나,
**실측 결과 ONOS 포트 통계 갱신 주기가 폴링 주기(수 초)보다 느려** 값이 몇 초씩
stale하다가 한꺼번에 튀는 현상이 나왔다 (순간 utilization 180%+ 등 물리적으로 불가능한 값).

`tc`는 커널의 실시간 카운터를 직접 읽으므로 이 지연이 없고, drop/backlog도 같은 명령
한 번으로 함께 얻을 수 있다. **세 지표 모두 `tc qdisc` 카운터 하나에서 뽑도록 통일했다.**

```python
_QDISC_SENT_RE    = re.compile(r"Sent (\d+) bytes")
_QDISC_DROPPED_RE = re.compile(r"dropped\s+(\d+)")
_QDISC_BACKLOG_RE = re.compile(r"backlog\s+(\d+)b")
```

| 지표 | 수집 방법 |
|---|---|
| 처리량(Mbps) | `Sent` 바이트 델타 ÷ 폴링 간격 |
| utilization(%) | 처리량 ÷ 링크 `bw`(토폴로지 프리셋 정의값) |
| 드롭 | `dropped` 카운터 델타 |
| 큐 백로그 | `backlog` 바이트 (현재 큐에 쌓인 양) |

**ping은 쓰지 않는다** — end-to-end 경로 전체를 뭉뚱그려 어느 링크가 병목인지 특정하지
못하는 반면, 링크(=인터페이스) 단위 `tc -s qdisc show dev <ifname>`은 정확히 짚을 수 있다.

> **주의**: `backlog`는 엄밀한 end-to-end RTT가 아니다. qdisc는 링크 단위 큐 상태이지
> 왕복시간이 아니므로, "RTT"가 아니라 **"드롭률 + 큐 백로그 기반 지연 근사치"**로 명명한다.

링크→인터페이스 매핑은 `twin_verifier._find_mininet_port()`를 그대로 재사용한다.

### 6-2. 폴링 주기 — 5초 (실측 확정)

계획 단계의 열린 질문이었고, `scripts/manual_traffic_check.py`로 실측해 확정했다.

```python
MONITOR_POLL_INTERVAL_SEC = 5.0
```

모니터 스레드는 `_stop_event.wait(interval)`로 대기하므로 `stop()` 호출 시 즉시 깨어난다.

### 6-3. 데이터 구조

```python
@dataclass
class LinkSample:   # 링크별 — id, source, target, bw_mbps,
                    #          throughput_mbps, util_pct, dropped_delta, backlog_bytes
@dataclass
class FlowSample:   # 트래픽 프리셋 flow별 — flow_id, src, dst, proto,
                    #          target_mbps, actual_mbps
```

`FlowSample.actual_mbps`는 송신 호스트의 인터페이스 바이트 델타로 계산해,
"의도한 부하(target) 대비 실제로 흘린 양(actual)"을 비교할 수 있게 한다.

---

## 7. ⚠ 계획 대비 변경: 파이프라인 통합 방식

계획에서는 **"세션 running 시 Stage 4를 스킵하고 세션의 client로 Stage 6 직접 배포"**로
정했었다. 실제 구현은 **더 나은 방향으로 바뀌었다 — Stage 4를 스킵하지 않고,
세션의 살아있는 네트워크 위에서 그대로 검증한다.**

```python
live_net = live_session.net if live_session.status == "running" else None
live_custom_data = live_session.topo_data if live_net is not None else None

twin_result = verifier.verify(
    flowrule,
    preloaded_flows=req.preloaded_flows,
    external_net=live_net,                    # ← 세션 네트워크 재사용
    external_custom_data=live_custom_data,
)
```

`TwinVerifier.verify()`의 `external_net` 파라미터:

> 지정하면 새 Mininet을 기동/종료하지 않고 이 네트워크에 그대로 검증한다 —
> 배경 트래픽이 흐르는 중이라도 그 실제 상태에서 검증하는 게 목적이므로 flow 정리도
> 생략한다. 검증용으로 배포한 flowrule 자체는 평소처럼 끝나면 rollback한다(네트워크는 안 건드림).

**이 방식이 계획보다 나은 이유**: 별도 임시 환경을 띄우지 않으면서도 검증을 포기하지 않는다.
오히려 "배경 트래픽이 실제로 흐르는 혼잡 상태"에서 검증하므로 이상적 환경보다 현실적이다.

### 상태별 분기

| 세션 status | Stage 4 동작 |
|---|---|
| `running` | 세션 네트워크 위에서 검증 (`external_net` 전달) |
| `starting` / `stopping` | **스킵** — net 객체가 기동/종료 중이라 불안정 |
| `error` | 일반 Digital Twin 진행 (`_cleanup_best_effort()`로 net이 이미 정리됨) |
| `idle` | 일반 Digital Twin 진행 (새 Mininet 기동) |

---

## 8. API 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/traffic-presets` | 사용 가능한 트래픽 프리셋 목록 |
| `POST` | `/api/network-preset/apply` | 세션 시작 — `202 Accepted` 즉시 반환 |
| `GET` | `/api/network-preset/stream` | SSE — 1초 간격 `link_stats` 스트리밍 |
| `POST` | `/api/network-preset/stop` | 세션 종료 |
| `GET` | `/api/network-preset/status` | 현재 스냅샷 |

쓰기 엔드포인트에는 `dependencies=[Depends(_require_api_key)]`가 적용된다.

### `apply` — 비동기 기동

Mininet 기동에 수십 초가 걸리므로 별도 스레드에서 `session.start()`를 실행하고
`202 Accepted`를 즉시 반환한다. 이미 활성 세션이 있으면 `409 Conflict`.

```python
threading.Thread(target=_run, daemon=True).start()
return JSONResponse(status_code=202, content={"ok": True, "status": "starting"})
```

### `stream` — SSE

세션 상태가 종료 상태가 되면 스트림도 자동으로 끝난다.

```python
while True:
    snap = session.snapshot()
    yield _sse({"type": "link_stats", **snap})
    if snap["status"] not in ("starting", "running", "stopping"):
        break
    await asyncio.sleep(1.0)
```

> 스트림 주기(1초)와 모니터 폴링 주기(5초)는 별개다. 스트림은 최신 스냅샷을 더 자주
> 내보내지만 실제 측정 갱신은 5초 간격이다.

---

## 9. 프론트엔드

- 사이드바 "네트워크 프리셋" 섹션: 토폴로지 프리셋 선택(기존 드롭다운 재사용) +
  트래픽 프리셋 선택 + "적용" 버튼 (`applyNetworkPreset()`)
- 토폴로지 뷰 링크 렌더링에 utilization 기반 색상 그라데이션 적용 —
  기존 `onTwinBw` 배지 로직을 "Twin 검증 중에만"이 아니라 "프리셋 스트림 수신 중이면 항상"으로 확장
- 링크 hover 시 드롭률/큐 백로그 툴팁
- 세션이 `running`이면 인텐트 실행 결과가 "새 Twin이 아니라 지금 보고 있는 이 네트워크에
  적용됨"을 배너로 명시

---

## 10. 알려진 리스크

- **백그라운드 프로세스 잔존**: iperf3 루프 정리 실패 시 다음 실행에 인터페이스 잔존 문제가
  생길 수 있다. `_cleanup_best_effort()`가 각 단계를 개별 `try/except`로 감싸고 마지막에
  `mn -c`를 실행해 완화한다.
- **장시간 방치 세션**: 세션이 오래 떠있으면 iperf3가 계속 도는데 서버 재시작 없이는
  회수되지 않는다. **타임아웃 자동 종료(예: 30분)는 미구현** — 향후 고려 사항.
- **단일 세션 제약**: 동시 다중 세션은 지원하지 않는다. 두 번째 `apply` 요청은 409로 거부된다.
