"""Call an OpenAI-compatible endpoint and capture E1 prediction records."""
from __future__ import annotations
import argparse, json, sys, time, uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from safe_intent_sdn.config import load_settings
from safe_intent_sdn.e1_evaluation import EvaluationCase, PredictionRecord
from safe_intent_sdn.intent_ir import IntentPrediction
from safe_intent_sdn.onos import OnosFlowSet, parse_onos_response

SYSTEM_IR='''/no_think
You translate one SDN operator instruction into strict JSON. Return JSON only. Accepted output: {"status":"accepted","program":{"rules":[...]},"rejection":null}. Rejected output: {"status":"rejected","program":null,"rejection":{"reason":"ambiguous|contradictory|unknown_entity|unsupported"}}. Rules are ordered highest policy priority first. Each rule has exactly these keys: intent_type, action, selector, qos, enforcement. The action value must be forward for forwarding, allow or deny for security, and prioritize for qos. The JSON Schema supplied with this request defines all object structure. Selector fields are source/destination endpoint objects using exactly one of host or ip, eth_type (ipv4|ipv6|arp), protocol (icmp|tcp|udp), source_port, destination_port, ingress_port. Use null for absent optional fields. QoS requires min_bandwidth_mbps, max_latency_ms, or queue. Enforcement supports device, egress_port, set_vlan_id. Do not invent entities. Never output a key named matching_action; the key is action.'''
SYSTEM_ONOS='''/no_think
Translate one SDN operator instruction into ONOS flow JSON only. Return {"flows":[...]} for accepted requests or {} when the request must be rejected. Each flow needs priority, timeout, isPermanent, deviceId, selector.criteria, and optionally treatment.instructions. A deny flow omits treatment. Supported criteria: ETH_TYPE, IPV4_SRC/DST, IPV6_SRC/DST, IP_PROTO, TCP_SRC/DST, UDP_SRC/DST, IN_PORT. Supported instructions: OUTPUT, QUEUE, and L2MODIFICATION with subtype VLAN_ID. Preserve every clause as a flow and use higher priority first. selector.criteria and treatment.instructions are always JSON arrays. Do not imitate benchmark answers or invent fields.'''

def load_cases(path:Path)->list[EvaluationCase]: return [EvaluationCase.model_validate_json(x) for x in path.read_text().splitlines()]
def few_shot(path:Path)->str:
    chosen=json.loads(path.read_text())
    chunks=[]
    for c in chosen:
        chunks.append(f'Instruction: {c["instruction"]}\nOutput: {json.dumps(c["output"],separators=(",",":"))}')
    return '\n\nExamples:\n'+'\n\n'.join(chunks)
def topology_text(path:Path)->str:
    data=json.loads(path.read_text()); return '\n\nAuthorized topology inventory:\n'+json.dumps(data,separators=(',',':'))
def extract_json(text:str)->dict:
    text=text.strip()
    if text.startswith('```'):
        text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
    value=json.loads(text)
    if not isinstance(value,dict): raise ValueError('model output must be a JSON object')
    return value
class TransportError(RuntimeError):
    pass

def call_once(base:str,key:str,model:str,messages:list[dict],timeout:float,max_tokens:int,temperature:float,schema:dict,seed:int)->tuple[dict,float,int,int,str]:
    endpoint=base.rstrip('/')
    if endpoint.endswith('/v1'): endpoint=endpoint[:-3]
    body={'model':model,'messages':messages,'think':False,'format':schema,'stream':False,'keep_alive':-1,
          'options':{'temperature':temperature,'num_predict':max_tokens,'num_ctx':4096,'seed':seed}}
    headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36'}
    if key: headers['Authorization']=f'Bearer {key}'
    started=time.perf_counter()
    try:
        with urlopen(Request(endpoint+'/api/chat',data=json.dumps(body).encode(),headers=headers,method='POST'),timeout=timeout) as response: payload=json.load(response)
    except HTTPError as exc:
        detail=exc.read().decode(errors="replace")[:1000]
        if 500 <= exc.code < 600: raise TransportError(f"HTTP {exc.code}: {detail}") from exc
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc: raise TransportError(f'connection error: {exc}') from exc
    latency=(time.perf_counter()-started)*1000; message=payload.get('message') or {}; content=message.get('content') or ''
    if not content: raise ValueError(f'empty message.content; done_reason={payload.get("done_reason")} thinking_length={len(message.get("thinking") or "")}')
    return extract_json(content),latency,int(payload.get('prompt_eval_count',0)),int(payload.get('eval_count',0)),content

def call(*args,retries:int=0,**kwargs):
    for attempt in range(retries+1):
        try:
            return call_once(*args,**kwargs)
        except TransportError:
            if attempt == retries: raise
            time.sleep(min(2 ** attempt, 8))
    raise AssertionError("unreachable")

