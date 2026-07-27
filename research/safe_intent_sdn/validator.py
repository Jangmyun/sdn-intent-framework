"""Static validation of Intent IR programs against a topology inventory.

Unlike ``compiler.CompilationError``, which raises on the first blocking
lowering problem, this module reports every defect it finds so that
precision/recall can be measured per defect category (reference, conflict,
feasibility) rather than being truncated at the first hit.
"""
from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import Field

from .intent_ir import Endpoint, IntentProgram, IntentRule, StrictModel, TrafficSelector

FindingCategory = Literal["reference", "conflict", "feasibility", "path"]


class TopologyInventory(StrictModel):
    aliases: dict[str, str]
    device_ports: dict[str, frozenset[int]]


def load_topology_inventory(data: Mapping[str, Any]) -> TopologyInventory:
    aliases: dict[str, str] = {}
    for entity in data["entities"]:
        for alias in entity["aliases"]:
            aliases[alias] = entity["id"]
    device_ports = {
        aliases.get(device, device): frozenset(ports)
        for device, ports in data.get("ports", {}).items()
    }
    return TopologyInventory(aliases=aliases, device_ports=device_ports)


class ValidationFinding(StrictModel):
    category: FindingCategory
    code: str
    rule_indices: list[int] = Field(min_length=1)
    message: str


class ValidationReport(StrictModel):
    findings: list[ValidationFinding] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.findings


def validate_program(program: IntentProgram, inventory: TopologyInventory) -> ValidationReport:
    findings = [
        *_check_references(program, inventory),
        *_check_feasibility(program, inventory),
        *_check_conflicts(program, inventory),
        *_check_path_constraints(program, inventory),
    ]
    return ValidationReport(findings=findings)


def _check_references(program: IntentProgram, inventory: TopologyInventory) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for index, rule in enumerate(program.rules):
        for endpoint in (rule.selector.source, rule.selector.destination):
            if endpoint is None:
                continue
            if endpoint.host is not None and endpoint.host not in inventory.aliases:
                findings.append(
                    ValidationFinding(
                        category="reference", code="unknown_host", rule_indices=[index],
                        message=f"rule {index}: unknown host {endpoint.host!r}",
                    )
                )
            elif endpoint.ip is not None and endpoint.ip not in inventory.aliases:
                findings.append(
                    ValidationFinding(
                        category="reference", code="unknown_ip", rule_indices=[index],
                        message=f"rule {index}: unknown IP {endpoint.ip!r}",
                    )
                )
        device = rule.enforcement.device if rule.enforcement else None
        if device is not None:
            canonical = inventory.aliases.get(device)
            if canonical is None or not canonical.startswith("device:"):
                findings.append(
                    ValidationFinding(
                        category="reference", code="unknown_device", rule_indices=[index],
                        message=f"rule {index}: unknown device {device!r}",
                    )
                )
    return findings


def _check_feasibility(program: IntentProgram, inventory: TopologyInventory) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for index, rule in enumerate(program.rules):
        enforcement = rule.enforcement
        device = enforcement.device if enforcement else None
        if device is None:
            continue
        ports = inventory.device_ports.get(inventory.aliases.get(device, device))
        if ports is None:
            continue  # unknown device is already reported by _check_references
        if enforcement.egress_port is not None:
            port = _coerce_port(enforcement.egress_port)
            if port is None or port not in ports:
                findings.append(
                    ValidationFinding(
                        category="feasibility", code="egress_port_out_of_range", rule_indices=[index],
                        message=f"rule {index}: egress_port {enforcement.egress_port!r} not valid on {device!r}",
                    )
                )
        if rule.selector.ingress_port is not None and rule.selector.ingress_port not in ports:
            findings.append(
                ValidationFinding(
                    category="feasibility", code="ingress_port_out_of_range", rule_indices=[index],
                    message=f"rule {index}: ingress_port {rule.selector.ingress_port} not valid on {device!r}",
                )
            )
    return findings


def _coerce_port(value: int | str) -> int | None:
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except ValueError:
        return None


def _check_conflicts(program: IntentProgram, inventory: TopologyInventory) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    rules = program.rules
    for i in range(len(rules)):
        device_i = _device_of(rules[i], inventory)
        if device_i is None:
            continue
        for j in range(i + 1, len(rules)):
            if rules[i].action == rules[j].action:
                continue
            if _device_of(rules[j], inventory) != device_i:
                continue
            if _selector_covers(rules[i].selector, rules[j].selector, inventory.aliases):
                findings.append(
                    ValidationFinding(
                        category="conflict", code="shadowed_rule", rule_indices=[i, j],
                        message=f"rule {j} is shadowed by higher-priority rule {i} with a different action",
                    )
                )
    return findings


def _device_of(rule: IntentRule, inventory: TopologyInventory) -> str | None:
    device = rule.enforcement.device if rule.enforcement else None
    if device is None:
        return None
    return inventory.aliases.get(device, device)


