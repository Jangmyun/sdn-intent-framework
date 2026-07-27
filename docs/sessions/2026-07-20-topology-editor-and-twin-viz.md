# 토폴로지 에디터 & Digital Twin 시각화 — 세션 기록 (2026-07-20)

> `docs/design/IMPLEMENTATION.md`에서 분리됨. 핵심 파이프라인 아키텍처(Stage 1~6)는
> 그 문서를 참고하고, 이 문서는 웹 UI 토폴로지 에디터와 Digital Twin 실시간 시각화
> 기능 추가 세션을 기록한다.

## 토폴로지 에디터 (`static/` — UI 기능)

### 개요

실제 OVS/ONOS 인프라 없이도 네트워크 토폴로지를 UI에서 직접 정의할 수 있는
D3.js 기반 드래그앤드롭 에디터다. 사용자가 배치한 토폴로지는 파이프라인 전체에
적용되며, ONOS가 오프라인 상태일 때 시각화 폴백으로도 동작한다.

**배경:** 실제 SDN 스위치나 OVS 환경은 고가 장비 또는 별도 인프라가 필요하다.
에디터를 통해 임의 토폴로지를 사전 정의하면 실제 장비 없이 다양한 실험이 가능하다.

---

### 아키텍처

```
[UI Edit Mode]
  사용자 조작 (드래그/클릭)
       │
       ▼
  editor state (app.js)
  { nodes: [...], links: [...] }
       │ POST /api/topology/custom
       ▼
  data/custom_topology.json  ←──── 영속 저장
       │
       ├──► GET /api/topology        → D3 시각화 (ONOS 폴백)
       └──► _run_pipeline()          → NetworkTopology.from_custom_file()
                                         └─ Stage 1~6 파이프라인에 반영
```

---

### UI 구성 (`static/index.html`, `static/app.js`)

#### 모드 전환

우측 토폴로지 패널 헤더의 **Edit 버튼**으로 라이브 모드 ↔ 에디터 모드를 전환한다.

| 라이브 모드 | 에디터 모드 |
|------------|------------|
| ONOS 토폴로지 자동 폴링 (1초) | 폴링 중단, 편집 캔버스 활성화 |
| Refresh 배지 표시 | 툴바 + Properties 패널 표시 |
| Metrics / Flow Table 표시 | Properties 패널로 교체 |

모드 진입 시 `clearTopologyGraph()` 로 기존 D3 요소를 완전히 제거한 뒤
해당 모드의 렌더링 함수를 호출한다. `fetchTopology()` 는 `editor.active` 가
`true` 일 때 즉시 반환하여 라이브 업데이트가 에디터를 덮어쓰지 않도록 한다.

#### 툴바 5개 도구

| 아이콘 | 도구 | 동작 |
|--------|------|------|
| ↖ | Select | 노드 클릭으로 선택, 드래그로 이동 |
| ⬡ | Switch | 캔버스 빈 공간 클릭 → 스위치 노드 배치 |
| ◎ | Host | 캔버스 빈 공간 클릭 → 호스트 노드 배치 |
| ╌ | Link | 노드 A 클릭 → 노드 B 클릭 → 링크 연결 |
| ✕ | Delete | 노드/링크 클릭으로 삭제 |

**Link 도구 Ghost Line:** 첫 번째 노드 클릭 후 마우스 이동 시 점선(`#ghost-link`)이
커서를 따라 표시되어 연결 방향을 시각적으로 안내한다. 동일 노드 재클릭 또는
빈 캔버스 클릭 시 취소된다. 동일 노드 쌍 중복 링크는 자동 방지된다.

#### Properties 패널

노드 선택 시 (Select 도구) 우측 하단에 속성 편집 폼이 나타난다.

| 노드 종류 | 편집 가능 필드 |
|-----------|--------------|
| Switch | Label, DPID (16자리 hex) |
| Host | Label, IP Address, MAC Address |
| 공통 | 연결된 링크 목록 (대역폭 Mbps 수정, 링크 삭제) |

