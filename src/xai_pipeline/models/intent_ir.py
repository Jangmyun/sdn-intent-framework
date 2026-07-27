"""
models/intent_ir.py — 인텐트 중간 표현(Intermediate Representation)

LLM이 파싱한 자연어 인텐트를 구조화된 형태로 저장한다.
Stage1(인텐트 파싱) → Stage2(FlowRule 컴파일)의 교환 형식.

── 스키마 구조 ──────────────────────────────────────────────────────────
  IntentIR
  ├── action          : 파이프라인 액션 타입 (forward/block/qos/sfc/reroute)
  ├── intent_type     : 의미 레이블 (forwarding/security/qos/sfc/reroute)
  ├── selector        : 트래픽 매칭 조건 (source/destination/protocol/port)
  ├── enforcement     : 집행 위치 (device/egress_port/alt_egress_port/vlan)
  ├── qos             : QoS 파라미터 (queue/bandwidth/latency)
  ├── routing         : 경로 지정 (waypoints/via_device/avoid_device)
  └── priority        : OpenFlow 우선순위

하위 호환 프로퍼티로 compiler.py / api.py 접근 방식은 그대로 유지.
"""
from __future__ import annotations

import ipaddress
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


def _is_valid_ip_with_mask(v: str) -> bool:
    """'ip' 또는 'ip/mask' 형식 검증 (옥텟 0-255, mask 0-32).

    단순 자릿수 패턴(예: 999.999.999.999)은 통과시키지 않는다 — LLM 환각으로
    나온 잘못된 옥텟이 그대로 FlowRule까지 흘러가는 것을 막기 위함.
    """
    parts = v.split("/")
    if len(parts) > 2:
        return False
    try:
        ipaddress.IPv4Address(parts[0])
    except ValueError:
        return False
    if len(parts) == 2:
        try:
            mask = int(parts[1])
        except ValueError:
            return False
        if not (0 <= mask <= 32):
            return False
    return True

# ── action → intent_type 자동 매핑 ───────────────────────────────────
_ACTION_TO_INTENT_TYPE: dict[str, str] = {
    "forward":  "forwarding",
    "block":    "security",
    "qos":      "qos",
    "sfc":      "sfc",
    "reroute":  "reroute",
}


# ════════════════════════════════════════════════════════════════════════
# 서브 모델
# ════════════════════════════════════════════════════════════════════════

class EndpointRef(BaseModel):
    """트래픽 출발지/목적지 엔드포인트 참조"""
    host: Optional[str] = None   # 호스트명 (예: "h1", "web-server")
    ip: Optional[str] = None     # IPv4 주소 with mask (예: "10.0.0.1/32")

    @field_validator("ip", mode="before")
    @classmethod
    def _normalize_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip()
        if not v:
            return None
        if not _is_valid_ip_with_mask(v):
            return None
        return v if "/" in v else v + "/32"


class IntentSelector(BaseModel):
    """트래픽 매칭 조건 — 어떤 패킷을 대상으로 하는가"""
    source: Optional[EndpointRef] = None
    destination: Optional[EndpointRef] = None
    eth_type: Optional[Literal["ipv4", "ipv6", "arp"]] = None
    protocol: Optional[Literal["tcp", "udp", "icmp"]] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    in_port: Optional[int] = None       # 입력 포트 매칭

    @field_validator("src_port", "dst_port", "in_port")
    @classmethod
    def _port_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (0 <= v <= 65535):
            raise ValueError(f"포트는 0~65535 범위여야 합니다. 현재: {v}")
        return v


class IntentEnforcement(BaseModel):
    """정책 집행 위치 및 출력 포트 — 어디서, 어느 포트로"""
    device: Optional[str] = None            # 스위치 힌트 (자연어 또는 ONOS ID)
    egress_port: Optional[int] = None       # 출력 포트 (forward/qos: 목적지, sfc: waypoint 포트)
    alt_egress_port: Optional[int] = None   # SFC waypoint 복귀 후 출력 포트 / reroute 대체 포트
    set_vlan_id: Optional[int] = None       # VLAN 태깅

    @field_validator("egress_port", "alt_egress_port")
    @classmethod
    def _egress_port_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (0 <= v <= 65535):
            raise ValueError(f"포트는 0~65535 범위여야 합니다. 현재: {v}")
        return v

    @field_validator("set_vlan_id")
    @classmethod
    def _vlan_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (0 <= v <= 4095):
            raise ValueError(f"VLAN ID는 0~4095 범위여야 합니다. 현재: {v}")
        return v


