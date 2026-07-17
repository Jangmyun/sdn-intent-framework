from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
import pytest
from pydantic import ValidationError
from safe_intent_sdn.e1_evaluation import EvaluationCase, PredictionRecord, aggregate_runs, evaluate_run, validate_records
from safe_intent_sdn.intent_ir import Endpoint, IntentPrediction
from safe_intent_sdn.onos import OnosFlowSet, parse_onos_response
from experiments.e1.run_experiment import SYSTEM_ONOS, few_shot

DATASET=Path('experiments/e1/data/intents.jsonl')
def cases(): return [EvaluationCase.model_validate_json(x) for x in DATASET.read_text().splitlines()]
def record(c,rep=1,treatment='E1-B',output=None):
 return PredictionRecord(case_id=c.id,treatment=treatment,run_id=f'run-{rep}',repetition=rep,output=output or c.expected.model_dump(mode='json'),latency_ms=10,input_tokens=4,output_tokens=2)

def test_dataset_distribution_provenance_and_compound_rows():
 x=cases(); assert len(x)==100 and len({c.id for c in x})==100
 assert Counter(c.category for c in x)=={'forwarding':42,'security':23,'qos':23,'compound':2,'ambiguous_unsupported':10}
 assert Counter(c.category for c in x if c.cohort=='upstream')=={'forwarding':27,'security':8,'qos':13,'compound':2}
 for row in (39,45):
  c=x[row-1]; assert c.id==f'N{row:03}' and len(c.expected.program.rules)==2
 assert all(c.provenance.repository and c.provenance.commit_sha for c in x)

def test_demonstrations_do_not_overlap_benchmark_and_direct_prompt_has_no_answer():
 fixture=json.loads(Path("experiments/e1/data/demonstrations.json").read_text())
 benchmark=cases()
 assert len(fixture)==5
 assert {row["category"] for row in fixture}=={"forwarding","security","qos","compound","rejection"}
 assert not ({row["id"] for row in fixture} & {case.id for case in benchmark})
 assert not ({row["instruction"] for row in fixture} & {case.instruction for case in benchmark})
 demo_pairs={(row["instruction"],json.dumps(row["output"],sort_keys=True)) for row in fixture}
 benchmark_pairs={(case.instruction,json.dumps(case.expected.model_dump(mode="json"),sort_keys=True)) for case in benchmark}
 assert not (demo_pairs & benchmark_pairs)
 assert "Examples:" in few_shot(Path("experiments/e1/data/demonstrations.json"))
 assert "\"priority\":100" not in SYSTEM_ONOS

def test_onos_deny_ipv6_arp_vlan_queue_udp_source_and_multiflow():
 x=cases()
 assert sum(1 for c in x[:50] if any(r.action=='deny' for r in parse_onos_response(c.upstream_output).program.rules))>=6
 for row in (40,41,44,48,45):
  normalized=parse_onos_response(x[row-1].upstream_output); assert normalized.status=='accepted'
 assert parse_onos_response(x[39].upstream_output).program.rules[0].selector.eth_type=='ipv6'
 assert parse_onos_response(x[40].upstream_output).program.rules[0].selector.eth_type=='arp'
 assert parse_onos_response(x[43].upstream_output).program.rules[0].selector.source_port==69
 assert parse_onos_response(x[47].upstream_output).program.rules[0].enforcement.set_vlan_id==100
 assert len(parse_onos_response(x[44].upstream_output).program.rules)==2
 with pytest.raises(ValidationError): OnosFlowSet.model_validate({'flows':[]})

def test_semantic_validation_rejects_mismatched_action_empty_qos_and_port():
 with pytest.raises(ValidationError): IntentPrediction.model_validate({'status':'accepted','program':{'rules':[{'intent_type':'security','action':'forward','selector':{}}]}})
 with pytest.raises(ValidationError): IntentPrediction.model_validate({'status':'accepted','program':{'rules':[{'intent_type':'qos','action':'prioritize','selector':{},'qos':{}}]}})
 with pytest.raises(ValidationError): IntentPrediction.model_validate({'status':'accepted','program':{'rules':[{'intent_type':'forwarding','action':'forward','selector':{'protocol':'icmp','destination_port':80}}]}})

def test_sfc_rule_requires_sfc_role_and_only_sfc_rules_may_set_it():
 with pytest.raises(ValidationError): IntentPrediction.model_validate({'status':'accepted','program':{'rules':[{'intent_type':'sfc','action':'forward','selector':{},'enforcement':{'device':'s1','egress_port':1}}],'sfc_chain':[]}})
 with pytest.raises(ValidationError): IntentPrediction.model_validate({'status':'accepted','program':{'rules':[{'intent_type':'forwarding','action':'forward','selector':{},'sfc_role':'ingress'}]}})

def test_avoid_device_is_only_valid_on_reroute_rules():
 IntentPrediction.model_validate({'status':'accepted','program':{'rules':[{'intent_type':'reroute','action':'forward','selector':{},'enforcement':{'device':'s1','egress_port':1,'avoid_device':'s2'}}]}})
 with pytest.raises(ValidationError): IntentPrediction.model_validate({'status':'accepted','program':{'rules':[{'intent_type':'forwarding','action':'forward','selector':{},'enforcement':{'device':'s1','egress_port':1,'avoid_device':'s2'}}]}})

