'use strict';

// ── Constants ─────────────────────────────────────────────────────────────────

const TOPOLOGY_PRESETS = {
  diamond: {
    label: 'Diamond',
    switches: [
      { id: 's1', label: 'S1', dpid: '0000000000000001', x: 170, y: 80  },
      { id: 's2', label: 'S2', dpid: '0000000000000002', x: 85,  y: 165 },
      { id: 's3', label: 'S3', dpid: '0000000000000003', x: 255, y: 165 },
      { id: 's4', label: 'S4', dpid: '0000000000000004', x: 170, y: 245 },
    ],
    hosts: [
      { id: 'h1', label: 'H1', ip: '10.0.0.1', mac: '00:00:00:00:00:01', x: 170, y: 24  },
      { id: 'h2', label: 'H2', ip: '10.0.0.2', mac: '00:00:00:00:00:02', x: 24,  y: 160 },
      { id: 'h3', label: 'H3', ip: '10.0.0.3', mac: '00:00:00:00:00:03', x: 316, y: 160 },
      { id: 'h4', label: 'H4', ip: '10.0.0.4', mac: '00:00:00:00:00:04', x: 170, y: 268 },
    ],
    links: [
      { id: 'l1', source: 's1', target: 's2', bw: 10 },
      { id: 'l2', source: 's1', target: 's3', bw: 10 },
      { id: 'l3', source: 's2', target: 's4', bw: 10 },
      { id: 'l4', source: 's3', target: 's4', bw: 10 },
      { id: 'l5', source: 'h1', target: 's1', bw: 100 },
      { id: 'l6', source: 'h2', target: 's2', bw: 100 },
      { id: 'l7', source: 'h3', target: 's3', bw: 100 },
      { id: 'l8', source: 'h4', target: 's4', bw: 100 },
    ],
  },
  linear: {
    label: 'Linear',
    switches: [
      { id: 's1', label: 'S1', dpid: '0000000000000001', x: 110, y: 140 },
      { id: 's2', label: 'S2', dpid: '0000000000000002', x: 230, y: 140 },
    ],
    hosts: [
      { id: 'h1', label: 'H1', ip: '10.0.0.1', mac: '00:00:00:00:00:01', x: 30,  y: 140 },
      { id: 'h2', label: 'H2', ip: '10.0.0.2', mac: '00:00:00:00:00:02', x: 310, y: 140 },
    ],
    links: [
      { id: 'l1', source: 'h1', target: 's1', bw: 100 },
      { id: 'l2', source: 's1', target: 's2', bw: 10  },
      { id: 'l3', source: 's2', target: 'h2', bw: 100 },
    ],
  },
  ring: {
    label: 'Ring',
    switches: [
      { id: 's1', label: 'S1', dpid: '0000000000000001', x: 170, y: 65  },
      { id: 's2', label: 'S2', dpid: '0000000000000002', x: 80,  y: 210 },
      { id: 's3', label: 'S3', dpid: '0000000000000003', x: 260, y: 210 },
    ],
    hosts: [
      { id: 'h1', label: 'H1', ip: '10.0.0.1', mac: '00:00:00:00:00:01', x: 170, y: 20  },
      { id: 'h2', label: 'H2', ip: '10.0.0.2', mac: '00:00:00:00:00:02', x: 25,  y: 230 },
      { id: 'h3', label: 'H3', ip: '10.0.0.3', mac: '00:00:00:00:00:03', x: 315, y: 230 },
    ],
    links: [
      { id: 'l1', source: 's1', target: 's2', bw: 10  },
      { id: 'l2', source: 's2', target: 's3', bw: 10  },
      { id: 'l3', source: 's3', target: 's1', bw: 10  },
      { id: 'l4', source: 'h1', target: 's1', bw: 100 },
      { id: 'l5', source: 'h2', target: 's2', bw: 100 },
      { id: 'l6', source: 'h3', target: 's3', bw: 100 },
    ],
  },

  // ── 추가 프리셋 ────────────────────────────────────────────────────────────

  // Spine-Leaf: 현대 데이터센터 표준 구조
  // 2 Spine (완전 연결) × 4 Leaf, 각 Leaf에 호스트 2개
  'spine-leaf': {
    label: 'Spine-Leaf',
    switches: [
      { id: 's1', label: 'S1', dpid: '0000000000000001', x: 110, y: 70  }, // Spine
      { id: 's2', label: 'S2', dpid: '0000000000000002', x: 230, y: 70  }, // Spine
      { id: 's3', label: 'S3', dpid: '0000000000000003', x: 40,  y: 175 }, // Leaf
      { id: 's4', label: 'S4', dpid: '0000000000000004', x: 125, y: 175 }, // Leaf
      { id: 's5', label: 'S5', dpid: '0000000000000005', x: 210, y: 175 }, // Leaf
      { id: 's6', label: 'S6', dpid: '0000000000000006', x: 300, y: 175 }, // Leaf
    ],
    hosts: [
      { id: 'h1', label: 'H1', ip: '10.0.0.1', mac: '00:00:00:00:00:01', x: 18,  y: 255 },
      { id: 'h2', label: 'H2', ip: '10.0.0.2', mac: '00:00:00:00:00:02', x: 65,  y: 255 },
      { id: 'h3', label: 'H3', ip: '10.0.0.3', mac: '00:00:00:00:00:03', x: 100, y: 255 },
      { id: 'h4', label: 'H4', ip: '10.0.0.4', mac: '00:00:00:00:00:04', x: 150, y: 255 },
      { id: 'h5', label: 'H5', ip: '10.0.0.5', mac: '00:00:00:00:00:05', x: 185, y: 255 },
      { id: 'h6', label: 'H6', ip: '10.0.0.6', mac: '00:00:00:00:00:06', x: 235, y: 255 },
      { id: 'h7', label: 'H7', ip: '10.0.0.7', mac: '00:00:00:00:00:07', x: 275, y: 255 },
      { id: 'h8', label: 'H8', ip: '10.0.0.8', mac: '00:00:00:00:00:08', x: 325, y: 255 },
    ],
    links: [
      // Each spine → all leaves (full bipartite)
      { id: 'l1',  source: 's1', target: 's3', bw: 40 },
      { id: 'l2',  source: 's1', target: 's4', bw: 40 },
      { id: 'l3',  source: 's1', target: 's5', bw: 40 },
      { id: 'l4',  source: 's1', target: 's6', bw: 40 },
      { id: 'l5',  source: 's2', target: 's3', bw: 40 },
      { id: 'l6',  source: 's2', target: 's4', bw: 40 },
      { id: 'l7',  source: 's2', target: 's5', bw: 40 },
      { id: 'l8',  source: 's2', target: 's6', bw: 40 },
      // Leaf → hosts (2 per leaf)
      { id: 'l9',  source: 's3', target: 'h1', bw: 1 },
      { id: 'l10', source: 's3', target: 'h2', bw: 1 },
      { id: 'l11', source: 's4', target: 'h3', bw: 1 },
      { id: 'l12', source: 's4', target: 'h4', bw: 1 },
      { id: 'l13', source: 's5', target: 'h5', bw: 1 },
      { id: 'l14', source: 's5', target: 'h6', bw: 1 },
      { id: 'l15', source: 's6', target: 'h7', bw: 1 },
      { id: 'l16', source: 's6', target: 'h8', bw: 1 },
    ],
  },

  // Fat-Tree (k=4, 2-pod simplified): 대규모 데이터센터 고대역폭 구조
  // Core 2개 × Agg 4개(팟당 2) × Edge 4개(팟당 2), 호스트 8개
  'fat-tree': {
    label: 'Fat-Tree',
    switches: [
      { id: 's1',  label: 'S1',  dpid: '0000000000000001', x: 120, y: 35  }, // Core
      { id: 's2',  label: 'S2',  dpid: '0000000000000002', x: 220, y: 35  }, // Core
      { id: 's3',  label: 'S3',  dpid: '0000000000000003', x: 65,  y: 115 }, // Pod1-Agg
      { id: 's4',  label: 'S4',  dpid: '0000000000000004', x: 145, y: 115 }, // Pod1-Agg
      { id: 's5',  label: 'S5',  dpid: '0000000000000005', x: 200, y: 115 }, // Pod2-Agg
      { id: 's6',  label: 'S6',  dpid: '0000000000000006', x: 275, y: 115 }, // Pod2-Agg
      { id: 's7',  label: 'S7',  dpid: '0000000000000007', x: 50,  y: 200 }, // Pod1-Edge
      { id: 's8',  label: 'S8',  dpid: '0000000000000008', x: 140, y: 200 }, // Pod1-Edge
      { id: 's9',  label: 'S9',  dpid: '0000000000000009', x: 200, y: 200 }, // Pod2-Edge
      { id: 's10', label: 'S10', dpid: '000000000000000a', x: 290, y: 200 }, // Pod2-Edge
    ],
    hosts: [
      { id: 'h1', label: 'H1', ip: '10.0.0.1', mac: '00:00:00:00:00:01', x: 25,  y: 265 },
      { id: 'h2', label: 'H2', ip: '10.0.0.2', mac: '00:00:00:00:00:02', x: 75,  y: 265 },
      { id: 'h3', label: 'H3', ip: '10.0.0.3', mac: '00:00:00:00:00:03', x: 115, y: 265 },
      { id: 'h4', label: 'H4', ip: '10.0.0.4', mac: '00:00:00:00:00:04', x: 165, y: 265 },
      { id: 'h5', label: 'H5', ip: '10.0.0.5', mac: '00:00:00:00:00:05', x: 175, y: 265 },
      { id: 'h6', label: 'H6', ip: '10.0.0.6', mac: '00:00:00:00:00:06', x: 225, y: 265 },
      { id: 'h7', label: 'H7', ip: '10.0.0.7', mac: '00:00:00:00:00:07', x: 265, y: 265 },
      { id: 'h8', label: 'H8', ip: '10.0.0.8', mac: '00:00:00:00:00:08', x: 315, y: 265 },
    ],
    links: [
      // Core → Aggregation (cross-pod connections)
      { id: 'l1',  source: 's1', target: 's3', bw: 40 },
      { id: 'l2',  source: 's1', target: 's5', bw: 40 },
      { id: 'l3',  source: 's2', target: 's4', bw: 40 },
      { id: 'l4',  source: 's2', target: 's6', bw: 40 },
      // Aggregation → Edge (within pod)
      { id: 'l5',  source: 's3', target: 's7',  bw: 10 },
      { id: 'l6',  source: 's3', target: 's8',  bw: 10 },
      { id: 'l7',  source: 's4', target: 's7',  bw: 10 },
      { id: 'l8',  source: 's4', target: 's8',  bw: 10 },
      { id: 'l9',  source: 's5', target: 's9',  bw: 10 },
      { id: 'l10', source: 's5', target: 's10', bw: 10 },
      { id: 'l11', source: 's6', target: 's9',  bw: 10 },
      { id: 'l12', source: 's6', target: 's10', bw: 10 },
      // Edge → hosts
      { id: 'l13', source: 's7',  target: 'h1', bw: 1 },
      { id: 'l14', source: 's7',  target: 'h2', bw: 1 },
      { id: 'l15', source: 's8',  target: 'h3', bw: 1 },
      { id: 'l16', source: 's8',  target: 'h4', bw: 1 },
      { id: 'l17', source: 's9',  target: 'h5', bw: 1 },
      { id: 'l18', source: 's9',  target: 'h6', bw: 1 },
      { id: 'l19', source: 's10', target: 'h7', bw: 1 },
      { id: 'l20', source: 's10', target: 'h8', bw: 1 },
    ],
  },

  // Tree (3-level binary): 전통적 계층형 캠퍼스/기업망
  // Root 1 → Aggregation 2 → Edge 4, 호스트 8개
  tree: {
    label: 'Tree',
    switches: [
      { id: 's1', label: 'S1', dpid: '0000000000000001', x: 170, y: 40  }, // Root
      { id: 's2', label: 'S2', dpid: '0000000000000002', x: 90,  y: 120 }, // Agg
      { id: 's3', label: 'S3', dpid: '0000000000000003', x: 250, y: 120 }, // Agg
      { id: 's4', label: 'S4', dpid: '0000000000000004', x: 45,  y: 205 }, // Edge
      { id: 's5', label: 'S5', dpid: '0000000000000005', x: 135, y: 205 }, // Edge
      { id: 's6', label: 'S6', dpid: '0000000000000006', x: 205, y: 205 }, // Edge
      { id: 's7', label: 'S7', dpid: '0000000000000007', x: 295, y: 205 }, // Edge
    ],
    hosts: [
      { id: 'h1', label: 'H1', ip: '10.0.0.1', mac: '00:00:00:00:00:01', x: 20,  y: 275 },
      { id: 'h2', label: 'H2', ip: '10.0.0.2', mac: '00:00:00:00:00:02', x: 70,  y: 275 },
      { id: 'h3', label: 'H3', ip: '10.0.0.3', mac: '00:00:00:00:00:03', x: 110, y: 275 },
      { id: 'h4', label: 'H4', ip: '10.0.0.4', mac: '00:00:00:00:00:04', x: 160, y: 275 },
      { id: 'h5', label: 'H5', ip: '10.0.0.5', mac: '00:00:00:00:00:05', x: 180, y: 275 },
      { id: 'h6', label: 'H6', ip: '10.0.0.6', mac: '00:00:00:00:00:06', x: 230, y: 275 },
      { id: 'h7', label: 'H7', ip: '10.0.0.7', mac: '00:00:00:00:00:07', x: 270, y: 275 },
      { id: 'h8', label: 'H8', ip: '10.0.0.8', mac: '00:00:00:00:00:08', x: 320, y: 275 },
    ],
    links: [
      { id: 'l1',  source: 's1', target: 's2', bw: 40 },
      { id: 'l2',  source: 's1', target: 's3', bw: 40 },
      { id: 'l3',  source: 's2', target: 's4', bw: 10 },
      { id: 'l4',  source: 's2', target: 's5', bw: 10 },
      { id: 'l5',  source: 's3', target: 's6', bw: 10 },
      { id: 'l6',  source: 's3', target: 's7', bw: 10 },
      { id: 'l7',  source: 's4', target: 'h1', bw: 1 },
      { id: 'l8',  source: 's4', target: 'h2', bw: 1 },
      { id: 'l9',  source: 's5', target: 'h3', bw: 1 },
      { id: 'l10', source: 's5', target: 'h4', bw: 1 },
      { id: 'l11', source: 's6', target: 'h5', bw: 1 },
      { id: 'l12', source: 's6', target: 'h6', bw: 1 },
      { id: 'l13', source: 's7', target: 'h7', bw: 1 },
      { id: 'l14', source: 's7', target: 'h8', bw: 1 },
    ],
  },

  // Full-Mesh: 스위치 간 완전 연결, 최대 경로 다양성
  // 4 switches × 6 links (완전 그래프), 호스트 8개
  'full-mesh': {
    label: 'Full Mesh',
    switches: [
      { id: 's1', label: 'S1', dpid: '0000000000000001', x: 115, y: 95  },
      { id: 's2', label: 'S2', dpid: '0000000000000002', x: 225, y: 95  },
      { id: 's3', label: 'S3', dpid: '0000000000000003', x: 115, y: 195 },
      { id: 's4', label: 'S4', dpid: '0000000000000004', x: 225, y: 195 },
    ],
    hosts: [
      { id: 'h1', label: 'H1', ip: '10.0.0.1', mac: '00:00:00:00:00:01', x: 50,  y: 50  },
      { id: 'h2', label: 'H2', ip: '10.0.0.2', mac: '00:00:00:00:00:02', x: 120, y: 28  },
      { id: 'h3', label: 'H3', ip: '10.0.0.3', mac: '00:00:00:00:00:03', x: 220, y: 28  },
      { id: 'h4', label: 'H4', ip: '10.0.0.4', mac: '00:00:00:00:00:04', x: 295, y: 50  },
      { id: 'h5', label: 'H5', ip: '10.0.0.5', mac: '00:00:00:00:00:05', x: 295, y: 240 },
      { id: 'h6', label: 'H6', ip: '10.0.0.6', mac: '00:00:00:00:00:06', x: 220, y: 260 },
      { id: 'h7', label: 'H7', ip: '10.0.0.7', mac: '00:00:00:00:00:07', x: 120, y: 260 },
      { id: 'h8', label: 'H8', ip: '10.0.0.8', mac: '00:00:00:00:00:08', x: 50,  y: 240 },
    ],
    links: [
      // Full mesh (n=4 → 6 inter-switch links)
      { id: 'l1',  source: 's1', target: 's2', bw: 10 },
      { id: 'l2',  source: 's1', target: 's3', bw: 10 },
      { id: 'l3',  source: 's1', target: 's4', bw: 10 },
      { id: 'l4',  source: 's2', target: 's3', bw: 10 },
      { id: 'l5',  source: 's2', target: 's4', bw: 10 },
      { id: 'l6',  source: 's3', target: 's4', bw: 10 },
      // 2 hosts per switch
      { id: 'l7',  source: 's1', target: 'h1', bw: 1 },
      { id: 'l8',  source: 's1', target: 'h2', bw: 1 },
      { id: 'l9',  source: 's2', target: 'h3', bw: 1 },
      { id: 'l10', source: 's2', target: 'h4', bw: 1 },
      { id: 'l11', source: 's4', target: 'h5', bw: 1 },
      { id: 'l12', source: 's4', target: 'h6', bw: 1 },
      { id: 'l13', source: 's3', target: 'h7', bw: 1 },
      { id: 'l14', source: 's3', target: 'h8', bw: 1 },
    ],
  },

  // Campus: 3계층 기업 캠퍼스망 (Core→Distribution→Access), 이중 업링크
  campus: {
    label: 'Campus',
    switches: [
      { id: 's1', label: 'S1', dpid: '0000000000000001', x: 170, y: 45  }, // Core
      { id: 's2', label: 'S2', dpid: '0000000000000002', x: 85,  y: 130 }, // Dist
      { id: 's3', label: 'S3', dpid: '0000000000000003', x: 255, y: 130 }, // Dist
      { id: 's4', label: 'S4', dpid: '0000000000000004', x: 45,  y: 220 }, // Access
      { id: 's5', label: 'S5', dpid: '0000000000000005', x: 170, y: 220 }, // Access (dual uplink)
      { id: 's6', label: 'S6', dpid: '0000000000000006', x: 295, y: 220 }, // Access
    ],
    hosts: [
      { id: 'h1', label: 'H1', ip: '10.0.0.1', mac: '00:00:00:00:00:01', x: 15,  y: 295 },
      { id: 'h2', label: 'H2', ip: '10.0.0.2', mac: '00:00:00:00:00:02', x: 75,  y: 295 },
      { id: 'h3', label: 'H3', ip: '10.0.0.3', mac: '00:00:00:00:00:03', x: 135, y: 295 },
      { id: 'h4', label: 'H4', ip: '10.0.0.4', mac: '00:00:00:00:00:04', x: 205, y: 295 },
      { id: 'h5', label: 'H5', ip: '10.0.0.5', mac: '00:00:00:00:00:05', x: 265, y: 295 },
      { id: 'h6', label: 'H6', ip: '10.0.0.6', mac: '00:00:00:00:00:06', x: 325, y: 295 },
    ],
    links: [
      { id: 'l1',  source: 's1', target: 's2', bw: 40 },
      { id: 'l2',  source: 's1', target: 's3', bw: 40 },
      { id: 'l3',  source: 's2', target: 's4', bw: 10 },
      { id: 'l4',  source: 's2', target: 's5', bw: 10 }, // S5 dual uplink ①
      { id: 'l5',  source: 's3', target: 's5', bw: 10 }, // S5 dual uplink ②
      { id: 'l6',  source: 's3', target: 's6', bw: 10 },
      { id: 'l7',  source: 's4', target: 'h1', bw: 1 },
      { id: 'l8',  source: 's4', target: 'h2', bw: 1 },
      { id: 'l9',  source: 's5', target: 'h3', bw: 1 },
      { id: 'l10', source: 's5', target: 'h4', bw: 1 },
      { id: 'l11', source: 's6', target: 'h5', bw: 1 },
      { id: 'l12', source: 's6', target: 'h6', bw: 1 },
    ],
  },

  // WAN Backbone: 비균등 비대칭 백본망 (ISP/GÉANT 스타일)
  // 8 PoP 스위치, 비규칙적 연결, 다양한 대역폭
  wan: {
    label: 'WAN Backbone',
    switches: [
      { id: 's1', label: 'S1', dpid: '0000000000000001', x: 80,  y: 75  }, // PoP-A
      { id: 's2', label: 'S2', dpid: '0000000000000002', x: 220, y: 55  }, // PoP-B
      { id: 's3', label: 'S3', dpid: '0000000000000003', x: 310, y: 145 }, // PoP-C
      { id: 's4', label: 'S4', dpid: '0000000000000004', x: 195, y: 175 }, // PoP-D (hub)
      { id: 's5', label: 'S5', dpid: '0000000000000005', x: 75,  y: 200 }, // PoP-E
      { id: 's6', label: 'S6', dpid: '0000000000000006', x: 300, y: 260 }, // PoP-F
      { id: 's7', label: 'S7', dpid: '0000000000000007', x: 160, y: 265 }, // PoP-G
      { id: 's8', label: 'S8', dpid: '0000000000000008', x: 50,  y: 295 }, // PoP-H
    ],
    hosts: [
      { id: 'h1', label: 'H1', ip: '10.0.0.1', mac: '00:00:00:00:00:01', x: 40,  y: 35  },
      { id: 'h2', label: 'H2', ip: '10.0.0.2', mac: '00:00:00:00:00:02', x: 200, y: 18  },
      { id: 'h3', label: 'H3', ip: '10.0.0.3', mac: '00:00:00:00:00:03', x: 330, y: 60  },
      { id: 'h4', label: 'H4', ip: '10.0.0.4', mac: '00:00:00:00:00:04', x: 330, y: 280 },
      { id: 'h5', label: 'H5', ip: '10.0.0.5', mac: '00:00:00:00:00:05', x: 160, y: 330 },
      { id: 'h6', label: 'H6', ip: '10.0.0.6', mac: '00:00:00:00:00:06', x: 20,  y: 330 },
      { id: 'h7', label: 'H7', ip: '10.0.0.7', mac: '00:00:00:00:00:07', x: 20,  y: 160 },
      { id: 'h8', label: 'H8', ip: '10.0.0.8', mac: '00:00:00:00:00:08', x: 260, y: 210 },
    ],
    links: [
      // Backbone (asymmetric, variable BW)
      { id: 'l1',  source: 's1', target: 's2', bw: 100 },
      { id: 'l2',  source: 's2', target: 's3', bw: 100 },
      { id: 'l3',  source: 's2', target: 's4', bw: 40  },
      { id: 'l4',  source: 's3', target: 's4', bw: 40  },
      { id: 'l5',  source: 's3', target: 's6', bw: 40  },
      { id: 'l6',  source: 's1', target: 's5', bw: 40  },
      { id: 'l7',  source: 's4', target: 's5', bw: 10  },
      { id: 'l8',  source: 's4', target: 's7', bw: 10  },
      { id: 'l9',  source: 's5', target: 's7', bw: 10  },
      { id: 'l10', source: 's5', target: 's8', bw: 10  },
      { id: 'l11', source: 's6', target: 's7', bw: 10  },
      // Host attachments (1 per PoP)
      { id: 'l12', source: 's1', target: 'h1', bw: 1 },
      { id: 'l13', source: 's2', target: 'h2', bw: 1 },
      { id: 'l14', source: 's3', target: 'h3', bw: 1 },
      { id: 'l15', source: 's6', target: 'h4', bw: 1 },
      { id: 'l16', source: 's7', target: 'h5', bw: 1 },
      { id: 'l17', source: 's8', target: 'h6', bw: 1 },
      { id: 'l18', source: 's5', target: 'h7', bw: 1 },
      { id: 'l19', source: 's4', target: 'h8', bw: 1 },
    ],
  },

  // Multi-Tier Clos: 5계층 Clos Fabric (사용자 커스텀 연구망)
  // Ingress(1) → Access(2) → Distribution(4) → Core(4) → Aggregation(2) → Egress(1)
  // 듀얼홈 호스트 포함, 14SW · 10H
  'clos-fabric': {
    label: 'Clos Fabric',
    switches: [
      { id: 's1',  label: 'S1',  dpid: '0000000000000001', x: -47,  y: 132 }, // Ingress
      { id: 's2',  label: 'S2',  dpid: '0000000000000002', x: 109,  y: 133 }, // Access
      { id: 's3',  label: 'S3',  dpid: '0000000000000003', x: 237,  y: 133 }, // Distribution
      { id: 's4',  label: 'S4',  dpid: '0000000000000004', x: 339,  y: 129 }, // Core
      { id: 's5',  label: 'S5',  dpid: '0000000000000005', x: 97,   y: 89  }, // Access
      { id: 's6',  label: 'S6',  dpid: '0000000000000006', x: 239,  y: 97  }, // Distribution
      { id: 's7',  label: 'S7',  dpid: '0000000000000007', x: 245,  y: 194 }, // Distribution
      { id: 's8',  label: 'S8',  dpid: '0000000000000008', x: 239,  y: 39  }, // Distribution
      { id: 's9',  label: 'S9',  dpid: '0000000000000009', x: 349,  y: 86  }, // Core
      { id: 's10', label: 'S10', dpid: '0000000000000010', x: 351,  y: 169 }, // Core
      { id: 's11', label: 'S11', dpid: '0000000000000011', x: 348,  y: 222 }, // Core
      { id: 's12', label: 'S12', dpid: '0000000000000012', x: 446,  y: 76  }, // Aggregation
      { id: 's13', label: 'S13', dpid: '0000000000000013', x: 455,  y: 143 }, // Aggregation
      { id: 's14', label: 'S14', dpid: '0000000000000014', x: 558,  y: 114 }, // Egress
    ],
    hosts: [
      { id: 'h1',  label: 'H1',  ip: '10.0.0.1',  mac: '00:00:00:00:00:01', x: -161, y: 122 },
      { id: 'h2',  label: 'H2',  ip: '10.0.0.2',  mac: '00:00:00:00:00:02', x: 574,  y: 167 },
      { id: 'h3',  label: 'H3',  ip: '10.0.0.3',  mac: '00:00:00:00:00:03', x: 85,   y: 270 },
      { id: 'h4',  label: 'H4',  ip: '10.0.0.4',  mac: '00:00:00:00:00:04', x: 227,  y: 305 },
      { id: 'h5',  label: 'H5',  ip: '10.0.0.5',  mac: '00:00:00:00:00:05', x: 361,  y: 307 },
      { id: 'h6',  label: 'H6',  ip: '10.0.0.6',  mac: '00:00:00:00:00:06', x: 480,  y: 268 },
      { id: 'h7',  label: 'H7',  ip: '10.0.0.7',  mac: '00:00:00:00:00:07', x: 55,   y: -34 },
      { id: 'h8',  label: 'H8',  ip: '10.0.0.8',  mac: '00:00:00:00:00:08', x: 282,  y: -63 },
      { id: 'h9',  label: 'H9',  ip: '10.0.0.9',  mac: '00:00:00:00:00:09', x: 385,  y: -42 },
      { id: 'h10', label: 'H10', ip: '10.0.0.10', mac: '00:00:00:00:00:10', x: 508,  y: -15 },
    ],
    links: [
      // Ingress ↔ Access
      { id: 'l10', source: 's1',  target: 's5',  bw: 10  },
      { id: 'l11', source: 's1',  target: 's2',  bw: 10  },
      // Access → Distribution (2×4 full bipartite)
      { id: 'l12', source: 's5',  target: 's8',  bw: 10  },
      { id: 'l13', source: 's5',  target: 's6',  bw: 10  },
      { id: 'l14', source: 's5',  target: 's3',  bw: 10  },
      { id: 'l15', source: 's5',  target: 's7',  bw: 10  },
      { id: 'l16', source: 's2',  target: 's8',  bw: 10  },
      { id: 'l17', source: 's2',  target: 's6',  bw: 10  },
      { id: 'l18', source: 's2',  target: 's3',  bw: 10  },
      { id: 'l19', source: 's2',  target: 's7',  bw: 10  },
      // Distribution → Core (4×4 full bipartite Clos)
      { id: 'l20', source: 's8',  target: 's9',  bw: 10  },
      { id: 'l21', source: 's8',  target: 's4',  bw: 10  },
      { id: 'l22', source: 's8',  target: 's10', bw: 10  },
      { id: 'l23', source: 's8',  target: 's11', bw: 10  },
      { id: 'l24', source: 's6',  target: 's9',  bw: 10  },
      { id: 'l25', source: 's6',  target: 's4',  bw: 10  },
      { id: 'l26', source: 's6',  target: 's10', bw: 10  },
      { id: 'l27', source: 's6',  target: 's11', bw: 10  },
      { id: 'l28', source: 's3',  target: 's9',  bw: 10  },
      { id: 'l29', source: 's3',  target: 's4',  bw: 10  },
      { id: 'l30', source: 's3',  target: 's10', bw: 10  },
      { id: 'l31', source: 's3',  target: 's11', bw: 10  },
      { id: 'l32', source: 's7',  target: 's9',  bw: 10  },
      { id: 'l33', source: 's7',  target: 's4',  bw: 10  },
      { id: 'l34', source: 's7',  target: 's10', bw: 10  },
      { id: 'l35', source: 's7',  target: 's11', bw: 10  },
      // Core → Aggregation (4×2)
      { id: 'l36', source: 's9',  target: 's12', bw: 10  },
      { id: 'l37', source: 's9',  target: 's13', bw: 10  },
      { id: 'l38', source: 's4',  target: 's12', bw: 10  },
      { id: 'l39', source: 's4',  target: 's13', bw: 10  },
      { id: 'l40', source: 's10', target: 's12', bw: 10  },
      { id: 'l41', source: 's10', target: 's13', bw: 10  },
      { id: 'l42', source: 's11', target: 's12', bw: 10  },
      { id: 'l43', source: 's11', target: 's13', bw: 10  },
      // Aggregation → Egress
      { id: 'l44', source: 's12', target: 's14', bw: 10  },
      { id: 'l45', source: 's13', target: 's14', bw: 10  },
      // Host uplinks (100 Mbps)
      { id: 'l9',  source: 'h1',  target: 's1',  bw: 100 },
      { id: 'l46', source: 's14', target: 'h2',  bw: 100 },
      { id: 'l47', source: 's2',  target: 'h3',  bw: 100 },
      { id: 'l48', source: 's7',  target: 'h4',  bw: 100 }, // dual-homed
      { id: 'l49', source: 's11', target: 'h4',  bw: 100 }, // dual-homed
      { id: 'l50', source: 's7',  target: 'h5',  bw: 100 }, // dual-homed
      { id: 'l51', source: 's11', target: 'h5',  bw: 100 }, // dual-homed
      { id: 'l52', source: 's13', target: 'h6',  bw: 100 },
      { id: 'l53', source: 'h7',  target: 's5',  bw: 100 },
      { id: 'l54', source: 'h8',  target: 's8',  bw: 100 }, // dual-homed
      { id: 'l55', source: 'h8',  target: 's9',  bw: 100 }, // dual-homed
      { id: 'l56', source: 's9',  target: 'h9',  bw: 100 }, // dual-homed
      { id: 'l57', source: 's8',  target: 'h9',  bw: 100 }, // dual-homed
      { id: 'l58', source: 'h10', target: 's12', bw: 100 },
    ],
  },
};