class IntentQoS(BaseModel):
    """QoS 파라미터 — 품질 요구사항"""
    queue: Optional[int] = None
    min_bandwidth_mbps: Optional[float] = None
    max_latency_ms: Optional[float] = None


class IntentRouting(BaseModel):
    """SFC / Reroute 경로 지정 — 어떤 경로를 통해"""
    waypoints: Optional[list[str]] = None   # SFC 경유 지점 (예: ["s2:9", "s3"])
    via_device: Optional[str] = None        # reroute: 이 스위치를 경유
    avoid_device: Optional[str] = None      # reroute: 이 스위치를 회피


# ════════════════════════════════════════════════════════════════════════
# 핵심 IR
# ════════════════════════════════════════════════════════════════════════

class IntentIR(BaseModel):
    """SDN 인텐트의 구조화된 중간 표현"""

    action: Literal["forward", "block", "qos", "sfc", "reroute"]
    intent_type: Optional[str] = None      # 의미 레이블 — 없으면 action으로부터 자동 파생
    selector: IntentSelector = Field(default_factory=IntentSelector)
    enforcement: Optional[IntentEnforcement] = None
    qos: Optional[IntentQoS] = None
    routing: Optional[IntentRouting] = None
    priority: Optional[int] = None

    # ── 의미 레이블 (XAI 설명용) ─────────────────────────────────────
    @property
    def resolved_intent_type(self) -> str:
        """action으로부터 자동 파생된 의미 레이블"""
        return self.intent_type or _ACTION_TO_INTENT_TYPE.get(self.action, "forwarding")

    # ── 하위 호환 프로퍼티 (compiler.py / api.py 변경 없이 사용 가능) ──

    @property
    def device_hint(self) -> str:
        if self.enforcement and self.enforcement.device:
            return self.enforcement.device
        return "switch 1"

    @property
    def src_ip(self) -> Optional[str]:
        return self.selector.source.ip if self.selector.source else None

    @property
    def dst_ip(self) -> Optional[str]:
        return self.selector.destination.ip if self.selector.destination else None

    @property
    def ip_proto(self) -> Optional[str]:
        return self.selector.protocol

    @property
    def src_port(self) -> Optional[int]:
        return self.selector.src_port

    @property
    def dst_port(self) -> Optional[int]:
        return self.selector.dst_port

    @property
    def in_port(self) -> Optional[int]:
        return self.selector.in_port

    @property
    def eth_type(self) -> Optional[str]:
        return self.selector.eth_type

    @property
    def out_port(self) -> Optional[int]:
        return self.enforcement.egress_port if self.enforcement else None

    @property
    def alt_out_port(self) -> Optional[int]:
        return self.enforcement.alt_egress_port if self.enforcement else None

    @property
    def vlan_id(self) -> Optional[int]:
        return self.enforcement.set_vlan_id if self.enforcement else None

    @property
    def queue_id(self) -> Optional[int]:
        return self.qos.queue if self.qos else None

    @property
    def waypoints(self) -> Optional[list]:
        return self.routing.waypoints if self.routing else None

    @property
    def via_device(self) -> Optional[str]:
        return self.routing.via_device if self.routing else None

    @property
    def avoid_device(self) -> Optional[str]:
        return self.routing.avoid_device if self.routing else None

    # ── 직렬화 ───────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """새 중첩 형식으로 직렬화 (None 필드 제외)"""
        result: dict = {
            "action": self.action,
            "intent_type": self.resolved_intent_type,
        }

        # selector
        sel: dict = {}
        if self.selector.source:
            src = self.selector.source.model_dump(exclude_none=True)
            if src:
                sel["source"] = src
        if self.selector.destination:
            dst = self.selector.destination.model_dump(exclude_none=True)
            if dst:
                sel["destination"] = dst
        for f in ("eth_type", "protocol", "src_port", "dst_port", "in_port"):
            v = getattr(self.selector, f)
            if v is not None:
                sel[f] = v
        if sel:
            result["selector"] = sel

        # enforcement
        if self.enforcement:
            enf = self.enforcement.model_dump(exclude_none=True)
            if enf:
                result["enforcement"] = enf

        # qos
        if self.qos:
            q = self.qos.model_dump(exclude_none=True)
            if q:
                result["qos"] = q

        # routing
        if self.routing:
            rt = self.routing.model_dump(exclude_none=True)
            if rt:
                result["routing"] = rt

        if self.priority is not None:
            result["priority"] = self.priority

        return result

    # ── LLM 출력 파싱 ────────────────────────────────────────────────

    @classmethod
    def from_llm_output(cls, raw: dict) -> "IntentIR":
        """
        LLM 출력 dict → IntentIR.

        새 중첩 형식(selector/enforcement/qos/routing)을 우선 파싱하고,
        구형 플랫 형식(src_ip/dst_ip/device_hint 등)도 폴백으로 지원한다.
        """

        def _safe_int(val) -> Optional[int]:
            if val is None:
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        # ── action ───────────────────────────────────────────────────
        action_raw = str(raw.get("action", "forward")).lower().strip()
        if action_raw not in ("forward", "block", "qos", "sfc", "reroute"):
            if any(w in action_raw for w in ("drop", "deny", "block", "reject")):
                action_raw = "block"
            elif any(w in action_raw for w in ("queue", "qos", "quality")):
                action_raw = "qos"
            elif any(w in action_raw for w in ("chain", "sfc", "waypoint", "middlebox")):
                action_raw = "sfc"
            elif any(w in action_raw for w in ("reroute", "redirect", "failover", "bypass")):
                action_raw = "reroute"
            else:
                action_raw = "forward"

        # ── intent_type ──────────────────────────────────────────────
        intent_type_raw = raw.get("intent_type") or None

        # ── selector ─────────────────────────────────────────────────
        sel_raw: dict = raw.get("selector") or {}

        def _validate_raw_ip(raw_ip, field_name: str) -> None:
            """LLM이 반환한 원본 ip 문자열을 정규화 전에 검증한다.

            EndpointRef._normalize_ip는 유효하지 않은 값을 조용히 None으로
            떨어뜨리므로, 여기서 먼저 검증해 환각된 IP(예: 999.999.999.999)를
            "제약 없음"으로 조용히 흘려보내지 않고 명시적으로 거부한다.
            """
            if not raw_ip:
                return
            if not _is_valid_ip_with_mask(str(raw_ip).strip()):
                raise ValueError(
                    f"LLM이 {field_name}에 유효하지 않은 값 '{raw_ip}'을 반환했습니다. "
                    "IP 주소(예: 10.0.0.1)를 포함한 인텐트를 입력해주세요."
                )

        # source
        src_raw = sel_raw.get("source") or {}
        if not src_raw and raw.get("src_ip"):          # 플랫 형식 폴백
            src_raw = {"ip": raw["src_ip"]}
        if isinstance(src_raw, str):
            src_raw = {"ip": src_raw}
        _validate_raw_ip(src_raw.get("ip"), "selector.source.ip")
        source_ref = EndpointRef(
            host=src_raw.get("host") or None,
            ip=src_raw.get("ip") or None,
        ) if src_raw else None

        # destination
        dst_raw = sel_raw.get("destination") or {}
        if not dst_raw and raw.get("dst_ip"):          # 플랫 형식 폴백
            dst_raw = {"ip": raw["dst_ip"]}
        if isinstance(dst_raw, str):
            dst_raw = {"ip": dst_raw}
        _validate_raw_ip(dst_raw.get("ip"), "selector.destination.ip")
        dest_ref = EndpointRef(
            host=dst_raw.get("host") or None,
            ip=dst_raw.get("ip") or None,
        ) if dst_raw else None

        # protocol
        proto_raw = sel_raw.get("protocol") or raw.get("ip_proto")
        if proto_raw:
            proto_raw = str(proto_raw).lower().strip()
            if proto_raw not in ("tcp", "udp", "icmp"):
                proto_raw = None

        # eth_type
        eth_raw = sel_raw.get("eth_type") or raw.get("eth_type")
        if eth_raw:
            eth_raw = str(eth_raw).lower().strip()
            if eth_raw not in ("ipv4", "ipv6", "arp"):
                eth_raw = None

        selector = IntentSelector(
            source=source_ref,
            destination=dest_ref,
            eth_type=eth_raw,
            protocol=proto_raw,
            src_port=_safe_int(sel_raw.get("src_port") or raw.get("src_port")),
            dst_port=_safe_int(sel_raw.get("dst_port") or raw.get("dst_port")),
            in_port=_safe_int(sel_raw.get("in_port") or raw.get("in_port")),
        )

        # ── enforcement ───────────────────────────────────────────────
        enf_raw: dict = raw.get("enforcement") or {}

        device_raw = enf_raw.get("device") or raw.get("device_hint") or raw.get("device")
        if not device_raw or str(device_raw).strip().lower() in ("none", "null", ""):
            device_raw = "switch 1"
        else:
            device_raw = str(device_raw).strip()

        enforcement = IntentEnforcement(
            device=device_raw,
            egress_port=_safe_int(
                enf_raw.get("egress_port") or raw.get("out_port")
            ),
            alt_egress_port=_safe_int(
                enf_raw.get("alt_egress_port") or raw.get("alt_out_port")
            ),
            set_vlan_id=_safe_int(
                enf_raw.get("set_vlan_id") or raw.get("vlan_id")
            ),
        )

        # ── qos ───────────────────────────────────────────────────────
        qos_raw: dict = raw.get("qos") or {}
        qos: Optional[IntentQoS] = None
        if action_raw == "qos" or qos_raw:
            qos = IntentQoS(
                queue=_safe_int(qos_raw.get("queue") or raw.get("queue_id")),
                min_bandwidth_mbps=qos_raw.get("min_bandwidth_mbps"),
                max_latency_ms=qos_raw.get("max_latency_ms"),
            )
            if (qos.queue is None
                    and qos.min_bandwidth_mbps is None
                    and qos.max_latency_ms is None):
                qos = None

        # ── routing ───────────────────────────────────────────────────
        rt_raw: dict = raw.get("routing") or {}
        waypoints_raw = rt_raw.get("waypoints") or raw.get("waypoints")
        via_raw = rt_raw.get("via_device") or raw.get("via_device")
        avoid_raw = rt_raw.get("avoid_device") or raw.get("avoid_device")

        routing: Optional[IntentRouting] = None
        if waypoints_raw or via_raw or avoid_raw:
            routing = IntentRouting(
                waypoints=(
                    [str(w) for w in waypoints_raw if w]
                    if isinstance(waypoints_raw, list)
                    else None
                ),
                via_device=str(via_raw).strip() if via_raw else None,
                avoid_device=str(avoid_raw).strip() if avoid_raw else None,
            )

        return cls(
            action=action_raw,
            intent_type=intent_type_raw,
            selector=selector,
            enforcement=enforcement,
            qos=qos,
            routing=routing,
            priority=_safe_int(raw.get("priority")),
        )


