"""
stage1_intent/intent_parser.py — 자연어 인텐트 → IntentIR 변환

LLM을 사용해 자연어를 구조화된 IntentIR로 파싱한다.
RAG가 활성화된 경우 유사 예시를 system prompt에 추가한다.
topology가 제공된 경우 시스템 프롬프트에 주입하고,
파싱 후 엔티티를 토폴로지 인벤토리와 대조하여 환각을 탐지한다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from models.intent_ir import IntentIR, IntentPrediction, CompoundIntentIR

if TYPE_CHECKING:
    from stage1_intent.llm_client import LLMClient
    from models.topology import NetworkTopology

SYSTEM_PROMPT = """You are an SDN network intent parser. Output strict JSON only — no explanation.

## Output format

For VALID intents:
{
  "rules": [
    {
      "action": "forward" | "block" | "qos" | "sfc" | "reroute",
      "intent_type": "forwarding" | "security" | "qos" | "sfc" | "reroute",
      "selector": {
        "source":      {"host": "<name or null>", "ip": "<x.x.x.x/mask or null>"},
        "destination": {"host": "<name or null>", "ip": "<x.x.x.x/mask or null>"},
        "eth_type": "ipv4" | "ipv6" | "arp" | null,
        "protocol": "tcp" | "udp" | "icmp" | null,
        "src_port": <int or null>,
        "dst_port": <int or null>,
        "in_port":  <int or null>
      },
      "enforcement": {
        "device":          "<switch name or number as mentioned>",
        "egress_port":     <int or null>,
        "alt_egress_port": <int or null>,
        "set_vlan_id":     <int or null>
      },
      "qos": {
        "queue":               <int or null>,
        "min_bandwidth_mbps":  <float or null>,
        "max_latency_ms":      <float or null>
      } | null,
      "routing": {
        "waypoints":    ["<device:port>" ...] | null,
        "via_device":   "<switch name>" | null,
        "avoid_device": "<switch name>" | null
      } | null,
      "priority": <int or null>
    }
  ],
  "description": "<one-line summary of the overall intent>"
}

For INVALID intents:
{"status": "rejected", "rejection_reason": "<reason>", "rejection_detail": "<brief explanation>"}

## action / intent_type mapping

| action   | intent_type  | when to use                                              |
|----------|--------------|----------------------------------------------------------|
| forward  | forwarding   | routing, forwarding, sending traffic to a destination    |
| block    | security     | dropping, blocking, denying, firewall rules              |
| qos      | qos          | queue assignment, bandwidth guarantee, prioritization    |
| sfc      | sfc          | traffic must pass through a middlebox/firewall/IDS first |
| reroute  | reroute      | path redirection, failover, bypass, alternate path       |

## Field rules

selector:
- source/destination: set ip to numeric IPv4 (append /32 if no mask); host is the name if mentioned
- eth_type: set "ipv4" when IP addresses or protocol are involved; null for port-only rules
- protocol: "tcp", "udp", or "icmp" only; null if not mentioned
- in_port: set when the intent specifies an ingress port on the switch

enforcement:
- device: the switch name/number exactly as mentioned (e.g. "switch 1", "s2")
- egress_port: output port number
  - forward/block/qos: the port traffic exits the switch
  - sfc: the waypoint port (e.g. port 9 for IDS)
- alt_egress_port: only for sfc — the egress port AFTER returning from the waypoint

qos: set to null unless action=qos; fill queue/bandwidth/latency as specified

routing: set to null unless action=sfc or action=reroute
- sfc: set waypoints = list of "switch:port" identifiers for the service chain
- reroute: set via_device (switch to route through) or avoid_device (switch to bypass)

## Compound intents

When the intent describes MULTIPLE independent policies (joined by "and", "but", "also", etc.),
output one rule per sub-policy in the rules array.

Examples:
- "Allow HTTP from 10.0.0.1 to 10.0.0.2 on switch 1, but block SSH between them"
  → rules[0]: action=forward, intent_type=forwarding, selector.dst_port=80, selector.protocol=tcp
  → rules[1]: action=block,   intent_type=security,   selector.dst_port=22, selector.protocol=tcp