모든 필드는 실시간으로 캔버스에 반영된다 (`input` 이벤트 → `renderEditorGraph()`).

#### 기본 토폴로지

Edit 모드 최초 진입 시 저장된 커스텀 토폴로지가 없으면
**다이아몬드 4-스위치 토폴로지** (Diamond)를 기본값으로 로드한다.

```
h1(10.0.0.1) ─┐         ┌─ h3(10.0.0.3)
               S1─(1M)─S2─(1M)─S4
h2(10.0.0.2) ─┘  ╲(10M)╱      └─ h4(10.0.0.4)
                   S3
```

스위치 자동 DPID: `0000000000000001` ~ `000000000000000N`
호스트 자동 IP: `10.0.0.N`, MAC: `00:00:00:00:00:0N`

#### Apply 동작

**Apply** 클릭 시:
1. `POST /api/topology/custom` 으로 현재 에디터 상태를 저장
2. 현재 토폴로지 기반으로 **Example Chips 자동 갱신**
   (호스트 IP와 스위치 번호를 읽어 Block / Forward / QoS 예시 인텐트 생성)
3. 에디터 모드 종료 → 라이브 모드로 복귀
4. `topoSnapshot = null` 로 즉시 재렌더 트리거

---

### D3.js 렌더링 분리

기존 라이브 모드(`updateTopology`)와 에디터 모드(`renderEditorGraph`)는
동일한 SVG를 공유하지만 선택자로 격리된다.

| 구분 | 선택자 | 설명 |
|------|--------|------|
| 라이브 노드 | `g.live-node` | ONOS 실시간 데이터 |
| 에디터 노드 | `g.ed-node` | 사용자 편집 데이터 |
| 라이브 링크 | `line` (직접) | D3 join |
| 에디터 링크 | `g.ed-link` | `<g>` 래퍼 + 히트 영역 포함 |

모드 전환 시 `clearTopologyGraph()` 가 두 레이어를 모두 비운다.
에디터의 D3 force simulation은 사용하지 않으며, 모든 노드가 `fx`/`fy` 고정 위치를 갖는다.
드래그 시 `d.x`/`d.y` 를 직접 수정하고 `renderEditorGraph()` 를 재호출한다.

---

### 데이터 포맷 (`data/custom_topology.json`)

```json
{
  "switches": [
    { "id": "s1", "label": "S1", "dpid": "0000000000000001", "x": 116, "y": 95 },
    { "id": "s2", "label": "S2", "dpid": "0000000000000002", "x":  96, "y": 180 }
  ],
  "hosts": [
    { "id": "h1", "label": "H1", "ip": "10.0.0.1", "mac": "00:00:00:00:00:01", "x": 41, "y": 70 }
  ],
  "links": [
    { "id": "l1", "source": "h1", "target": "s1", "bw": 100 },
    { "id": "l5", "source": "s1", "target": "s2", "bw": 1 }
  ]
}
```

- `id`: 에디터 내부 식별자 (단순 문자열)
- `dpid`: 16자리 hex, ONOS device_id 변환 시 `of:{dpid}` 형식
- `bw`: 링크 대역폭 (Mbps), 캔버스에 레이블로 표시

---

### API 엔드포인트 (`api.py`)

#### `GET /api/topology/custom`

저장된 커스텀 토폴로지 JSON을 그대로 반환한다.
파일이 없으면 빈 객체 `{}` 반환.

#### `POST /api/topology/custom`

에디터에서 Apply 시 호출된다. Request body를
`data/custom_topology.json` 에 저장하고 `{"ok": true}` 반환.

#### `GET /api/topology` (수정)

ONOS 연결 실패 시 커스텀 토폴로지를 D3 포맷으로 변환하여 반환한다.

