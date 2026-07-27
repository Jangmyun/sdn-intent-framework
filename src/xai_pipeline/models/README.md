# models/

파이프라인 전반에서 공유되는 데이터 모델을 정의한다.

| 파일 | 역할 |
|---|---|
| `intent_ir.py` | 자연어 인텐트 → 구조화된 중간 표현 (IntentIR) |
| `topology.py` | 네트워크 토폴로지 정의 및 엔티티 검증 |

---

## intent_ir.py

Stage 1(LLM 파싱) → Stage 2(FlowRule 컴파일) 사이의 교환 형식을 정의한다.  
LLM이 자연어를 읽어 만든 구조화된 인텐트를 담는 그릇이다.

### 전체 클래스 구조

```
IntentPrediction                   ← 파싱 결과 최종 래퍼
  ├── status: "accepted" | "rejected"
  ├── program: IntentIR            ← 단일 룰
  ├── compound: CompoundIntentIR   ← 복합 룰
  ├── rejection_reason
  └── rejection_detail

CompoundIntentIR
  └── rules: list[IntentIR]        ← 복합 인텐트의 각 서브 룰

IntentIR                           ← 핵심 IR
  ├── action                       ← 필수 (forward/block/qos/sfc/reroute)
  ├── intent_type                  ← 의미 레이블 (forwarding/security/qos/sfc/reroute)
  ├── selector: IntentSelector     ← 어떤 트래픽을
  ├── enforcement: IntentEnforcement  ← 어디서, 어느 포트로
  ├── qos: IntentQoS               ← 품질 요구사항
  ├── routing: IntentRouting       ← 어떤 경로로
  └── priority                     ← OpenFlow 우선순위
```

---

### 서브 모델

#### `EndpointRef` — 엔드포인트 참조

출발지 또는 목적지 하나를 표현한다.

```python
EndpointRef(host="h1", ip="10.0.0.1/32")
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `host` | `str \| None` | 호스트명 (XAI 설명용) |
| `ip` | `str \| None` | IPv4 주소 (OpenFlow 매칭용). `/32` 마스크 자동 추가 |

`ip` 필드에는 `_normalize_ip` validator가 있어 마스크 없는 IP에 `/32`를 자동으로 붙이고, 유효하지 않은 형식은 `None`으로 처리한다.

---

#### `IntentSelector` — 트래픽 매칭 조건

OpenFlow의 **match** 필드에 해당한다. "어떤 패킷을 대상으로 하는가"를 정의한다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `source` | `EndpointRef \| None` | 출발지 엔드포인트 |
| `destination` | `EndpointRef \| None` | 목적지 엔드포인트 |
| `eth_type` | `"ipv4" \| "ipv6" \| "arp" \| None` | 이더넷 타입 |
| `protocol` | `"tcp" \| "udp" \| "icmp" \| None` | L4 프로토콜 |
| `src_port` | `int \| None` | 출발지 포트 |
| `dst_port` | `int \| None` | 목적지 포트 |
| `in_port` | `int \| None` | 스위치 입력 포트 매칭 |

```python
# "TCP port 80 from 10.0.0.1 to 10.0.0.3"
IntentSelector(
    source=EndpointRef(ip="10.0.0.1/32"),
    destination=EndpointRef(ip="10.0.0.3/32"),
    protocol="tcp",
    dst_port=80,
)
```

---

#### `IntentEnforcement` — 집행 위치 및 출력 포트

"어느 스위치의 어느 포트에서 실행할지"를 정의한다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `device` | `str \| None` | 스위치 힌트 (자연어 또는 ONOS ID). 컴파일러가 ONOS ID로 변환 |
| `egress_port` | `int \| None` | 출력 포트. forward/qos: 목적지 포트, sfc: waypoint 포트 |
| `alt_egress_port` | `int \| None` | SFC waypoint 복귀 후 최종 출력 포트 / reroute 대체 포트 |
| `set_vlan_id` | `int \| None` | VLAN 태깅 |

```python
IntentEnforcement(device="switch 1", egress_port=2)
# → 컴파일러가 "of:0000000000000001"로 변환
```

---

#### `IntentQoS` — QoS 파라미터

`action=qos`일 때만 사용한다. 세 필드 모두 `None`이면 `qos` 객체 자체를 생성하지 않는다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `queue` | `int \| None` | OpenFlow Queue ID |
| `min_bandwidth_mbps` | `float \| None` | 최소 보장 대역폭 (Mbps) |
| `max_latency_ms` | `float \| None` | 최대 허용 지연 (ms) |

---

#### `IntentRouting` — 경로 지정

`action=sfc` 또는 `action=reroute`일 때만 사용한다.

| 필드 | 타입 | 용도 |
|---|---|---|
| `waypoints` | `list[str] \| None` | SFC 경유 지점 목록 (예: `["s2:9", "s3"]`) |
| `via_device` | `str \| None` | reroute: 이 스위치를 반드시 경유 |
| `avoid_device` | `str \| None` | reroute: 이 스위치를 회피 |

```python
# SFC: 포트 9의 IDS를 경유
IntentRouting(waypoints=["s2:9"])