- "Forward HTTP from 10.0.0.1 to 10.0.0.3 via port 2 on switch 1,
   and block all traffic from 10.0.0.2 to 10.0.0.4 on switch 2"
  → rules[0]: action=forward, enforcement.device=switch 1, enforcement.egress_port=2
  → rules[1]: action=block,   enforcement.device=switch 2

## Rejection reasons

- "ambiguous"      : too vague to map to a concrete action
    e.g. "make network better", "optimize traffic", "prioritize h1" (no specific action/target)
- "contradictory"  : mutually exclusive requirements on the SAME traffic flow
    e.g. "allow AND block h1→h2 TCP 80 on switch 1"
    (compound intents targeting DIFFERENT flows are NOT contradictory)
- "unsupported"    : requires functionality beyond forward/block/qos/sfc/reroute
    e.g. configure MPLS, multicast routing, reboot switch, upgrade firmware
- "unknown_entity" : references a host, IP, or switch not in the topology
    e.g. "h9", "database-server", "10.0.0.99", "switch 99"

## Selector completeness requirements

- A rule is VALID as long as its selector has at least ONE concrete match criterion:
  source, destination, protocol, a port number, or an ingress port (in_port).
  One-sided flows ARE supported:
  Valid: "On switch 1, drop all traffic from 10.0.0.1"          (source only)
  Valid: "On switch 4, block traffic to h4"                     (destination only)
  Valid: "Drop packets arriving on port 3 of switch 1"          (in_port only)
  Valid: "On switch 1, forward traffic for 10.0.0.2 out port 4" (destination + egress port)
- Exception — action=forward with NO destination and NO egress_port (outside a
  compound default clause) is ambiguous: there is no way to know where the
  traffic should go.
  Invalid: "Forward traffic from 10.0.0.1 on switch 1" (source only, no target → ambiguous)