const STAGE_DEFS = [
  { num: 1, name: '① Intent Parsing' },
  { num: 2, name: '② FlowRule Compile' },
  { num: 3, name: '③ Static Validation' },
  { num: 4, name: '④ Digital Twin' },
  { num: 5, name: '⑤ XAI Explanation' },
  { num: 6, name: '⑥ ONOS Deploy' },
];

// ── State ─────────────────────────────────────────────────────────────────────

// 스테이지 카드가 running 상태로 최소 이 시간(ms)은 보이도록 보장
const MIN_STAGE_VISIBLE_MS = 700;
const _stageRunningAt = {}; // stageNum → Date.now() when running was shown

const state = {
  intent: '',
  model: 'gemini-3.1-flash-lite',
  enableRag: false,
  skipTwin: false,
  skipDeploy: false,
  running: false,
  stages: STAGE_DEFS.map(s => ({
    ...s,
    status: 'idle',   // idle | running | done | error | skipped
    elapsed: null,
    result: null,
    expanded: false,
    progress_log: [],
  })),
  decision: null,
  decisionReport: null,
  deployFailed: false,
  confidenceBreakdown: {},
  history: [],
  refreshIn: 1,
  twinActive: false,
  // Flow State
  topologyId: 'custom',          // 현재 선택된 토폴로지 ID
  preloadedFlows: [],             // Load State로 불러온 FlowRule 목록
};

// ── Network Preset (Live Traffic) 상태 ────────────────────────────────────────
// LIVE_NETWORK_PRESET_PLAN.md 6-4장. LiveNetworkSession의 apply/stream/stop을
// 사용해 프리셋을 켜고 실시간 링크 통계를 토폴로지 그래프에 색으로 얹는다.

let allTrafficPresets = [];   // GET /api/traffic-presets 캐시
let netPresetState = {
  status: 'idle',              // idle | starting | running | stopping | error
  topologyId: '',
  trafficPresetId: '',
  error: '',
  linksById: {},                // link_id → {source,target,bw_mbps,throughput_mbps,util_pct,dropped_delta,backlog_bytes}
  flows: [],                    // [{id,src,dst,proto,target_mbps,actual_mbps}, ...]
};
let netPresetStatsMap = new Map(); // "of:dpidA|of:dpidB" → 같은 link 통계 (링크 색칠용)
let netPresetAnimTimers = [];       // 라이브 트래픽 패킷 애니메이션 타이머 (twinAnimTimers와 별개)

function _fmtBytes(n) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return `${n}B`;
}

function _netPresetPairKey(d) {
  const a = d.source?.id ?? d.source;
  const b = d.target?.id ?? d.target;
  return [a, b].sort().join('|');
}

function _netPresetTopoDef(topologyId) {
  return TOPOLOGY_PRESETS[topologyId] || null;
}

function buildNetPresetStatsMap() {
  const map = new Map();
  if (netPresetState.status === 'idle') return map;
  const topo = _netPresetTopoDef(netPresetState.topologyId);
  if (!topo) return map;
  const dpidOf = {};
  topo.switches.forEach(sw => { dpidOf[sw.id] = `of:${sw.dpid}`; });
  Object.values(netPresetState.linksById).forEach(l => {
    const a = dpidOf[l.source], b = dpidOf[l.target];
    if (!a || !b) return;
    map.set([a, b].sort().join('|'), l);
  });
  return map;
}

// bwLinkColor/bwLinkStroke를 대체하는 utilization 기반 색상 — null 반환 시
// 호출부가 기존 bw 기반 스타일로 fall back한다.
function netPresetLinkColor(d) {
  if (netPresetState.status !== 'running' && netPresetState.status !== 'starting') return null;
  const s = netPresetStatsMap.get(_netPresetPairKey(d));
  if (!s) return null;
  if (s.util_pct >= 90) return '#ef4444';
  if (s.util_pct >= 60) return '#f59e0b';
  if (s.util_pct > 0)   return '#10b981';
  return '#374151';
}

function netPresetLinkStroke(d) {
  if (netPresetState.status !== 'running' && netPresetState.status !== 'starting') return null;
  const s = netPresetStatsMap.get(_netPresetPairKey(d));
  if (!s) return null;
  return 1.5 + Math.min(s.util_pct, 150) / 100 * 2.5;
}

function netPresetTooltip(d) {
  const s = netPresetStatsMap.get(_netPresetPairKey(d));
  if (!s) return null;
  return `${s.throughput_mbps.toFixed(1)}/${s.bw_mbps}Mbps (${s.util_pct.toFixed(0)}%)\n` +
         `dropped +${s.dropped_delta}\nbacklog ${s.backlog_bytes}B`;
}

// 링크 중점에 표시할 실측 처리량 텍스트 ("4.6M") — null이면 호출부가
// bwLabelsVisible 여부에 따라 정적 용량 텍스트로 fall back한다.
function netPresetLinkLabel(d) {
  if (netPresetState.status !== 'running' && netPresetState.status !== 'starting') return null;
  const s = netPresetStatsMap.get(_netPresetPairKey(d));
  if (!s) return null;
  return `${s.throughput_mbps.toFixed(1)}M`;
}

// 링크 중점 두 번째 줄에 표시할 손실/큐 백로그 텍스트 ("drop+3 q1.2K") —
// 엄밀한 RTT는 아니고 드롭 카운트 + 큐 백로그 기반 지연 근사치임에 주의
// (LIVE_NETWORK_PRESET_PLAN.md 6-1장). 문제 없는 링크는 아무것도 안 보여준다.
function netPresetLinkIssue(d) {
  const s = netPresetStatsMap.get(_netPresetPairKey(d));
  if (!s) return null;
  const parts = [];
  if (s.dropped_delta > 0) parts.push(`drop+${s.dropped_delta}`);
  if (s.backlog_bytes > 0) parts.push(`q${_fmtBytes(s.backlog_bytes)}`);
  return parts.length ? parts.join(' ') : null;
}

// 현재 렌더된 토폴로지 그래프의 링크 selection에 색/두께/툴팁/대역폭 텍스트를
// 다시 입힌다. updateTopology()의 다음 폴링을 기다리지 않고 SSE 이벤트마다
// 즉시 반영하기 위함.
function applyNetPresetColors() {
  netPresetStatsMap = buildNetPresetStatsMap();
  if (!topoZoomLayer) return;
  const link = topoZoomLayer.select('.links').selectAll('line');
  link
    .attr('stroke',       d => netPresetLinkColor(d)  ?? (bwLabelsVisible ? bwLinkColor(d.bw) : '#374151'))
    .attr('stroke-width', d => netPresetLinkStroke(d) ?? (bwLabelsVisible ? bwLinkStroke(d.bw) : 1.5));
  link.each(function(d) {
    const info = netPresetTooltip(d);
    const sel = d3.select(this);
    sel.select('title').remove();
    if (info) sel.append('title').text(info);
  });

  const showBwLayer = bwLabelsVisible || netPresetStatsMap.size > 0;
  topoZoomLayer.select('.bw-labels').style('display', showBwLayer ? null : 'none');
  topoZoomLayer.select('.bw-labels').selectAll('text.live-bw')
    .attr('fill', d => netPresetLinkColor(d) ?? bwLinkColor(d.bw))
    .text(d => netPresetLinkLabel(d) ?? (bwLabelsVisible ? `${d.bw}M` : ''));
  topoZoomLayer.select('.bw-labels').selectAll('text.live-issue')
    .text(d => netPresetLinkIssue(d) || '');

  updateNetPresetPacketAnim();
}

