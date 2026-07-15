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
You translate one SDN operator instruction into strict JSON. Return JSON only. Accepted output: {"status":"accepted","program":{"rules":[...]},"rejection":null}. Rejected output: {"status":"rejected","program":null,"rejection":{"reason":"ambiguous|contradictory|unknown_entity|unsupported"}}. Rules are ordered highest policy priority first. Each rule has exactly these keys: intent_type, action, selector, qos, enforcement. The action value must be forward for forwarding, allow or deny for security, and prioritize for qos. Selector fields are source/destination endpoint objects using exactly one of host or ip, eth_type (ipv4|ipv6|arp), protocol (icmp|tcp|udp), source_port, destination_port, ingress_port. Use null for absent optional fields. QoS requires min_bandwidth_mbps, max_latency_ms, or queue. Enforcement supports device, egress_port, set_vlan_id. Do not invent entities. Never output a key named matching_action; the key is action.'''
SYSTEM_ONOS='''/no_think
Translate one SDN operator instruction into ONOS flow JSON only. Return {"flows":[...]} for accepted requests or {} when the request must be rejected. Each flow needs priority, timeout, isPermanent, deviceId, selector.criteria, and optionally treatment.instructions. A deny flow omits treatment. Supported criteria: ETH_TYPE, IPV4_SRC/DST, IPV6_SRC/DST, IP_PROTO, TCP_SRC/DST, UDP_SRC/DST, IN_PORT. Supported instructions: OUTPUT, QUEUE, and L2MODIFICATION with subtype VLAN_ID. Preserve every clause as a flow and use higher priority first. selector.criteria and treatment.instructions are always JSON arrays. Example: {"flows":[{"priority":100,"timeout":0,"isPermanent":true,"deviceId":"of:0000000000000001","selector":{"criteria":[{"type":"ETH_TYPE","ethType":"0x800"},{"type":"IP_PROTO","protocol":1}]},"treatment":{"instructions":[{"type":"OUTPUT","port":"3"}]}}]}.'''

def load_cases(path:Path)->list[EvaluationCase]: return [EvaluationCase.model_validate_json(x) for x in path.read_text().splitlines()]
def few_shot(cases:list[EvaluationCase], direct:bool)->str:
    chosen=[cases[i] for i in (0,4,44,53,89)]
    chunks=[]
    for c in chosen:
        answer=c.upstream_output if direct and c.upstream_output is not None else c.expected.model_dump(mode='json')
        chunks.append(f'Instruction: {c.instruction}\nOutput: {json.dumps(answer,separators=(",",":"))}')
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
def call(base:str,key:str,model:str,messages:list[dict],timeout:float,max_tokens:int,temperature:float,schema:dict)->tuple[dict,float,int,int,str]:
    endpoint=base.rstrip('/')
    if endpoint.endswith('/v1'): endpoint=endpoint[:-3]
    body={'model':model,'messages':messages,'think':False,'format':schema,'stream':False,'keep_alive':-1,
          'options':{'temperature':temperature,'num_predict':max_tokens,'num_ctx':4096}}
    headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36'}
    if key: headers['Authorization']=f'Bearer {key}'
    started=time.perf_counter()
    try:
        with urlopen(Request(endpoint+'/api/chat',data=json.dumps(body).encode(),headers=headers,method='POST'),timeout=timeout) as response: payload=json.load(response)
    except HTTPError as exc: raise RuntimeError(f'HTTP {exc.code}: {exc.read().decode(errors="replace")[:1000]}') from exc
    except URLError as exc: raise RuntimeError(f'connection error: {exc.reason}') from exc
    latency=(time.perf_counter()-started)*1000; message=payload.get('message') or {}; content=message.get('content') or ''
    if not content: raise ValueError(f'empty message.content; done_reason={payload.get("done_reason")} thinking_length={len(message.get("thinking") or "")}')
    return extract_json(content),latency,int(payload.get('prompt_eval_count',0)),int(payload.get('eval_count',0)),content

def main()->None:
    parser=argparse.ArgumentParser(); parser.add_argument('--treatment',choices=['E1-A','E1-B','E1-C','E1-D'],required=True); parser.add_argument('--model',default='qwen3:8b'); parser.add_argument('--repetition',type=int,default=1); parser.add_argument('--limit',type=int); parser.add_argument('--case-id',action='append'); parser.add_argument('--output',type=Path); parser.add_argument('--quiet',action='store_true'); parser.add_argument('--timeout',type=float); parser.add_argument('--max-tokens',type=int); args=parser.parse_args()
    settings=load_settings(f'config/experiments/{args.treatment.lower().replace("-","_")}.toml'); base=settings.secrets.llm_base_url
    if base is None: raise SystemExit('SAFE_SDN_LLM_BASE_URL is required')
    cases=load_cases(ROOT/settings.translation_experiment.dataset_path)
    if args.case_id: cases=[c for c in cases if c.id in set(args.case_id)]
    if args.limit is not None: cases=cases[:args.limit]
    direct=args.treatment=='E1-A'; system=SYSTEM_ONOS if direct else SYSTEM_IR
    flow_schema=OnosFlowSet.model_json_schema(); flow_defs=flow_schema.pop('$defs',{})
    schema={'$defs':flow_defs,'anyOf':[flow_schema,{'type':'object','maxProperties':0}]} if direct else IntentPrediction.model_json_schema()
    if settings.translation_experiment.few_shot: system+=few_shot(load_cases(ROOT/settings.translation_experiment.dataset_path),direct)
    if settings.translation_experiment.state_grounding: system+=topology_text(ROOT/settings.translation_experiment.topology_path)
    run_id=f'{args.treatment.lower()}-{args.model.replace(":","-")}-{uuid.uuid4().hex[:8]}'; target=args.output or ROOT/'logs'/'e1'/f'{run_id}-r{args.repetition}.jsonl'; target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as stream:
        for index,case in enumerate(cases,1):
            output={}; latency=0.0; input_tokens=output_tokens=0; raw=''; error=None
            try:
                output,latency,input_tokens,output_tokens,raw=call(str(base),settings.secrets.llm_api_key.get_secret_value(),args.model,[{'role':'system','content':system},{'role':'user','content':case.instruction+'\n/no_think'}],args.timeout or settings.llm.timeout_seconds,args.max_tokens or settings.llm.max_tokens,settings.llm.temperature,schema)
                if direct: parse_onos_response(output)
                else: IntentPrediction.model_validate(output)
            except Exception as exc:
                error=f'{type(exc).__name__}: {exc}'
            record=PredictionRecord(case_id=case.id,treatment=args.treatment,run_id=run_id,repetition=args.repetition,output=output,latency_ms=latency,input_tokens=input_tokens,output_tokens=output_tokens)
            saved={**record.model_dump(mode='json'),'raw_content':raw,'error':error}; stream.write(json.dumps(saved,ensure_ascii=False)+'\n'); stream.flush()
            if not args.quiet or error is not None or index % 10 == 0 or index == len(cases): print(f'[{index}/{len(cases)}] {case.id}: {"ok" if error is None else error}',flush=True)
    print(target)
if __name__=='__main__': main()