변환 규칙 (`_custom_topo_as_d3`):
- 스위치 노드 ID: `s1` → `of:0000000000000001`
- 호스트 노드 ID: 그대로 유지 (`h1`)
- 링크: 스위치 ID를 `of:` 포맷으로 치환
- `_source: "custom"` 필드를 포함해 프론트엔드에서 구분 가능

```
ONOS 응답 정상 → ONOS 데이터 반환
ONOS 오프라인 → custom_topology.json 존재 시 D3 변환 반환
              → 파일 없으면 error 반환
```

---

### 파이프라인 통합

#### `_run_pipeline()` (api.py) 수정

```python
custom_topo = _load_custom_topology()
topology = (
    NetworkTopology.from_custom_file(custom_topo)
    if custom_topo
    else NetworkTopology.diamond()
)
```

커스텀 토폴로지가 저장되어 있으면 그것을 사용하고,
없으면 기존 Diamond 정적 토폴로지로 폴백한다.

#### `NetworkTopology.from_custom_file()` (models/topology.py)

커스텀 토폴로지 dict → `NetworkTopology` 변환 메서드.

```python
@classmethod
def from_custom_file(cls, data: dict) -> "NetworkTopology":
    hosts    = { h["id"]: h.get("ip", "") for h in data["hosts"] }
    switches = { sw["id"]: f"of:{sw['dpid']}" for sw in data["switches"] }
    # 링크에서 스위치별 포트 번호 순번 부여
    for lnk in data["links"]:
        for node_id in (lnk["source"], lnk["target"]):
            if node_id in switches:
                ports[switches[node_id]].append(port_counter[...] + 1)
    return cls(hosts=hosts, switches=switches, ports=ports)
```

파이프라인의 토폴로지 그라운딩 (B-2), 인텐트 검증, 프롬프트 주입 모두
커스텀 토폴로지 기반으로 동작한다.

---

### 설계 결정

#### OVS 직접 읽기 대신 UI 에디터를 선택한 이유

| 방식 | 장점 | 단점 |
|------|------|------|
| OVS 직접 읽기 | 실제 네트워크 반영 | 실제 SDN 스위치 또는 OVS 설치 필요, Windows 미지원 |
| ONOS REST API | 자동 토폴로지 발견 | ONOS 실행 환경 필요 |
| **UI 에디터 (선택)** | 환경 독립적, 즉시 실험 가능 | 수동 입력 필요 |

논문 개발 단계에서 라즈베리파이나 실제 SDN 장비 없이 다양한 토폴로지를
실험할 수 있다는 점에서 현실적인 접근이다. ONOS가 연결되면 라이브 모드로
자동 전환되므로 실제 환경 연동 시 추가 수정 없이 사용 가능하다.

#### D3 force simulation을 에디터에서 비활성화한 이유

라이브 모드에서는 힘-지향 레이아웃이 자동 배치에 유용하지만,
에디터에서는 사용자가 배치한 위치가 즉시 고정되어야 한다.
simulation의 alpha decay로 위치가 계속 변하면 정밀한 배치가 불가능하다.
에디터는 `fx`/`fy` 고정 좌표만 사용하고 simulation을 생략했다.

#### 노드 선택자 분리 (`g.live-node` vs `g.ed-node`)

모드 전환 없이 라이브 업데이트와 에디터가 동일 SVG를 공유할 경우,
`selectAll('g')` 가 두 레이어를 모두 선택해 데이터 바인딩이 충돌할 수 있다.
클래스로 명시적 격리하고 `clearTopologyGraph()` 로 전환 시 완전히 비움으로써
레이어 간 간섭을 완전히 제거했다.

---

## UI 개선 — 사이드바 접기 + 토폴로지 프리셋

### 사이드바 접기

#### 구현

`#sidebar-toggle-btn` (`◀`/`▶`) 버튼을 사이드바 로고 우측에 추가했다.
클릭 시 `#sidebar` 에 `.collapsed` 클래스를 토글하고 상태를 `localStorage`에 저장한다.