// ── 라이브 트래픽 패킷 애니메이션 ──────────────────────────────────────────────
// twinAnimTimers/.twin-viz와 완전히 별개 레이어·타이머를 써서 Digital Twin
// 시각화와 동시에 떠 있어도 서로 안 건드린다. 링크 자체의 색/두께는 이미
// utilization으로 표현하므로, 여기선 highlightPath()를 부르지 않고 패킷 점만
// spawnPacket()으로 재사용해 찍는다.

function getNetPresetLayer() {
  if (!topoZoomLayer) return null;
  let layer = topoZoomLayer.select('.netpreset-viz');
  if (layer.empty()) layer = topoZoomLayer.append('g').attr('class', 'netpreset-viz');
  return layer;
}

function stopNetPresetPacketAnim() {
  netPresetAnimTimers.forEach(t => clearTimeout(t));
  netPresetAnimTimers = [];
  if (topoZoomLayer) topoZoomLayer.select('.netpreset-viz').selectAll('*').remove();
}

function startNetPresetPacketLoop(path, color) {
  if (!path || path.length < 2) return;
  const totalMs = Math.min(1800, path.length * 450);
  const interval = 650;

  function fire() {
    if (netPresetState.status !== 'running' && netPresetState.status !== 'starting') return;
    const layer = getNetPresetLayer();
    if (!layer) return;
    spawnPacket(layer, path, color, totalMs, undefined);
    const t = setTimeout(fire, interval);
    netPresetAnimTimers.push(t);
  }
  fire();
  const t2 = setTimeout(fire, interval / 2); // 두 번째 스트림 (오프셋)
  netPresetAnimTimers.push(t2);
}

// 활성 flow마다 호스트→호스트 경로를 찾아 패킷 루프를 (재)시작한다.
// 색은 목표 대비 실측 비율로 정해서(netPresetFlowColor), 병목 때문에 밀리는
// flow는 자연스럽게 빨간 점으로 보인다.
function updateNetPresetPacketAnim() {
  stopNetPresetPacketAnim();
  renderNetPresetFlowBadges();
  if (netPresetState.status !== 'running' && netPresetState.status !== 'starting') return;
  if (!currentTopoNodes.length) return;

  netPresetState.flows.forEach(f => {
    const srcNode = currentTopoNodes.find(n => n.type === 'host' && n.id === f.src);
    const dstNode = currentTopoNodes.find(n => n.type === 'host' && n.id === f.dst);
    if (!srcNode || !dstNode) return;
    const path = findTopoPath(srcNode.id, dstNode.id);
    if (!path) return;
    startNetPresetPacketLoop(path, netPresetFlowColor(f));
  });
}

// flow별 실측 대역폭을 src-dst 경로 중점에 작은 배지로 표시 — 사이드 패널이
// 아니라 토폴로지 위에서 바로 보이게 하기 위함(onTwinBw의 배지 패턴 재사용).
function renderNetPresetFlowBadges() {
  const layer = getNetPresetLayer();
  if (!layer) return;
  layer.selectAll('.netpreset-flow-badge').remove();
  if (netPresetState.status !== 'running' && netPresetState.status !== 'starting') return;

  netPresetState.flows.forEach(f => {
    const srcNode = currentTopoNodes.find(n => n.type === 'host' && n.id === f.src);
    const dstNode = currentTopoNodes.find(n => n.type === 'host' && n.id === f.dst);
    if (!srcNode || !dstNode) return;
    const srcPos = nodePositions.get(srcNode.id);
    const dstPos = nodePositions.get(dstNode.id);
    if (!srcPos || !dstPos) return;

    const mx = (srcPos.x + dstPos.x) / 2;
    const my = (srcPos.y + dstPos.y) / 2;
    const color = netPresetFlowColor(f);

    const badge = layer.append('g')
      .attr('class', 'netpreset-flow-badge')
      .attr('transform', `translate(${mx},${my})`);
    badge.append('rect')
      .attr('x', -22).attr('y', -8).attr('width', 44).attr('height', 16).attr('rx', 4)
      .attr('fill', '#0a0e1a').attr('stroke', color).attr('stroke-width', 1);
    badge.append('text')
      .attr('text-anchor', 'middle').attr('dy', '0.35em')
      .attr('font-size', 8).attr('font-family', 'JetBrains Mono, monospace')
      .attr('fill', color).attr('pointer-events', 'none')
      .text(`${f.actual_mbps.toFixed(1)}M`);
  });
}

function renderNetPresetStatus() {
  const statusEl = document.getElementById('netpreset-status');
  const stopBtn  = document.getElementById('netpreset-stop-btn');
  const applyBtn = document.getElementById('netpreset-apply-btn');
  if (!statusEl || !stopBtn || !applyBtn) return;

  const labelMap = {
    idle: '대기', starting: '기동 중… (수십 초 소요될 수 있음)',
    running: '실행 중', stopping: '정지 중…', error: '오류',
  };
  let text = labelMap[netPresetState.status] || netPresetState.status;
  if (netPresetState.status === 'running' && netPresetState.trafficPresetId) {
    text += ` — ${netPresetState.trafficPresetId}`;
  }
  if (netPresetState.status === 'error' && netPresetState.error) {
    text += `: ${netPresetState.error}`;
  }
  statusEl.textContent = text;
  statusEl.className = `netpreset-status netpreset-status-${netPresetState.status}`;

  const active = netPresetState.status === 'starting'
    || netPresetState.status === 'running'
    || netPresetState.status === 'stopping';
  stopBtn.style.display  = active ? '' : 'none';
  applyBtn.style.display = active ? 'none' : '';
}

function handleNetPresetEvent(ev) {
  netPresetState.status = ev.status;
  netPresetState.topologyId = ev.topology_id;
  netPresetState.trafficPresetId = ev.traffic_preset_id;
  netPresetState.error = ev.error || '';
  netPresetState.linksById = {};
  (ev.links || []).forEach(l => { netPresetState.linksById[l.id] = l; });
  netPresetState.flows = ev.flows || [];
  renderNetPresetStatus();
  renderNetPresetFlows();
  applyNetPresetColors();
}

// flow의 실제 대역폭이 목표치 대비 얼마나 못 미치는지로 색 결정
// (많이 못 미치면 그만큼 다른 flow와 경합 중이라는 신호)
function netPresetFlowColor(f) {
  if (!f.target_mbps) return '#9ca3af';
  const ratio = f.actual_mbps / f.target_mbps;
  if (ratio >= 0.85) return '#10b981';
  if (ratio >= 0.5)  return '#f59e0b';
  return '#ef4444';
}

function renderNetPresetFlows() {
  const container = document.getElementById('netpreset-flows');
  if (!container) return;
  if (netPresetState.status === 'idle' || netPresetState.flows.length === 0) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = netPresetState.flows.map(f => `
    <div class="netpreset-flow-row">
      <span class="netpreset-flow-dir">
        [${escHtml(f.id)}] ${escHtml(f.src)} → ${escHtml(f.dst)}
        <span class="netpreset-flow-proto">${escHtml((f.proto || '').toUpperCase())}</span>
      </span>
      <span class="netpreset-flow-bw" style="color:${netPresetFlowColor(f)}">
        ${f.actual_mbps.toFixed(1)}/${f.target_mbps.toFixed(0)}Mbps
      </span>
    </div>
  `).join('');
}

async function startNetworkPresetStream() {
  try {
    const resp = await fetch('/api/network-preset/stream');
    if (!resp.ok || !resp.body) return;
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const chunks = buf.split('\n\n');
      buf = chunks.pop();
      for (const chunk of chunks) {
        const line = chunk.trim();
        if (!line.startsWith('data: ')) continue;
        try {
          const parsed = JSON.parse(line.slice(6));
          if (parsed.type === 'link_stats') handleNetPresetEvent(parsed);
        } catch { /* skip malformed */ }
      }
    }
  } catch (err) {
    console.error('[NetworkPreset] stream error:', err);
  } finally {
    renderNetPresetStatus();
  }
}

async function loadTrafficPresets() {
  try {
    const resp = await fetch('/api/traffic-presets');
    allTrafficPresets = await resp.json();
  } catch (err) {
    console.error('[NetworkPreset] failed to load traffic presets:', err);
    allTrafficPresets = [];
  }
  renderTrafficPresetOptions();
}

function renderTrafficPresetOptions() {
  const sel = document.getElementById('netpreset-select');
  if (!sel) return;
  sel.innerHTML = '';

  const placeholder = document.createElement('option');
  placeholder.textContent = '— 트래픽 프리셋 선택 —';
  placeholder.disabled = true;
  placeholder.selected = true;
  sel.appendChild(placeholder);

  const byTopo = {};
  allTrafficPresets.forEach(p => {
    (byTopo[p.topology_id] ||= []).push(p);
  });

  Object.keys(byTopo).sort().forEach(topoId => {
    const grp = document.createElement('optgroup');
    grp.label = topoId;
    byTopo[topoId].forEach(p => {
      const opt = document.createElement('option');
      opt.value = `${topoId}::${p.id}`;
      opt.textContent = p.flow_count > 0 ? `${p.label} (${p.flow_count} flow)` : p.label;
      opt.dataset.topologyId = topoId;
      opt.dataset.presetId = p.id;
      grp.appendChild(opt);
    });
    sel.appendChild(grp);
  });
}

async function applyNetworkPreset() {
  const sel = document.getElementById('netpreset-select');
  const opt = sel && sel.selectedOptions[0];
  if (!opt || !opt.dataset.topologyId) {
    alert('트래픽 프리셋을 선택하세요.');
    return;
  }
  const topologyId = opt.dataset.topologyId;
  const trafficPresetId = opt.dataset.presetId || '';

  const applyBtn = document.getElementById('netpreset-apply-btn');
  const origText = applyBtn.textContent;
  applyBtn.disabled = true;
  applyBtn.textContent = '적용 중…';

  try {
    // 선택한 트래픽 프리셋의 토폴로지가 현재 그래프와 다르면 먼저 맞춰준다
    // (기존 "⊞ Presets" 버튼과 동일한 경로로 저장 + ONOS netcfg push).
    if (state.topologyId !== topologyId && TOPOLOGY_PRESETS[topologyId]) {
      await applyPreset(topologyId);
    }

    const resp = await fetch('/api/network-preset/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topology_id: topologyId, traffic_preset_id: trafficPresetId }),
    });

    if (resp.status === 409) {
      alert('이미 실행 중인 네트워크 프리셋 세션이 있습니다.');
      return;
    }
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      alert(`적용 실패: ${body.detail || resp.status}`);
      return;
    }

    netPresetState.status = 'starting';
    netPresetState.topologyId = topologyId;
    netPresetState.trafficPresetId = trafficPresetId;
    netPresetState.error = '';
    renderNetPresetStatus();
    startNetworkPresetStream();
  } catch (err) {
    console.error('[NetworkPreset] apply failed:', err);
  } finally {
    applyBtn.disabled = false;
    applyBtn.textContent = origText;
  }
}

async function stopNetworkPreset() {
  const stopBtn = document.getElementById('netpreset-stop-btn');
  const origText = stopBtn.textContent;
  stopBtn.disabled = true;
  stopBtn.textContent = '정지 중…';
  try {
    await fetch('/api/network-preset/stop', { method: 'POST' });
  } catch (err) {
    console.error('[NetworkPreset] stop failed:', err);
  } finally {
    stopBtn.disabled = false;
    stopBtn.textContent = origText;
  }
}

async function initNetworkPresetPanel() {
  const applyBtn = document.getElementById('netpreset-apply-btn');
  const stopBtn  = document.getElementById('netpreset-stop-btn');
  if (applyBtn) applyBtn.addEventListener('click', applyNetworkPreset);
  if (stopBtn)  stopBtn.addEventListener('click', stopNetworkPreset);

  await loadTrafficPresets();

  // 새로고침으로 페이지가 다시 열렸을 때 이미 실행 중인 세션을 이어서 표시
  try {
    const resp = await fetch('/api/network-preset/status');
    const data = await resp.json();
    handleNetPresetEvent({ type: 'link_stats', ...data });
    if (data.status === 'starting' || data.status === 'running') {
      startNetworkPresetStream();
    }
  } catch (err) {
    console.error('[NetworkPreset] status fetch failed:', err);
  }
}

// ── Pipeline ──────────────────────────────────────────────────────────────────

async function runPipeline() {
  if (state.running || !state.intent.trim()) return;

  state.running = true;
  state.decision = null;
  state.decisionReport = null;
  state.deployFailed = false;
  state.confidenceBreakdown = {};
  state.stages.forEach(s => {
    s.status = 'idle'; s.elapsed = null; s.result = null; s.expanded = false; s.progress_log = [];
  });
  Object.keys(_stageRunningAt).forEach(k => delete _stageRunningAt[k]);
  buildStageCards();   // 이전 실행 카드 DOM 전체 초기화
  renderDecision();
  setRunBtn(true);

  try {
    const resp = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        intent: state.intent,
        model: state.model,
        rag_k: 3,
        no_rag: !state.enableRag,
        skip_twin: state.skipTwin,
        skip_deploy: state.skipDeploy,
        topology_id: state.topologyId,
        preloaded_flows: state.preloadedFlows,
      }),
    });

    if (!resp.ok) throw new Error(`Server error: ${resp.status}`);

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const chunks = buf.split('\n\n');
      buf = chunks.pop(); // keep incomplete chunk
      for (const chunk of chunks) {
        const line = chunk.trim();
        if (line.startsWith('data: ')) {
          try {
            handleSSEEvent(JSON.parse(line.slice(6)));
          } catch { /* skip malformed */ }
        }
      }
    }
  } catch (err) {
    console.error('Pipeline error:', err);
  } finally {
    state.running = false;
    setRunBtn(false);
    loadHistory();
  }
}

function handleSSEEvent(ev) {
  if (ev.type === 'progress') {
    const s = state.stages[ev.stage - 1];
    s.progress_log.push(ev.msg);
    appendLogLine(ev.stage, ev.msg);
    // Digital Twin 단계별 시각화 페이즈 전환
    if (ev.stage === 4 && state.twinActive && twinVizInfoList.length) {
      const m = ev.msg;
      if (m.includes('⑤') && m.includes('[baseline]'))        setTwinPhase('baseline');
      else if (m.includes('⑥') && m.includes('FlowRule'))     setTwinPhase('deployed');
      else if (m.includes('⑦') && m.includes('[intent'))       setTwinPhase('intent');
      else if (m.includes('⑧') && m.includes('[regression]')) setTwinPhase('regression');
    }
  } else if (ev.type === 'stage') {
    const s = state.stages[ev.stage - 1];

    if (ev.status === 'running') {
      // 즉시 카드 생성 + running 상태 표시
      s.status = 'running';
      ensureStageCard(ev.stage);
      if (ev.stage === 4) {
        s.expanded = true;
        state.twinActive = true;
        twinVizInfoList = [];
      }
      _stageRunningAt[ev.stage] = Date.now();
      renderStage(ev.stage - 1);
      renderPipelineProgress();
    } else {
      // done / error / skipped: running 상태를 최소 MIN_STAGE_VISIBLE_MS 동안 보여준 뒤 전환
      ensureStageCard(ev.stage); // skipped처럼 running 없이 끝나는 경우 대비

      const applyFinal = () => {
        s.status = ev.status;
        if (ev.elapsed != null) s.elapsed = ev.elapsed;
        if (ev.result != null) s.result = ev.result;
        if (ev.error != null) s.result = { error: ev.error };
        if (ev.status === 'error') s.expanded = true;
        if (ev.stage === 4) {
          s.expanded = false;
          state.twinActive = false;
          stopTwinViz();
          topoSnapshot = null;
          fetchTopology();
        }
        renderStage(ev.stage - 1);
        renderPipelineProgress();
      };

      const ranAt = _stageRunningAt[ev.stage];
      if (ranAt) {
        const waited = Date.now() - ranAt;
        const delay  = Math.max(0, MIN_STAGE_VISIBLE_MS - waited);
        if (delay > 0) setTimeout(applyFinal, delay);
        else applyFinal();
      } else {
        // running 이벤트 없이 바로 종료 (skip 등): 카드 진입 애니메이션만 기다림
        setTimeout(applyFinal, 120);
      }
    }
  } else if (ev.type === 'twin_info') {
    onTwinInfo(ev);
  } else if (ev.type === 'twin_bw') {
    onTwinBw(ev);
  } else if (ev.type === 'decision') {
    state.decision = ev.decision;
    state.decisionReport = ev.report;
    state.deployFailed = !!ev.deploy_failed;
    state.confidenceBreakdown = (ev.report && ev.report.confidence_breakdown) || {};
    // REJECT 시 실패한 단계 모두 자동 펼치기
    if (ev.decision === 'REJECT') {
      state.stages.forEach(s => {
        if (s.status === 'error' || (s.status === 'done' && s.result && !s.result.passed)) {
          s.expanded = true;
          renderStage(s.num - 1);
        }
      });
    }
    renderConfidenceBadges();
    renderDecision();
  }
}

// ── API Calls ─────────────────────────────────────────────────────────────────

// Last successful topology snapshot (JSON string for cheap diffing)
let topoSnapshot = null;

async function fetchTopology() {
  if (editor.active) return; // don't overwrite editor canvas
  try {
    const resp = await fetch('/api/topology');
    const data = await resp.json();

    if (data.error) {
      // ONOS 오프라인 — 이전 데이터 유지 (초기화하지 않음)
      if (!topoSnapshot) showTopoError(data.error);
      return;
    }

    // Digital Twin 실행 중: Mininet 가상 스위치가 ONOS에 연결되어
    // 토폴로지가 교란됨 → 표시 업데이트를 중단하고 이전 스냅샷 유지
    if (state.twinActive) return;

    // 변경 감지: nodes/links/flow_table/rule_count만 비교 (D3 좌표 제외)
    const key = JSON.stringify({
      nodes: data.nodes,
      links: data.links,
      flow_table: data.flow_table,
      rule_count: data.rule_count,
    });

    if (key === topoSnapshot) return; // 변경 없으면 렌더 스킵
    topoSnapshot = key;

    updateTopology(data);
    updateMetrics(data);
    updateHostLegend(data);
    updateFlowTable(data);
  } catch {
    // 네트워크 오류 — 이전 데이터 유지
  }
}

async function loadHistory() {
  try {
    const resp = await fetch('/api/logs');
    state.history = await resp.json();
    renderHistory();
  } catch { /* silent */ }
}

// ── Rendering ─────────────────────────────────────────────────────────────────

const PP_LABELS = ['NLP', 'Flow', 'Validate', 'Twin', 'XAI', 'Deploy'];

