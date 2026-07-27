"""
pipeline/flow_state_manager.py — 토폴로지별 FlowRule 누적 상태 관리

각 토폴로지의 배포 성공 flow들을 JSON 파일로 캐시한다.
파이프라인 Stage 6 성공 시 자동 저장, 사용자 명시적 Load State 시 제공.

커스텀 토폴로지('custom')는 구조 변경 시 topo_hash로 캐시를 자동 무효화한다.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent.parent
FLOW_STATE_DIR = _BASE_DIR / "data" / "flow_state"

# FastAPI는 동기 경로 함수를 threadpool에서 실행하므로, 동시 요청이 같은
# state 파일을 동시에 read-modify-write할 수 있다. 프로세스 내 동시 접근만
# 막으면 되므로(멀티 프로세스 배포는 가정하지 않음) 단순 전역 락으로 충분하다.
_LOCK = threading.Lock()


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _state_path(topology_id: str) -> Path:
    FLOW_STATE_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = topology_id.replace("/", "_").replace("\\", "_")
    return FLOW_STATE_DIR / f"{safe_id}.json"


def _read_file(topology_id: str) -> dict:
    p = _state_path(topology_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[FlowState] {topology_id} 파일 읽기 실패: {e}")
        return {}


def _write_file(topology_id: str, data: dict) -> None:
    """임시 파일에 쓴 뒤 os.replace()로 원자적 교체 — 쓰기 도중 프로세스가
    죽어도 기존 파일이 손상되지 않는다(부분 쓰기 상태로 남지 않음)."""
    p = _state_path(topology_id)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


def _strip_meta(flows: list[dict]) -> list[dict]:
    """_meta 필드를 제거해 ONOS REST API에 전달 가능한 형식으로 변환."""
    result = []
    for f in flows:
        clean = {k: v for k, v in f.items() if k != "_meta"}
        result.append(clean)
    return result


# ── 공개 API ──────────────────────────────────────────────────────────────────

def compute_topo_hash(custom_data: dict) -> str:
    """
    custom_topology.json의 구조(switches id/dpid + links source/target)를 해싱.
    x/y 좌표, label 등 레이아웃 정보는 제외 — 네트워크 구조만 비교.
    """
    key = {
        "switches": sorted(
            [{"id": s["id"], "dpid": s.get("dpid", "")} for s in custom_data.get("switches", [])],
            key=lambda x: x["id"],
        ),
        "links": sorted(
            [{"s": min(l["source"], l["target"]), "t": max(l["source"], l["target"])}
             for l in custom_data.get("links", [])],
            key=lambda x: (x["s"], x["t"]),
        ),
    }
    return hashlib.md5(json.dumps(key, sort_keys=True).encode()).hexdigest()[:8]


def load_state(topology_id: str, topo_hash: Optional[str] = None) -> list[dict]:
    """
    저장된 FlowRule 목록을 반환. 없으면 [].

    topo_hash가 제공되고 저장된 해시와 다르면 캐시를 무효화([] 반환).
    커스텀 토폴로지 전용 — 프리셋은 topo_hash 없이 호출.
    """
    state = _read_file(topology_id)
    if not state:
        return []
    if topo_hash is not None and state.get("topo_hash") != topo_hash:
        logger.warning(
            f"[FlowState] '{topology_id}' 토폴로지 구조 변경 감지 "
            f"(stored={state.get('topo_hash')}, current={topo_hash}) — 캐시 무효화"
        )
        return []
    return state.get("flows", [])


def save_flows(
    topology_id: str,
    new_flows: list[dict],
    intent_summary: str = "",
    topo_hash: Optional[str] = None,
) -> None:
    """
    기존 state에 new_flows를 추가 저장 (누적).

    각 flow에 _meta 필드(배포 시각, 인텐트 요약)를 첨부해 UI 표시에 활용.
    topo_hash는 커스텀 토폴로지에만 사용.
    """
    with _LOCK:
        state = _read_file(topology_id)
        existing_flows: list[dict] = state.get("flows", [])

        now = datetime.now(timezone.utc).isoformat()
        annotated = []
        for f in new_flows:
            entry = dict(f)
            entry["_meta"] = {
                "intent": intent_summary,
                "deployed_at": now,
            }
            annotated.append(entry)

        updated_flows = existing_flows + annotated
        payload: dict = {
            "topology_id": topology_id,
            "flows": updated_flows,
            "updated_at": now,
        }
        if topo_hash is not None:
            payload["topo_hash"] = topo_hash

        _write_file(topology_id, payload)
    logger.info(f"[FlowState] '{topology_id}' state 저장: +{len(new_flows)}개 → 총 {len(updated_flows)}개")


def remove_flow(topology_id: str, flow_index: int) -> Optional[dict]:
    """
    특정 인덱스의 flow를 state에서 제거. 제거된 flow 반환, 없으면 None.
    """
    with _LOCK:
        state = _read_file(topology_id)
        flows: list[dict] = state.get("flows", [])
        if flow_index < 0 or flow_index >= len(flows):
            return None
        removed = flows.pop(flow_index)
        state["flows"] = flows
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_file(topology_id, state)
    logger.info(f"[FlowState] '{topology_id}' flow[{flow_index}] 삭제됨")
    return removed


def clear_state(topology_id: str) -> bool:
    """해당 토폴로지의 state 파일 삭제. 삭제 성공 여부 반환."""
    p = _state_path(topology_id)
    if p.exists():
        p.unlink()
        logger.info(f"[FlowState] '{topology_id}' state 초기화됨")
        return True
    return False


def list_states() -> dict[str, dict]:
    """
    모든 토폴로지의 state 요약 반환.
    { topology_id: { "count": int, "updated_at": str } }
    """
    result = {}
    if not FLOW_STATE_DIR.exists():
        return result
    for p in sorted(FLOW_STATE_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            topo_id = data.get("topology_id", p.stem)
            result[topo_id] = {
                "count": len(data.get("flows", [])),
                "updated_at": data.get("updated_at", ""),
            }
        except Exception:
            continue
    return result


def get_state_detail(topology_id: str) -> Optional[dict]:
    """
    특정 토폴로지의 전체 state 반환. 없으면 None.
    반환 형식: { "topology_id", "flows", "updated_at", "topo_hash"(optional) }
    """
    state = _read_file(topology_id)
    if not state:
        return None
    return state


# ── 편의 함수 ─────────────────────────────────────────────────────────────────

def strip_meta_for_deploy(flows: list[dict]) -> list[dict]:
    """ONOS 배포 전 _meta 필드 제거용 공개 래퍼."""
    return _strip_meta(flows)
