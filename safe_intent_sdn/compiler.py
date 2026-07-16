"""Deterministic compilation from controller-neutral Intent IR to ONOS flows."""
from __future__ import annotations

from ipaddress import ip_address
from typing import Mapping

from .intent_ir import Endpoint, IntentPrediction, IntentRule, TrafficSelector
from .onos import (
    EthTypeCriterion,
    InPortCriterion,
    IpCriterion,
    OnosFlow,
    OnosFlowSet,
    OnosSelector,
    OnosTreatment,
    OutputInstruction,
    ProtocolCriterion,
    QueueInstruction,
    TransportCriterion,
    VlanInstruction,
)


class CompilationError(ValueError):
    """Raised when valid IR cannot be represented safely as an ONOS flow."""


def compile_prediction(
    prediction: IntentPrediction,
    *,
    endpoint_ips: Mapping[str, str] | None = None,
    priority_start: int = 500,
    priority_step: int = 1,
) -> OnosFlowSet:
    """Compile an accepted prediction while preserving IR rule order.

    ``endpoint_ips`` resolves controller-neutral host names (for example ``h1``)
    to IP addresses. IP endpoints require no resolver. Placement is deliberately
    not inferred: every rule must identify its target device and forwarding-like
    rules must identify an egress port.
    """
    if prediction.status != "accepted" or prediction.program is None:
        raise CompilationError("a rejected intent cannot be compiled")
    if priority_step < 1:
        raise ValueError("priority_step must be at least 1")
    last_priority = priority_start - priority_step * (len(prediction.program.rules) - 1)
    if last_priority < 0:
        raise ValueError("generated priorities must be non-negative")

    resolver = endpoint_ips or {}
    flows: list[OnosFlow] = []
    for index, rule in enumerate(prediction.program.rules):
        try:
            flows.append(
                _compile_rule(
                    rule,
                    priority=priority_start - index * priority_step,
                    endpoint_ips=resolver,
                )
            )
        except CompilationError as exc:
            raise CompilationError(f"rule {index}: {exc}") from exc
    return OnosFlowSet(flows=flows)


def _compile_rule(
    rule: IntentRule,
    *,
    priority: int,
    endpoint_ips: Mapping[str, str],
) -> OnosFlow:
    enforcement = rule.enforcement
    if enforcement is None or enforcement.device is None:
        raise CompilationError("enforcement.device is required for placement")

    deny = rule.action == "deny"
    if deny:
        if enforcement.egress_port is not None or enforcement.set_vlan_id is not None:
            raise CompilationError("deny rules cannot contain output or VLAN actions")
        treatment = None
    else:
        if enforcement.egress_port is None:
            raise CompilationError(f"{rule.action} requires enforcement.egress_port")
        instructions = []
        if rule.intent_type == "qos":
            if rule.qos is None or rule.qos.queue is None:
                raise CompilationError("ONOS flow compilation requires an explicit QoS queue")
            instructions.append(QueueInstruction(type="QUEUE", queueId=rule.qos.queue))
        if enforcement.set_vlan_id is not None:
            instructions.append(
                VlanInstruction(
                    type="L2MODIFICATION",
                    subtype="VLAN_ID",
                    vlanId=enforcement.set_vlan_id,
                )
            )
        instructions.append(OutputInstruction(type="OUTPUT", port=enforcement.egress_port))
        treatment = OnosTreatment(instructions=instructions)

    return OnosFlow(
        priority=priority,
        timeout=0,
        isPermanent=True,
        deviceId=enforcement.device,
        selector=OnosSelector(criteria=_compile_selector(rule.selector, endpoint_ips)),
        treatment=treatment,
    )


def _compile_selector(
    selector: TrafficSelector,
    endpoint_ips: Mapping[str, str],
) -> list:
    source = _resolve_endpoint(selector.source, endpoint_ips)
    destination = _resolve_endpoint(selector.destination, endpoint_ips)
    addresses = [value for value in (source, destination) if value is not None]
    versions = {ip_address(value).version for value in addresses}
    if len(versions) > 1:
        raise CompilationError("source and destination use different IP families")

    eth_type = selector.eth_type
    inferred = {4: "ipv4", 6: "ipv6"}.get(next(iter(versions), None))
    if eth_type == "arp" and addresses:
        raise CompilationError("ARP endpoint matching is not representable by this ONOS schema")
    if eth_type is not None and inferred is not None and eth_type != inferred:
        raise CompilationError("eth_type conflicts with endpoint IP family")
    effective_eth_type = eth_type or inferred
    if effective_eth_type == "ipv6" and selector.protocol == "icmp":
        raise CompilationError("IR protocol icmp denotes IPv4 ICMP, not ICMPv6")

    criteria = []
    if effective_eth_type is not None:
        criteria.append(
            EthTypeCriterion(
                type="ETH_TYPE",
                ethType={"ipv4": "0x0800", "ipv6": "0x86DD", "arp": "0x0806"}[
                    effective_eth_type
                ],
            )
        )
    if selector.protocol is not None:
        criteria.append(
            ProtocolCriterion(
                type="IP_PROTO", protocol={"icmp": 1, "tcp": 6, "udp": 17}[selector.protocol]
            )
        )
    family = "IPV6" if effective_eth_type == "ipv6" else "IPV4"
    if source is not None:
        criteria.append(IpCriterion(type=f"{family}_SRC", ip=_prefix(source)))
    if destination is not None:
        criteria.append(IpCriterion(type=f"{family}_DST", ip=_prefix(destination)))
    transport = selector.protocol.upper() if selector.protocol in {"tcp", "udp"} else None
    if selector.source_port is not None:
        criteria.append(_transport_criterion(transport, "SRC", selector.source_port))
    if selector.destination_port is not None:
        criteria.append(_transport_criterion(transport, "DST", selector.destination_port))
    if selector.ingress_port is not None:
        criteria.append(InPortCriterion(type="IN_PORT", port=selector.ingress_port))
    return criteria


def _resolve_endpoint(endpoint: Endpoint | None, endpoint_ips: Mapping[str, str]) -> str | None:
    if endpoint is None:
        return None
    value = endpoint.ip
    if endpoint.host is not None:
        value = endpoint_ips.get(endpoint.host)
        if value is None:
            raise CompilationError(f"no IP mapping for host {endpoint.host!r}")
    assert value is not None
    try:
        return str(ip_address(value.split("/", 1)[0]))
    except ValueError as exc:
        raise CompilationError(f"invalid endpoint IP {value!r}") from exc


def _prefix(value: str) -> str:
    return f"{value}/{32 if ip_address(value).version == 4 else 128}"


def _transport_criterion(protocol: str | None, direction: str, port: int) -> TransportCriterion:
    if protocol is None:
        raise CompilationError("transport port requires TCP or UDP")
    values = {"type": f"{protocol}_{direction}"}
    values["tcpPort" if protocol == "TCP" else "udpPort"] = port
    return TransportCriterion.model_validate(values)