function renderPipelineProgress() {
  const el       = document.getElementById('pipeline-progress');
  const track    = document.getElementById('pp-track');
  const steps    = document.getElementById('pp-steps');
  const nameEl   = document.getElementById('pp-stage-name');
  const counterEl = document.getElementById('pp-counter');
  const pctEl    = document.getElementById('pp-pct');

  const anyActive = state.stages.some(s => s.status !== 'idle');
  if (!anyActive) { el.style.display = 'none'; return; }
  el.style.display = 'block';

  const running   = state.stages.find(s => s.status === 'running');
  const doneCount = state.stages.filter(s => ['done', 'skipped', 'error'].includes(s.status)).length;
  const total     = state.stages.length;
  const pctVal    = Math.round(doneCount / total * 100);

  if (running) {
    nameEl.textContent = running.name.replace(/^[①②③④⑤⑥]\s*/, '');
    nameEl.style.color = '#60a5fa';
  } else {
    const last = [...state.stages].reverse().find(s => s.status !== 'idle');
    if (last) {
      if (last.status === 'error') {
        nameEl.textContent = '✕ ' + last.name.replace(/^[①②③④⑤⑥]\s*/, '');
        nameEl.style.color = '#ef4444';
      } else if (doneCount === total) {
        nameEl.textContent = '✓ Pipeline Complete';
        nameEl.style.color = '#10b981';
      } else {
        nameEl.textContent = last.name.replace(/^[①②③④⑤⑥]\s*/, '');
        nameEl.style.color = '#9ca3af';
      }
    }
  }

  counterEl.textContent = `${doneCount} / ${total}`;
  pctEl.textContent = ` · ${pctVal}%`;

  // Rebuild segments (only replace content if changed to avoid restarting CSS animation)
  const segs  = track.querySelectorAll('.pp-seg');
  const stps  = steps.querySelectorAll('.pp-step');
  state.stages.forEach((s, i) => {
    const segClass  = `pp-seg${s.status !== 'idle' ? ' seg-' + s.status : ''}`;
    const stepClass = `pp-step${s.status !== 'idle' ? ' step-' + s.status : ''}`;
    if (segs[i]) {
      segs[i].className = segClass;
    } else {
      const seg = document.createElement('div');
      seg.className = segClass;
      track.appendChild(seg);
    }
    if (stps[i]) {
      stps[i].className = stepClass;
    } else {
      const step = document.createElement('div');
      step.className = stepClass;
      step.textContent = PP_LABELS[i] || s.num;
      steps.appendChild(step);
    }
  });
}

function buildStageCards() {
  const section = document.getElementById('stages-section');
  const ppEl    = document.getElementById('pipeline-progress');
  const cards   = Array.from(section.querySelectorAll('.stage-card'));
  if (cards.length === 0) {
    section.style.display = 'none';
    ppEl.style.display = 'none';
    return;
  }
  // 기존 카드 + progress bar fade-out 후 제거
  ppEl.style.opacity = '0';
  ppEl.style.transition = 'opacity 0.3s ease';
  cards.forEach(card => card.classList.add('stage-card-exit'));
  setTimeout(() => {
    section.innerHTML = '';
    section.style.display = 'none';
    ppEl.style.display = 'none';
    ppEl.style.opacity = '';
    ppEl.style.transition = '';
    document.getElementById('pp-track').innerHTML = '';
    document.getElementById('pp-steps').innerHTML = '';
  }, 350);
}

function ensureStageCard(stageNum) {
  const section = document.getElementById('stages-section');
  if (document.getElementById(`stage-${stageNum}`)) return;

  const i   = stageNum - 1;
  const def = STAGE_DEFS[i];
  const card = document.createElement('div');
  card.className = 'stage-card stage-card-enter';
  card.id = `stage-${def.num}`;
  const hasConf = def.num === 3 || def.num === 4;
  card.innerHTML = `
    <div class="stage-header" data-idx="${i}">
      <div class="stage-badge" id="badge-${def.num}">${def.num}</div>
      <div class="stage-name">${def.name}</div>
      <div class="stage-time" id="time-${def.num}">—</div>
      ${hasConf ? `<div class="stage-conf" id="conf-${def.num}" style="display:none"></div>` : ''}
      <div class="stage-icon" id="icon-${def.num}">${iconDot()}</div>
    </div>
    <div class="stage-progress" id="progress-${def.num}">
      <div class="stage-progress-bar" id="progress-bar-${def.num}"></div>
    </div>
    <div class="live-log" id="live-${def.num}"></div>
    <div class="stage-detail" id="detail-${def.num}"></div>
  `;
  card.querySelector('.stage-header').addEventListener('click', () => {
    state.stages[i].expanded = !state.stages[i].expanded;
    renderStage(i);
  });
  section.style.display = 'flex';
  section.appendChild(card);
  // Double RAF: first frame paints opacity:0/translateY(12px), second triggers CSS transition
  requestAnimationFrame(() => requestAnimationFrame(() => card.classList.remove('stage-card-enter')));
}

function renderAllStages() {
  state.stages.forEach((_, i) => renderStage(i));
}

function renderStage(i) {
  const s = state.stages[i];
  const n = s.num;

  const card    = document.getElementById(`stage-${n}`);
  const badge   = document.getElementById(`badge-${n}`);
  const timeEl  = document.getElementById(`time-${n}`);
  const iconEl  = document.getElementById(`icon-${n}`);
  const liveEl  = document.getElementById(`live-${n}`);
  const detail  = document.getElementById(`detail-${n}`);
  const progBar = document.getElementById(`progress-bar-${n}`);

  if (!card) return;

  // Card border
  card.className = `stage-card${s.status === 'running' ? ' border-running' : s.status === 'error' ? ' border-error' : ''}`;

  // Badge
  badge.className = s.status === 'idle' ? 'stage-badge' : `stage-badge badge-${s.status}`;
  badge.textContent = n;

  // Time
  timeEl.textContent = s.elapsed != null ? `${s.elapsed}s` : '—';

  // Icon
  iconEl.innerHTML = statusIcon(s.status);

  // Progress bar
  if (progBar) {
    progBar.className = 'stage-progress-bar';
    if (s.status === 'running')  progBar.classList.add('bar-running');
    else if (s.status === 'done')    progBar.classList.add('bar-done');
    else if (s.status === 'error')   progBar.classList.add('bar-error');
    else if (s.status === 'skipped') progBar.classList.add('bar-skipped');
    // idle: no extra class → invisible
  }

  // Live log: running 중에만 표시, 완료 시 "current" 강조 해제
  if (liveEl) {
    if (s.status === 'running') {
      liveEl.style.display = 'block';
    } else {
      liveEl.style.display = 'none';
      // 완료 후 current 라인 일반화 (다음 실행 대비)
      liveEl.querySelectorAll('.log-line.current').forEach(el => {
        el.classList.remove('current');
        el.classList.add('done');
      });
    }
  }

  // Detail (클릭 확장)
  if (s.expanded && s.result) {
    detail.className = 'stage-detail open';
    detail.innerHTML = renderStageDetail(s);
  } else {
    detail.className = 'stage-detail';
    detail.innerHTML = '';
  }
}

// ── Stage Detail Renderers ────────────────────────────────────────────────────

function renderStageDetail(s) {
  const r = s.result;
  if (!r) return '';
  if (r.error) return `<div class="sd-section"><span class="sd-badge sd-badge-error">Error</span><div class="sd-reason">${escHtml(String(r.error))}</div></div>`;
  try {
    switch (s.num) {
      case 1: return renderSD1(r);
      case 2: return renderSD2(r);
      case 3: return renderSD3(r);
      case 4: return renderSD4(r);
      case 5: return renderSD5(r);
      case 6: return renderSD6(r);
      default: return `<pre style="font-size:11px;color:#9ca3af;white-space:pre-wrap">${escHtml(JSON.stringify(r, null, 2))}</pre>`;
    }
  } catch(e) {
    return `<pre style="font-size:11px;color:#9ca3af;white-space:pre-wrap">${escHtml(JSON.stringify(r, null, 2))}</pre>`;
  }
}

/* Stage 1 — Intent Parsing */
function renderSD1(r) {
  if (r.status === 'rejected') {
    return `<div class="sd-section">
      <span class="sd-badge sd-badge-error">Rejected</span>
      <div class="sd-reason">${escHtml(r.rejection_reason || '')}${r.rejection_detail ? '<br><span style="color:#6b7280">' + escHtml(r.rejection_detail) + '</span>' : ''}</div>
    </div>`;
  }
  const compound = r.compound;
  const ir = r.program;
  if (compound) {
    const rules = compound.rules || [];
    return `<div class="sd-section"><span class="sd-badge sd-badge-info">Compound Intent</span>${compound.description ? `<div class="sd-desc">${escHtml(compound.description)}</div>` : ''}</div>` +
      rules.map((rule, i) => `<div class="sd-section"><div class="sd-label">Sub-rule ${i + 1} — ${(rule.action || '').toUpperCase()}</div>${irTable(rule)}</div>`).join('');
  }
  if (ir) {
    const cls = ir.action === 'block' ? 'sd-badge-block' : ir.action === 'forward' ? 'sd-badge-forward' : 'sd-badge-info';
    return `<div class="sd-section"><span class="sd-badge ${cls}">${(ir.action || 'INTENT').toUpperCase()}</span></div>
      <div class="sd-section">${irTable(ir)}</div>`;
  }
  return `<div class="sd-section"><span class="sd-badge sd-badge-ok">Accepted</span></div>`;
}

function irTable(ir) {
  const rows = [
    ['Action', ir.action], ['Intent Type', ir.intent_type],
    ['Device', ir.device_hint], ['Src IP', ir.src_ip], ['Dst IP', ir.dst_ip],
    ['Protocol', ir.ip_proto ?? ir.eth_type], ['Src Port', ir.src_port],
    ['Dst Port', ir.dst_port], ['In Port', ir.in_port], ['Out Port', ir.out_port],
    ['Alt Port', ir.alt_out_port], ['Priority', ir.priority],
    ['Waypoints', Array.isArray(ir.waypoints) ? ir.waypoints.join(' → ') : ir.waypoints],
  ].filter(([, v]) => v != null && v !== '');
  return `<table class="sd-table">${rows.map(([k,v]) =>
    `<tr><td class="sd-key">${k}</td><td class="sd-val">${escHtml(String(v))}</td></tr>`).join('')}</table>`;
}

/* Stage 2 — FlowRule Compile */
function renderSD2(r) {
  const flows = r.flows || [];
  const action = (r.intent_action || '').toLowerCase();
  const badgeCls = action === 'block' ? 'sd-badge-block' : action === 'compound' ? 'sd-badge-info' : 'sd-badge-forward';
  const subRules = r.sub_rules || [];

  let html = `<div class="sd-section"><span class="sd-badge ${badgeCls}">${action.toUpperCase()}</span>
    <span class="sd-meta">${flows.length} flow rule${flows.length !== 1 ? 's' : ''}</span></div>`;

  if (subRules.length) {
    html += subRules.map((sub, si) => {
      const subFlows = sub.flows || [];
      return `<div class="sd-section"><div class="sd-label">Sub-rule ${si+1} — ${(sub.intent_action||'').toUpperCase()}</div>` +
        subFlows.map((f,fi) => flowCard(f, fi)).join('') + '</div>';
    }).join('');
  } else {
    html += flows.map((f, i) => flowCard(f, i)).join('');
  }
  return html;
}

function flowCard(f, idx) {
  const criteria = (f.selector?.criteria || []);
  const instructions = (f.treatment?.instructions || []);
  const isBlock = instructions.some(i => i.type === 'NOACTION');
  const actionStr = instructions.map(inst => {
    if (inst.type === 'NOACTION') return '<span class="sd-action-drop">⛔ DROP</span>';
    if (inst.type === 'OUTPUT')   return `<span class="sd-action-forward">→ Port ${escHtml(String(inst.port))}</span>`;
    if (inst.type === 'QUEUE')    return `<span>Queue ${inst.queueId ?? ''}</span>`;
    return `<span>${escHtml(inst.type)}</span>`;
  }).join(' ');

  const matchRows = criteria.map(c => {
    const v = c.ip ?? c.ethType ?? c.tcpPort ?? c.udpPort ?? c.port ?? c.protocol ?? '';
    return `<tr><td class="sd-key">${c.type.replace(/_/g,' ')}</td><td class="sd-val">${escHtml(String(v))}</td></tr>`;
  }).join('');

  const devShort = (f.deviceId || '').replace('of:000000000000', 's');
  return `<div class="sd-flow-card">
    <div class="sd-flow-header">
      <span class="sd-flow-title">Rule ${idx + 1}</span>
      <span class="sd-flow-device">${escHtml(devShort)} · Pri ${f.priority ?? '—'}</span>
    </div>
    <div class="sd-flow-body">
      <div class="sd-match-col">
        <div class="sd-sublabel">Match</div>
        <table class="sd-table">${matchRows || '<tr><td class="sd-key" colspan="2" style="color:#4b5563">any</td></tr>'}</table>
      </div>
      <div class="sd-action-col">
        <div class="sd-sublabel">Action</div>
        <div class="sd-action-str">${actionStr}</div>
      </div>
    </div>
  </div>`;
}

/* Stage 3 — Static Validation */
function renderSD3(r) {
  const passed = r.passed;
  const errors = r.schema_errors || [];
  const conflicts = r.conflicts || [];
  const warnings = r.warnings || [];

  let html = `<div class="sd-section"><span class="sd-badge ${passed ? 'sd-badge-ok' : 'sd-badge-error'}">${passed ? '✓ Passed' : '✗ Failed'}</span></div>`;
  if (errors.length) html += `<div class="sd-section"><div class="sd-label">Schema Errors</div>${errors.map(e => `<div class="sd-error-item">${escHtml(e)}</div>`).join('')}</div>`;
  if (conflicts.length) html += `<div class="sd-section"><div class="sd-label">Conflicts</div>
    <table class="sd-table"><tr><th>Type</th><th>Reason</th></tr>${conflicts.map(c =>
      `<tr><td class="sd-key">${escHtml(c.conflict_type||'')}</td><td class="sd-val">${escHtml(c.reason||'')}</td></tr>`).join('')}</table></div>`;
  if (warnings.length) html += `<div class="sd-section"><div class="sd-label">Warnings</div>${warnings.map(w => `<div class="sd-warn-item">⚠ ${escHtml(w)}</div>`).join('')}</div>`;
  if (!errors.length && !conflicts.length && !warnings.length) html += `<div class="sd-section"><div class="sd-ok-msg">✓ No schema errors, conflicts, or warnings found.</div></div>`;
  return html;
}

/* Stage 4 — Digital Twin */
function renderSD4(r) {
  const stCls = r.status === 'passed' ? 'sd-badge-ok' : r.status === 'skipped' ? 'sd-badge-skip' : 'sd-badge-error';
  const checks = r.checks || {};
  const evidence = r.evidence || {};

  const checkRows = Object.entries(checks).map(([name, ok]) => {
    const label = name.replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase());
    return `<div class="sd-check-row">
      <span class="sd-check-icon" style="color:${ok?'#10b981':'#ef4444'}">${ok?'✓':'✗'}</span>
      <span class="sd-check-name">${escHtml(label)}</span>
      <span class="sd-check-status ${ok?'check-pass':'check-fail'}">${ok?'PASS':'FAIL'}</span>
    </div>`;
  }).join('');

  const evidRows = Object.entries(evidence).filter(([,v]) => v != null).map(([k,v]) =>
    `<tr><td class="sd-key">${k.replace(/_/g,' ')}</td><td class="sd-val">${escHtml(String(v))}</td></tr>`).join('');

  return `<div class="sd-section"><span class="sd-badge ${stCls}">${(r.status||'—').toUpperCase()}</span>${r.reason ? `<div class="sd-reason">${escHtml(r.reason)}</div>` : ''}</div>` +
    (checkRows ? `<div class="sd-section"><div class="sd-label">Verification Checks</div><div class="sd-checks">${checkRows}</div></div>` : '') +
    (evidRows  ? `<div class="sd-section"><div class="sd-label">Evidence</div><table class="sd-table">${evidRows}</table></div>` : '');
}

/* Stage 5 — XAI Explanation */
function renderSD5(r) {
  const isApprove = (r.decision || '').includes('APPROVE');
  const conf = r.confidence != null ? Math.round(r.confidence * 100) : null;
  const confColor = conf >= 80 ? '#10b981' : conf >= 50 ? '#f59e0b' : '#ef4444';
  const breakdown = r.confidence_breakdown || {};
  const evidence = r.evidence || [];

  const bdRows = Object.entries(breakdown).map(([stage, score]) => {
    const pct = Math.round(score * 100);
    const col = pct >= 80 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444';
    return `<div class="sd-conf-row">
      <span class="sd-conf-label">${escHtml(stage)}</span>
      <div class="sd-conf-bar-wrap"><div class="sd-conf-bar-fill" style="width:${pct}%;background:${col}"></div></div>
      <span class="sd-conf-pct" style="color:${col}">${pct}%</span>
    </div>`;
  }).join('');

  const evItems = evidence.map(e => `<div class="sd-evidence-item">
    <span class="sd-ev-stage">${escHtml(e.stage||'')}</span>
    <span class="sd-ev-finding">${escHtml(e.finding||'')}</span>
  </div>`).join('');

  return `<div class="sd-section"><span class="sd-badge ${isApprove ? 'sd-badge-ok' : 'sd-badge-error'}">${escHtml(r.decision||'')}</span>${r.decision_reason ? `<div class="sd-reason">${escHtml(r.decision_reason)}</div>` : ''}</div>` +
    (conf != null ? `<div class="sd-section"><div class="sd-label">Overall Confidence</div>
      <div class="sd-conf-overall"><div class="sd-conf-bar-wrap large"><div class="sd-conf-bar-fill" style="width:${conf}%;background:${confColor}"></div></div>
      <span class="sd-conf-pct large" style="color:${confColor}">${conf}%</span></div></div>` : '') +
    (bdRows ? `<div class="sd-section"><div class="sd-label">Stage Breakdown</div>${bdRows}</div>` : '') +
    (evItems ? `<div class="sd-section"><div class="sd-label">Evidence</div>${evItems}</div>` : '') +
    (r.ir_summary ? `<div class="sd-section"><div class="sd-label">Intent Summary</div><div class="sd-summary">${escHtml(r.ir_summary)}</div></div>` : '') +
    (r.twin_summary ? `<div class="sd-section"><div class="sd-label">Twin Summary</div><div class="sd-summary">${escHtml(r.twin_summary)}</div></div>` : '');
}

/* Stage 6 — ONOS Deploy */
function renderSD6(r) {
  const ok = r.success;
  const flowIds = r.flow_ids || [];

  return `<div class="sd-section"><span class="sd-badge ${ok ? 'sd-badge-ok' : 'sd-badge-error'}">${ok ? '✓ Deployed' : '✗ Failed'}</span></div>` +
    (r.error ? `<div class="sd-section"><div class="sd-error-item">${escHtml(r.error)}</div></div>` : '') +
    (flowIds.length ? `<div class="sd-section"><div class="sd-label">${flowIds.length} Flow Rule${flowIds.length > 1 ? 's' : ''} Installed</div>${flowIds.map(id => `<div class="sd-flow-id">${escHtml(String(id))}</div>`).join('')}</div>` : '') +
    (!flowIds.length && ok ? `<div class="sd-section"><div class="sd-ok-msg">✓ Rules applied successfully.</div></div>` : '');
}

function renderConfidenceBadges() {
  const map = { 3: 'static', 4: 'twin' };
  Object.entries(map).forEach(([stageNum, key]) => {
    const el = document.getElementById(`conf-${stageNum}`);
    if (!el) return;
    const score = state.confidenceBreakdown[key];
    if (score == null) { el.style.display = 'none'; return; }
    const pct = Math.round(score * 100);
    const color = pct >= 80 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444';
    el.style.display = 'flex';
    el.style.color = color;
    el.style.borderColor = color + '40';
    el.textContent = `${pct}%`;
  });
}

