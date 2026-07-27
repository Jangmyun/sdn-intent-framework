# Installation Guide

## 지원 환경

자동화 대상은 Ubuntu 24.04 LTS x86_64 단일 서버입니다. Mininet과 Open vSwitch는 호스트에서, ONOS는 host network를 사용하는 Docker 컨테이너에서 실행합니다.

### 사전 조건

- Ubuntu 24.04 LTS x86_64
- 인터넷 연결
- `sudo` 사용 권한
- Git과 `curl`

## 설치

저장소를 받은 뒤 프로젝트 루트에서 설치 스크립트를 실행합니다.

```bash
git clone <repository-url>
cd sdn-intent-framework
chmod +x scripts/installation/*.sh scripts/*.sh
./scripts/installation/setup.sh
```

`setup.sh`는 다음 작업을 순서대로 수행합니다.

1. Ubuntu 24.04 및 x86_64 환경 여부를 확인합니다.
2. `apt`로 Mininet 2.3.x와 Open vSwitch 3.3.x를 설치하고 OVS 서비스를 활성화합니다.
3. Docker가 없다면 Ubuntu의 `docker.io` 패키지를 설치하고 서비스를 활성화합니다.
4. 사용자 영역에 `uv` 0.11.28을 설치합니다.
5. `.python-version`과 `uv.lock`을 기준으로 Python 3.11 가상환경을 동기화합니다.
6. `onosproject/onos:2.7.0` Docker 이미지를 내려받습니다.
7. 설치된 도구와 서비스 버전을 검사하고 `logs/setup/`에 보고서를 저장합니다.

Docker 그룹에 새로 추가된 경우 비-`sudo` Docker 명령은 다시 로그인한 후 적용됩니다. 설치 중에는 필요한 경우 스크립트가 `sudo docker`를 사용합니다.

## 설치 검증

```bash
./scripts/installation/doctor.sh
./scripts/onos.sh start
./scripts/smoke_test.sh
./scripts/onos.sh stop
```

`smoke_test.sh`가 `PASS: connectivity and ONOS device discovery succeeded.`를 출력하면 Mininet host 통신, OpenFlow 1.3 연결 및 ONOS 장치 인식이 정상입니다.

보고서 파일을 생성하지 않고 환경만 검사하려면 다음 명령을 사용합니다.

```bash
./scripts/installation/doctor.sh --no-write
```

## 환경 관리

```bash
# ONOS 수명주기 관리
./scripts/onos.sh start
./scripts/onos.sh status
./scripts/onos.sh logs
./scripts/onos.sh restart
./scripts/onos.sh stop

# 대화형 single-switch/three-host Mininet 실행
./scripts/start_mn_single3.sh

# pingall과 ONOS device discovery 자동 검증
./scripts/smoke_test.sh
```

ONOS 컨테이너 이름은 `safe-intent-onos`이며 다음 포트를 사용합니다.

| Port | Purpose |
| ---: | --- |
| 6653 | OpenFlow controller |
| 8101 | ONOS SSH/Karaf console |
| 8181 | ONOS REST API |

로컬 실험용 ONOS 기본 계정은 `onos` / `rocks`입니다. `ONOS_USER`, `ONOS_PASSWORD` 환경변수로 재정의할 수 있습니다.

Reactive forwarding 앱(`org.onosproject.fwd`)은 정책 실험을 방해하지 않도록 평상시에는 활성화하지 않습니다. `smoke_test.sh`가 테스트 중에만 활성화하고 성공 또는 실패 시 자동으로 비활성화합니다. OpenFlow 앱은 ONOS 시작 시 활성화됩니다.

## 문제 해결 및 정리

```bash
./scripts/installation/doctor.sh --no-write
./scripts/onos.sh status
./scripts/onos.sh logs
sudo ss -lntp | grep -E ':(6653|8101|8181)\b'

# 비정상 종료된 Mininet namespace와 OVS 상태 정리
sudo mn -c

# ONOS 컨테이너 완전 제거
./scripts/onos.sh stop
docker rm safe-intent-onos
```

이번 setup은 최초 환경 검증을 위한 단일 ONOS/Mininet 구성만 지원합니다. production emulator와 validation twin 동시 실행 및 Ryu fallback은 후속 구현 범위입니다.