def _selector_covers(general: TrafficSelector, specific: TrafficSelector, aliases: dict[str, str]) -> bool:
    for field in ("eth_type", "protocol", "source_port", "destination_port", "ingress_port"):
        gval = getattr(general, field)
        if gval is not None and gval != getattr(specific, field):
            return False
    for field in ("source", "destination"):
        gep: Endpoint | None = getattr(general, field)
        if gep is None:
            continue
        sep: Endpoint | None = getattr(specific, field)
        if sep is None or _canonical_endpoint(gep, aliases) != _canonical_endpoint(sep, aliases):
            return False
    return True


def _canonical_endpoint(endpoint: Endpoint, aliases: dict[str, str]) -> str:
    spelling = endpoint.host or endpoint.ip or ""
    return aliases.get(spelling, spelling)


def _check_path_constraints(program: IntentProgram, inventory: TopologyInventory) -> list[ValidationFinding]:
    """SFC chain continuity/order and reroute avoid_device checks.

    These are cross-rule/metadata concerns that don't fit reference (entity
    existence), conflict (pairwise shadowing), or feasibility (single-rule port
    range) -- hence the separate ``path`` category.
    """
    return [
        *_check_sfc_chain(program, inventory),
        *_check_sfc_role_order(program),
        *_check_avoid_device(program, inventory),
    ]


def _parse_chain_token(token: str) -> tuple[str, str | None]:
    if token.count(":") <= 1:
        return token, None
    device, port = token.rsplit(":", 1)
    return device, port


def _check_sfc_chain(program: IntentProgram, inventory: TopologyInventory) -> list[ValidationFinding]:
    rules = program.rules
    if not any(rule.intent_type == "sfc" for rule in rules):
        return []
    chain = program.sfc_chain or []
    if len(chain) != len(rules) - 1:
        return [
            ValidationFinding(
                category="path", code="path_chain_length_mismatch", rule_indices=list(range(len(rules))),
                message=f"sfc_chain has {len(chain)} entries but program has {len(rules)} rules (expected {len(rules) - 1})",
            )
        ]
    findings: list[ValidationFinding] = []
    for k in range(1, len(rules)):
        token = chain[k - 1]
        device_part, port_part = _parse_chain_token(token)
        token_device = inventory.aliases.get(device_part, device_part)
        rule_device = _device_of(rules[k], inventory)
        if rule_device is None or token_device != rule_device:
            findings.append(
                ValidationFinding(
                    category="path", code="path_waypoint_device_mismatch", rule_indices=[k - 1, k],
                    message=f"sfc_chain[{k - 1}]={token!r} does not match rule {k}'s device {rules[k].enforcement.device if rules[k].enforcement else None!r}",
                )
            )
            continue
        ports = inventory.device_ports.get(token_device)
        if ports is None:
            findings.append(
                ValidationFinding(
                    category="path", code="path_unknown_waypoint", rule_indices=[k - 1, k],
                    message=f"sfc_chain[{k - 1}]={token!r} references an unknown device",
                )
            )
            continue
        token_port = _coerce_port(port_part) if port_part is not None else None
        if port_part is not None and (token_port is None or token_port not in ports):
            findings.append(
                ValidationFinding(
                    category="path", code="path_waypoint_port_out_of_range", rule_indices=[k - 1, k],
                    message=f"sfc_chain[{k - 1}]={token!r} port not valid on {device_part!r}",
                )
            )
            continue
        prev_device = _device_of(rules[k - 1], inventory)
        if prev_device == token_device:
            prev_enforcement = rules[k - 1].enforcement
            prev_egress = _coerce_port(prev_enforcement.egress_port) if prev_enforcement and prev_enforcement.egress_port is not None else None
            next_ingress = rules[k].selector.ingress_port
            if token_port is None or prev_egress != token_port or next_ingress != token_port:
                findings.append(
                    ValidationFinding(
                        category="path", code="path_port_discontinuity", rule_indices=[k - 1, k],
                        message=f"same-device hop at rule {k} is not port-continuous with rule {k - 1}",
                    )
                )
    return findings


def _check_sfc_role_order(program: IntentProgram) -> list[ValidationFinding]:
    sfc_indices = [i for i, rule in enumerate(program.rules) if rule.intent_type == "sfc"]
    if not sfc_indices:
        return []
    roles = [program.rules[i].sfc_role for i in sfc_indices]
    invalid = (
        roles[0] != "ingress"
        or roles.count("ingress") > 1
        or ("egress" in roles and roles.index("egress") != len(roles) - 1)
    )
    if not invalid:
        return []
    return [
        ValidationFinding(
            category="path", code="path_role_order_invalid", rule_indices=sfc_indices,
            message=f"sfc_role sequence {roles} is not a valid ingress[...transit...][egress] order",
        )
    ]


def _check_avoid_device(program: IntentProgram, inventory: TopologyInventory) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for index, rule in enumerate(program.rules):
        enforcement = rule.enforcement
        if enforcement is None or enforcement.avoid_device is None:
            continue
        avoid = inventory.aliases.get(enforcement.avoid_device, enforcement.avoid_device)
        device = _device_of(rule, inventory)
        if device is not None and device == avoid:
            findings.append(
                ValidationFinding(
                    category="path", code="path_avoid_device_conflict", rule_indices=[index],
                    message=f"rule {index}: enforcement.device {enforcement.device!r} conflicts with avoid_device {enforcement.avoid_device!r}",
                )
            )
    return findings
