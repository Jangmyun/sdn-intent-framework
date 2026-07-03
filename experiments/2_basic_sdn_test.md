# Day 1: Basic SDN Test — ONOS + Mininet Single Topology

## 목표

- ONOS + Mininet 기본 연결 검증
- single,3 토폴로지에서 pingall 0% dropped 확인
- Mininet 상태 명령(`net`, `links`, `dump`) 출력 기록

---

## 실행 환경

- Controller: ONOS 2.7 (Docker, `--network host`)
- Topology: `single,3` (스위치 1개, 호스트 3개)
- Switch: Open vSwitch (OpenFlow 1.3)
- Controller Port: 6653

---

## 1. ONOS 실행

```bash
./scripts/start_onos.sh
```

ONOS Web UI 확인:

```text
http://localhost:8181/onos/ui
ID: onos / PW: rocks
```

OpenFlow 포트 확인 결과:

```text
# sudo ss -lntp | grep 6653
LISTEN  0  ...  *:6653  ...
```

---

## 2. Mininet 실행

```bash
./scripts/start_mn_single3.sh
```

---

## 3. Mininet CLI 출력

### pingall

```text
# logs/day1_pingall.txt 참조
```

실행 명령:

```
mininet> pingall
```

### net

```
mininet> net
```

출력 예시:

```text
h1 h1-eth0:s1-eth1
h2 h2-eth0:s1-eth2
h3 h3-eth0:s1-eth3
s1 lo:  s1-eth1:h1-eth0 s1-eth2:h2-eth0 s1-eth3:h3-eth0
c0
```

### links

```
mininet> links
```

출력 예시:

```text
h1-eth0<->s1-eth1 (OK OK)
h2-eth0<->s1-eth2 (OK OK)
h3-eth0<->s1-eth3 (OK OK)
```

### dump

```
mininet> dump
```

출력 예시:

```text
<Host h1: h1-eth0:10.0.0.1 pid=...>
<Host h2: h2-eth0:10.0.0.2 pid=...>
<Host h3: h3-eth0:10.0.0.3 pid=...>
<OVSSwitch s1: lo:127.0.0.1,s1-eth1:None,s1-eth2:None,s1-eth3:None pid=...>
<RemoteController c0: 127.0.0.1:6653 pid=...>
```

---

## 4. 결과 요약

| 항목 | 결과 |
|------|------|
| ONOS 기동 | 성공 |
| OpenFlow 앱 활성화 | 성공 |
| Mininet 연결 | 성공 |
| pingall | 0% dropped |

---

## 5. 토폴로지 구조

```text
h1 ──┐
h2 ──┤── s1 (OVS, OF1.3) ── ONOS Controller (6653)
h3 ──┘
```

---

## 산출물

| 파일 | 설명 |
|------|------|
| `scripts/start_onos.sh` | ONOS Docker 실행 스크립트 |
| `scripts/start_mn_single3.sh` | Mininet single,3 실행 스크립트 |
| `logs/day1_pingall.txt` | pingall 출력 로그 |
| `experiments/2_basic_sdn_test.md` | 이 문서 |