# Reroute: s2를 피해 s3로
IntentRouting(via_device="s3", avoid_device="s2")
```

---

### `IntentIR` — 핵심 IR

#### `action` vs `intent_type`

두 필드는 같은 정책을 다른 관점으로 표현한다.

| `action` | `intent_type` | 용도 |
|---|---|---|
| `"forward"` | `"forwarding"` | 컴파일러 분기 / XAI 레이블 |
| `"block"` | `"security"` | |
| `"qos"` | `"qos"` | |
| `"sfc"` | `"sfc"` | |
| `"reroute"` | `"reroute"` | |

- **`action`**: 컴파일러(`compiler.py`)가 어떤 FlowRule을 만들지 결정하는 코드
- **`intent_type`**: XAI 설명에서 사람이 읽기 좋은 의미 레이블
- `intent_type`이 없으면 `resolved_intent_type` 프로퍼티가 `action`에서 자동 파생

#### 하위 호환 프로퍼티

리팩토링 이전 flat 방식 접근(`ir.src_ip`, `ir.device_hint` 등)을 유지한다.  
`compiler.py`, `api.py`는 수정 없이 그대로 동작한다.

| 프로퍼티 | 실제 접근 경로 |
|---|---|
| `ir.src_ip` | `ir.selector.source.ip` |
| `ir.dst_ip` | `ir.selector.destination.ip` |
| `ir.device_hint` | `ir.enforcement.device` |
| `ir.ip_proto` | `ir.selector.protocol` |
| `ir.dst_port` | `ir.selector.dst_port` |
| `ir.in_port` | `ir.selector.in_port` |
| `ir.out_port` | `ir.enforcement.egress_port` |
| `ir.alt_out_port` | `ir.enforcement.alt_egress_port` |
| `ir.vlan_id` | `ir.enforcement.set_vlan_id` |
| `ir.queue_id` | `ir.qos.queue` |
| `ir.waypoints` | `ir.routing.waypoints` |
| `ir.via_device` | `ir.routing.via_device` |
| `ir.avoid_device` | `ir.routing.avoid_device` |

#### `from_llm_output(raw)` — LLM 출력 파싱

LLM이 반환한 JSON dict를 `IntentIR`로 변환하는 팩토리 메서드다.

```
LLM JSON dict
  ↓
① action 정규화  (deny→block, prioritize→qos 등 의미 기반 매핑)
② selector 파싱  (source/destination IP 정규화, protocol 검증)
③ enforcement 파싱  (device null → "switch 1" 기본값)
④ qos 파싱  (action=qos 이거나 qos 필드 있을 때만 생성)
⑤ routing 파싱  (waypoints/via_device/avoid_device 있을 때만 생성)
  ↓
IntentIR
```

**구형 플랫 형식 폴백**: `selector` 없이 `src_ip`, `dst_ip`, `device_hint` 등 flat 키를 직접 쓴 구형 포맷도 인식한다.

#### `to_dict()` — 직렬화

UI 표시와 로그 저장에 사용한다. `None` 필드는 생략하고 중첩 형식으로 출력한다.

```json
{
  "action": "forward",
  "intent_type": "forwarding",
  "selector": {
    "source": {"ip": "10.0.0.1/32"},
    "destination": {"ip": "10.0.0.3/32"},
    "protocol": "tcp",
    "dst_port": 80
  },
  "enforcement": {
    "device": "switch 1",
    "egress_port": 2
  }
}
```

---

### `IntentPrediction` — 파이프라인 진입점

`intent_parser.py`가 반환하고 `api.py`가 받아 다음 스테이지로 전달하는 최종 래퍼다.

```python
# 정상 — 단일 룰
IntentPrediction(status="accepted", program=IntentIR(...))

# 정상 — 복합 룰
IntentPrediction(status="accepted", compound=CompoundIntentIR(rules=[...]))

# 거부
IntentPrediction(
    status="rejected",
    rejection_reason="unknown_entity",
    rejection_detail="device 'switch 99' is not in the topology",
)
```

**거부 사유 4종**

| `rejection_reason` | 의미 | 예시 |
|---|---|---|
| `ambiguous` | 너무 모호해 매핑 불가 | "make network better" |
| `unknown_entity` | 토폴로지에 없는 호스트/스위치 | "switch 99", "10.0.0.99" |
| `contradictory` | 동일 플로우에 모순된 요구 | 같은 포트에 allow + block |
| `unsupported` | 미지원 기능 | MPLS, multicast routing |

---

### 액션별 필드 사용 패턴

| action | selector | enforcement | qos | routing |
|---|---|---|---|---|
| `forward` | source + destination + protocol/port | device + egress_port | — | — |
| `block` | source + destination + (protocol/port) | device | — | — |
| `qos` | source + destination | device + egress_port | queue / bandwidth / latency | — |
| `sfc` | source + destination | device + egress_port(waypoint) + alt_egress_port | — | waypoints |
| `reroute` | source + destination | device + egress_port | — | via_device / avoid_device |