function renderDecision() {
  const el = document.getElementById('decision-banner');
  if (!state.decision) { el.style.display = 'none'; return; }

  const deployFailed = !!state.deployFailed;
  const approve = state.decision.includes('APPROVE') && !deployFailed;
  const color   = approve ? '#10b981' : '#ef4444';
  const bgColor = approve ? '#0f1c16' : '#1c0f0f';
  const icon    = approve
    ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0a0e1a" stroke-width="3"><path d="M5 13l4 4L19 7" stroke-linecap="round" stroke-linejoin="round"/></svg>`
    : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0a0e1a" stroke-width="3"><path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/></svg>`;

  const report = state.decisionReport || {};
  // XAIReport.to_dict() fields: decision_reason, ir_summary, static_summary, twin_summary
  const baseReason = report.decision_reason || report.ir_summary || '';
  const reason = deployFailed
    ? `⚠ ONOS 배포 실패 — 검증은 통과했으나 실제 배포가 반영되지 않았습니다. ${baseReason}`.trim()
    : baseReason;
  const title = deployFailed ? `${state.decision} (배포 실패)` : state.decision;

  el.style.display = 'flex';
  el.style.background = bgColor;
  el.style.borderColor = color;
  el.innerHTML = `
    <div class="decision-icon" style="background:${color}">${icon}</div>
    <div>
      <div class="decision-title" style="color:${color}">${title}</div>
      <div class="decision-reason">${reason}</div>
    </div>
  `;
}

function renderHistory() {
  const el = document.getElementById('history-list');
  if (!el) return;
  if (state.history.length === 0) {
    el.innerHTML = '<div style="font-size:11px;color:#4b5563;font-family:\'JetBrains Mono\',monospace">No runs yet</div>';
    return;
  }
  el.innerHTML = state.history.map(h => {
    const badge = h.decision
      ? `<span style="font-size:10px;color:${h.decision.includes('APPROVE') ? '#10b981' : '#ef4444'}">${h.decision.includes('APPROVE') ? '✓' : '✗'}</span> `
      : '';
    return `<div class="history-item" title="${h.intent}" data-intent="${escHtml(h.intent)}">${badge}${escHtml(h.intent)}</div>`;
  }).join('');
  el.querySelectorAll('.history-item').forEach(item => {
    item.addEventListener('click', () => fillIntent(item.dataset.intent));
  });
}

function updateMetrics(data) {
  const nodes = data.nodes || [];
  const links = data.links || [];
  const switches = nodes.filter(n => n.type === 'switch').length;
  const hosts    = nodes.filter(n => n.type === 'host').length;
  const swLinks  = links.filter(l => {
    const s = typeof l.source === 'object' ? l.source.id : l.source;
    const t = typeof l.target === 'object' ? l.target.id : l.target;
    return s && t && s.startsWith('of:') && t.startsWith('of:');
  }).length;

  document.getElementById('metric-switches').textContent = switches || '—';
  document.getElementById('metric-hosts').textContent    = hosts    || '—';
  document.getElementById('metric-links').textContent    = swLinks  || '—';
  document.getElementById('metric-rules').textContent    = data.rule_count ?? '—';
}

function updateHostLegend(data) {
  const body = document.getElementById('host-legend-body');
  if (!body) return;
  const hosts = (data.nodes || []).filter(n => n.type === 'host' && n.ip);
  if (hosts.length === 0) {
    body.innerHTML = '<div style="color:#4b5563;font-size:11px;padding:4px 8px">No host info</div>';
    return;
  }
  body.innerHTML = hosts.map(h => {
    const label = h.label || h.id;
    const mac   = h.mac ? `<span class="host-legend-mac">${h.mac}</span>` : '';
    return `<div class="host-legend-row">
      <span class="host-legend-dot"></span>
      <span class="host-legend-label">${label}</span>
      <span class="host-legend-ip">${h.ip}</span>
      ${mac}
    </div>`;
  }).join('');
}

function updateFlowTable(data) {
  const body = document.getElementById('flow-table-body');
  const rows = data.flow_table || [];
  if (rows.length === 0) {
    body.innerHTML = `<div style="padding:12px 10px;font-size:11px;color:#4b5563;font-family:'JetBrains Mono',monospace">No flow rules</div>`;
    return;
  }
  body.innerHTML = rows.map(r => {
    const actionColor = r.action === 'FORWARD' ? '#10b981' : r.action === 'DROP' ? '#f59e0b' : '#9ca3af';
    return `
      <div class="flow-table-row">
        <div class="flow-cell-device">${escHtml(String(r.device))}</div>
        <div class="flow-cell-pri">${r.priority}</div>
        <div class="flow-cell-match">${escHtml(String(r.match))}</div>
        <div class="flow-cell-action" style="color:${actionColor}">
          <span class="flow-action-dot" style="background:${actionColor}"></span>
          ${escHtml(String(r.action))}
        </div>
      </div>`;
  }).join('');
}

function showTopoError(msg) {
  const el = document.getElementById('topology-placeholder');
  if (el) {
    el.style.display = 'flex';
    el.textContent = `ONOS offline — ${msg}`;
  }
}

// ── D3 Topology ───────────────────────────────────────────────────────────────

let topoSvg = null;
let topoZoom = null;
let topoZoomLayer = null;
let simulation = null;
const nodePositions = new Map(); // persist positions across refreshes
let currentTopoNodes = []; // snapshot for twin viz (id, type, label, ip)
let currentTopoLinks = []; // snapshot for twin viz (source, target as string IDs)
let twinVizInfoList = []; // [{ srcNode, dstNode, blockNode, action }, ...]
let twinVizPhase   = 'idle';
let twinAnimTimers = [];
let bwLabelsVisible = false; // 대역폭 레이블 표시 여부

// ── Topology Editor State ─────────────────────────────────────────────────────

const editor = {
  active: false,
  tool: 'select',   // 'select' | 'switch' | 'host' | 'link' | 'delete'
  linking: null,    // null | { sourceId }  — while drawing a link
  nodes: [],        // { id, label, type, dpid?, ip?, mac?, x, y }
  links: [],        // { id, source, target, bw? }
  selected: null,   // selected node id
  _cnt: { s: 1, h: 1, l: 1 },
};

const TOOL_HINTS = {
  select: '[Esc] Select · Drag to move · Shift+drag to lasso-delete',
  switch: '[S] Click canvas to add switch · Del=delete selected',
  host:   '[H] Click canvas to add host · Del=delete selected',
  link:   '[L] Click source node → click target node',
  delete: '[D] Click node/link · Shift+drag to delete area · Ctrl+Z undo',
};

function editorNewId(type) {
  // For switches and hosts: scan from 1 to find the first unused number.
  // This ensures new nodes start from s1/h1 even when existing ones are s5–s8.
  if (type === 'switch' || type === 'host') {
    const prefix = type === 'switch' ? 's' : 'h';
    const existingIds = new Set(editor.nodes.map(n => n.id));
    let n = 1;
    while (existingIds.has(`${prefix}${n}`)) n++;
    return `${prefix}${n}`;
  }
  return `l${editor._cnt.l++}`;
}

// ── Editor: mode transitions ──────────────────────────────────────────────────

async function enterEditMode() {
  editor.active = true;
  console.log('[Editor] entering edit mode');

  const ids = ['topo-title', 'live-mode-controls', 'topo-editor-bar',
                'metrics-grid', 'flow-table-section', 'topo-props-panel'];
  for (const id of ids) {
    if (!document.getElementById(id)) {
      console.error(`[Editor] missing element: #${id}`);
    }
  }

  document.getElementById('topo-title').textContent = 'Topology Editor';
  document.getElementById('live-mode-controls').style.display = 'none';
  document.getElementById('topo-editor-bar').style.display = 'flex';
  document.getElementById('metrics-grid').style.display = 'none';
  document.getElementById('flow-table-section').style.display = 'none';
  document.getElementById('topo-props-panel').style.display = 'block';

  clearTopologyGraph();
  await loadEditorData();
  setEditorTool('select');
  renderEditorGraph();
  console.log('[Editor] ready — nodes:', editor.nodes.length, 'links:', editor.links.length);
}

function exitEditMode() {
  editor.active = false;
  editor.linking = null;
  editor.selected = null;

  document.getElementById('topo-title').textContent = 'Live Network Topology';
  document.getElementById('live-mode-controls').style.display = 'flex';
  document.getElementById('topo-editor-bar').style.display = 'none';
  document.getElementById('metrics-grid').style.display = 'grid';
  document.getElementById('flow-table-section').style.display = 'block';
  document.getElementById('topo-props-panel').style.display = 'none';

  clearTopologyGraph();
  topoSnapshot = null;

  // Render immediately from editor state so the user sees their topology
  // right away without waiting for the ONOS connection attempt to time out.
  // _renderEditorSnapshot() sets topoSnapshot — we deliberately keep it
  // so fetchTopology() doesn't call showTopoError() on ONOS-offline errors.
  _renderEditorSnapshot();
  fetchTopology();
}

// Render the current editor.nodes / editor.links as a static live graph.
// Positions are preserved from the editor (x/y), so the layout matches.
function _renderEditorSnapshot() {
  if (!editor.nodes.length) return;

  const nodes = editor.nodes.map(n => ({
    id: n.id, label: n.label, type: n.type, state: 'idle',
    ip: n.ip || '', x: n.x, y: n.y,
  }));
  const links = editor.links.map(l => ({ source: l.source, target: l.target }));
  const data = { nodes, links, flow_table: [], rule_count: nodes.length };

  // Store snapshot so the next fetchTopology() only re-renders if data changed
  topoSnapshot = JSON.stringify({
    nodes: data.nodes, links: data.links,
    flow_table: [], rule_count: data.rule_count,
  });

  updateTopology(data);
  updateMetrics(data);
  updateHostLegend(data);
  updateFlowTable(data);
}

function clearTopologyGraph() {
  if (!topoSvg || !topoZoomLayer) return;
  if (simulation) { simulation.stop(); simulation = null; }
  topoZoomLayer.select('.links').selectAll('*').remove();
  topoZoomLayer.select('.bw-labels').selectAll('*').remove();
  topoZoomLayer.select('.nodes').selectAll('*').remove();
  topoSvg.selectAll('#ghost-link').remove();
  topoSvg.selectAll('#lasso-rect').remove();
  topoSvg.on('click', null).on('mousemove', null)
         .on('mousedown.lasso', null).on('mouseup.lasso', null);
  lasso.active = false;
}

// ── Editor: data loading ──────────────────────────────────────────────────────

async function loadEditorData() {
  try {
    const resp = await fetch('/api/topology/custom');
    if (!resp.ok) throw new Error('no custom topology');
    const data = await resp.json();
    if ((data.switches || []).length > 0 || (data.hosts || []).length > 0) {
      importCustomData(data);
      return;
    }
  } catch { /* fall through */ }
  loadDefaultDiamond();
}

function importCustomData(data) {
  const allSw = (data.switches || []);
  const allH  = (data.hosts   || []);
  // _cnt.s/_cnt.h are no longer used for switch/host IDs (editorNewId scans from 1).
  // Keep _cnt.l for link IDs since those are internal-only.
  editor._cnt.l = (data.links || []).length + 1;

  editor.nodes = [
    ...allSw.map(sw => ({
      id: sw.id, label: sw.label || sw.id, type: 'switch',
      dpid: sw.dpid, x: sw.x ?? 150, y: sw.y ?? 140,
    })),
    ...allH.map(h => ({
      id: h.id, label: h.label || h.id, type: 'host',
      ip: h.ip, mac: h.mac, x: h.x ?? 80, y: h.y ?? 80,
    })),
  ];
  editor.links = (data.links || []).map(l => ({
    id: l.id || editorNewId('link'),
    source: l.source, target: l.target, bw: l.bw,
  }));
}

function loadDefaultDiamond() {
  editor._cnt = { s: 5, h: 5, l: 9 };
  const cx = 171, cy = 140;
  editor.nodes = [
    { id: 's1', label: 'S1', type: 'switch', dpid: '0000000000000001', x: cx - 55, y: cy - 45 },
    { id: 's2', label: 'S2', type: 'switch', dpid: '0000000000000002', x: cx - 75, y: cy + 40 },
    { id: 's3', label: 'S3', type: 'switch', dpid: '0000000000000003', x: cx + 75, y: cy + 40 },
    { id: 's4', label: 'S4', type: 'switch', dpid: '0000000000000004', x: cx + 55, y: cy - 45 },
    { id: 'h1', label: 'H1', type: 'host', ip: '10.0.0.1', mac: '00:00:00:00:00:01', x: cx - 130, y: cy - 70 },
    { id: 'h2', label: 'H2', type: 'host', ip: '10.0.0.2', mac: '00:00:00:00:00:02', x: cx - 135, y: cy + 15 },
    { id: 'h3', label: 'H3', type: 'host', ip: '10.0.0.3', mac: '00:00:00:00:00:03', x: cx + 135, y: cy + 15 },
    { id: 'h4', label: 'H4', type: 'host', ip: '10.0.0.4', mac: '00:00:00:00:00:04', x: cx + 130, y: cy - 70 },
  ];
  editor.links = [
    { id: 'l1', source: 'h1', target: 's1', bw: 100 },
    { id: 'l2', source: 'h2', target: 's1', bw: 100 },
    { id: 'l3', source: 'h3', target: 's4', bw: 100 },
    { id: 'l4', source: 'h4', target: 's4', bw: 100 },
    { id: 'l5', source: 's1', target: 's2', bw: 1   },
    { id: 'l6', source: 's2', target: 's4', bw: 1   },
    { id: 'l7', source: 's1', target: 's3', bw: 10  },
    { id: 'l8', source: 's3', target: 's4', bw: 10  },
  ];
}

// ── Editor: tool selection ────────────────────────────────────────────────────

function setEditorTool(tool) {
  editor.tool = tool;
  editor.linking = null;
  if (topoSvg) {
    topoZoomLayer.select('#ghost-link').attr('opacity', 0);
    const cur = { select: 'default', switch: 'crosshair', host: 'crosshair', link: 'crosshair', delete: 'not-allowed' };
    topoSvg.style('cursor', cur[tool] || 'default');
  }
  document.querySelectorAll('.tool-btn').forEach(b => b.classList.toggle('active', b.dataset.tool === tool));
  const hint = document.getElementById('tool-hint');
  if (hint) hint.textContent = TOOL_HINTS[tool] || '';
}

// ── Editor: D3 rendering ──────────────────────────────────────────────────────

function renderEditorGraph() {
  if (!editor.active) return;
  if (!topoSvg) initTopology();

  const container = document.getElementById('topology-graph');
  const W = container.clientWidth  || 342;
  const H = container.clientHeight || 280;

  const ph = document.getElementById('topology-placeholder');
  if (ph) ph.style.display = 'none';

  // Ghost link (drawn above everything)
  if (topoZoomLayer.select('#ghost-link').empty()) {
    topoZoomLayer.append('line')
      .attr('id', 'ghost-link')
      .attr('stroke', '#3b82f6')
      .attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '6,4')
      .attr('opacity', 0)
      .attr('pointer-events', 'none');
  }

  // Lasso rect (Shift+drag delete) — stays outside zoom so it covers screen coords
  if (topoSvg.select('#lasso-rect').empty()) {
    topoSvg.insert('rect', ':first-child')
      .attr('id', 'lasso-rect')
      .attr('opacity', 0);
  }

  // SVG background interactions
  topoSvg.on('click', function(ev) {
    if (!editor.active) return;
    if (ev.target !== this) return;
    const t = d3.zoomTransform(topoSvg.node());
    const [px, py] = d3.pointer(ev);
    const [x, y] = t.invert([px, py]);
    if (editor.tool === 'switch') {
      editorAddNode('switch', x, y);
    } else if (editor.tool === 'host') {
      editorAddNode('host', x, y);
    } else if (editor.tool === 'link' && editor.linking) {
      editor.linking = null;
      topoZoomLayer.select('#ghost-link').attr('opacity', 0);
      renderEditorGraph();
    } else {
      editor.selected = null;
      renderPropsPanel();
      renderEditorGraph();
    }
  });

  topoSvg.on('mousemove', function(ev) {
    const [mx, my] = d3.pointer(ev);
    if (lasso.active) {
      lasso.x1 = mx; lasso.y1 = my;
      updateLassoRect();
    }
    if (!editor.active || editor.tool !== 'link' || !editor.linking) return;
    const src = editor.nodes.find(n => n.id === editor.linking.sourceId);
    if (!src) return;
    const t = d3.zoomTransform(topoSvg.node());
    const [ix, iy] = t.invert([mx, my]);
    topoZoomLayer.select('#ghost-link')
      .attr('x1', src.x).attr('y1', src.y)
      .attr('x2', ix).attr('y2', iy)
      .attr('opacity', 1);
  });

  topoSvg.on('mousedown.lasso', function(ev) {
    if (!editor.active || !ev.shiftKey) return;
    if (!isEditorBg(ev)) return;
    ev.preventDefault();
    const [x, y] = d3.pointer(ev);
    lasso.active = true;
    lasso.x0 = lasso.x1 = x;
    lasso.y0 = lasso.y1 = y;
    updateLassoRect();
  });

  topoSvg.on('mouseup.lasso', function() {
    if (!lasso.active) return;
    lasso.active = false;
    topoSvg.select('#lasso-rect').attr('opacity', 0);
    commitLasso();
  });

  // ── Links ──
  const linkGs = topoZoomLayer.select('.links')
    .selectAll('g.ed-link')
    .data(editor.links, d => d.id)
    .join(enter => {
      const g = enter.append('g').attr('class', 'ed-link').style('cursor', 'pointer');
      g.append('line').attr('class', 'lhit').attr('stroke', 'transparent').attr('stroke-width', 8);
      g.append('line').attr('class', 'lvis').attr('stroke-width', 1.5);
      g.append('text').attr('class', 'lbw')
        .attr('text-anchor', 'middle').attr('font-size', 9)
        .attr('font-family', 'JetBrains Mono, monospace').attr('fill', '#6b7280');
      return g;
    });

  linkGs.each(function(d) {
    const src = editor.nodes.find(n => n.id === d.source);
    const tgt = editor.nodes.find(n => n.id === d.target);
    if (!src || !tgt) return;
    const mx = (src.x + tgt.x) / 2, my = (src.y + tgt.y) / 2;
    const isDel = editor.tool === 'delete';
    const g = d3.select(this);
    g.select('.lhit').attr('x1', src.x).attr('y1', src.y).attr('x2', tgt.x).attr('y2', tgt.y);
    g.select('.lvis')
      .attr('x1', src.x).attr('y1', src.y).attr('x2', tgt.x).attr('y2', tgt.y)
      .attr('stroke', isDel ? '#ef444488' : '#374151');
    g.select('.lbw').attr('x', mx).attr('y', my - 5).text(d.bw != null ? `${d.bw}M` : '');
  });

  linkGs.on('click', (ev, d) => {
    ev.stopPropagation();
    if (editor.tool === 'delete') {
      editorPushHistory();
      editor.links = editor.links.filter(l => l.id !== d.id);
      renderEditorGraph();
    }
  });

  // ── Nodes ──
  const drag = d3.drag()
    .filter(ev => !ev.shiftKey)  // Shift+drag → lasso, not node drag
    .on('start', (ev, d) => { if (editor.tool !== 'select') ev.sourceEvent.stopPropagation(); })
    .on('drag',  (ev, d) => {
      if (editor.tool !== 'select') return;
      d.x = Math.max(18, Math.min(W - 18, ev.x));
      d.y = Math.max(18, Math.min(H - 18, ev.y));
      renderEditorGraph();
    });

  const nodeGs = topoZoomLayer.select('.nodes')
    .selectAll('g.ed-node')
    .data(editor.nodes, d => d.id)
    .join(enter => enter.append('g').attr('class', 'ed-node'))
    .call(drag);

  nodeGs.selectAll('*').remove();

  nodeGs.each(function(d) {
    const g = d3.select(this);
    const sel  = editor.selected === d.id;
    const lsrc = editor.linking?.sourceId === d.id;
    const fill = lsrc ? '#1e3a5f' : nodeColor(d);
    const strokeColor = sel ? '#60a5fa' : lsrc ? '#3b82f6' : (d.type === 'switch' ? '#0a0e1a' : '#3b82f6');
    const strokeW = sel ? 2.5 : 1.5;

    if (d.type === 'switch') {
      g.append('polygon')
        .attr('points', '0,-15 13,-7.5 13,7.5 0,15 -13,7.5 -13,-7.5')
        .attr('fill', fill)
        .attr('stroke', strokeColor)
        .attr('stroke-width', strokeW);
    } else {
      g.append('circle')
        .attr('r', 10)
        .attr('fill', '#111827')
        .attr('stroke', strokeColor)
        .attr('stroke-width', strokeW);
    }

    g.append('text')
      .attr('text-anchor', 'middle').attr('dy', '0.35em')
      .attr('font-size', 9).attr('font-weight', '700')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('fill', d.type === 'switch' ? (lsrc ? '#60a5fa' : '#0a0e1a') : '#f9fafb')
      .attr('pointer-events', 'none')
      .text(d.label);

    g.attr('transform', `translate(${d.x},${d.y})`)
      .style('cursor', editor.tool === 'delete' ? 'not-allowed' : editor.tool === 'select' ? 'grab' : 'pointer');
  });

  nodeGs.on('click', (ev, d) => {
    ev.stopPropagation();
    handleEditorNodeClick(d);
  });

  // Keep ghost link on top
  topoZoomLayer.select('#ghost-link').raise();
}