def test_sfc_chain_required_iff_program_has_an_sfc_rule():
 with pytest.raises(ValidationError): IntentPrediction.model_validate({'status':'accepted','program':{'rules':[{'intent_type':'sfc','action':'forward','sfc_role':'ingress','selector':{},'enforcement':{'device':'s1','egress_port':1}}]}})
 with pytest.raises(ValidationError): IntentPrediction.model_validate({'status':'accepted','program':{'rules':[{'intent_type':'forwarding','action':'forward','selector':{},'enforcement':{'device':'s1','egress_port':1}}],'sfc_chain':['of:0000000000000002']}})

def test_normalized_equal_and_slot_accuracy_cover_sfc_role_and_sfc_chain():
 expected=IntentPrediction.model_validate({'status':'accepted','program':{'rules':[
  {'intent_type':'sfc','action':'forward','sfc_role':'ingress','selector':{},'enforcement':{'device':'s1','egress_port':9}},
  {'intent_type':'sfc','action':'forward','sfc_role':'egress','selector':{},'enforcement':{'device':'s1','egress_port':1}},
 ],'sfc_chain':['of:0000000000000001:9']}})
 c=EvaluationCase(id='x',cohort='project_authored',category='sfc',variation='v',instruction='i',expected=expected,provenance={'repository':'r','commit_sha':'c'})
 same=expected.model_copy(deep=True)
 assert evaluate_run([c],[record(c,output=same.model_dump(mode='json'))])['normalized_exact_match']==1
 wrong_role=expected.model_copy(deep=True); wrong_role.program.rules[1].sfc_role='transit'
 report=evaluate_run([c],[record(c,output=wrong_role.model_dump(mode='json'))])
 assert report['normalized_exact_match']==0 and report['normalized_slot_accuracy']['sfc_role']==0.5
 wrong_chain=expected.model_copy(deep=True); wrong_chain.program.sfc_chain=['of:0000000000000002']
 report=evaluate_run([c],[record(c,output=wrong_chain.model_dump(mode='json'))])
 assert report['normalized_exact_match']==0

def test_aliases_and_unknown_hallucination():
 c=cases()[50]; actual=c.expected.model_copy(deep=True); actual.program.rules[0].selector.source=Endpoint(ip='10.0.0.1')
 report=evaluate_run([c],[record(c,output=actual.model_dump(mode='json'))],aliases={'h1':'host:h1','10.0.0.1':'host:h1'},inventory_entities={'host:h1','h3'})
 assert report['normalized_slot_accuracy']['source']==1 and report['hallucinated_entity_rate']==0
 actual.program.rules[0].selector.source=Endpoint(host='h9')
 report=evaluate_run([c],[record(c,output=actual.model_dump(mode='json'))],aliases={'h1':'host:h1'},inventory_entities={'host:h1','h3'})
 assert report['hallucinated_cases']==[c.id]

def test_rejection_only_subset_does_not_divide_by_zero():
 x=[c for c in cases() if c.expected.status=='rejected']
 report=evaluate_run(x,[record(c) for c in x])
 assert report['normalized_rule_count_accuracy']==0
 assert report['required_rejection_rate']==1

def test_rejection_denominators_are_separate():
 x=cases(); records=[record(c) for c in x]
 report=evaluate_run(x,records)
 assert report['unsupported_intent_rejection_rate']==report['required_rejection_rate']==1
 assert sum(bool(c.expected.rejection and c.expected.rejection.reason=='unsupported') for c in x)==2
 assert sum(c.expected.status=='rejected' for c in x)==10

def test_e1a_call_failure_leftover_default_is_not_scored_as_successful_rejection():
 x=[c for c in cases() if c.expected.status=='rejected' and c.expected.rejection.reason!='unsupported'][:1]
 rec=PredictionRecord(case_id=x[0].id,treatment='E1-A',run_id='run-1',repetition=1,output={},latency_ms=0,input_tokens=0,output_tokens=0,error_kind='schema_invalid',error='JSONDecodeError: bad json')
 report=evaluate_run(x,[rec])
 assert report['schema_invalid_cases']==[x[0].id]
 assert report['response_schema_validity']==0
 assert report['required_rejection_rate']==0

def test_duplicate_incomplete_and_unpaired_runs_fail():
 x=cases(); one=[record(c) for c in x]
 with pytest.raises(ValueError,match='duplicate'): validate_records(x,one+[one[0]],min_repetitions=1)
 with pytest.raises(ValueError,match='incomplete'): validate_records(x,one[:-1],min_repetitions=1)
 two=one+[record(c,rep=2,treatment='E1-C') for c in x]
 with pytest.raises(ValueError,match='different repetitions'): validate_records(x,two,min_repetitions=1)

def test_five_perfect_runs_have_zero_sd_and_ci_width():
 x=cases(); records=[record(c,rep=rep) for rep in range(1,6) for c in x]
 report=aggregate_runs(x,records); metric=report['treatments']['E1-B']['normalized_exact_match']
 assert metric['mean']==1 and metric['sample_sd']==0 and metric['exploratory_ci_95']==[1,1]
 assert 'n=5' in report['caveat']
