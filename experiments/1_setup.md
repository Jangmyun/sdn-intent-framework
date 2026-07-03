# SDN Lab Setup Log

## 1. Host Environment

- Host OS: Arch Linux
- VM software: KVM + libvirt + virt-manager
- Guest OS: Ubuntu 24.04
- Goal: Mininet + Open vSwitch + ONOS 기반 SDN 실험 환경 구축

---

## 2. Arch Host: KVM / virt-manager 설치

### CPU 가상화 확인

```bash
LC_ALL=C lscpu | grep Virtualization
```

정상 예시:

```text
Virtualization: VT-x
```

KVM 모듈 확인:

```bash
lsmod | grep kvm
```

정상 예시:

```text
kvm_intel
kvm
```

### 패키지 설치

```bash
sudo pacman -Syu

sudo pacman -S \
    qemu-full \
    virt-manager \
    virt-viewer \
    libvirt \
    dnsmasq \
    vde2 \
    openbsd-netcat \
    edk2-ovmf
```

### libvirt 서비스 실행

```bash
sudo systemctl enable --now libvirtd
```

### 사용자 권한 추가

```bash
sudo usermod -aG libvirt $USER
newgrp libvirt
```

확인:

```bash
groups
```

`libvirt`가 포함되어 있으면 정상.

### 기본 NAT 네트워크 활성화

```bash
sudo virsh net-start default
sudo virsh net-autostart default
sudo virsh net-list
```

정상 예시:

```text
Name      State    Autostart
--------------------------------
default   active   yes
```

### virt-manager 실행

```bash
virt-manager
```

---

## 3. Ubuntu VM 생성

virt-manager에서 새 VM 생성.

권장 설정:

```text
OS: Ubuntu 24.04
CPU: 4 vCPU
Memory: 8192 MB
Disk: 50 GB
Network: Virtual network 'default' NAT
```

설치 중 OpenSSH Server는 선택 가능.

---

## 4. Ubuntu GUI 및 클립보드 공유

Ubuntu Server만 사용하면 복사/붙여넣기가 불편하므로 Xubuntu Desktop 설치.

```bash
sudo apt update
sudo apt install -y xubuntu-desktop spice-vdagent
sudo reboot
```

virt-manager VM 설정에서 `Display Spice`가 사용 중이면 `spice-vdagent` 설치 후 호스트 ↔ VM 클립보드 공유 가능.

---

## 5. Ubuntu 기본 패키지 설치

```bash
sudo apt update

sudo apt install -y \
    mininet \
    openvswitch-switch \
    iperf3 \
    tcpdump \
    git \
    curl \
    docker.io \
    openjdk-17-jdk
```

Docker 실행:

```bash
sudo systemctl enable --now docker
```

Docker 권한 추가:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

확인:

```bash
docker run hello-world
```

---

## 6. 인터넷 연결 확인

NAT 환경에서 `ping 8.8.8.8`은 실패할 수 있었지만, 실제 인터넷은 정상 동작함.

확인 명령:

```bash
curl -4 ifconfig.me
```

공인 IP가 출력되면 인터넷 정상.

---

## 7. ONOS Docker 실행

ONOS tar 설치는 Java/Karaf 호환성 문제로 실패했으므로 Docker 방식 사용.

ONOS 컨테이너 실행:

```bash
docker run -d \
  --name onos \
  --network host \
  onosproject/onos:2.7-latest
```

확인:

```bash
docker ps
```

ONOS Web UI 접속:

```text
http://localhost:8181/onos/ui
```

로그인:

```text
ID: onos
PW: rocks
```

---

## 8. ONOS 앱 활성화

ONOS에서 OpenFlow Provider와 Reactive Forwarding 앱을 활성화.

```bash
docker exec -it onos /root/onos/bin/onos-app localhost activate org.onosproject.openflow
```

```bash
docker exec -it onos /root/onos/bin/onos-app localhost activate org.onosproject.fwd
```

OpenFlow 포트 확인:

```bash
sudo ss -lntp | grep 6653
```

`LISTEN`이 뜨면 정상.

---

## 9. Mininet + ONOS 연결

기존 Mininet 상태 정리:

```bash
sudo mn -c
```

ONOS를 Controller로 지정하여 Mininet 실행:

```bash
sudo mn \
  --topo single,3 \
  --controller remote,ip=127.0.0.1,port=6653 \
  --switch ovsk,protocols=OpenFlow13
```

Mininet CLI에서 연결성 확인:

```text
pingall
```

최종 결과:

```text
0% dropped
```

---

## 10. 현재 성공한 구조

```text
Mininet Hosts
h1, h2, h3
    ↓
Open vSwitch s1
    ↓ OpenFlow 1.3
ONOS Controller
    ↓
org.onosproject.openflow
org.onosproject.fwd
```

현재까지 성공한 것:

```text
1. Arch Host에서 KVM/libvirt/virt-manager 설치
2. Ubuntu 24.04 VM 생성
3. Xubuntu Desktop 및 클립보드 공유 설정
4. Mininet 설치
5. Open vSwitch 설치
6. Docker 설치
7. ONOS Docker 컨테이너 실행
8. ONOS Web UI 로그인 성공
9. OpenFlow Provider 활성화
10. fwd 앱 활성화
11. Mininet switch가 ONOS Controller에 연결
12. pingall 0% dropped 성공
```

---
