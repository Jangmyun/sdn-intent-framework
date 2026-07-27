# SDN Intent Guide

이 파이프라인은 자연어 인텐트를 SDN 플로우 룰로 변환합니다.  
인텐트는 **영어로 작성**하는 것을 권장합니다 — LLM이 영어 네트워크 용어에 더 정확하게 반응하며, 파싱 오류 가능성이 낮아집니다.

---

## 인텐트 유형 (Action Types)

### 1. `block` — 트래픽 차단

특정 흐름을 스위치에서 완전히 드롭(DROP)합니다.

**실제 네트워크 사용 사례**
- 보안 정책: 특정 IP 간 통신 금지
- 공격 대응: 의심 IP에서 오는 트래픽 즉시 차단
- 접근 제어: 특정 포트(SSH, RDP 등) 노출 차단

**필수 필드**
| 필드 | 설명 | 예시 |
|------|------|------|
| `src_ip` | 출발지 IP (반드시 명시) | `10.0.0.1` |
| `dst_ip` | 목적지 IP (반드시 명시) | `10.0.0.4` |
| `device_hint` | 규칙을 설치할 스위치 | `switch 4` |
| `ip_proto` | 프로토콜 (선택) | `tcp`, `udp`, `icmp` |
| `dst_port` | 목적지 포트 (선택) | `22` |

**인텐트 예시**
```
Block all traffic from 10.0.0.1 to 10.0.0.4 on switch 4
Block TCP traffic on port 22 destined for 10.0.0.2 on switch 1
```
```
(한국어) 스위치 4에서 10.0.0.1 → 10.0.0.4 모든 트래픽 차단
(한국어) 스위치 1에서 10.0.0.2로 향하는 TCP 포트 22(SSH) 차단
```

> **주의:** `src_ip`와 `dst_ip` 중 하나라도 생략하면 `ambiguous`로 거부됩니다.  
> "block all traffic on switch 4" 같은 인텐트는 대상이 없어 처리 불가입니다.

---

### 2. `forward` — 트래픽 전달 경로 지정

특정 흐름을 지정한 포트로 내보내도록 플로우 룰을 설치합니다.

**실제 네트워크 사용 사례**
- 정적 라우팅: ONOS 자동 경로 대신 특정 포트로 강제 전달
- 프로토콜 분리: ICMP는 포트 3, HTTP는 포트 2 등 트래픽 종류별 경로 분리
- 장애 우회: 특정 링크가 다운됐을 때 수동으로 대체 포트 지정

**필수 필드**
| 필드 | 설명 | 예시 |
|------|------|------|
| `src_ip` | 출발지 IP (반드시 명시) | `10.0.0.1` |
| `dst_ip` | 목적지 IP (반드시 명시) | `10.0.0.3` |
| `device_hint` | 규칙을 설치할 스위치 | `switch 1` |
| `out_port` | 출력 포트 번호 | `3` |
| `ip_proto` | 프로토콜 (선택) | `icmp`, `tcp` |
| `dst_port` | 목적지 포트 (선택) | `80` |

**인텐트 예시**
```
Forward ICMP traffic destined for 10.0.0.1 through port 3 on switch 1
Forward TCP traffic on port 80 destined for 10.0.0.3 via port 2 on switch 1
```
```
(한국어) 스위치 1에서 10.0.0.1로 향하는 ICMP 트래픽을 포트 3으로 전달
(한국어) 스위치 1에서 10.0.0.3:80(HTTP)으로 향하는 TCP를 포트 2로 전달
```

---

### 3. `qos` — 서비스 품질 (Quality of Service)

트래픽에 우선순위 또는 큐(Queue)를 할당합니다. 대역폭 보장, 지연 최소화 등에 사용합니다.

**실제 네트워크 사용 사례**
- 영상 회의/스트리밍: 높은 우선순위 큐에 배치하여 지연 최소화
- VoIP: 패킷 손실에 민감한 음성 트래픽 우선 처리
- 데이터센터: 백엔드 스토리지 트래픽보다 사용자 요청 트래픽 우선

**필수/선택 필드**
| 필드 | 설명 | 예시 |
|------|------|------|
| `device_hint` | 규칙을 설치할 스위치 | `switch 1` |
| `queue_id` | 할당할 큐 번호 (선택) | `1` |
| `priority` | 플로우 룰 우선순위 (선택) | `50000` |
| `src_ip` | 출발지 IP (권장) | `10.0.0.1` |
| `dst_ip` | 목적지 IP (권장) | `10.0.0.4` |

**인텐트 예시**
```
Apply QoS for video streaming from 10.0.0.1 to 10.0.0.4 on switch 1
Prioritize VoIP traffic from 10.0.0.2 to 10.0.0.3 on switch 1
```
```
(한국어) 스위치 1에서 10.0.0.1 → 10.0.0.4 영상 스트리밍 트래픽에 QoS 적용
(한국어) 스위치 1에서 10.0.0.2 → 10.0.0.3 VoIP 트래픽 우선 처리
```