- Compound default clauses ("and forward everything else normally", "keep
  forwarding the rest") are VALID: emit a catch-all rule with
  selector.eth_type="ipv4" and all other selector fields null.
  Example: "Drop all traffic from h2 on switch 1 and forward everything else normally"
  → rules[0]: action=block,   selector.source.host=h2,       enforcement.device=switch 1
  → rules[1]: action=forward, selector.eth_type="ipv4" (catch-all), enforcement.device=switch 1
- Reject with "ambiguous" ONLY when no concrete match criterion AND no concrete
  action can be identified (e.g. "make the network better", "optimize traffic").
- Do NOT invent IPs, hosts, switches, or ports that are not stated in the intent
  or present in the topology inventory."""


class IntentParser:
    """자연어 인텐트를 IntentPrediction(IntentIR 래퍼)으로 변환하는 파서"""

    def __init__(
        self,
        client: "LLMClient",
        rag_index=None,
        rag_texts: Optional[list[str]] = None,
        rag_outputs: Optional[list[str]] = None,
        k: int = 3,
        topology: Optional["NetworkTopology"] = None,
    ) -> None:
        self.client = client
        self.rag_index = rag_index
        self.rag_texts = rag_texts
        self.rag_outputs = rag_outputs
        self.k = k
        self.topology = topology

    def parse(self, intent: str, repair_feedback: str | None = None) -> IntentPrediction:
        """
        자연어 인텐트를 파싱하여 IntentPrediction으로 반환한다.

        단일 룰 인텐트 → IntentPrediction(program=IntentIR)
        복합 룰 인텐트 → IntentPrediction(compound=CompoundIntentIR)

        repair_feedback: 이전 검증 실패 피드백 (Repair Loop에서 재시도 시 사용)

        Raises:
            ValueError: LLM 응답 없음 또는 JSON 파싱 실패
        """
        system = self._build_system_prompt(intent)
        user_msg = intent if not repair_feedback else f"{intent}\n\n{repair_feedback}"
        raw = self.client.call(system, user_msg)

        if raw is None:
            raise ValueError(
                f"LLM이 응답을 반환하지 않았습니다. 인텐트: {intent[:80]}"
            )

        # ── LLM 자체 거부 감지 ────────────────────────────────────
        if raw.get("status") == "rejected":
            reason_raw = str(raw.get("rejection_reason", "")).strip().lower()
            valid_reasons = {"ambiguous", "contradictory", "unsupported", "unknown_entity"}
            reason = reason_raw if reason_raw in valid_reasons else "ambiguous"
            detail = str(raw.get("rejection_detail", "")).strip()
            return IntentPrediction(
                status="rejected",
                rejection_reason=reason,
                rejection_detail=detail or f"LLM rejected: {reason}",
            )

        # ── rules 배열 파싱 ──────────────────────────────────────
        rules_raw = raw.get("rules")
        if rules_raw and isinstance(rules_raw, list):
            return self._parse_rules(rules_raw, raw.get("description", ""))

        # ── 하위 호환: 구형 단일 JSON 형식 처리 ─────────────────
        return self._parse_single(raw)

    def _parse_single(self, raw: dict) -> IntentPrediction:
        """단일 룰 JSON → IntentPrediction(program=IntentIR)"""
        ir = IntentIR.from_llm_output(raw)
        if self.topology is not None:
            violation = self.topology.check_intent(
                src_ip=ir.src_ip,
                dst_ip=ir.dst_ip,
                device_hint=ir.device_hint,
            )
            if violation is not None:
                reason, detail = violation
                return IntentPrediction(
                    status="rejected",
                    rejection_reason=reason,
                    rejection_detail=detail,
                )
        return IntentPrediction(status="accepted", program=ir)

    def _parse_rules(self, rules_raw: list, description: str) -> IntentPrediction:
        """rules 배열 JSON → 단일 또는 복합 IntentPrediction"""
        parsed: list[IntentIR] = []
        for i, rule_raw in enumerate(rules_raw):
            try:
                ir = IntentIR.from_llm_output(rule_raw)
            except Exception as exc:
                return IntentPrediction(
                    status="rejected",
                    rejection_reason="ambiguous",
                    rejection_detail=f"rule[{i}] 파싱 실패: {exc}",
                )
            # 토폴로지 그라운딩 검증
            if self.topology is not None:
                violation = self.topology.check_intent(
                    src_ip=ir.src_ip,
                    dst_ip=ir.dst_ip,
                    device_hint=ir.device_hint,
                )
                if violation is not None:
                    reason, detail = violation
                    return IntentPrediction(
                        status="rejected",
                        rejection_reason=reason,
                        rejection_detail=f"rule[{i}]: {detail}",
                    )
            parsed.append(ir)

        if not parsed:
            return IntentPrediction(
                status="rejected",
                rejection_reason="ambiguous",
                rejection_detail="LLM이 rules 배열을 비워서 반환했습니다.",
            )

        # 단일 룰이면 program으로 반환 (하위 호환)
        if len(parsed) == 1:
            return IntentPrediction(status="accepted", program=parsed[0])

        # 복합 룰
        return IntentPrediction(
            status="accepted",
            compound=CompoundIntentIR(rules=parsed, description=description),
        )

    def _build_system_prompt(self, intent: str) -> str:
        """토폴로지 컨텍스트 + RAG 예시를 system prompt에 추가"""
        base = SYSTEM_PROMPT

        # 토폴로지 주입 (환각 억제)
        if self.topology is not None:
            base = self.topology.to_prompt_text() + "\n\n" + base

        # RAG 예시 추가
        if self.rag_index is not None and self.rag_texts and self.rag_outputs:
            from stage1_intent.rag import search_similar

            similar = search_similar(
                query=intent,
                index=self.rag_index,
                texts=self.rag_texts,
                outputs=self.rag_outputs,
                client=self.client,
                k=self.k,
            )

            if similar:
                examples = "\n\n".join(
                    f"Input: {txt}\nOutput: {out}" for txt, out in similar
                )
                base = (
                    base
                    + f"\n\nRelevant examples retrieved from knowledge base:\n\n{examples}\n"
                )

        return base
