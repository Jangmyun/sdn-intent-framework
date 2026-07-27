"""Join reviewed annotations to the pinned CSV and build canonical 100-case JSONL."""
from __future__ import annotations
import csv, hashlib, json
from collections import Counter
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from safe_intent_sdn.e1_evaluation import EvaluationCase

DATA=Path(__file__).parent/'data'; CSV=DATA/'upstream_NetIntent/Intent2Flow-ONOS.csv'; ANNOTATIONS=DATA/'upstream_annotations.jsonl'; AUTHORED=DATA/'project_authored.jsonl'; TARGET=DATA/'intents.jsonl'
REPOSITORY='https://github.com/Muhammadkamrul/NetIntent'; COMMIT='5d5a2377673893dc8a6585346e64272da43a54fc'; SHA256='d884b12355dcd4e203edec9b748023f24e334d61a9ff8129bdc1a593f29dcdfd'
EXPECTED=Counter({'forwarding':42,'security':23,'qos':23,'compound':2,'ambiguous_unsupported':10})

def _jsonl(path:Path)->list[dict]: return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
def build()->list[dict]:
    if hashlib.sha256(CSV.read_bytes()).hexdigest()!=SHA256: raise ValueError('upstream CSV checksum mismatch')
    annotations=_jsonl(ANNOTATIONS); by_row={a['source_row']:a for a in annotations}
    if len(annotations)!=50 or len(by_row)!=50 or {a['id'] for a in annotations}!={f'N{i:03}' for i in range(1,51)}: raise ValueError('missing, duplicate, or mismatched upstream annotation')
    upstream=[]
    with CSV.open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    if len(rows)!=50: raise ValueError('upstream CSV must contain 50 rows')
    for source_row,row in enumerate(rows,1):
        a=by_row[source_row]; raw=json.loads(row['output'])
        case={'id':a['id'],'cohort':'upstream','category':a['category'],'variation':a['variation'],'instruction':row['instruction'],'expected':a['expected'],
              'provenance':{'source_row':source_row,'repository':REPOSITORY,'commit_sha':COMMIT,'csv_sha256':SHA256},'upstream_output':raw,'upstream_label_status':a['upstream_label_status']}
        EvaluationCase.model_validate(case); upstream.append(case)
    authored=_jsonl(AUTHORED)
    if len(authored)!=50: raise ValueError('project-authored cohort must contain 50 rows')
    cases=upstream+authored
    if len({c['id'] for c in cases})!=100: raise ValueError('case IDs must be unique')
    distribution=Counter(c['category'] for c in cases)
    if distribution!=EXPECTED: raise ValueError(f'category distribution mismatch: {distribution}')
    return cases

def main()->None:
    TARGET.write_text(''.join(json.dumps(c,separators=(',',':'),ensure_ascii=False)+'\n' for c in build()),encoding='utf-8')
if __name__=='__main__': main()