# ════════════════════════════════════════════════════════════════════════
# 복합 인텐트
# ════════════════════════════════════════════════════════════════════════

class CompoundIntentIR(BaseModel):
    """
    복합 인텐트의 중간 표현 — 여러 개의 IntentIR을 포함한다.

    예: "Allow HTTP from h1 to h2, but block SSH from h1 to h2"
    → rules = [
        IntentIR(action="forward", selector.dst_port=80, ...),
        IntentIR(action="block",   selector.dst_port=22, ...),
      ]
    """
    rules: list[IntentIR]
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "rules": [r.to_dict() for r in self.rules],
        }


# ════════════════════════════════════════════════════════════════════════
# 파싱 결과 래퍼
# ════════════════════════════════════════════════════════════════════════

class IntentPrediction(BaseModel):
    """
    LLM 파싱 + 토폴로지 검증 결과 래퍼.

    status="accepted" → program(단일) 또는 compound(복합)에 결과가 담긴다.
    status="rejected" → rejection_reason + rejection_detail에 이유가 담긴다.

    rejection_reason 값:
      ambiguous      — 인텐트가 너무 모호해 특정 액션으로 매핑 불가
      unknown_entity — 토폴로지에 없는 호스트/스위치 참조
      contradictory  — 서로 모순되는 요구 (동일 플로우 allow + block)
      unsupported    — 미지원 기능 (MPLS, multicast routing 등)
    """
    status: Literal["accepted", "rejected"]
    program: Optional["IntentIR"] = None
    compound: Optional["CompoundIntentIR"] = None
    rejection_reason: Optional[
        Literal["ambiguous", "unknown_entity", "contradictory", "unsupported"]
    ] = None
    rejection_detail: Optional[str] = None
