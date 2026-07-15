"""Controller-neutral ordered rule IR used by Experiment 1."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Endpoint(StrictModel):
    host: str | None = None
    ip: str | None = None
    @model_validator(mode="after")
    def require_identity(self) -> "Endpoint":
        if (self.host is None) == (self.ip is None): raise ValueError("endpoint must contain exactly one of host or ip")
        return self

class TrafficSelector(StrictModel):
    source: Endpoint | None = None
    destination: Endpoint | None = None
    eth_type: Literal["ipv4", "ipv6", "arp"] | None = None
    protocol: Literal["icmp", "tcp", "udp"] | None = None
    source_port: int | None = Field(default=None, ge=1, le=65535)
    destination_port: int | None = Field(default=None, ge=1, le=65535)
    ingress_port: int | None = Field(default=None, ge=1)
    @model_validator(mode="after")
    def ports_require_transport(self) -> "TrafficSelector":
        if (self.source_port is not None or self.destination_port is not None) and self.protocol not in {"tcp", "udp"}: raise ValueError("transport ports require tcp or udp")
        return self

class QosConstraint(StrictModel):
    min_bandwidth_mbps: float | None = Field(default=None, gt=0)
    max_latency_ms: float | None = Field(default=None, gt=0)
    queue: int | None = Field(default=None, ge=0)
    @model_validator(mode="after")
    def require_value(self) -> "QosConstraint":
        if all(v is None for v in (self.min_bandwidth_mbps, self.max_latency_ms, self.queue)): raise ValueError("qos requires bandwidth, latency, or queue")
        return self

class EnforcementConstraint(StrictModel):
    device: str | None = None
    egress_port: int | str | None = None
    set_vlan_id: int | None = Field(default=None, ge=0, le=4095)
    @model_validator(mode="after")
    def require_value(self) -> "EnforcementConstraint":
        if self.device is None and self.egress_port is None and self.set_vlan_id is None: raise ValueError("empty enforcement constraint")
        return self

class IntentRule(StrictModel):
    intent_type: Literal["forwarding", "security", "qos"]
    action: Literal["forward", "allow", "deny", "prioritize"]
    selector: TrafficSelector = Field(default_factory=TrafficSelector)
    qos: QosConstraint | None = None
    enforcement: EnforcementConstraint | None = None
    @model_validator(mode="after")
    def validate_semantics(self) -> "IntentRule":
        valid = {"forwarding": {"forward"}, "security": {"allow", "deny"}, "qos": {"prioritize"}}
        if self.action not in valid[self.intent_type]: raise ValueError(f"{self.intent_type} cannot use action {self.action}")
        if self.intent_type == "qos" and self.qos is None: raise ValueError("qos rule requires a qos constraint")
        if self.intent_type != "qos" and self.qos is not None: raise ValueError("qos constraint is only valid for qos rules")
        return self

class IntentProgram(StrictModel):
    """Rules in evaluation order, highest policy priority first."""
    rules: list[IntentRule] = Field(min_length=1)

class RejectedIntent(StrictModel):
    reason: Literal["ambiguous", "contradictory", "unknown_entity", "unsupported"]

class IntentPrediction(StrictModel):
    status: Literal["accepted", "rejected"]
    program: IntentProgram | None = None
    rejection: RejectedIntent | None = None
    @model_validator(mode="after")
    def validate_branch(self) -> "IntentPrediction":
        accepted = self.status == "accepted"
        if accepted != (self.program is not None) or accepted == (self.rejection is not None): raise ValueError("prediction must contain exactly the selected result branch")
        return self
