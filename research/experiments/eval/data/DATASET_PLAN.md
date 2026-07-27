# 평가 데이터셋 구성 계획

> 위치: `experiments/eval/data/`  
> 스키마: 파이프라인 IntentIR 직접 사용 (정규화 레이어 없음)  
> 최종 수정: 2026-07-21

---

## 1. 설계 원칙

### 1-1. 파이프라인 스키마 직접 사용

기존 `data/intents_v2.jsonl`(E1 스키마)은 `action: forward/deny/allow/prioritize`를 사용해 파이프라인 출력(`action: forward/block/qos/sfc/reroute`)과 달랐다. 이 데이터셋은 **정규화 레이어를 두지 않고** 파이프라인 IntentIR 스키마를 gold로 직접 사용한다.

### 1-2. 카테고리 균형 (9:1 비율)

| 카테고리 | accepted | rejected | 합계 |
|---|---|---|---|
| forwarding | 9 | 1 | 10 |
| security | 9 | 1 | 10 |
| qos | 9 | 1 | 10 |
| sfc | 9 | 1 | 10 |
| reroute | 9 | 1 | 10 |
| compound | 9 | 1 | 10 |
| **합계** | **54** | **6** | **60** |

**9:1 비율 선택 이유:** 실제 운영 환경에서 거부되는 인텐트 비율이 낮다는 현실을 반영. 거부 케이스를 과도하게 포함하면 rejection_recall이 과장되어 평가가 왜곡됨.

### 1-3. 카테고리당 거부 이유 1개

각 카테고리에서 가장 대표적인 거부 이유 1개만 포함. Small과 Large에서 서로 다른 유형을 커버해 상보적 평가.

---

## 2. 토폴로지

### Small (`topology_eval.json`)

```
호스트 (4개):  h1=10.0.0.1, h2=10.0.0.2, h3=10.0.0.3, h4=10.0.0.4
스위치 (4개):  s1 (포트 1,2,3,4,9), s2,s3,s4 (포트 1,2,3,4)
IDS 웨이포인트: s1:9
Phantom (거부용): h5,h6,h7 / s9
```

### Large (`topology_large.json`)

```
호스트 (16개): h1–h16 (10.0.0.1–10.0.0.16)
스위치 (8개):  s1,s3 (포트 1–9), s2,s4–s8 (포트 1–8)
IDS 웨이포인트: s1:9, s3:9 (2개)
Phantom (거부용): h17,h18,h19,h20 / s9,s10
```

---

## 3. 파일 목록

| 파일 | 토폴로지 | 케이스 | 비율 | 상태 |
|---|---|---|---|---|
| `intents_eval.jsonl` | Small | 60 | 54:6 (9:1) | ✅ 완료 |
| `intents_eval_large.jsonl` | Large | 60 | 54:6 (9:1) | ✅ 완료 |

---

## 4. 케이스 ID 명명 규칙

```
<접두사>-<번호>     # 수락 케이스
<접두사>-R<번호>    # 거부 케이스

접두사:
  FWD = forwarding
  SEC = security
  QOS = qos
  SFC = sfc
  RRT = reroute
  CMP = compound

Large 데이터셋: "L-" 접두사 추가 (L-FWD-01, L-SEC-R01 등)
```

---

## 5. Gold 스키마

### 수락 케이스 (단일 룰)

```json
{
  "case_id": "FWD-01",
  "category": "forwarding",
  "intent_text": "...",
  "gold": {
    "status": "accepted",
    "action": "forward|block|qos|sfc|reroute",
    "intent_type": "forwarding|security|qos|sfc|reroute",
    "selector": {
      "source": {"host": "h1", "ip": "10.0.0.1"},
      "destination": {"host": "h2", "ip": "10.0.0.2"},
      "protocol": "tcp|udp|icmp|null",
      "dst_port": 80
    },
    "enforcement": {
      "device": "switch 1",
      "egress_port": 2,
      "alt_egress_port": null
    },
    "qos": null,
    "routing": null
  }
}
```

### 수락 케이스 (복합 룰 — compound 카테고리)

```json
{
  "case_id": "CMP-01",
  "category": "compound",
  "intent_text": "...",
  "gold": {
    "status": "accepted",
    "rules": [
      {
        "action": "forward",
        "intent_type": "forwarding",
        "selector": {...},
        "enforcement": {...}
      },
      {
        "action": "block",
        "intent_type": "security",
        "selector": {...},
        "enforcement": {...}
      }
    ]
  }
}
```

### 거부 케이스

```json
{
  "case_id": "FWD-R01",
  "category": "forwarding",
  "rejection_type": "ambiguous",
  "intent_text": "...",
  "gold": {
    "status": "rejected",
    "rejection_reason": "ambiguous|unknown_entity|contradictory|unsupported"
  }
}
```

