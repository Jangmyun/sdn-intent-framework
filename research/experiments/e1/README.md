# Experiment 1: Natural Language to Intent Programs

E1은 순서가 있는 controller-neutral rule program으로의 번역을 평가합니다. Rule
순서는 policy evaluation order이며(우선순위가 가장 높은 것이 먼저), 절대적인 ONOS
priority 값은 semantic scoring에서 의도적으로 제외됩니다.

## Treatments

| ID | Output | Few-shot | Retrieved topology/state |
| --- | --- | --- | --- |
| E1-A | ONOS flow JSON, normalized before scoring | no | no |
| E1-B | Intent program | no | no |
| E1-C | Intent program | yes | no |
| E1-D | Intent program | yes | yes |

모든 treatment에서 동일한 case 순서와 repetition 번호를 사용하십시오. 각 treatment는
최소 5회의 완전한 100-case repetition을 필요로 합니다. 중복된 composite key,
불완전한 run, 누락된 paired repetition은 오류로 처리됩니다.

## Dataset and annotation

`data/intents.jsonl`은 표준 100-case benchmark입니다. 이는 50개의 고정된
NetIntent row(`N001`-`N050`)와 50개의 project-authored case로 구성됩니다.
분포는 forwarding 42, security 23, QoS 23, compound 2, 필수 rejection 10입니다.
각 row는 cohort와 provenance를 기록합니다. Upstream row는 추가로 parsed
raw output과 그 label-review status를 보존합니다.

수정되지 않은 upstream CSV는 commit
`5d5a2377673893dc8a6585346e64272da43a54fc`에 고정되어 있으며 SHA-256은
`d884b12355dcd4e203edec9b748023f24e334d61a9ff8129bdc1a593f29dcdfd`입니다.
`build_dataset.py`는 checksum 변경, annotation 누락/중복, ID 불일치, 잘못된
row 수, distribution drift를 거부합니다. Instruction이 semantic의 근거이며,
controller output은 evidence입니다. Row 39와 45는 compound
two-rule program입니다. Row 39는 raw output에 forwarding clause가 누락되어
있어 불완전한 upstream label로 명시적으로 표시되어 있습니다.

현재 annotation 파일은 파이프라인 검증을 위해 자동 생성된 provisional gold입니다.
실제 두 명의 독립 annotator agreement로 인용해서는 안 됩니다. 두 annotator의
독립 annotation, agreement 계산, disagreement rationale과 adjudication이 완료될
때까지 모든 표와 보고서는 `provisional_gold`로 표시합니다.

## Scoring and reporting

E1-A는 model rejection sentinel로 `{}`를 허용하고, `{"flows":[]}`는 거부하며,
모든 flow를 normalize합니다. Treatment가 없는 경우는 accepted deny rule로
간주됩니다. 비어 있지 않은 treatment는 OUTPUT, QUEUE, VLAN modification을
지원합니다. Flow는 priority 내림차순으로 정렬되며 source order를 tie-breaker로
사용합니다. E1-B부터 E1-D까지는 `schemas/intent_prediction.schema.json`을
사용하며, E1-A는 `schemas/onos_flow_set.schema.json`과 rejection sentinel을
사용합니다.

비교는 먼저 rule count를 확인한 뒤 정렬된 rule과 slot을 정렬하여 확인합니다.
Host/IP alias는 `data/topology.json`을 통해 resolve되며, 알려지지 않은
inventory entity만 hallucination으로 집계됩니다. Report는 response schema
validity, normalized rule/type/slot accuracy, required rejection rate,
unsupported-only rejection rate, reason-specific recall, diagnostic case
list를 포함합니다. Raw ONOS exact match는 upstream-only diagnostic이며 이러한
모든 필드는 `raw_onos_only_` prefix를 사용합니다.

Treatment summary 이전에 run별로 metric을 계산하십시오. Summary는 개별 run
값, mean, sample SD, min/max, 그리고 seed-42 10,000-resample interval인
`exploratory_ci_95`를 포함합니다. 이 interval은 n=5 run을 기반으로 하므로
불확실성은 신중하게 해석되어야 하며, 강한 formal inference보다는 descriptive
비교와 paired same-repetition 비교를 강조해야 합니다. Variation label은 아직
완전히 검증되지 않았으므로 논문 결론에 사용해서는 안 됩니다.
