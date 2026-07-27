# 디버그 세션 — 2026-07-23

## 개요

2026-07-22 세션에서 구현한 Digital Twin 부분 차단 OVS 검증 로직의 후속 디버그 세션.  
`_block_rule_check()` 완성 → 서버 재시작 후 테스트 → DPID 버그 발견 및 수정.

---

## 1. `_block_rule_check()` 구현 완료

이전 세션에서 `verify()` 내 block 검증 코드가 `self._block_rule_check()`를 호출하도록 재구조화되었으나, 해당 메서드가 클래스에 존재하지 않아 `AttributeError` 상태였음.

`pipeline/stage4_twin/twin_verifier.py`의 `_ping_check()` 앞에 삽입:

```python
def _block_rule_check(self, net, sw_name, src_ip, dst_ip, flow) -> tuple[bool, str]:
    """OVS flow table에서 NOACTION/DROP 블록 룰 설치 여부 확인 (최대 3회 재시도)"""
    if not sw_name:
        return False, "블록 스위치 이름 미확인 — OVS 검증 불가"
    sw_node = net.get(sw_name)
    for attempt in range(3):
        raw = sw_node.cmd(f"ovs-ofctl dump-flows {sw_name} -O OpenFlow13 2>/dev/null")
        for line in raw.strip().splitlines():
            is_drop = "actions=drop" in line.lower() or re.search(r"actions=\s*$", line.strip())
            if not is_drop: continue
            if src_ip and f"nw_src={src_ip}" not in line: continue
            if dst_ip and f"nw_dst={dst_ip}" not in line: continue
            return True, f"OVS {sw_name} 블록 룰 확인됨 (src={src_ip}, dst={dst_ip})"
        if attempt < 2: time.sleep(1)
    return False, f"OVS {sw_name}에 블록 룰 미발견 (src={src_ip}, dst={dst_ip})"
```

---

## 2. 서버 재시작 전 — 구 코드 동작 확인

서버 재시작 없이 테스트 시 Evidence 메시지가 여전히 ping 포맷(`h1→10.0.0.2 ping 통과됨`)으로 출력됨.  
`intent_check_4` FAIL 유지. → 서버 재시작 필요.

---

## 3. DPID 버그 발견 및 수정

서버 재시작 후 재실행 결과:
- `intent_check_4 (s11)`, `intent_check_6 (s10)`, `intent_check_7 (s12)` → FAIL
- Evidence: `OVS s10에 블록 룰 미발견 (src=10.0.0.1, dst=10.0.0.2)` (OVS 포맷 확인됨)

### 원인 분석

`data/custom_topology.json`에서 s10~s14의 DPID가 **decimal 표기**로 저장되어 있었음.

```
s10: dpid = "0000000000000010"  →  0x10 = 16 (10이 아님)
s11: dpid = "0000000000000011"  →  0x11 = 17
...
```

- `compiler.py`: `"s10"` → `f"of:{10:016x}"` = `of:000000000000000a`
- `topology.py`: `addSwitch("s10", dpid="0000000000000010")` → ONOS에 `of:0000000000000010` (=16)으로 연결
- 두 값 불일치 → ONOS가 존재하지 않는 `of:000000000000000a`에 룰 푸시 → 설치 실패 → OVS 미발견

s1~s9는 정상 (0x01~0x09 = 1~9, decimal과 일치). s10부터 diverge.

### 수정 내용

`data/custom_topology.json`:

| 스위치 | 수정 전 | 수정 후 |
|---|---|---|
| s10 | `0000000000000010` | `000000000000000a` |
| s11 | `0000000000000011` | `000000000000000b` |
| s12 | `0000000000000012` | `000000000000000c` |
| s13 | `0000000000000013` | `000000000000000d` |
| s14 | `0000000000000014` | `000000000000000e` |
| h10 MAC | `00:00:00:00:00:10` | `00:00:00:00:00:0a` |

수정 후 재실행 → 전체 `intent_check_0~7` PASS 확인.

---

## 4. ping vs OVS 검증 정책 정리

| 방식 | 강점 | 약점 |
|---|---|---|
| **OVS 제어플레인** | 우회 경로 무관, 빠름 | 우선순위 충돌 등 데이터플레인 이상 감지 불가 |
| **Ping 데이터플레인** | 실제 동작 확인 | 우회 경로 있으면 오탐 |

현재 구조: **OVS 1차(판정 기준) + Ping 스티어링 2차(보조 기록)**.  
완전 차단이 필요한 경우 `intent_ok = ovs_ok and ping_blocked`로 변경 가능.

---

## 파일 변경 목록

| 파일 | 변경 내용 |
|---|---|
| `pipeline/stage4_twin/twin_verifier.py` | `_block_rule_check()` 메서드 추가 |
| `data/custom_topology.json` | s10~s14 DPID 및 h10 MAC hex 수정 |
| `docs/sessions/2026-07-22-ui-improvements.md` | 섹션 11, 12 추가 |