```javascript
function initSidebarToggle() {
  const btn = document.getElementById('sidebar-toggle-btn');
  const sidebar = document.getElementById('sidebar');
  if (localStorage.getItem('sidebarCollapsed') === '1') {
    sidebar.classList.add('collapsed');
    btn.textContent = '▶';
  }
  btn.addEventListener('click', () => {
    const collapsed = sidebar.classList.toggle('collapsed');
    btn.textContent = collapsed ? '▶' : '◀';
    localStorage.setItem('sidebarCollapsed', collapsed ? '1' : '0');
  });
}
```

CSS:

```css
#sidebar {
  width: 240px;
  transition: width 0.25s cubic-bezier(.4,0,.2,1);
  overflow: hidden;
}
#sidebar.collapsed { width: 52px; }
#sidebar.collapsed .sidebar-body { display: none; }
```

로고(`#sidebar-logo`)는 항상 표시되어 사이드바가 접혀도 버튼으로 다시 펼 수 있다.

---

### 토폴로지 프리셋

#### 목적

사용자가 `custom_topology.json`을 수동으로 편집하거나 에디터에서 일일이 노드를 배치하지 않고도,
미리 정의된 표준 토폴로지를 원클릭으로 적용할 수 있게 한다.

#### 프리셋 정의 (`app.js`)

```javascript
const TOPOLOGY_PRESETS = {
  diamond: {
    switches: [
      { id:"s1", label:"S1", dpid:"0000000000000001", x:185, y:100 },
      { id:"s2", label:"S2", dpid:"0000000000000002", x:100, y:220 },
      { id:"s3", label:"S3", dpid:"0000000000000003", x:270, y:220 },
      { id:"s4", label:"S4", dpid:"0000000000000004", x:185, y:340 }
    ],
    hosts: [
      { id:"h1", label:"H1", ip:"10.0.0.1", mac:"00:00:00:00:00:01", x:60, y:100 },
      { id:"h2", label:"H2", ip:"10.0.0.2", mac:"00:00:00:00:00:02", x:60, y:340 },
      { id:"h3", label:"H3", ip:"10.0.0.3", mac:"00:00:00:00:00:03", x:310, y:100 },
      { id:"h4", label:"H4", ip:"10.0.0.4", mac:"00:00:00:00:00:04", x:310, y:340 }
    ],
    links: [ /* s1-s2, s1-s3, s2-s4, s3-s4, h1-s1, h2-s2, h3-s3, h4-s4 */ ]
  },
  linear: { /* s1-s2, h1-s1, h2-s2 */ },
  ring:   { /* s1-s2-s3-s1, h1-s1, h2-s2, h3-s3 */ }
};
```

#### 드롭다운 UI (`index.html`)

```html
<button id="topo-preset-btn" class="topo-mode-btn">⊞ Presets</button>
<div id="topo-preset-menu" class="preset-menu">
  <div class="preset-item" data-preset="diamond">◇ Diamond (s1–s4, h1–h4)</div>
  <div class="preset-item" data-preset="linear">— Linear (s1–s2, h1–h2)</div>
  <div class="preset-item" data-preset="ring">○ Ring (s1–s3, h1–h3)</div>
</div>
```

#### `applyPreset(presetName)` 동작 순서

1. `POST /api/topology/custom` — 프리셋 데이터를 `custom_topology.json`에 저장
2. `POST /api/topology/apply` — 저장된 커스텀 토폴로지를 파이프라인에 적용
3. `updateExampleChips()` — 인텐트 예시 칩을 새 토폴로지 IP/스위치 기준으로 갱신
4. `topoSnapshot = null; fetchTopology()` — 토폴로지 그래프 즉시 재렌더

---

## 토폴로지 렌더링 버그 수정

### Bug: 전체화면 → 프리셋 변경 시 토폴로지 미표시

