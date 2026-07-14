# Scripts Guide

초기 설치가 끝난 뒤 SDN 실험 환경을 실행하고 관리하는 순서입니다. 최초 설치 방법은 [Installation Guide](installation/README.md)를 참고하세요.

## 권장 실행 순서

모든 명령은 프로젝트 루트에서 실행합니다.

### 1. 환경 상태 확인

```bash
./scripts/installation/doctor.sh
```

Python, uv, Mininet, OVS, Docker와 ONOS 이미지 상태를 확인하고 `logs/setup/`에 환경 보고서를 저장합니다. 보고서가 필요 없다면 `--no-write` 옵션을 사용합니다.

```bash
./scripts/installation/doctor.sh --no-write
```

### 2. ONOS 시작

```bash
./scripts/onos.sh start
```

`safe-intent-onos` 컨테이너를 시작하고 REST API가 준비될 때까지 기다린 뒤 OpenFlow 앱을 활성화합니다.

상태를 확인하려면 다음 명령을 사용합니다.

```bash
./scripts/onos.sh status
```

### 3. 연결 Smoke Test

```bash
./scripts/smoke_test.sh
```

단일 OVS switch와 host 3개를 만들고 다음 항목을 자동으로 검사합니다.

- Mininet과 OVS 실행
- OVS와 ONOS의 OpenFlow 1.3 연결
- host 간 `pingall` 통신
- ONOS의 switch 장치 인식

`PASS: connectivity and ONOS device discovery succeeded.`가 출력되면 기본 실험 환경이 정상입니다. 테스트용 reactive forwarding 앱과 Mininet 환경은 성공 또는 실패 시 자동 정리됩니다. ONOS 컨테이너는 계속 실행됩니다.

### 4. 수동 Mininet 실험

```bash
./scripts/start_mn_single3.sh
```

ONOS에 연결되는 단일 switch 및 host 3개 토폴로지를 대화형 Mininet CLI로 실행합니다.

예시:

```text
mininet> nodes
mininet> net
mininet> pingall
mininet> exit
```

이 스크립트는 종료 시 Mininet namespace와 OVS 잔여 설정을 자동으로 정리합니다.

### 5. 실험 종료

```bash
./scripts/onos.sh stop
```

ONOS 컨테이너를 중지합니다. 컨테이너는 삭제하지 않으며 다음 `start` 실행 시 자동으로 다시 생성됩니다.

Mininet이 비정상 종료되어 잔여 상태가 있을 경우 다음 명령으로 정리합니다.

```bash
sudo mn -c
```

## 전체 실행 예시

```bash
./scripts/installation/doctor.sh
./scripts/onos.sh start
./scripts/smoke_test.sh
./scripts/start_mn_single3.sh
./scripts/onos.sh stop
```

매번 수동 Mininet 실험이 필요한 것은 아닙니다. 자동 연결 검증만 수행할 때는 `start_mn_single3.sh`를 생략합니다.

## 스크립트 역할

| Script | Role |
| --- | --- |
| `installation/setup.sh` | 최초 시스템 패키지, uv, Python 및 ONOS 이미지 설치 |
| `installation/doctor.sh` | 설치 상태, 서비스, 버전 및 포트 진단 |
| `onos.sh` | ONOS 시작, 중지, 재시작, 상태 및 로그 관리 |
| `start_onos.sh` | 기존 호환용 ONOS 시작 진입점 |
| `smoke_test.sh` | Mininet 통신과 ONOS 장치 인식 자동 검증 |
| `start_mn_single3.sh` | 단일 switch 및 host 3개 대화형 Mininet 실행 |

## ONOS 관리 명령

```bash
./scripts/onos.sh start
./scripts/onos.sh status
./scripts/onos.sh logs
./scripts/onos.sh restart
./scripts/onos.sh stop
```

ONOS는 TCP 6653(OpenFlow), 8101(SSH/Karaf), 8181(REST) 포트를 사용합니다.
