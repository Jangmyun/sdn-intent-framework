"""Run-aware semantic scoring for Experiment 1."""
from __future__ import annotations
import random
from collections import Counter
from math import sqrt
from statistics import mean, stdev
from typing import Any, Iterable
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .intent_ir import IntentPrediction, IntentRule
from .onos import parse_onos_response

RULE_SLOTS = ("intent_type", "action", "source", "destination", "eth_type", "protocol", "source_port", "destination_port", "ingress_port", "qos", "device", "egress_port", "set_vlan_id")

class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_row: int | None = None
    repository: str
    commit_sha: str
    csv_sha256: str | None = None

class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    cohort: str
    category: str
    variation: str
    instruction: str
    expected: IntentPrediction
    provenance: Provenance
    upstream_output: dict[str, Any] | None = None
    upstream_label_status: str | None = None
    @model_validator(mode="after")
    def upstream_fields(self) -> "EvaluationCase":
        upstream = self.cohort == "upstream"
        if upstream != (self.upstream_output is not None) or upstream != (self.upstream_label_status is not None): raise ValueError("upstream-only fields must occur together")
        return self

class PredictionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    treatment: str
    run_id: str
    repetition: int = Field(ge=1)
    output: dict[str, Any]
    latency_ms: float = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)

def _endpoint(value: Any, aliases: dict[str, str]) -> Any:
    if value is None: return None
    item = value.model_dump(exclude_none=True) if hasattr(value, "model_dump") else value
    spelling = item.get("host") or item.get("ip")
    return aliases.get(spelling, spelling)

def _rule_slots(rule: IntentRule, aliases: dict[str, str]) -> dict[str, Any]:
    s, e = rule.selector, rule.enforcement
    return {"intent_type":rule.intent_type, "action":rule.action, "source":_endpoint(s.source, aliases), "destination":_endpoint(s.destination, aliases),
            "eth_type":s.eth_type, "protocol":s.protocol, "source_port":s.source_port, "destination_port":s.destination_port,
            "ingress_port":s.ingress_port, "qos":rule.qos.model_dump(exclude_none=True) if rule.qos else None,
            "device":e.device if e else None, "egress_port":e.egress_port if e else None, "set_vlan_id":e.set_vlan_id if e else None}

def _entity_spellings(prediction: IntentPrediction) -> set[str]:
    result: set[str] = set()
    if prediction.program:
        for rule in prediction.program.rules:
            for ep in (rule.selector.source, rule.selector.destination):
                if ep: result.add(ep.host or ep.ip or "")
            if rule.enforcement and rule.enforcement.device: result.add(rule.enforcement.device)
    return result

def validate_records(cases: Iterable[EvaluationCase], records: Iterable[PredictionRecord], *, min_repetitions: int = 5, require_paired: bool = True) -> tuple[list[EvaluationCase], list[PredictionRecord]]:
    cases, records = list(cases), list(records)
    case_ids = {c.id for c in cases}
    if len(case_ids) != len(cases): raise ValueError("duplicate case id")
    keys = [(r.treatment, r.run_id, r.repetition, r.case_id) for r in records]
    if len(keys) != len(set(keys)): raise ValueError("duplicate prediction composite key")
    groups: dict[tuple[str,str,int], set[str]] = {}
    for r in records: groups.setdefault((r.treatment,r.run_id,r.repetition),set()).add(r.case_id)
    for key, ids in groups.items():
        if ids != case_ids: raise ValueError(f"incomplete run {key}: expected {len(case_ids)}, got {len(ids)}")
    treatments = {r.treatment for r in records}
    for treatment in treatments:
        run_ids_by_rep: dict[int, set[str]] = {}
        for record in records:
            if record.treatment == treatment: run_ids_by_rep.setdefault(record.repetition, set()).add(record.run_id)
        if any(len(run_ids) != 1 for run_ids in run_ids_by_rep.values()): raise ValueError(f"duplicate repetition for treatment {treatment}")
        reps = {r.repetition for r in records if r.treatment == treatment}
        if len(reps) < min_repetitions: raise ValueError(f"treatment {treatment} requires at least {min_repetitions} repetitions")
    if require_paired and treatments:
        rep_sets = [{r.repetition for r in records if r.treatment == t} for t in treatments]
        if any(s != rep_sets[0] for s in rep_sets[1:]): raise ValueError("paired treatments have different repetitions")
    return cases, records