**증상:** 우측 토폴로지 패널을 전체화면(`⛶`)으로 키운 상태에서 프리셋을 변경하면
토폴로지가 표시되지 않는다.

**원인:**
- D3 force simulation이 전체화면 크기(`w × h`)로 노드 좌표를 계산함
- SVG `viewBox`는 초기화 시 한 번만 설정되어 패널 크기와 불일치
- 노드가 viewBox 밖에 위치하여 clipped out

**수정 (`app.js` — `updateTopology()`):**

```javascript
// 매 호출마다 viewBox를 현재 컨테이너 크기에 맞게 동기화
const w = container.clientWidth || 300;
const h = container.clientHeight || 200;
topoSvg.attr('viewBox', `0 0 ${w} ${h}`);
```

**추가 수정 — 전체화면 토글 시 라이브 토폴로지 리프레시:**

```javascript
function toggleTopoFullscreen() {
  // ... 클래스 토글 ...
  if (!editor.active) {
    setTimeout(() => {
      topoSnapshot = null;
      fetchTopology();   // 전체화면 크기로 재계산
    }, 80);
  }
}
```

---

### Bug: Digital Twin 실행 중 ONOS에 가상 스위치가 표시됨

**증상:** Digital Twin(Stage 4) 실행 중 라이브 토폴로지에 Mininet 가상 스위치가 나타남.
이는 Mininet이 가상 OVS 스위치를 ONOS에 연결하기 때문이다.

**수정:** `twinActive` 플래그로 폴링 중단.

```javascript
// state 객체에 추가
state.twinActive = false;

// fetchTopology() 최상단
function fetchTopology() {
  if (state.twinActive) return;  // Twin 실행 중엔 폴링 차단
  // ...
}

// SSE Stage 4 핸들러
if (ev.stage === 4) {
  if (ev.status === 'running') {
    state.twinActive = true;
  } else {
    state.twinActive = false;
    stopTwinViz();
    topoSnapshot = null;
    fetchTopology();  // 종료 후 원래 토폴로지 복원
  }
}
```

---

## Digital Twin 시각화

### 목적

Digital Twin (Stage 4) 검증 중, 현재 무엇을 테스트하고 있는지 사용자가 직관적으로
파악할 수 있도록 토폴로지 그래프에 실시간 시각 피드백을 제공한다.

- **SRC / DST / BLOCK** 노드 식별자 표시
- **패킷 애니메이션**: 실제 FlowRule 검증 단계별로 색상·경로·차단 여부 표현
- **노드 따라다니기**: 드래그 중에도 표시가 해당 노드 위에 정확히 유지됨

---

### 아키텍처

#### 데이터 흐름

```
api.py (twin 실행 중)
  │  SSE: progress 이벤트 (⑤⑥⑦⑧ 마커 포함 로그)
  │  SSE: twin_info 이벤트 { src_ip, dst_ip, device_id }
  ▼
app.js
  ├── progress → setTwinPhase("baseline" | "deployed" | "intent/block" | "regression")
  └── twin_info → onTwinInfo(ev) → renderTwinHighlights() + startPacketLoop()
```

#### SSE 이벤트 확장 (`api.py`)

FlowRule criteria에서 src_ip, dst_ip, action을 추출한 뒤, Digital Twin 시작 전에
`twin_info` 이벤트를 전송한다.

```python
emit({"type": "twin_info",
      "test": _tdesc,          # 설명 문자열
      "action": _act,          # "block" | "forward"
      "src_ip": _src or "",
      "dst_ip": _dst or "",
      "device_id": _flows[0].get("deviceId", "") if _flows else ""})
```

#### 단계 감지 (`app.js`)

검증기 내부 로그 메시지에 단계 마커(①~⑩)를 삽입하고, 프론트엔드가 메시지를 파싱해
단계를 추론한다. 별도 SSE 이벤트 타입을 추가하지 않아도 되는 방식이다.