---

## 6. 거부 이유 정의

| 거부 이유 | 정의 | 예시 |
|---|---|---|
| `ambiguous` | 필수 필드 누락 (block/forward는 src+dst IP 모두 필요) | "Block traffic from 10.0.0.1" (dst 없음) |
| `unknown_entity` | 토폴로지에 없는 엔티티 참조 | "Forward HTTP from h5 to h2" (h5 없음) |
| `contradictory` | 내부 자기모순 (동일 흐름에 forward+block 동시 등) | "via switch 2 and avoid switch 2" |
| `unsupported` | 파이프라인이 지원하지 않는 기능 | MPLS, BGP, ML-based QoS, 10-stage SFC |

---

## 7. Small vs Large 거부 이유 분포

| 카테고리 | Small | Large |
|---|---|---|
| forwarding | ambiguous | unknown_entity |
| security | unknown_entity | ambiguous |
| qos | unsupported | contradictory |
| sfc | ambiguous | unsupported |
| reroute | contradictory | ambiguous |
| compound | unknown_entity | contradictory |

두 데이터셋을 합치면 4종 거부 이유가 모두 최소 2회 등장.

---

## 8. 채점 방식 (score_exp1.py 설계 기반)

### 수락 케이스

| 지표 | 설명 |
|---|---|
| `schema_validity` | LLM 출력 파싱 성공 여부 |
| `status_match` | gold accepted ↔ 예측 accepted |
| `action_match` | gold action = 예측 action |
| `slot_accuracy[*]` | 슬롯별 정확도 (gold null 슬롯 제외) |
| `hallucinated_entity_rate` | 토폴로지 alias에 없는 엔티티 비율 |
| `normalized_exact_match` | 모든 슬롯 동시 일치 |

**복합 인텐트 매칭:** predicted rules 배열과 gold rules 배열 간 order-agnostic best-match 적용 (Hungarian algorithm 또는 최적 순열 탐색).

### 거부 케이스

| 지표 | 설명 |
|---|---|
| `rejection_recall` | 거부 케이스 중 올바르게 rejected 예측 비율 |
| `rejection_reason_match` | rejection_reason까지 일치 |
| `false_acceptance_rate` | 거부해야 할 케이스를 accepted로 잘못 예측한 비율 |

---

## 9. 카테고리별 설계 가이드라인

### forwarding
- 프로토콜 다양화: null / icmp / tcp / udp / HTTP(80) / HTTPS(443) / DNS(53)
- egress_port 명시 케이스와 미명시 케이스 혼합
- 호스트 쌍 다양화 (같은 쌍 반복 최소화)

### security
- block 전용 (deny 표현도 허용 — LLM이 "deny"를 "block"으로 파싱해야 함)
- src+dst IP 모두 명시 (필수 조건)
- 포트별 차단(22,80,443,53,5060) + 프로토콜별 차단(icmp) + 전체 차단 혼합

### qos
- queue ID / bandwidth(Mbps) / latency 조합 다양화
- 한 케이스에 하나의 qos 파라미터 집중 (명확성)

### sfc
- Small: 웨이포인트 `s1:9` 고정
- Large: `s1:9`와 `s3:9` 혼합 사용
- `egress_port`(waypoint 진입) + `alt_egress_port`(복귀 후 출구) 항상 명시

### reroute
- `via_device` 케이스와 `avoid_device` 케이스 균등 비율
- 프로토콜 있는 케이스와 없는 케이스 혼합

### compound
- 2개 룰 조합: forward+block, block+forward, forward+qos, block+qos
- 각 룰이 서로 다른 프로토콜/포트 대상 → 실제로 수락 가능한 조합
- gold `rules` 배열 순서가 채점에 영향 없도록 order-agnostic 매칭 적용

---

## 10. 작성 주의사항

1. **IP 주소**: `host`는 `"h1"~"h16"`, `ip`는 `"10.0.0.x"` (CIDR 없이)
2. **device 표기**: gold는 `"switch 1"~"switch 8"` 형태 (alias 해석의 기준점)
3. **null 처리**: 사용하지 않는 선택적 필드는 `null` 명시 또는 생략 (채점 시 동등)
4. **의도 텍스트**: 같은 의미를 다양한 표현으로 작성 (forward/route/allow/send, deny/block/drop)
5. **phantom 엔티티**: 거부 케이스에서만 사용. 수락 케이스에는 반드시 topology 내 엔티티만 사용
6. **Large 케이스 다양성**: 호스트 쌍을 h1~h16 전역에 걸쳐 분산 (같은 쌍 반복 최소화)