def main()->None:
    parser=argparse.ArgumentParser(); parser.add_argument('--treatment',choices=['E1-A','E1-B','E1-C','E1-D'],required=True); parser.add_argument('--model',default='qwen3:8b'); parser.add_argument('--repetition',type=int,default=1); parser.add_argument('--limit',type=int); parser.add_argument('--case-id',action='append'); parser.add_argument('--output',type=Path); parser.add_argument('--quiet',action='store_true'); parser.add_argument('--timeout',type=float); parser.add_argument('--max-tokens',type=int); args=parser.parse_args()
    if args.repetition not in range(1,6): raise SystemExit("repetition must be 1..5 (seeds 42..46)")
    seed=41+args.repetition
    settings=load_settings(f'config/experiments/{args.treatment.lower().replace("-","_")}.toml'); base=settings.secrets.llm_base_url
    if base is None: raise SystemExit('SAFE_SDN_LLM_BASE_URL is required')
    cases=load_cases(ROOT/settings.translation_experiment.dataset_path)
    if args.case_id: cases=[c for c in cases if c.id in set(args.case_id)]
    if args.limit is not None: cases=cases[:args.limit]
    direct=args.treatment=='E1-A'; system=SYSTEM_ONOS if direct else SYSTEM_IR
    flow_schema=OnosFlowSet.model_json_schema(); flow_defs=flow_schema.pop('$defs',{})
    schema={'$defs':flow_defs,'anyOf':[flow_schema,{'type':'object','maxProperties':0}]} if direct else IntentPrediction.model_json_schema()
    if settings.translation_experiment.few_shot: system+=few_shot(ROOT/"experiments"/"e1"/"data"/"demonstrations.json")
    if settings.translation_experiment.state_grounding: system+=topology_text(ROOT/settings.translation_experiment.topology_path)
    run_id=f'{args.treatment.lower()}-{args.model.replace(":","-")}-{uuid.uuid4().hex[:8]}'; target=args.output or ROOT/'logs'/'e1'/f'{run_id}-r{args.repetition}.jsonl'; target.parent.mkdir(parents=True,exist_ok=True)
    completed=set()
    if target.exists():
        prior=[json.loads(line) for line in target.read_text().splitlines() if line.strip()]
        if prior:
            run_id=prior[0]["run_id"]
        for row in prior:
            key=(row["treatment"],row["run_id"],row["repetition"],row["case_id"])
            if key[:1] != (args.treatment,) or key[2] != args.repetition: raise SystemExit("output contains a different treatment or repetition")
            if row["case_id"] in completed: raise SystemExit("duplicate composite key in partial output")
            completed.add(row["case_id"])
    pending=[case for case in cases if case.id not in completed]
    with target.open('a',encoding='utf-8') as stream:
        cases=pending
        for index,case in enumerate(cases,1):
            output={}; latency=0.0; input_tokens=output_tokens=0; raw=''; error=None; error_kind=None
            try:
                output,latency,input_tokens,output_tokens,raw=call(str(base),settings.secrets.llm_api_key.get_secret_value(),args.model,[{'role':'system','content':system},{'role':'user','content':case.instruction+'\n/no_think'}],args.timeout or settings.llm.timeout_seconds,args.max_tokens or settings.llm.max_tokens,0.2,schema,seed,retries=settings.llm.retries)
                if direct: parse_onos_response(output)
                else: IntentPrediction.model_validate(output)
            except Exception as exc:
                error=f'{type(exc).__name__}: {exc}'
                error_kind="transport" if isinstance(exc,TransportError) else "schema_invalid"
            record=PredictionRecord(case_id=case.id,treatment=args.treatment,run_id=run_id,repetition=args.repetition,output=output,latency_ms=latency,input_tokens=input_tokens,output_tokens=output_tokens,seed=seed,raw_content=raw,error_kind=error_kind,error=error)
            saved=record.model_dump(mode='json'); stream.write(json.dumps(saved,ensure_ascii=False)+'\n'); stream.flush()
            if not args.quiet or error is not None or index % 10 == 0 or index == len(cases): print(f'[{index}/{len(cases)}] {case.id}: {"ok" if error is None else error}',flush=True)
    final_ids={json.loads(line)["case_id"] for line in target.read_text().splitlines() if line.strip()}
    expected_ids={case.id for case in load_cases(ROOT/settings.translation_experiment.dataset_path)} if args.limit is None and not args.case_id else completed | {case.id for case in cases}
    if final_ids != expected_ids: raise SystemExit(f"incomplete run: expected {len(expected_ids)} unique cases, got {len(final_ids)}")
    print(target)
if __name__=='__main__': main()