```javascript
// progress 이벤트 핸들러
if (msg.includes('⑤') || msg.includes('[baseline]')) setTwinPhase('baseline');
else if (msg.includes('⑥') || msg.includes('FlowRule')) setTwinPhase('deployed');
else if (msg.includes('⑦') || msg.includes('[intent]')) setTwinPhase('intent/' + currentAction);
else if (msg.includes('⑧') || msg.includes('[regression]')) setTwinPhase('regression');
```

---

### 노드 하이라이트 (`renderTwinHighlights()`)

SRC, DST, BLOCK 노드에 링/레이블을 붙인다.

#### 노드 식별 로직

| 정보 | 조회 방법 |
|------|-----------|
| SRC | `currentTopoNodes.find(n => n.ip === src_ip)` |
| DST | `currentTopoNodes.find(n => n.ip === dst_ip)` |
| BLOCK | `device_id` → `parseInt(hex, 16)` → 번호 N → `currentTopoNodes.find(n => n.label === 'SN')` |

#### 노드 따라다니기 구현

**문제:** `.twin-viz` 레이어는 절대 좌표를 사용하므로, D3 force simulation으로 노드를
드래그하면 링/레이블이 원래 위치에 고정된 채 노드만 이동한다.

**해결:** 링과 레이블을 `.twin-viz`가 아닌 해당 `.live-node` `<g>` 그룹의 **자식**으로 추가한다.
D3가 `<g>`에 `transform="translate(x,y)"` 를 적용하면 자식 요소도 함께 이동한다.

```javascript
function renderTwinHighlights() {
  // 기존 인디케이터 제거
  topoSvg.selectAll('.twin-node-indicator').remove();

  [
    { node: srcNode,   color: '#22c55e', labelText: 'SRC' },
    { node: dstNode,   color: '#3b82f6', labelText: 'DST' },
    { node: blockNode, color: '#ef4444', labelText: 'BLOCK' },
  ].forEach(({ node, color, labelText }) => {
    if (!node) return;
    // .live-node <g> 를 찾아서 자식으로 추가
    const grp = topoSvg.selectAll('g.live-node')
      .filter(d => d.id === node.id);

    // 링 (node-local 좌표: cx=0, cy=0)
    grp.append('circle')
      .attr('class', 'twin-node-indicator twin-ring')
      .attr('cx', 0).attr('cy', 0)
      .attr('r', node.type === 'switch' ? 20 : 16)
      .attr('fill', 'none')
      .attr('stroke', color)
      .attr('stroke-width', 2.5);

    // 레이블
    grp.append('text')
      .attr('class', 'twin-node-indicator twin-label')
      .attr('y', node.type === 'switch' ? -26 : -22)
      .attr('text-anchor', 'middle')
      .style('fill', color)
      .style('font-size', '10px')
      .style('font-weight', '700')
      .text(labelText);
  });
}
```

CSS pulse 애니메이션:

```css
@keyframes twin-pulse {
  0%   { stroke-width: 2.5; opacity: 0.85; }
  50%  { stroke-width: 4;   opacity: 0.45; }
  100% { stroke-width: 2.5; opacity: 0.85; }
}
.twin-ring { animation: twin-pulse 1.4s ease-in-out infinite; }
```

---

### 패킷 애니메이션

#### 경로 탐색 (`findTopoPath(fromId, toId)`)

BFS로 `currentTopoLinks` 를 순회해 두 노드 사이의 최단 경로를 반환한다.

```javascript
function findTopoPath(fromId, toId) {
  const adj = {};
  currentTopoLinks.forEach(l => {
    (adj[l.source] ||= []).push(l.target);
    (adj[l.target] ||= []).push(l.source);
  });
  // BFS ...
  return path;  // [fromId, ..., toId]
}
```

#### 패킷 이동 (`spawnPacket(layer, pathIds, color, durationMs, stopIdx)`)

`nodePositions` Map에서 각 노드의 현재 (x, y)를 읽어 D3 `transition().tween()` 으로
패킷 원을 이동시킨다.