function handleEditorNodeClick(d) {
  if (editor.tool === 'delete') {
    editorPushHistory();
    editor.nodes = editor.nodes.filter(n => n.id !== d.id);
    editor.links = editor.links.filter(l => l.source !== d.id && l.target !== d.id);
    if (editor.selected === d.id) editor.selected = null;
    renderEditorGraph();
    renderPropsPanel();
    return;
  }

  if (editor.tool === 'link') {
    if (!editor.linking) {
      editor.linking = { sourceId: d.id };
      renderEditorGraph();
    } else if (editor.linking.sourceId === d.id) {
      // Cancel link on same node
      editor.linking = null;
      topoZoomLayer.select('#ghost-link').attr('opacity', 0);
      renderEditorGraph();
    } else {
      // Complete link — prevent duplicates
      const a = editor.linking.sourceId, b = d.id;
      const dup = editor.links.some(l =>
        (l.source === a && l.target === b) || (l.source === b && l.target === a)
      );
      if (!dup) {
        editorPushHistory();
        const bw = (editor.nodes.find(n=>n.id===a)?.type === 'switch' &&
                    editor.nodes.find(n=>n.id===b)?.type === 'switch') ? 10 : 100;
        editor.links.push({ id: editorNewId('link'), source: a, target: b, bw });
      }
      editor.linking = null;
      topoZoomLayer.select('#ghost-link').attr('opacity', 0);
      renderEditorGraph();
    }
    return;
  }

  // Select tool
  editor.selected = d.id;
  renderPropsPanel();
  renderEditorGraph();
}

function editorAddNode(type, x, y) {
  editorPushHistory();
  const id  = editorNewId(type);
  const num = parseInt(id.replace(/\D/g, ''), 10);
  const node = { id, label: type === 'switch' ? `S${num}` : `H${num}`, type, x, y };
  if (type === 'switch') {
    node.dpid = `0000000000000000${num}`.slice(-16);
  } else {
    node.ip  = `10.0.0.${num}`;
    node.mac = `00:00:00:00:00:${`0${num}`.slice(-2)}`;
  }
  editor.nodes.push(node);
  editor.selected = id;
  renderEditorGraph();
  renderPropsPanel();
}

// ── Editor: properties panel ──────────────────────────────────────────────────