def evaluate_run(cases: Iterable[EvaluationCase], records: Iterable[PredictionRecord], *, aliases: dict[str,str] | None = None, inventory_entities: set[str] | None = None) -> dict[str, Any]:
    cases, records = list(cases), list(records); aliases = aliases or {}; inventory_entities = inventory_entities or set(aliases)
    by_id = {r.case_id:r for r in records}; counts = Counter(total=len(cases)); slots = Counter(); diagnostics = {k:[] for k in ("schema_invalid_cases","hallucinated_cases","incorrectly_accepted_cases","rule_count_mismatch_cases")}; reason_total=Counter(); reason_hit=Counter(); lat=[]; tokens=Counter()
    for case in cases:
        expected=case.expected; rec=by_id.get(case.id)
        if expected.status == "rejected": reason_total[expected.rejection.reason] += 1
        if rec is None: continue
        lat.append(rec.latency_ms); tokens.update(input=rec.input_tokens, output=rec.output_tokens)
        try: actual=parse_onos_response(rec.output) if rec.treatment == "E1-A" else IntentPrediction.model_validate(rec.output)
        except Exception: diagnostics["schema_invalid_cases"].append(case.id); continue
        counts["schema_valid"] += 1; counts["exact"] += actual == expected
        if rec.treatment == "E1-A" and case.cohort == "upstream": counts["raw_onos_total"] += 1; counts["raw_onos_exact"] += rec.output == case.upstream_output
        if expected.status == "rejected":
            if actual.status == "rejected": reason_hit[expected.rejection.reason] += 1
            else: diagnostics["incorrectly_accepted_cases"].append(case.id)
            continue
        if actual.status != "accepted": continue
        erules, arules = expected.program.rules, actual.program.rules
        counts["expected_rules"] += len(erules); counts["rule_count_correct"] += len(erules) == len(arules)
        if len(erules) != len(arules): diagnostics["rule_count_mismatch_cases"].append(case.id)
        for index in range(max(len(erules),len(arules))):
            if index >= len(erules) or index >= len(arules): continue
            es, ass = _rule_slots(erules[index],aliases), _rule_slots(arules[index],aliases)
            for slot in RULE_SLOTS: slots[slot] += es[slot] == ass[slot]
        unknown = {e for e in _entity_spellings(actual) if e not in inventory_entities and aliases.get(e,e) not in inventory_entities}
        counts["actual_entities"] += len(_entity_spellings(actual)); counts["hallucinated"] += len(unknown)
        if unknown: diagnostics["hallucinated_cases"].append(case.id)
    total=counts["total"] or 1; expected_rules=counts["expected_rules"] or 1; required=sum(reason_total.values()) or 1; unsupported=reason_total["unsupported"] or 1
    report={"case_count":counts["total"],"response_schema_validity":counts["schema_valid"]/total,"normalized_exact_match":counts["exact"]/total,
            "normalized_rule_count_accuracy":counts["rule_count_correct"]/(sum(c.expected.status=="accepted" for c in cases) or 1),
            "normalized_type_accuracy":slots["intent_type"]/expected_rules,"normalized_slot_accuracy":{s:slots[s]/expected_rules for s in RULE_SLOTS if s!="intent_type"},
            "hallucinated_entity_rate":counts["hallucinated"]/(counts["actual_entities"] or 1),"required_rejection_rate":sum(reason_hit.values())/required,
            "unsupported_intent_rejection_rate":reason_hit["unsupported"]/unsupported,"rejection_recall_by_reason":{r:reason_hit[r]/n for r,n in sorted(reason_total.items())},
            "raw_onos_only_exact_match":counts["raw_onos_exact"]/(counts["raw_onos_total"] or 1) if counts["raw_onos_total"] else None,
            "mean_api_latency_ms":mean(lat) if lat else None,"token_usage":{"input":tokens["input"],"output":tokens["output"],"total":tokens["input"]+tokens["output"]},**diagnostics}
    return report

def _bootstrap(values: list[float], seed: int=42, samples: int=10_000) -> list[float]:
    if len(set(values)) == 1: return [values[0],values[0]]
    rng=random.Random(seed); means=sorted(mean(rng.choices(values,k=len(values))) for _ in range(samples)); return [means[int(.025*samples)],means[int(.975*samples)-1]]

def aggregate_runs(cases: Iterable[EvaluationCase], records: Iterable[PredictionRecord], *, aliases: dict[str,str] | None=None, inventory_entities: set[str] | None=None, min_repetitions:int=5) -> dict[str,Any]:
    cases,records=validate_records(cases,records,min_repetitions=min_repetitions); grouped:dict[tuple[str,str,int],list[PredictionRecord]]={}
    for r in records: grouped.setdefault((r.treatment,r.run_id,r.repetition),[]).append(r)
    runs={"|".join(map(str,k)):evaluate_run(cases,v,aliases=aliases,inventory_entities=inventory_entities) for k,v in grouped.items()}; metrics=("response_schema_validity","normalized_exact_match","normalized_rule_count_accuracy","normalized_type_accuracy","required_rejection_rate","unsupported_intent_rejection_rate","hallucinated_entity_rate")
    treatments={}
    for treatment in sorted({r.treatment for r in records}):
        selected=[report for key,report in runs.items() if key.split("|",1)[0]==treatment]; summary={}
        for metric in metrics:
            vals=[x[metric] for x in selected]; summary[metric]={"runs":vals,"mean":mean(vals),"sample_sd":stdev(vals) if len(vals)>1 else 0.0,"min":min(vals),"max":max(vals),"exploratory_ci_95":_bootstrap(vals)}
        treatments[treatment]=summary
    by_treatment_rep = {(key.split("|")[0], int(key.rsplit("|", 1)[1])): report for key, report in runs.items()}
    paired = {}
    names = sorted(treatments)
    for left_index, left in enumerate(names):
        for right in names[left_index + 1:]:
            repetitions = sorted(rep for treatment, rep in by_treatment_rep if treatment == left)
            paired[f"{right}_minus_{left}"] = {metric: [by_treatment_rep[(right, rep)][metric] - by_treatment_rep[(left, rep)][metric] for rep in repetitions] for metric in metrics}
    return {"runs":runs,"treatments":treatments,"paired_comparisons":paired,"caveat":"exploratory_ci_95 is based on n=5 runs; interpret uncertainty cautiously."}
