"""Strict ONOS flow response models and ordered-rule normalization."""
from __future__ import annotations
from typing import Annotated, Any, Literal, Union
from pydantic import Field, model_validator
from .intent_ir import Endpoint, EnforcementConstraint, IntentPrediction, IntentProgram, IntentRule, QosConstraint, StrictModel, TrafficSelector

class EthTypeCriterion(StrictModel):
    type: Literal["ETH_TYPE"]
    ethType: str
class IpCriterion(StrictModel):
    type: Literal["IPV4_SRC", "IPV4_DST", "IPV6_SRC", "IPV6_DST"]
    ip: str
class ProtocolCriterion(StrictModel):
    type: Literal["IP_PROTO"]
    protocol: int
class TransportCriterion(StrictModel):
    type: Literal["TCP_SRC", "TCP_DST", "UDP_SRC", "UDP_DST"]
    tcpPort: int | None = Field(default=None, ge=1, le=65535)
    udpPort: int | None = Field(default=None, ge=1, le=65535)
    @model_validator(mode="after")
    def correct_port(self) -> "TransportCriterion":
        tcp = self.type.startswith("TCP")
        if tcp != (self.tcpPort is not None) or tcp == (self.udpPort is not None): raise ValueError("criterion must carry its matching transport port")
        return self
class InPortCriterion(StrictModel):
    type: Literal["IN_PORT"]
    port: int
Criterion = Annotated[Union[EthTypeCriterion, IpCriterion, ProtocolCriterion, TransportCriterion, InPortCriterion], Field(discriminator="type")]
class OutputInstruction(StrictModel):
    type: Literal["OUTPUT"]
    port: str | int
class QueueInstruction(StrictModel):
    type: Literal["QUEUE"]
    queueId: int = Field(ge=0)
class VlanInstruction(StrictModel):
    type: Literal["L2MODIFICATION"]
    subtype: Literal["VLAN_ID"]
    vlanId: int = Field(ge=0, le=4095)
Instruction = Annotated[Union[OutputInstruction, QueueInstruction, VlanInstruction], Field(discriminator="type")]
class OnosSelector(StrictModel):
    criteria: list[Criterion]
class OnosTreatment(StrictModel):
    instructions: list[Instruction] = Field(min_length=1)
class OnosFlow(StrictModel):
    priority: int
    timeout: int
    isPermanent: bool | str
    deviceId: str
    selector: OnosSelector
    treatment: OnosTreatment | None = None
class OnosFlowSet(StrictModel):
    flows: list[OnosFlow] = Field(min_length=1)

def parse_onos_response(value: dict[str, Any]) -> IntentPrediction:
    if value == {}: return IntentPrediction(status="rejected", rejection={"reason": "unsupported"})
    flow_set = OnosFlowSet.model_validate(value)
    flows = sorted(enumerate(flow_set.flows), key=lambda p: (-p[1].priority, p[0]))
    return IntentPrediction(status="accepted", program=IntentProgram(rules=[_normalize_flow(f) for _, f in flows]))

def _normalize_flow(flow: OnosFlow) -> IntentRule:
    selector: dict[str, Any] = {}
    for c in flow.selector.criteria:
        if isinstance(c, EthTypeCriterion):
            value = {0x800:"ipv4", 0x86DD:"ipv6", 0x806:"arp"}.get(int(c.ethType, 16))
            if value is None: raise ValueError(f"unsupported ETH_TYPE {c.ethType}")
            selector["eth_type"] = value
        elif isinstance(c, IpCriterion): selector["source" if c.type.endswith("SRC") else "destination"] = Endpoint(ip=c.ip.split("/", 1)[0])
        elif isinstance(c, ProtocolCriterion):
            value = {1:"icmp", 6:"tcp", 17:"udp"}.get(c.protocol)
            if value is None: raise ValueError(f"unsupported IP protocol {c.protocol}")
            selector["protocol"] = value
        elif isinstance(c, TransportCriterion): selector["source_port" if c.type.endswith("SRC") else "destination_port"] = c.tcpPort or c.udpPort
        else: selector["ingress_port"] = c.port
    enforcement: dict[str, Any] = {"device": flow.deviceId}; queue = None
    if flow.treatment is not None:
        for i in flow.treatment.instructions:
            if isinstance(i, OutputInstruction): enforcement["egress_port"] = i.port
            elif isinstance(i, QueueInstruction): queue = i.queueId
            else: enforcement["set_vlan_id"] = i.vlanId
    if flow.treatment is None: kind, action, qos = "security", "deny", None
    elif queue is not None: kind, action, qos = "qos", "prioritize", QosConstraint(queue=queue)
    else: kind, action, qos = "forwarding", "forward", None
    return IntentRule(intent_type=kind, action=action, selector=TrafficSelector.model_validate(selector), qos=qos, enforcement=EnforcementConstraint.model_validate(enforcement))