> `src_ip`/`dst_ip`는 `block`/`forward`와 달리 없어도 거부되지 않지만, 명시하면 더 정확한 규칙이 생성됩니다.

---

### 4. `sfc` — 서비스 함수 체이닝 (Service Function Chaining)

트래픽이 목적지로 가기 전에 반드시 **중간 장치(방화벽, IDS, NAT 등)를 경유**하도록 강제합니다.

```
[출발지] → [스위치] →(port 9)→ [IDS/방화벽] →(port 2)→ [목적지]
              ↑ out_port=9            ↑ alt_out_port=2
```

**실제 네트워크 사용 사례**
- 보안 검사: 외부에서 오는 트래픽을 IDS/IPS를 통과시킨 후 내부로 허용
- 방화벽 삽입: 두 세그먼트 사이에 방화벽을 논리적으로 삽입
- NAT 체이닝: 트래픽이 NAT 장치를 거친 후 서버에 도달

**필수 필드**
| 필드 | 설명 | 예시 |
|------|------|------|
| `src_ip` | 출발지 IP | `10.0.0.1` |
| `dst_ip` | 목적지 IP | `10.0.0.4` |
| `device_hint` | 체이닝 규칙을 설치할 스위치 | `switch 2` |
| `out_port` | 중간 장치로 보내는 포트 (웨이포인트 포트) | `9` |
| `alt_out_port` | 중간 장치에서 돌아온 후 목적지로 보내는 포트 | `2` |

**인텐트 예시**
```
Steer HTTP traffic from 10.0.0.1 to 10.0.0.4 through IDS at port 9, then forward out port 2 on switch 2
Route all traffic from 10.0.0.2 to 10.0.0.3 via firewall at port 9, then egress port 3 on switch 1
```
```
(한국어) 스위치 2에서 10.0.0.1→10.0.0.4 HTTP 트래픽을 포트 9의 IDS로 보낸 뒤 포트 2로 전달
(한국어) 스위치 1에서 10.0.0.2→10.0.0.3 트래픽을 포트 9의 방화벽 경유 후 포트 3으로 전달
```

> `out_port`(웨이포인트 포트)와 `alt_out_port`(복귀 후 출력 포트) **둘 다 반드시 명시**해야 합니다.

---

### 5. `reroute` — 경로 재지정 (Reroute / Failover)

특정 스위치를 **경유하도록** 또는 **우회하도록** 경로를 변경합니다.

**실제 네트워크 사용 사례**
- 장애 대응(Failover): 링크/스위치 장애 시 트래픽을 대체 경로로 전환
- 유지보수 우회: 점검 중인 스위치를 트래픽이 피해가도록 설정
- 부하 분산: 혼잡한 경로 대신 여유 있는 경로로 트래픽 유도

**필수/선택 필드**
| 필드 | 설명 | 예시 |
|------|------|------|
| `src_ip` | 출발지 IP | `10.0.0.2` |
| `dst_ip` | 목적지 IP | `10.0.0.3` |
| `device_hint` | 규칙을 설치할 스위치 | `switch 1` |
| `via_device` | 경유할 스위치 (선택) | `switch 3` |
| `avoid_device` | 피해야 할 스위치 (선택) | `switch 2` |
| `out_port` | 대체 출력 포트 (선택) | `4` |

**인텐트 예시**
```
Reroute traffic from 10.0.0.2 to 10.0.0.3 via switch 3 avoiding switch 2 on switch 1
Redirect traffic from 10.0.0.1 to 10.0.0.4 to bypass switch 2, use port 4 on switch 1
```
```
(한국어) 스위치 1에서 10.0.0.2→10.0.0.3 트래픽을 스위치 2를 피해 스위치 3 경유로 재지정
(한국어) 스위치 1에서 10.0.0.1→10.0.0.4 트래픽을 스위치 2 대신 포트 4로 우회
```

---

## 왜 영어로 작성해야 하나요?

| | 영어 | 한국어 |
|---|---|---|
| LLM 파싱 정확도 | 높음 (네트워크 용어가 영어 기반) | 낮음 (번역 오차 가능) |
| 필드 추출 신뢰도 | 높음 | 중간 |
| 거부율 | 낮음 | 높음 |

`out_port`, `alt_out_port`, `via_device` 같은 SDN 개념은 영어로 표현했을 때 LLM이 훨씬 정확하게 인식합니다.

---

## 거부(Rejection) 사유

인텐트가 다음 조건에 해당하면 파이프라인이 실행을 거부합니다.

| 사유 | 설명 | 예시 |
|------|------|------|
| `ambiguous` | 너무 모호하여 구체적인 네트워크 액션으로 매핑 불가 | "make network better", "block all traffic on switch 4" (src/dst 없음) |
| `contradictory` | 모순된 요구사항 | "allow and block 10.0.0.1 to 10.0.0.2" |
| `unsupported` | 지원 범위 외 기능 | "reboot switch 1", "configure MPLS" |
| `unknown_entity` | 토폴로지에 없는 호스트/IP/스위치 참조 | "block traffic to 10.0.0.99" (존재하지 않는 IP) |