- `stopIdx`가 지정되면 해당 인덱스 노드(차단 스위치)에서 멈추고 **burst 이펙트** 표시
- 일반 경우 DST 노드까지 이동 후 fade-out

```javascript
function spawnPacket(layer, pathIds, color, durationMs, stopIdx = -1) {
  const pkt = layer.append('circle')
    .attr('r', 5).attr('fill', color).attr('opacity', 0.9);

  // 체인 트랜지션: 경로의 각 노드 좌표로 순차 이동
  let t = pkt.transition().duration(50)
    .attr('cx', pos0.x).attr('cy', pos0.y);

  for (let i = 1; i <= endIdx; i++) {
    const segDur = durationMs / endIdx;
    t = t.transition().duration(segDur)
      .attr('cx', pos[i].x).attr('cy', pos[i].y);
  }

  if (stopIdx >= 0) {
    // 차단: burst 원 확산 + fade
    t.on('end', () => {
      layer.append('circle').attr('r', 5).attr('fill', color)
        .transition().duration(300).attr('r', 18).attr('opacity', 0)
        .remove();
    });
  }
  t.transition().duration(200).attr('opacity', 0).remove();
}
```

`nodePositions`는 D3 simulation의 `tick` 이벤트마다 업데이트되어,
드래그 중에도 패킷 경로가 최신 좌표를 사용한다.

```javascript
simulation.on('tick', () => {
  // 링크·노드 위치 업데이트 ...
  nodePositions.set(d.id, { x: d.x, y: d.y });  // tick마다 갱신
});
```

#### 루프 실행 (`startPacketLoop(path, color, stopIdx)`)

두 개의 패킷 스트림을 offset을 두고 반복 실행한다.

```javascript
function startPacketLoop(path, color, stopIdx) {
  const dur = 1400;
  const layer = getTwinLayer();

  function loop() {
    if (!state.twinActive) return;
    spawnPacket(layer, path, color, dur, stopIdx);
    const t1 = setTimeout(() => spawnPacket(layer, path, color, dur, stopIdx), dur * 0.5);
    const t2 = setTimeout(loop, dur);
    twinAnimTimers.push(t1, t2);
  }
  loop();
}
```

---

### 단계별 시각화 (`setTwinPhase(phase)`)

| 단계 | 색상 | 경로 | 차단 여부 |
|------|------|------|---------|
| `baseline` | 초록(`#22c55e`) | src → dst (전체) | 없음 |
| `deployed` | — | 하이라이트만 (패킷 없음) | — |
| `intent/block` | 빨강(`#ef4444`) | src → blockSwitch | blockSwitch에서 burst |
| `intent/forward` | 초록(`#22c55e`) | src → dst (전체) | 없음 |
| `regression` | 보라(`#a855f7`) | 비대상 pair (h2→h3) | 없음 |

```javascript
function setTwinPhase(phase) {
  stopTwinViz();
  renderTwinHighlights();
  twinVizPhase = phase;

  if (phase === 'baseline') {
    const path = findTopoPath(srcNode.id, dstNode.id);
    startPacketLoop(path, '#22c55e', -1);
  } else if (phase === 'intent/block') {
    const path = findTopoPath(srcNode.id, blockNode.id);
    const stopIdx = path.length - 1;
    startPacketLoop(path, '#ef4444', stopIdx);
  } else if (phase === 'intent/forward') {
    const path = findTopoPath(srcNode.id, dstNode.id);
    startPacketLoop(path, '#22c55e', -1);
  } else if (phase === 'regression') {
    // h2→h3 pair로 회귀 테스트 시각화
    const otherPair = findRegressionPair();
    if (otherPair) startPacketLoop(otherPair, '#a855f7', -1);
  }
}
```

---

### progress_cb 콜백 패턴 (`twin_verifier.py`)