function renderPropsPanel() {
  const panel = document.getElementById('props-content');
  if (!panel) return;

  const node = editor.nodes.find(n => n.id === editor.selected);
  if (!node) {
    panel.innerHTML = `<div class="props-hint">Click a node to edit its properties</div>`;
    return;
  }

  const swFields  = [{ k:'label', l:'Label' }, { k:'dpid', l:'DPID (16 hex digits)' }];
  const hostFields = [{ k:'label', l:'Label' }, { k:'ip', l:'IP Address' }, { k:'mac', l:'MAC Address' }];
  const fields = node.type === 'switch' ? swFields : hostFields;

  // Connected links for this node
  const connLinks = editor.links.filter(l => l.source === node.id || l.target === node.id);
  const linkRows = connLinks.length > 0
    ? connLinks.map(l => {
        const peerId = l.source === node.id ? l.target : l.source;
        const peer = editor.nodes.find(n => n.id === peerId);
        return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">
          <span style="font-size:11px;color:#9ca3af;flex:1">${peer?.label ?? peerId}</span>
          <input class="props-input link-bw-input" data-lid="${l.id}" value="${l.bw ?? ''}"
            style="width:60px;text-align:right" placeholder="Mbps" />
          <span style="font-size:10px;color:#4b5563">M</span>
          <button class="props-delete-btn" data-lid="${l.id}"
            style="width:auto;margin:0;padding:3px 6px;font-size:10px">✕</button>
        </div>`;
      }).join('')
    : `<div class="props-hint">No connected links</div>`;

  panel.innerHTML = `
    ${fields.map(f => `
      <div class="props-field">
        <div class="props-field-label">${f.l}</div>
        <input class="props-input" data-key="${f.k}" value="${escHtml(node[f.k] || '')}" />
      </div>`).join('')}
    <div class="props-section-title">Links</div>
    ${linkRows}
    <button id="props-delete-node-btn" class="props-delete-btn">Delete ${node.type === 'switch' ? 'Switch' : 'Host'}</button>
  `;

  // Node field changes
  panel.querySelectorAll('.props-input[data-key]').forEach(inp => {
    inp.addEventListener('input', ev => {
      const n = editor.nodes.find(x => x.id === editor.selected);
      if (n) { n[ev.target.dataset.key] = ev.target.value; renderEditorGraph(); }
    });
  });

  // Link bw changes
  panel.querySelectorAll('.link-bw-input').forEach(inp => {
    inp.addEventListener('input', ev => {
      const lnk = editor.links.find(l => l.id === ev.target.dataset.lid);
      if (lnk) { lnk.bw = Number(ev.target.value) || null; renderEditorGraph(); }
    });
  });

  // Link delete buttons
  panel.querySelectorAll('button[data-lid]').forEach(btn => {
    btn.addEventListener('click', () => {
      editorPushHistory();
      editor.links = editor.links.filter(l => l.id !== btn.dataset.lid);
      renderEditorGraph();
      renderPropsPanel();
    });
  });

  // Node delete
  document.getElementById('props-delete-node-btn')?.addEventListener('click', () => {
    editorPushHistory();
    editor.nodes = editor.nodes.filter(n => n.id !== editor.selected);
    editor.links = editor.links.filter(l => l.source !== editor.selected && l.target !== editor.selected);
    editor.selected = null;
    renderEditorGraph();
    renderPropsPanel();
  });
}

// ── Editor: apply / save ──────────────────────────────────────────────────────

async function applyTopology() {
  const payload = {
    switches: editor.nodes
      .filter(n => n.type === 'switch')
      .map(n => ({ id: n.id, label: n.label, dpid: n.dpid, x: Math.round(n.x), y: Math.round(n.y) })),
    hosts: editor.nodes
      .filter(n => n.type === 'host')
      .map(n => ({ id: n.id, label: n.label, ip: n.ip, mac: n.mac, x: Math.round(n.x), y: Math.round(n.y) })),
    links: editor.links.map(l => ({ id: l.id, source: l.source, target: l.target, bw: l.bw })),
  };

  // Show "Applying..." in the apply button
  const applyBtn = document.getElementById('topo-apply-btn');
  const origText = applyBtn.textContent;
  applyBtn.textContent = 'Applying…';
  applyBtn.disabled = true;

  try {
    // 1. Save topology file
    await fetch('/api/topology/custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    // 2. Push to ONOS netcfg (best-effort — ONOS may be offline)
    let onosMsg = '';
    try {
      const applyRes = await fetch('/api/topology/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const applyData = await applyRes.json();
      if (applyData.ok) {
        const d = applyData.pushed || {};
        onosMsg = `ONOS synced (${d.devices ?? 0} devices, ${d.hosts ?? 0} hosts)`;
      } else {
        onosMsg = `ONOS offline — topology saved locally (${applyData.error || ''})`;
      }
    } catch (_) {
      onosMsg = 'ONOS offline — topology saved locally';
    }

    updateExampleChips(payload);
    exitEditMode();

    // Show brief status in topology title
    const titleEl = document.getElementById('topo-title');
    if (titleEl) {
      const prev = titleEl.textContent;
      titleEl.textContent = onosMsg;
      setTimeout(() => { titleEl.textContent = prev; }, 4000);
    }
  } catch (err) {
    console.error('Failed to apply topology:', err);
    applyBtn.textContent = 'Error';
    setTimeout(() => {
      applyBtn.textContent = origText;
      applyBtn.disabled = false;
    }, 2000);
    return;
  }

  applyBtn.textContent = origText;
  applyBtn.disabled = false;
}

function updateExampleChips(topo) {
  const hosts = topo.hosts || [];
  const switches = topo.switches || [];
  if (hosts.length < 2 || switches.length < 1) return;

  const h1 = hosts[0];
  const h2 = hosts[hosts.length - 1];
  const s1 = switches[0];
  const swLabel = s1.label?.toLowerCase() ?? s1.id;
  const swPhrase = `switch ${swLabel.replace(/\D/g, '') || 1}`;

  const sw2 = switches.length >= 2 ? switches[1] : s1;
  const sw2Phrase = `switch ${sw2.label?.toLowerCase().replace(/\D/g, '') || 2}`;
  const sw3 = switches.length >= 3 ? switches[2] : s1;
  const sw3Phrase = `switch ${sw3.label?.toLowerCase().replace(/\D/g, '') || 3}`;

  const swNum  = swLabel.replace(/\D/g, '') || 1;
  const sw2Num = sw2.label?.replace(/\D/g, '') || 2;
  const sw3Num = sw3.label?.replace(/\D/g, '') || 3;
  const swLast = switches[switches.length - 1].label?.replace(/\D/g, '') || switches.length;

  const chips = [
    { t: `Block ${h1.ip}→${h2.ip}`,
      i: `Block all traffic from ${h1.ip} to ${h2.ip} on ${swPhrase}`,
      k: `[차단] 스위치 ${swNum}에서 ${h1.ip} → ${h2.ip} 모든 트래픽을 드롭합니다.` },
    { t: `Block SSH to ${h1.ip}`,
      i: `Block TCP traffic on port 22 destined for ${h1.ip} on ${swPhrase}`,
      k: `[차단] 스위치 ${swNum}에서 ${h1.ip}로 향하는 SSH(TCP:22) 트래픽을 차단합니다.` },
    { t: `Forward ICMP→${h1.ip}`,
      i: `Forward ICMP traffic destined for ${h1.ip} through port 3 on ${swPhrase}`,
      k: `[전달] 스위치 ${swNum}에서 ${h1.ip}로 향하는 ICMP(ping) 트래픽을 포트 3으로 내보냅니다.` },
    { t: `Forward HTTP→${h2.ip}`,
      i: `Forward TCP traffic on port 80 destined for ${h2.ip} via port 2 on ${swPhrase}`,
      k: `[전달] 스위치 ${swNum}에서 ${h2.ip}:80(HTTP)으로 향하는 TCP 트래픽을 포트 2로 내보냅니다.` },
  ];
  if (hosts.length >= 4) {
    const h3 = hosts[2], h4 = hosts[3];
    chips.push({
      t: `QoS ${h1.ip}→${h4.ip}`,
      i: `Apply QoS for video streaming from ${h1.ip} to ${h4.ip} on ${swPhrase}`,
      k: `[QoS] 스위치 ${swNum}에서 ${h1.ip} → ${h4.ip} 영상 스트리밍 트래픽에 우선순위 큐를 적용합니다.`,
    });
    chips.push({
      t: `Block ${h3.ip}→${h4.ip}`,
      i: `Block all traffic from ${h3.ip} to ${h4.ip} on switch ${swLast}`,
      k: `[차단] 스위치 ${swLast}에서 ${h3.ip} → ${h4.ip} 모든 트래픽을 드롭합니다.`,
    });
    chips.push({
      t: `SFC: IDS ${h1.ip}→${h4.ip}`,
      i: `Steer HTTP traffic from ${h1.ip} to ${h4.ip} through IDS at port 9, then forward out port 2 on ${sw2Phrase}`,
      k: `[SFC] 스위치 ${sw2Num}에서 ${h1.ip}→${h4.ip} HTTP 트래픽을 포트 9의 IDS로 검사한 뒤, 포트 2로 목적지에 전달합니다.`,
    });
    chips.push({
      t: `Reroute via ${sw3.label || 's3'}`,
      i: `Reroute traffic from ${h2.ip} to ${h3.ip} via ${sw3Phrase} avoiding ${sw2Phrase} on ${swPhrase}`,
      k: `[재경로] 스위치 ${swNum}에서 ${h2.ip}→${h3.ip} 트래픽을 스위치 ${sw2Num}을 우회하여 스위치 ${sw3Num} 경로로 재지정합니다.`,
    });
    chips.push({
      t: `Compound: Allow HTTP, Block SSH`,
      i: `Allow HTTP from ${h1.ip} to ${h2.ip} via port 2 on ${swPhrase}, but block SSH from ${h1.ip} to ${h2.ip} on ${swPhrase}`,
      k: `[복합] ${swPhrase}에서 ${h1.ip}→${h2.ip} HTTP(TCP:80)는 포트 2로 허용하고, SSH(TCP:22)는 차단합니다.`,
    });
    chips.push({
      t: `Compound: Multi-switch rules`,
      i: `Forward HTTP from ${h1.ip} to ${h3.ip} via port 2 on ${swPhrase}, and block all traffic from ${h2.ip} to ${h4.ip} on ${sw2Phrase}`,
      k: `[복합] ${swPhrase}에서 ${h1.ip}→${h3.ip} HTTP를 포트 2로 전달하고, ${sw2Phrase}에서 ${h2.ip}→${h4.ip}를 차단합니다.`,
    });
  }

  // Update the dynamic section in the intent preset menu
  const menu = document.getElementById('intent-preset-menu');
  if (!menu) return;
  // Remove existing dynamic items (all items after first static group)
  menu.querySelectorAll('.dynamic-preset-item, .dynamic-preset-label').forEach(el => el.remove());

  if (chips.length === 0) return;
  const label = document.createElement('div');
  label.className = 'preset-group-label dynamic-preset-label';
  label.textContent = 'Current Topology';
  menu.appendChild(label);
  chips.forEach(c => {
    const item = document.createElement('div');
    item.className = 'preset-item dynamic-preset-item';
    item.textContent = c.t;
    item.addEventListener('click', e => {
      e.stopPropagation();
      menu.classList.remove('open');
      fillIntent(c.i);
    });
    menu.appendChild(item);
  });
}

function initTopology() {
  const container = document.getElementById('topology-graph');
  const w = container.clientWidth  || 342;
  const h = container.clientHeight || 280;

  topoSvg = d3.select('#topology-graph')
    .append('svg')
    .attr('width',  '100%')
    .attr('height', '100%')
    .attr('viewBox', `0 0 ${w} ${h}`);

  topoZoomLayer = topoSvg.append('g').attr('class', 'zoom-layer');
  topoZoomLayer.append('g').attr('class', 'links');
  topoZoomLayer.append('g').attr('class', 'bw-labels');    // link bandwidth text layer
  topoZoomLayer.append('g').attr('class', 'twin-bw-layer'); // iperf 측정값 (항상 표시)
  topoZoomLayer.append('g').attr('class', 'nodes');

  topoZoom = d3.zoom()
    .scaleExtent([0.2, 4])
    .on('zoom', ev => topoZoomLayer.attr('transform', ev.transform));

  topoSvg.call(topoZoom);

  // Double-click to reset zoom
  topoSvg.on('dblclick.zoom', () => {
    topoSvg.transition().duration(300).call(topoZoom.transform, d3.zoomIdentity);
  });
}

function updateTopology(data) {
  if (!topoSvg) initTopology();

  const placeholder = document.getElementById('topology-placeholder');
  if (placeholder) placeholder.style.display = 'none';

  const { nodes, links } = data;
  // Snapshot for twin visualization (before D3 mutates objects)
  currentTopoNodes = (data.nodes || []).map(n => ({ id: n.id, type: n.type, label: n.label || '', ip: n.ip || null }));
  currentTopoLinks = (data.links || []).map(l => ({ source: String(l.source), target: String(l.target) }));
  if (!nodes || nodes.length === 0) {
    showTopoError('No devices found');
    return;
  }

  const container = document.getElementById('topology-graph');
  const w = container.clientWidth  || 342;
  const h = container.clientHeight || 280;

  // Always sync viewBox to current container size (handles fullscreen transitions)
  topoSvg.attr('viewBox', `0 0 ${w} ${h}`);

  // Seed positions: prefer stored positions, then backend-provided x/y
  nodes.forEach(n => {
    const prev = nodePositions.get(n.id);
    if (prev) { n.x = prev.x; n.y = prev.y; }
    else if (n.x != null && n.y != null) {
      nodePositions.set(n.id, { x: n.x, y: n.y }); // cache backend coords
    }
  });

  if (simulation) simulation.stop();

  simulation = d3.forceSimulation(nodes)
    .force('link',      d3.forceLink(links).id(d => d.id).distance(70))
    .force('charge',    d3.forceManyBody().strength(-180))
    .force('center',    d3.forceCenter(w / 2, h / 2))
    .force('collision', d3.forceCollide(24));

  // Links — 네트워크 프리셋 세션이 활성화돼 있으면 utilization 기반 색상이
  // 우선하고, 아니면 BW 표시 ON일 때만 대역폭 색상·두께 적용
  const link = topoZoomLayer.select('.links')
    .selectAll('line')
    .data(links, d => `${d.source?.id ?? d.source}-${d.target?.id ?? d.target}`)
    .join('line')
    .attr('stroke',       d => netPresetLinkColor(d)  ?? (bwLabelsVisible ? bwLinkColor(d.bw) : '#374151'))
    .attr('stroke-width', d => netPresetLinkStroke(d) ?? (bwLabelsVisible ? bwLinkStroke(d.bw) : 1.5));
  link.each(function(d) {
    const info = netPresetTooltip(d);
    const sel = d3.select(this);
    sel.select('title').remove();
    if (info) sel.append('title').text(info);
  });

  // Bandwidth labels — 링크 중점에 텍스트 표시. 네트워크 프리셋 세션이 켜져
  // 있으면 실측 처리량("4.6M")을, 아니면 BW 표시 ON일 때 정적 용량("10M")을 보여준다.
  const bwLabelGroup = topoZoomLayer.select('.bw-labels')
    .style('display', (bwLabelsVisible || netPresetStatsMap.size > 0) ? null : 'none');
  const bwLabel = bwLabelGroup
    .selectAll('text.live-bw')
    .data(links.filter(d => d.bw != null),
          d => `bw-${d.source?.id ?? d.source}-${d.target?.id ?? d.target}`)
    .join('text')
    .attr('class', 'live-bw')
    .attr('text-anchor', 'middle')
    .attr('font-size', 8)
    .attr('font-family', 'JetBrains Mono, monospace')
    .attr('pointer-events', 'none')
    .attr('fill', d => netPresetLinkColor(d) ?? bwLinkColor(d.bw))
    .text(d => netPresetLinkLabel(d) ?? (bwLabelsVisible ? `${d.bw}M` : ''));

  // 손실/큐 백로그 — 대역폭 텍스트 바로 아래 작은 줄 (문제 있는 링크만 표시)
  const issueLabel = bwLabelGroup
    .selectAll('text.live-issue')
    .data(links.filter(d => d.bw != null),
          d => `issue-${d.source?.id ?? d.source}-${d.target?.id ?? d.target}`)
    .join('text')
    .attr('class', 'live-issue')
    .attr('text-anchor', 'middle')
    .attr('font-size', 7)
    .attr('font-family', 'JetBrains Mono, monospace')
    .attr('pointer-events', 'none')
    .attr('fill', '#ef4444')
    .text(d => netPresetLinkIssue(d) || '');

  // Nodes
  const drag = d3.drag()
    .on('start', (ev, d) => {
      if (!ev.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x; d.fy = d.y;
    })
    .on('drag', (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
    .on('end',  (ev, d) => {
      if (!ev.active) simulation.alphaTarget(0);
      d.fx = null; d.fy = null;
    });

  const nodeG = topoZoomLayer.select('.nodes')
    .selectAll('g.live-node')
    .data(nodes, d => d.id)
    .join(enter => enter.append('g').attr('class', 'live-node'))
    .call(drag);

  nodeG.selectAll('*').remove();

  nodeG.each(function(d) {
    const g = d3.select(this);
    const fill = nodeColor(d);

    if (d.type === 'switch') {
      g.append('polygon')
        .attr('points', '0,-15 13,-7.5 13,7.5 0,15 -13,7.5 -13,-7.5')
        .attr('fill', fill)
        .attr('stroke', '#0a0e1a')
        .attr('stroke-width', 1.5);
    } else {
      g.append('circle')
        .attr('r', 10)
        .attr('fill', '#111827')
        .attr('stroke', '#3b82f6')
        .attr('stroke-width', 2);
    }

    g.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('font-size', 9)
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('fill', d.type === 'switch' ? '#0a0e1a' : '#f9fafb')
      .attr('font-weight', '700')
      .attr('pointer-events', 'none')
      .text(d.label);
  });

  simulation.on('tick', () => {
    // Read live container size each tick so clamp follows panel resizes
    const topoEl = document.getElementById('topology-graph');
    const cw = topoEl ? topoEl.clientWidth  : w;
    const ch = topoEl ? topoEl.clientHeight : h;
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);
    bwLabel
      .attr('x', d => (d.source.x + d.target.x) / 2)
      .attr('y', d => (d.source.y + d.target.y) / 2 - 4);
    issueLabel
      .attr('x', d => (d.source.x + d.target.x) / 2)
      .attr('y', d => (d.source.y + d.target.y) / 2 + 7);
    nodeG.attr('transform', d => {
      // clamp to svg bounds
      const x = Math.max(20, Math.min(cw - 20, d.x));
      const y = Math.max(20, Math.min(ch - 20, d.y));
      // Update continuously (not just on 'end') so twin packet paths
      // stay accurate while the user drags nodes
      nodePositions.set(d.id, { x, y });
      return `translate(${x},${y})`;
    });
  });

  simulation.on('end', () => {
    nodes.forEach(n => nodePositions.set(n.id, { x: n.x, y: n.y }));
  });
}

function nodeColor(d) {
  if (d.type === 'host') return '#3b82f6';
  return { forward: '#10b981', drop: '#f59e0b', offline: '#ef4444', idle: '#6b7280' }[d.state] || '#6b7280';
}

// 대역폭 → 링크 색상 (100M=녹색, 40M=파랑, 10M=노랑, ≤1M=회색)
function bwLinkColor(bw) {
  if (bw == null) return '#374151';
  if (bw >= 100) return '#10b981';
  if (bw >= 40)  return '#3b82f6';
  if (bw >= 10)  return '#f59e0b';
  return '#4b5563';
}

// 대역폭 → 링크 두께
function bwLinkStroke(bw) {
  if (bw == null) return 1.5;
  if (bw >= 100) return 2.5;
  if (bw >= 40)  return 2;
  if (bw >= 10)  return 1.5;
  return 1;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function statusIcon(status) {
  if (status === 'done')
    return `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3"><path d="M5 13l4 4L19 7" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  if (status === 'running')
    return `<svg width="16" height="16" viewBox="0 0 24 24" style="animation:spin 1s linear infinite"><circle cx="12" cy="12" r="9" fill="none" stroke="#1f2937" stroke-width="3"/><path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="#3b82f6" stroke-width="3" stroke-linecap="round"/></svg>`;
  if (status === 'error')
    return `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="3"><path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/></svg>`;
  if (status === 'skipped')
    return `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>`;
  return iconDot();
}

function iconDot() {
  return `<div style="width:8px;height:8px;border-radius:50%;background:#374151;margin:auto"></div>`;
}

function appendLogLine(stageNum, msg) {
  const el = document.getElementById(`live-${stageNum}`);
  if (!el) return;

  // 이전 current 라인 → done으로 강등
  const prev = el.querySelector('.log-line.current');
  if (prev) {
    prev.classList.remove('current');
    prev.classList.add('done');
  }

  // 새 라인 → current로 추가
  const line = document.createElement('div');
  line.className = 'log-line current';
  if (msg.startsWith('✓')) line.classList.add('log-ok');
  else if (msg.startsWith('✗')) line.classList.add('log-fail');
  else if (msg.startsWith('⚠')) line.classList.add('log-warn');
  line.textContent = msg;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

function fillIntent(text) {
  state.intent = text;
  document.getElementById('intent-input').value = text;
}

function setRunBtn(running) {
  const btn = document.getElementById('run-btn');
  btn.disabled = running;
  btn.innerHTML = running
    ? `<svg width="14" height="14" viewBox="0 0 24 24" style="animation:spin 1s linear infinite"><circle cx="12" cy="12" r="9" fill="none" stroke="rgba(255,255,255,0.3)" stroke-width="3"/><path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="white" stroke-width="3" stroke-linecap="round"/></svg> Running...`
    : `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> Run Pipeline`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Topology Refresh Countdown ────────────────────────────────────────────────

let topoFetching = false;

function startRefreshLoop() {
  async function tick() {
    if (!topoFetching) {
      topoFetching = true;
      await fetchTopology();
      topoFetching = false;
    }
    setTimeout(tick, 1000);
  }
  tick();
}

// ── Digital Twin Visualization ────────────────────────────────────────────────

function highlightPath(pathIds, color) {
  if (!topoSvg) return;
  clearPathHighlight();
  const linkSel = topoZoomLayer.select('.links').selectAll('line');
  for (let i = 0; i < pathIds.length - 1; i++) {
    const a = pathIds[i], b = pathIds[i + 1];
    linkSel.filter(d => {
      const s = String(typeof d.source === 'object' ? d.source.id : d.source);
      const t = String(typeof d.target === 'object' ? d.target.id : d.target);
      return (s === a && t === b) || (s === b && t === a);
    })
    .classed('path-active', true)
    .attr('stroke', color)
    .attr('stroke-width', 3)
    .attr('stroke-opacity', 0.75);
  }
}

function clearPathHighlight() {
  if (!topoSvg) return;
  topoZoomLayer.select('.links').selectAll('line.path-active')
    .classed('path-active', false)
    .attr('stroke', '#374151')
    .attr('stroke-width', 1.5)
    .attr('stroke-opacity', 1);
}

function stopTwinViz() {
  twinAnimTimers.forEach(t => clearTimeout(t));
  twinAnimTimers = [];
  clearPathHighlight();
  if (topoSvg) {
    topoSvg.selectAll('.twin-viz').remove();
    topoSvg.selectAll('.twin-node-indicator').remove();
  }
  if (topoZoomLayer) {
    topoZoomLayer.select('.twin-bw-layer').selectAll('.twin-bw-badge').remove();
  }
  twinVizInfoList = [];
  twinVizPhase    = 'idle';
}

function onTwinInfo(ev) {
  // host: IP 로 찾기
  const srcNode   = currentTopoNodes.find(n => n.type === 'host'   && n.ip === ev.src_ip) || null;
  const dstNode   = currentTopoNodes.find(n => n.type === 'host'   && n.ip === ev.dst_ip) || null;
  // switch: device_id "of:0000000000000001" → switchNum=1 → label "S1"
  let blockNode = null;
  if (ev.device_id) {
    const swNum  = parseInt(ev.device_id.replace('of:', ''), 16);
    const swLabel = `S${swNum}`;
    blockNode = currentTopoNodes.find(n => n.type === 'switch' && n.label === swLabel) || null;
  }
  twinVizInfoList.push({ srcNode, dstNode, blockNode, action: ev.action });
  twinVizPhase = 'idle';
  renderTwinHighlights();
}

// twin_bw: iperf 측정 결과를 토폴로지 링크 중점에 배지로 표시
function onTwinBw(ev) {
  if (!topoZoomLayer) return;
  const srcNode = currentTopoNodes.find(n => n.type === 'host' && n.ip === ev.src_ip) || null;
  const dstNode = currentTopoNodes.find(n => n.type === 'host' && n.ip === ev.dst_ip) || null;
  if (!srcNode || !dstNode) return;

  const srcPos = nodePositions.get(srcNode.id);
  const dstPos = nodePositions.get(dstNode.id);
  if (!srcPos || !dstPos) return;

  const mx = (srcPos.x + dstPos.x) / 2;
  const my = (srcPos.y + dstPos.y) / 2;

  // twin-bw-layer에 배지 추가 (BW 토글 무관, 줌과 함께 움직임)
  if (!topoZoomLayer) return;
  const layer = topoZoomLayer.select('.twin-bw-layer');
  if (layer.empty()) return;

  // 기존 배지 제거 후 새로 그리기
  layer.selectAll('.twin-bw-badge').remove();

  const badge = layer.append('g')
    .attr('class', 'twin-bw-badge')
    .attr('transform', `translate(${mx},${my})`);

  badge.append('rect')
    .attr('x', -20).attr('y', -8)
    .attr('width', 40).attr('height', 16)
    .attr('rx', 4)
    .attr('fill', '#0a0e1a')
    .attr('stroke', '#10b981')
    .attr('stroke-width', 1);

  badge.append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', '0.35em')
    .attr('font-size', 8)
    .attr('font-family', 'JetBrains Mono, monospace')
    .attr('fill', '#10b981')
    .text(`${ev.bw_mbps}M`);
}

function findTopoPath(fromId, toId) {
  const adj = {};
  currentTopoLinks.forEach(({ source, target }) => {
    (adj[source] = adj[source] || []).push(target);
    (adj[target] = adj[target] || []).push(source);
  });
  if (!adj[fromId]) return null;
  const visited = new Set([fromId]);
  const queue   = [[fromId]];
  while (queue.length) {
    const path = queue.shift();
    const node = path[path.length - 1];
    if (node === toId) return path;
    for (const nb of (adj[node] || [])) {
      if (!visited.has(nb)) { visited.add(nb); queue.push([...path, nb]); }
    }
  }
  return null;
}

function getTwinLayer() {
  if (!topoZoomLayer) return null;
  let layer = topoZoomLayer.select('.twin-viz');
  if (layer.empty()) layer = topoZoomLayer.append('g').attr('class', 'twin-viz');
  return layer;
}

function renderTwinHighlights() {
  if (!topoSvg) return;
  // Remove previous node-attached indicators
  topoSvg.selectAll('.twin-node-indicator').remove();
  if (!twinVizInfoList.length) return;

  // Collect unique node specs across all sub-rules
  // (compound: multiple src/dst/block entries may exist)
  const seenNodeIds = new Set();
  const specs = [];
  for (const { srcNode, dstNode, blockNode, action } of twinVizInfoList) {
    if (srcNode   && !seenNodeIds.has(srcNode.id))   { seenNodeIds.add(srcNode.id);   specs.push({ node: srcNode,   color: '#10b981', tag: 'SRC',   ip: srcNode.ip }); }
    if (dstNode   && !seenNodeIds.has(dstNode.id))   { seenNodeIds.add(dstNode.id);   specs.push({ node: dstNode,   color: '#60a5fa', tag: 'DST',   ip: dstNode.ip }); }
    if (blockNode && action === 'block' && !seenNodeIds.has(blockNode.id)) { seenNodeIds.add(blockNode.id); specs.push({ node: blockNode, color: '#ef4444', tag: 'BLOCK', ip: null }); }
  }

  specs.forEach(({ node, color, tag, ip }) => {
    const r = node.type === 'switch' ? 22 : 17;

    // Attach directly to the .live-node <g> so it inherits translate(x,y)
    // and follows the node when dragged
    topoSvg.selectAll('g.live-node')
      .filter(d => d.id === node.id)
      .each(function() {
        const g = d3.select(this);

        // Pulsing ring (cx/cy=0 → node center in local coords)
        g.append('circle')
          .attr('class', 'twin-node-indicator twin-ring')
          .attr('r', r).attr('cx', 0).attr('cy', 0)
          .attr('fill', 'none').attr('stroke', color).attr('stroke-width', 2.5)
          .attr('pointer-events', 'none');

        // Tag label above node
        g.append('text')
          .attr('class', 'twin-node-indicator')
          .attr('x', 0).attr('y', -r - 6)
          .attr('text-anchor', 'middle')
          .attr('font-size', 9).attr('font-weight', '700')
          .attr('font-family', 'JetBrains Mono, monospace')
          .attr('fill', color).attr('pointer-events', 'none')
          .text(tag);

        // IP address label (one line above the tag)
        if (ip) {
          g.append('text')
            .attr('class', 'twin-node-indicator')
            .attr('x', 0).attr('y', -r - 17)
            .attr('text-anchor', 'middle')
            .attr('font-size', 8)
            .attr('font-family', 'JetBrains Mono, monospace')
            .attr('fill', color).attr('opacity', 0.75).attr('pointer-events', 'none')
            .text(ip);
        }

        // BLOCK: red ✕ overlay on the switch
        if (tag === 'BLOCK') {
          g.append('text')
            .attr('class', 'twin-node-indicator')
            .attr('x', 0).attr('y', 5)
            .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
            .attr('font-size', 13).attr('font-weight', '700')
            .attr('fill', '#ef4444').attr('pointer-events', 'none')
            .text('✕');
        }
      });
  });
}

function spawnPacket(layer, pathIds, color, durationMs, stopIdx) {
  const initialPositions = pathIds.map(id => nodePositions.get(id)).filter(Boolean);
  if (initialPositions.length < 2) return;
  const endIdx = (stopIdx !== undefined) ? Math.min(stopIdx, initialPositions.length - 1) : initialPositions.length - 1;
  const segMs  = durationMs / (initialPositions.length - 1);

  const dot = layer.append('circle')
    .attr('r', 4.5).attr('fill', color).attr('opacity', 0.92)
    .attr('cx', initialPositions[0].x).attr('cy', initialPositions[0].y)
    .attr('pointer-events', 'none');

  let t = dot.transition().duration(0);
  for (let i = 1; i <= endIdx; i++) {
    const fromId = pathIds[i - 1];
    const toId   = pathIds[i];
    t = t.transition().duration(segMs).ease(d3.easeLinear)
         .tween('pos', () => (tv) => {
           const from = nodePositions.get(fromId);
           const to   = nodePositions.get(toId);
           if (!from || !to) return;
           dot.attr('cx', from.x + (to.x - from.x) * tv)
              .attr('cy', from.y + (to.y - from.y) * tv);
         });
  }

  if (stopIdx !== undefined && stopIdx < initialPositions.length - 1) {
    // Blocked: burst and vanish
    t.transition().duration(250).attr('r', 9).attr('opacity', 0).remove();
  } else {
    t.transition().duration(300).attr('opacity', 0).remove();
  }
}

function startPacketLoop(path, color, stopIdx) {
  if (!path || path.length < 2) return;
  highlightPath(path, color);
  const totalMs = Math.min(1800, path.length * 450);
  const interval = 650;

  function fire(offset) {
    if (!state.twinActive) return;
    const layer = getTwinLayer();
    if (!layer) return;
    spawnPacket(layer, path, color, totalMs, stopIdx);
    const t = setTimeout(() => fire(interval), interval);
    twinAnimTimers.push(t);
  }

  fire(0);
  // second stream with offset
  const t2 = setTimeout(() => fire(0), interval / 2);
  twinAnimTimers.push(t2);
}

function setTwinPhase(phase) {
  if (twinVizPhase === phase) return;
  twinVizPhase = phase;

  // Clear old animation timers only (keep highlights)
  twinAnimTimers.forEach(t => clearTimeout(t));
  twinAnimTimers = [];
  renderTwinHighlights(); // redraw highlights for new phase

  if (!twinVizInfoList.length || !topoSvg) return;
  // Use all sub-rule specs for animation; first entry drives baseline/regression logic
  const primary = twinVizInfoList[0];
  const { srcNode, dstNode } = primary;

  if (phase === 'baseline') {
    // Green packets: src → dst (no rule yet, full path)
    if (srcNode && dstNode) {
      const path = findTopoPath(srcNode.id, dstNode.id);
      if (path) startPacketLoop(path, '#10b981', undefined);
    }
  } else if (phase === 'deployed') {
    // FlowRule 배포 중 — 블록 스위치만 강조, 패킷 없음
  } else if (phase === 'intent') {
    // Animate each sub-rule's intent
    for (const { srcNode: sn, dstNode: dn, blockNode: bn, action } of twinVizInfoList) {
      if (action === 'block' && sn && bn) {
        const path = findTopoPath(sn.id, bn.id);
        if (path) startPacketLoop(path, '#f87171', path.length - 1);
      } else if (action !== 'block' && sn && dn) {
        const path = findTopoPath(sn.id, dn.id);
        if (path) startPacketLoop(path, '#10b981', undefined);
      }
    }
  } else if (phase === 'regression') {
    // Animate between two hosts that are neither src nor dst of any sub-rule
    const usedIds = new Set(twinVizInfoList.flatMap(v => [v.srcNode?.id, v.dstNode?.id].filter(Boolean)));
    const others  = currentTopoNodes.filter(n => n.type === 'host' && !usedIds.has(n.id));
    if (others.length >= 2) {
      const path = findTopoPath(others[0].id, others[1].id);
      if (path) startPacketLoop(path, '#818cf8', undefined);
    } else if (others.length === 1 && srcNode) {
      const path = findTopoPath(others[0].id, srcNode.id);
      if (path) startPacketLoop(path, '#818cf8', undefined);
    }
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────

function init() {
  // Build stage cards
  buildStageCards();

  // Intent textarea
  const intentInput = document.getElementById('intent-input');
  intentInput.addEventListener('input', e => {
    state.intent = e.target.value;
  });

  // Run button
  document.getElementById('run-btn').addEventListener('click', runPipeline);

  // Load State button (initial render)
  renderLoadStateBtn();

  // Intent presets
  initIntentPresets();

  // Settings
  document.getElementById('model-select').addEventListener('change', e => { state.model = e.target.value; });
  document.getElementById('toggle-rag').addEventListener('change',  e => { state.enableRag = e.target.checked; });
  document.getElementById('toggle-twin').addEventListener('change', e => { state.skipTwin  = e.target.checked; });
  document.getElementById('toggle-deploy').addEventListener('change', e => { state.skipDeploy = e.target.checked; });

  // Layout swap (restore saved state)
  if (localStorage.getItem('layout-swapped') === 'true') {
    document.getElementById('app').classList.add('layout-swapped');
  }
  document.getElementById('layout-swap-btn').addEventListener('click', toggleLayoutSwap);

  // BW 레이블 토글 버튼
  document.getElementById('topo-bw-toggle-btn').addEventListener('click', () => {
    bwLabelsVisible = !bwLabelsVisible;
    const btn = document.getElementById('topo-bw-toggle-btn');
    if (bwLabelsVisible) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
    applyNetPresetColors(); // 링크 색상·두께·대역폭 텍스트 즉시 업데이트
  });

  // Topology editor controls

  document.getElementById('topo-edit-btn').addEventListener('click', () => {
    if (editor.active) {
      exitEditMode();
    } else {
      enterEditMode().catch(err => console.error('[Editor] enterEditMode failed:', err));
    }
  });
  document.querySelectorAll('.tool-btn').forEach(btn => {
    btn.addEventListener('click', () => setEditorTool(btn.dataset.tool));
  });
  document.getElementById('topo-apply-btn').addEventListener('click', applyTopology);
  document.getElementById('topo-cancel-btn').addEventListener('click', exitEditMode);

  document.getElementById('clear-history-btn').addEventListener('click', async () => {
    if (!confirm('히스토리를 모두 삭제할까요?')) return;
    await fetch('/api/logs', { method: 'DELETE' });
    state.history = [];
    renderHistory();
  });

  // Load history + start topology refresh
  loadHistory();
  startRefreshLoop();

  // Auto-update example chips from saved custom topology on page load
  fetch('/api/topology/custom')
    .then(r => r.ok ? r.json() : null)
    .then(data => { if (data && (data.switches || []).length > 0) updateExampleChips(data); })
    .catch(() => {});

  // Sidebar collapse toggle
  initSidebarToggle();

  // Topology presets
  initTopoPresets();

  // Network preset (live traffic) panel
  initNetworkPresetPanel();

  // Panel resizer
  initPanelResizer();

  // Default topology panel width: as wide as possible
  const topoPanel = document.getElementById('topology-panel');
  if (topoPanel && !localStorage.getItem('topo-panel-width')) {
    topoPanel.style.width = Math.floor(window.innerWidth * 0.5) + 'px';
  } else if (topoPanel && localStorage.getItem('topo-panel-width')) {
    topoPanel.style.width = localStorage.getItem('topo-panel-width');
  }

  // Topo info sections: start collapsed
  document.querySelectorAll('.topo-info-section').forEach(section => {
    const body = section.querySelector('.topo-info-body');
    if (!body) return;
    section.classList.add('collapsed');
    body.style.maxHeight = '0';
  });
}

// ── Panel Resizer ─────────────────────────────────────────────────────────────

function initPanelResizer() {
  const resizer = document.getElementById('panel-resizer');
  const panel   = document.getElementById('topology-panel');
  if (!resizer || !panel) return;

  let startX, startWidth;

  resizer.addEventListener('mousedown', e => {
    startX     = e.clientX;
    startWidth = panel.offsetWidth;
    resizer.classList.add('dragging');
    document.body.style.userSelect = 'none';
    document.body.style.cursor     = 'col-resize';
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup',   onMouseUp);
    e.preventDefault();
  });

  function onMouseMove(e) {
    const swapped  = document.getElementById('app').classList.contains('layout-swapped');
    // Normal: topology is on the right → drag left (startX > clientX) expands panel
    // Swapped: topology is on the left → drag right (clientX > startX) expands panel
    const delta    = swapped ? e.clientX - startX : startX - e.clientX;
    const minWidth = 220;
    const maxWidth = Math.floor(window.innerWidth * 0.6);
    const newWidth = Math.min(Math.max(startWidth + delta, minWidth), maxWidth);
    panel.style.width = newWidth + 'px';
    syncTopoSize();
  }

  function onMouseUp() {
    resizer.classList.remove('dragging');
    document.body.style.userSelect = '';
    document.body.style.cursor     = '';
    localStorage.setItem('topo-panel-width', panel.style.width);
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup',   onMouseUp);
  }
}

// ── Topology Size Sync ────────────────────────────────────────────────────────

function syncTopoSize() {
  if (!topoSvg) return;
  const container = document.getElementById('topology-graph');
  const w = container.clientWidth  || 342;
  const h = container.clientHeight || 280;
  topoSvg.attr('viewBox', `0 0 ${w} ${h}`);
  if (editor.active) {
    renderEditorGraph();
  } else if (simulation) {
    simulation.force('center', d3.forceCenter(w / 2, h / 2));
    simulation.alpha(0.3).restart();
  }
}

// ── Collapsible Info Sections ─────────────────────────────────────────────────

function toggleInfoSection(id) {
  const section = document.getElementById(id);
  if (!section) return;
  const body      = section.querySelector('.topo-info-body');
  const collapsed = section.classList.toggle('collapsed');
  body.style.maxHeight = collapsed ? '0' : body.scrollHeight + 'px';
  setTimeout(syncTopoSize, 260);
}

function initIntentPresets() {
  const btn  = document.getElementById('intent-preset-btn');
  const menu = document.getElementById('intent-preset-menu');

  btn.addEventListener('click', e => {
    e.stopPropagation();
    const isOpen = menu.classList.contains('open');
    if (!isOpen) {
      menu.style.visibility = 'hidden';
      menu.style.display = 'block';
      const menuH = menu.offsetHeight;
      menu.style.display = '';
      menu.style.visibility = '';

      const r = btn.getBoundingClientRect();
      const spaceBelow = window.innerHeight - r.bottom - 8;
      if (spaceBelow >= menuH || spaceBelow >= 200) {
        menu.style.top    = (r.bottom + 5) + 'px';
        menu.style.bottom = '';
      } else {
        menu.style.top    = '';
        menu.style.bottom = (window.innerHeight - r.top + 5) + 'px';
      }
      menu.style.left = r.left + 'px';
    }
    menu.classList.toggle('open');
  });

  document.addEventListener('click', () => menu.classList.remove('open'));

  menu.querySelectorAll('.preset-item').forEach(item => {
    item.addEventListener('click', e => {
      e.stopPropagation();
      menu.classList.remove('open');
      fillIntent(item.dataset.intent);
    });
  });
}

function toggleTopoPanel() {
  const panel = document.getElementById('topology-panel');
  const collapsed = panel.classList.toggle('topo-collapsed');
  // After transition, sync resizer behaviour
  setTimeout(syncTopoSize, 310);
  // Shrink panel width when collapsed so main gets the space
  if (collapsed) {
    panel._savedWidth = panel.style.width;
    panel.style.width = '';
  } else {
    if (panel._savedWidth) panel.style.width = panel._savedWidth;
    setTimeout(syncTopoSize, 310);
  }
}

// ── Sidebar Toggle ────────────────────────────────────────────────────────────

function initSidebarToggle() {
  const btn     = document.getElementById('sidebar-toggle-btn');
  const sidebar = document.getElementById('sidebar');
  const stored  = localStorage.getItem('sidebar-collapsed') === 'true';

  if (stored) {
    sidebar.classList.add('collapsed');
    btn.textContent = '▶';
    btn.title = '사이드바 펼치기';
  }

  btn.addEventListener('click', () => {
    const collapsed = sidebar.classList.toggle('collapsed');
    btn.textContent = collapsed ? '▶' : '◀';
    btn.title       = collapsed ? '사이드바 펼치기' : '사이드바 접기';
    localStorage.setItem('sidebar-collapsed', collapsed);
  });
}

// ── Topology Presets ──────────────────────────────────────────────────────────

function initTopoPresets() {
  const btn  = document.getElementById('topo-preset-btn');
  const menu = document.getElementById('topo-preset-menu');

  btn.addEventListener('click', e => {
    e.stopPropagation();
    const isOpen = menu.classList.contains('open');
    if (!isOpen) {
      // Temporarily show to measure height
      menu.style.visibility = 'hidden';
      menu.style.display = 'block';
      const menuH = menu.offsetHeight;
      menu.style.display = '';
      menu.style.visibility = '';

      const r = btn.getBoundingClientRect();
      const spaceBelow = window.innerHeight - r.bottom - 8;
      if (spaceBelow >= menuH || spaceBelow >= 200) {
        menu.style.top    = (r.bottom + 5) + 'px';
        menu.style.bottom = '';
      } else {
        menu.style.top    = '';
        menu.style.bottom = (window.innerHeight - r.top + 5) + 'px';
      }
      menu.style.right = (window.innerWidth - r.right) + 'px';
    }
    menu.classList.toggle('open');
  });

  document.addEventListener('click', () => menu.classList.remove('open'));

  menu.querySelectorAll('.preset-item').forEach(item => {
    item.addEventListener('click', e => {
      e.stopPropagation();
      menu.classList.remove('open');
      applyPreset(item.dataset.preset);
    });
  });
}

async function applyPreset(presetName) {
  const preset = TOPOLOGY_PRESETS[presetName];
  if (!preset) return;
  // 현재 토폴로지 ID를 프리셋 키로 업데이트
  state.topologyId = presetName;
  renderLoadStateBtn();

  const payload = {
    switches: preset.switches,
    hosts:    preset.hosts,
    links:    preset.links,
  };

  const btn = document.getElementById('topo-preset-btn');
  const orig = btn.textContent;
  btn.textContent = '저장 중…';
  btn.disabled = true;

  try {
    // 1. Save to custom topology file
    await fetch('/api/topology/custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    // 2. Push to ONOS (best-effort)
    try {
      await fetch('/api/topology/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (_) {}

    // 3. Update intent chips and title flash
    updateExampleChips(payload);

    const titleEl = document.getElementById('topo-title');
    if (titleEl) {
      const prev = titleEl.textContent;
      titleEl.textContent = `${preset.label} 프리셋 적용됨`;
      setTimeout(() => { titleEl.textContent = prev; }, 3000);
    }

    // 4. Trigger immediate topology display refresh
    fetchTopology();

  } catch (err) {
    console.error('[Preset] apply failed:', err);
  }

  btn.textContent = orig;
  btn.disabled = false;
}

function toggleLayoutSwap() {
  const app     = document.getElementById('app');
  const swapped = app.classList.toggle('layout-swapped');
  localStorage.setItem('layout-swapped', swapped);
  const btn = document.getElementById('layout-swap-btn');
  if (btn) btn.title = swapped ? '원래 배치로 전환' : '좌우 배치 전환';
}


// ── Editor: undo stack ─────────────────────────────────────────────────────────

const editorHistory = [];

function editorPushHistory() {
  editorHistory.push({
    nodes: JSON.parse(JSON.stringify(editor.nodes)),
    links: JSON.parse(JSON.stringify(editor.links)),
  });
  if (editorHistory.length > 30) editorHistory.shift();
}

function editorUndo() {
  if (!editorHistory.length) return;
  const snap = editorHistory.pop();
  editor.nodes = snap.nodes;
  editor.links = snap.links;
  editor.selected = null;
  renderEditorGraph();
  renderPropsPanel();
}

// ── Editor: lasso (Shift+drag) ─────────────────────────────────────────────────

const lasso = { active: false, x0: 0, y0: 0, x1: 0, y1: 0 };

function updateLassoRect() {
  if (!topoSvg) return;
  const x = Math.min(lasso.x0, lasso.x1);
  const y = Math.min(lasso.y0, lasso.y1);
  const w = Math.abs(lasso.x1 - lasso.x0);
  const h = Math.abs(lasso.y1 - lasso.y0);
  topoSvg.select('#lasso-rect')
    .attr('x', x).attr('y', y).attr('width', w).attr('height', h)
    .attr('opacity', 1);
}

function commitLasso() {
  const x0 = Math.min(lasso.x0, lasso.x1);
  const x1 = Math.max(lasso.x0, lasso.x1);
  const y0 = Math.min(lasso.y0, lasso.y1);
  const y1 = Math.max(lasso.y0, lasso.y1);
  if (x1 - x0 < 5 && y1 - y0 < 5) return; // too small — treat as click, ignore
  const inside = editor.nodes.filter(n => n.x >= x0 && n.x <= x1 && n.y >= y0 && n.y <= y1);
  if (inside.length === 0) return;
  editorPushHistory();
  const ids = new Set(inside.map(n => n.id));
  editor.nodes = editor.nodes.filter(n => !ids.has(n.id));
  editor.links = editor.links.filter(l => !ids.has(l.source) && !ids.has(l.target));
  if (ids.has(editor.selected)) editor.selected = null;
  renderEditorGraph();
  renderPropsPanel();
}

function isEditorBg(ev) {
  // True if the click target is SVG background (not an ed-node or ed-link group)
  let el = ev.target;
  while (el && el !== topoSvg?.node()) {
    if (el.classList?.contains('ed-node') || el.classList?.contains('ed-link')) return false;
    el = el.parentElement;
  }
  return true;
}

// ── Keyboard shortcuts ──────────────────────────────────────────────────────────

document.addEventListener('keydown', ev => {
  const inInput = ev.target.tagName === 'INPUT' || ev.target.tagName === 'TEXTAREA';

  if (!editor.active || inInput) return;

  switch (ev.key) {
    case 's': setEditorTool('switch'); break;
    case 'h': setEditorTool('host');   break;
    case 'l': setEditorTool('link');   break;
    case 'd': setEditorTool('delete'); break;
    case 'Escape':
      if (editor.linking) {
        editor.linking = null;
        topoSvg?.select('#ghost-link').attr('opacity', 0);
        renderEditorGraph();
      } else {
        setEditorTool('select');
      }
      break;
    case 'Backspace':
    case 'Delete':
      if (editor.selected) {
        editorPushHistory();
        editor.nodes = editor.nodes.filter(n => n.id !== editor.selected);
        editor.links = editor.links.filter(l =>
          l.source !== editor.selected && l.target !== editor.selected
        );
        editor.selected = null;
        renderEditorGraph();
        renderPropsPanel();
        ev.preventDefault();
      }
      break;
    case 'z':
      if (ev.ctrlKey || ev.metaKey) { editorUndo(); ev.preventDefault(); }
      break;
  }
});

// ── Flow State ────────────────────────────────────────────────────────────────

async function loadFlowState() {
  const btn = document.getElementById('load-state-btn');
  if (btn) { btn.textContent = '불러오는 중…'; btn.disabled = true; }
  try {
    const resp = await fetch(`/api/flow-state/${encodeURIComponent(state.topologyId)}`);
    if (resp.status === 404) {
      state.preloadedFlows = [];
      renderLoadStateBtn();
      renderSavedStateTab([]);
      alert(`저장된 state 없음 (${state.topologyId})`);
      return;
    }
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    state.preloadedFlows = data.flows || [];
    renderLoadStateBtn();
    renderSavedStateTab(state.preloadedFlows, data.sync_status);
  } catch (err) {
    console.error('[FlowState] load failed:', err);
    alert(`Load State 오류: ${err.message}`);
  } finally {
    if (btn) { btn.disabled = false; }
    renderLoadStateBtn();
  }
}

function clearLoadedState() {
  state.preloadedFlows = [];
  renderLoadStateBtn();
  renderSavedStateTab([]);
}

async function deleteFlowStateEntry(index) {
  try {
    const resp = await fetch(
      `/api/flow-state/${encodeURIComponent(state.topologyId)}/flows/${index}`,
      { method: 'DELETE' }
    );
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    // 로컬 state에서도 제거
    state.preloadedFlows.splice(index, 1);
    renderLoadStateBtn();
    renderSavedStateTab(state.preloadedFlows);
  } catch (err) {
    console.error('[FlowState] delete failed:', err);
    alert(`삭제 오류: ${err.message}`);
  }
}

async function clearAllFlowState() {
  if (!confirm(`'${state.topologyId}' 토폴로지의 모든 저장된 FlowRule을 삭제하시겠습니까?`)) return;
  try {
    const resp = await fetch(
      `/api/flow-state/${encodeURIComponent(state.topologyId)}`,
      { method: 'DELETE' }
    );
    if (!resp.ok && resp.status !== 404) throw new Error(`HTTP ${resp.status}`);
    state.preloadedFlows = [];
    renderLoadStateBtn();
    renderSavedStateTab([]);
  } catch (err) {
    alert(`초기화 오류: ${err.message}`);
  }
}

function renderLoadStateBtn() {
  const btn = document.getElementById('load-state-btn');
  const clearBtn = document.getElementById('clear-state-btn');
  if (!btn) return;
  const n = state.preloadedFlows.length;
  if (n > 0) {
    btn.textContent = `⬇ Loaded ●${n}`;
    btn.classList.add('state-loaded');
    if (clearBtn) clearBtn.style.display = 'inline-flex';
  } else {
    btn.textContent = '⬇ Load State';
    btn.classList.remove('state-loaded');
    if (clearBtn) clearBtn.style.display = 'none';
  }
}

function renderSavedStateTab(flows, syncStatus) {
  // FLOW RULES 탭 전환 — Saved State 탭 활성화
  activateFlowTab('saved');

  const body = document.getElementById('saved-state-body');
  if (!body) return;

  if (!flows || flows.length === 0) {
    body.innerHTML = `<div style="padding:12px 10px;font-size:11px;color:#4b5563;font-family:'JetBrains Mono',monospace">저장된 state 없음</div>`;
    return;
  }

  // sync_status 배너
  let banner = '';
  if (syncStatus) {
    if (syncStatus.in_cache_not_onos > 0) {
      banner = `<div class="sync-banner warn">⚠ ${syncStatus.in_cache_not_onos}개 rule이 ONOS에 미설치 상태</div>`;
    } else if (syncStatus.in_onos_not_cache > 0) {
      banner = `<div class="sync-banner info">ℹ ${syncStatus.in_onos_not_cache}개 외부 rule 감지됨</div>`;
    }
  }

  body.innerHTML = banner + flows.map((f, i) => {
    const criteria = (f.selector || {}).criteria || [];
    const src = (criteria.find(c => c.type === 'IPV4_SRC') || {}).ip || '';
    const dst = (criteria.find(c => c.type === 'IPV4_DST') || {}).ip || '';
    const instructions = (f.treatment || {}).instructions || [];
    const isBlock = !instructions.length || instructions.some(inst => inst.type === 'NOACTION' || inst.type === 'DROP');
    const actionStr = isBlock ? 'DROP' : 'FORWARD';
    const actionColor = isBlock ? '#f59e0b' : '#10b981';
    const devShort = (f.deviceId || '').split(':').pop() || f.deviceId || '?';
    const meta = f._meta || {};
    const intent = meta.intent ? escHtml(meta.intent.slice(0, 40)) : '';
    return `
      <div class="saved-state-row">
        <div class="flow-cell-device" title="${escHtml(f.deviceId || '')}">${escHtml(devShort.replace(/^0+/, '') || devShort)}</div>
        <div class="flow-cell-pri">${f.priority || ''}</div>
        <div class="flow-cell-match">${escHtml(src ? `${src}→${dst}` : dst || '—')}</div>
        <div class="flow-cell-action" style="color:${actionColor}">
          <span class="flow-action-dot" style="background:${actionColor}"></span>
          ${actionStr}
        </div>
        ${intent ? `<div class="flow-cell-intent" title="${escHtml(meta.intent || '')}">${intent}</div>` : '<div></div>'}
        <button class="state-del-btn" onclick="deleteFlowStateEntry(${i})" title="이 rule 삭제">✕</button>
      </div>`;
  }).join('');
}

function activateFlowTab(tab) {
  const tabs = document.querySelectorAll('.flow-tab-btn');
  tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  const onos = document.getElementById('flow-table-section');
  const saved = document.getElementById('saved-state-section');
  if (onos) onos.style.display = tab === 'onos' ? '' : 'none';
  if (saved) saved.style.display = tab === 'saved' ? '' : 'none';
}

document.addEventListener('DOMContentLoaded', init);
window.addEventListener('resize', syncTopoSize);