검증기 내부 로그를 실시간으로 UI Stage 4 카드에 스트리밍하기 위해
`progress_cb` 콜백 패턴을 도입했다.

#### `twin_verifier.py` 수정

```python
def verify(self, flowrule: dict, progress_cb=None) -> TwinResult:
    self._progress_cb = progress_cb
    # ...

def _log(self, msg: str):
    print(f"    [Twin] {msg}")
    if self._progress_cb:
        self._progress_cb(msg)
```

검증 10단계에 번호 마커 추가:

```python
self._log("⑤ [baseline] h1 → h4 ping 테스트 시작...")
self._log("⑥ FlowRule 배포 중...")
self._log("⑦ [intent] block intent_check 시작...")
self._log("⑧ [regression] h2 → h3 회귀 테스트...")
```

#### `api.py` 수정

```python
result = verifier.verify(
    flowrule,
    progress_cb=lambda msg: progress(4, msg)
)
```

`progress(stage, msg)` 함수가 SSE `progress` 이벤트를 프론트엔드로 전송한다.

---

### SVG 클리핑 버그 수정

**증상:** 토폴로지 상단 노드의 레이블이 SVG 경계에서 잘린다.

**원인:** SVG 기본값 `overflow="hidden"` → viewBox 밖 내용 clipped.

**수정:** SVG 초기화 시 `overflow="visible"` 설정.

```javascript
topoSvg = d3.select('#topology-graph').append('svg')
  .attr('width', '100%')
  .attr('height', '100%')
  .attr('overflow', 'visible');   // ← 추가
```

외부 컨테이너(`#topology-graph`)의 `overflow: hidden` CSS가 실제 시각 경계 역할을 한다.

---

## 설계 결정 노트

### baseline 연결성 확인이 필요한 이유

Digital Twin 검증 시 intent_check 전에 h1→h4 ping을 먼저 실행하는 이유:

- FlowRule **배포 후** ping 실패만 확인하면, 실패 원인이 (a) Rule이 정상 차단한 것인지
  (b) Mininet 네트워크 자체 문제인지 구분할 수 없다
- baseline이 통과해야 "네트워크는 작동하고, Rule이 차단을 유발했다"는 결론이 유효해진다
- 이는 **통제된 실험** 원칙: 변수(FlowRule)를 하나씩 바꾸어 인과관계를 확인

### 캐시 버스터 (`?v=N`)

`app.js`, `style.css` URL에 `?v=N` 쿼리 파라미터를 붙이면 브라우저가 이전 버전 파일을
캐시에서 로드하지 않고 서버에서 새로 받는다. 실제 파일명 변경 없이 배포할 수 있다.

`index.html`은 캐시 버스터가 없어도 되는 이유: 브라우저가 HTML을 먼저 로드하고,
그 안의 스크립트·스타일시트 URL에 붙은 `?v=N`을 새 요청으로 처리한다.

### Twin 시각화를 별도 레이어가 아닌 노드 자식으로 구현한 이유

절대 좌표 레이어에 SVG 원을 그리면 D3 drag 중 노드가 이동해도 인디케이터는
고정된다. `.live-node <g>`의 자식으로 추가하면 부모의 `transform="translate(x,y)"`
를 상속받아 자동으로 따라 이동한다. 별도 좌표 계산이나 drag 이벤트 핸들러 없이
D3 데이터 바인딩 구조만으로 해결된다.

### 단계 감지를 별도 이벤트 타입 없이 로그 파싱으로 구현한 이유

SSE에 새 이벤트 타입(`phase_change`)을 추가하면 백엔드·프론트엔드 모두 수정이 필요하다.
검증기 로그 메시지에 ①~⑩ 유니코드 마커를 삽입하고 프론트엔드가 파싱하면
백엔드 인터페이스를 변경하지 않아도 된다. 로그는 이미 Stage 4 카드에 표시되므로
마커도 사용자에게 노출되어 현재 단계를 명시적으로 알 수 있다.
