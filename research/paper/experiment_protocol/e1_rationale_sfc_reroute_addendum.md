# E1-SFC/Reroute 확장 실험 결과 (addendum to `e1_rationale.md`)

> **범위 고지**: 이 문서는 `e1_rationale.md`가 다루는 원본 100-case E1 벤치마크(upstream
> 50 + project-authored 50)를 대체하지 않는다. 여기서 다루는 100-case 확장 데이터셋
> (`experiments/e1/data/intents_sfc_reroute.jsonl` — project-authored 50 재사용 +
> sfc/reroute 신규 50)과 그 결과는 별도로 보고하며, 원본 결과(`paper/result_tables/e1_results.md`)와
> 수치를 합산하거나 같은 표에 병기하지 않는다. 데이터셋 구성·분리 사유는
> `experiments/e1/DATASET_CARD_SFC_REROUTE.md`에 문서화되어 있다. Gold status는 원본과
> 동일하게 **provisional**이다(독립 이중 annotation 미완료).

## 1. 실행 프로토콜

원본 E1과 동일한 프로토콜을 그대로 적용했다: model `qwen3:8b`(Ollama-compatible,
temperature 0.2, num_ctx 4096, `/no_think`), 4 treatment(E1-A/B/C/D) × 5
repetition(seed 42–46) × 100 case = 2,000 call. 유일한 차이는 `--dataset`/`--topology`가
`intents_sfc_reroute.jsonl`/`topology_diamond.json`을 가리킨다는 것과, IR treatment(B/C/D)의
시스템 프롬프트에 `SFC_REROUTE_ADDENDUM`(sfc/reroute 필드 설명)이 추가된다는 것뿐이다
(`experiments/e1/run_experiment.py`, `dataset_path.name`에 `"sfc_reroute"`가 포함될 때만
조건부 적용 — 원본 벤치마크의 프롬프트와 기존 로그의 재현성은 영향받지 않는다).

이번 확장을 실행하기 위해 `run_experiment.py`에 `--config` 옵션을 추가했다(기존에는
`--treatment` 값에서 `config/experiments/e1_{a,b,c,d}.toml` 경로를 하드코딩으로만 생성했다).
재현 명령:

```
python experiments/e1/run_experiment.py --treatment E1-B \
  --config config/experiments/e1_sfc_reroute_b.toml --repetition 1 \
  --output logs/e1/e1-sfc-reroute-b-qwen3-8b-r1.jsonl
```

20개 로그 파일(`logs/e1/e1-sfc-reroute-{a,b,c,d}-qwen3-8b-r{1..5}.jsonl`)을
`experiments/e1/score.py`에 전달하면 동일한 `logs/e1/e1_sfc_reroute_aggregate_full.json`이
생성된다.

## 2. Table 4′. Intent translation 성능 (E1-SFC/Reroute, mean of 5 runs, 100-case 전체)

| Metric | E1-A (direct flow) | E1-B (IR, zero-shot) | E1-C (IR, few-shot) | E1-D (IR, few-shot+grounded) |
| --- | ---: | ---: | ---: | ---: |
| Response schema validity | 0.692 | 0.858 | 0.940 | 0.910 |
| Normalized exact match | 0.020 | 0.134 | 0.258 | 0.270 |
| Normalized rule-count accuracy | 0.004 | 0.598 | 0.611 | 0.602 |
| Normalized type accuracy | 0.600\* | 0.529 | 0.343 | 0.406 |
| Required rejection rate (10-case) | 1.000\* | 0.600 | 0.700 | 0.820 |
| Unsupported-only rejection rate (2-case) | 1.000 | 1.000 | 1.000 | 1.000 |
| Hallucinated entity rate | 0.100\* | 0.205 | 0.228 | 0.014 |

\* E1-A는 원본 문서(`e1_results.md` §3)와 동일한 이유로 대량 과잉거절(over-rejection)의
부산물이 섞여 있어 다른 treatment와 직접 비교할 수 없다. 특히 `normalized_type_accuracy`는
run 간 표준편차가 0.418로 7개 지표 중 압도적으로 크다(direct ONOS flow 출력의 비결정성).

Response schema validity와 required rejection rate는 원본 100-case 결과와 유사한 추세(A<B<C,
D가 few-shot 단독보다 개선)를 보인다. 그러나 **normalized exact match는 원본보다 전 구간에서
낮고(E1-D: 0.270 vs 원본 0.368), normalized type accuracy는 B→C→D에서 개선되지 않고 오히려
악화된다(0.529→0.343→0.406)** — 원본에서 grounding이 만든 가장 뚜렷한 개선(§2 참고)이
이 확장에서는 재현되지 않는다. §3–4에서 원인을 사례 수준으로 분해한다.

## 3. 카테고리별 분해: 개선이 재현되지 않는 지점은 어디인가

Treatment×category별로 재채점한 결과(각 category를 독립적으로 `evaluate_run`에 통과시켜
평균):

| Category (n) | E1-A schema/exact | E1-B schema/exact | E1-C schema/exact | E1-D schema/exact |
| --- | ---: | ---: | ---: | ---: |
| forwarding (15) | 0.587 / 0.000 | 0.880 / 0.120 | 1.000 / 0.333 | 1.000 / 0.320 |
| security (15) | 0.600 / 0.000 | 0.867 / 0.253 | 1.000 / 0.667 | 1.000 / 0.613 |
| qos (10) | 0.800 / 0.000 | 0.840 / 0.300 | 1.000 / 0.400 | 1.000 / 0.300 |
| ambiguous_unsupported (10) | 1.000 / 0.200 | 0.800 / 0.480 | 0.900 / 0.680 | 1.000 / 0.800 |
| **sfc (25)** | 0.680 / **0.000** | 0.824 / **0.000** | 0.960 / **0.000** | 0.920 / **0.000** |
| **reroute (25)** | 0.656 / **0.000** | 0.904 / **0.000** | 0.840 / **0.000** | 0.720 / **0.080** |

원본 벤치마크와 구조적으로 동일한 4개 base category(forwarding/security/qos/
ambiguous_unsupported, project-authored 50 재사용분)는 원본과 일관된 추세로 개선된다 — 이
50건에 한정하면 확장이 기존 결과의 재현성을 훼손하지 않는다는 뜻이다. 문제는 신규 50건에
있다: **`sfc` 카테고리는 A/B/C/D 전부에서 exact match 0.000**이고(schema validity는
0.68–0.96으로 낮지 않음에도), `reroute`도 E1-D 한 조건(0.080)을 제외하면 전부 0.000이다.
즉 이번 확장에서 관찰된 전체 exact-match 하락과 type-accuracy 역전은 base 4-category가
아니라 **sfc/reroute 두 신규 category에서 전적으로 발생**한다.

## 4. 왜 sfc는 0%인가: 구조적 붕괴, 오답이 아니다

E1-D(few-shot+grounded, 4개 조건 중 최고 성능) run 1의 SFC 25건 중 schema-valid 응답
23건을 직접 대조한 결과, **23건 모두 gold의 2-rule(ingress+egress) 체인 구조를 만들지
않았다**. 예시(`SFC-A01`, "Route HTTP from 10.0.0.1 to 10.0.0.3 through the firewall on
switch 1 port 9."):

```
expected: intent_type=sfc(×2, sfc_role=ingress/egress), sfc_chain=["of:...:9"]
actual  : intent_type=forwarding(×1), enforcement.egress_port=9 (waypoint를 단일 egress_port로 흡수)
```

모델은 "포트 9의 firewall을 거쳐서"라는 지시를 **단일 forwarding rule의 egress_port 값**으로
흡수해버린다 — 방화벽을 거쳐 트래픽이 두 단계(ingress: 방화벽으로, egress: 방화벽에서
목적지로)로 나뉘어야 한다는 sfc 고유의 의미를 표현하지 않는다. `intent_type`도 `sfc`가 아닌
`forwarding`/`security`로 출력되므로, `sfc_role`/`sfc_chain` 필드 자체가 등장하지 않는다.
`SYSTEM_IR`의 `SFC_REROUTE_ADDENDUM`이 sfc_role/sfc_chain 요구사항을 프롬프트 텍스트로
명시함에도(§1), few-shot 예시와 topology grounding 둘 다 이 구조적 요구를 따르게 만들지
못했다 — few-shot 예시(`demonstrations.json`)에 sfc 사례가 없고, topology grounding은
device/port 존재 여부만 알려줄 뿐 "몇 개의 rule로 어떻게 나눌지"는 알려주지 않기 때문으로
해석하는 것이 데이터와 부합한다. `normalized_type_accuracy`가 B→C→D에서 개선되지 않는
이유도 이것으로 설명된다: type accuracy는 rule 단위로 계산되는데, sfc 25건의 예측 rule
대부분이 `intent_type: sfc`가 아니므로 카테고리 하나가 지표 전체를 구조적으로 끌어내린다.

## 5. 왜 reroute도 낮은가: 오답이 아니라 gold 인코딩과의 불일치

Reroute는 sfc와 실패 양상이 다르다 — 구조 붕괴가 아니라 **`enforcement` 필드 선택의
불일치**다. `reroute` gold 50건 전체는 실제로 `avoid_device`를 단 한 건도 사용하지 않는다
(review 기록대로 "unused by any gold case"). 대신 gold는 재배치된 실제 placement를
`device`+`egress_port`로 직접 인코딩한다. 그러나 `RR-A01`("Reroute traffic ... via switch 2
instead of switch 3.")처럼 **회피 표현("instead of", "avoid X")으로 서술된 instruction**에
대해, 모델은 문언 그대로 `enforcement.avoid_device`를 채우는 경향을 보인다:

```
expected: enforcement={device: "of:...0001", egress_port: "1", avoid_device: null}
actual  : enforcement={avoid_device: "s3"}  # device/egress_port 없이 회피 제약만 인코딩
```

E1-D r1에서 이 경향을 변이형(`variation`)별로 정량화하면, `alt_switch`(회피 표현이 명시적인
변이형, 10건 중) 9/10건이 `avoid_device`를 사용했고, `port_change`(회피 표현이 없는 변이형)는
0/8건, `failover`는 4/7건이었다 — 회피 표현이 있는 instruction일수록 모델이 `avoid_device`
필드를 쓰는 빈도가 뚜렷하게 높다. 즉 **모델이 명시적으로 등장하는 자연어 제약(avoid X)을
IR의 대응 필드(`avoid_device`)로 옮기는 것은 설계상 지원되는 정상적인 동작**이며, 오히려
gold가 이 필드를 한 번도 쓰지 않고 항상 "결과 placement"만 요구한다는 점이 두 표현 사이의
비대칭을 만든다. exact-match 채점 관점에서는 여전히 오답이지만, "모델이 의미를 잘못
이해했다"기보다 "gold 인코딩 관례와 모델의 자연스러운 선택이 갈렸다"에 더 가깝다 — 이는
sfc의 구조적 붕괴(§4)와는 질적으로 다른 실패 유형이므로 하나의 "reroute 실패"로 뭉뚱그려
보고하지 않는다.

## 6. Slot-level 분해 (참고, B/C/D 평균)

| Slot | E1-B | E1-C | E1-D |
| --- | ---: | ---: | ---: |
| device | 0.281 | 0.361 | 0.587 |
| egress_port | 0.444 | 0.537 | 0.550 |
| sfc_role | 0.578 | 0.528 | 0.538 |
| eth_type | 0.450 | 0.606 | 0.513 |
| action | 0.665 | 0.652 | 0.656 |

원본 벤치마크(§2, `e1_results.md`)에서는 grounding이 `device` slot 정확도를 0.481→0.924로
거의 두 배 끌어올렸지만, 이 확장에서는 같은 개입이 0.361→0.587에 그친다. Diamond topology의
device 수가 원본보다 많고(§4/§5에서 보듯 sfc/reroute rule 자체가 device 배치를 더 복잡하게
요구), sfc의 구조적 붕괴로 인해 애초에 device 슬롯을 채울 rule 수 자체가 gold와 달라지는
경우가 많다는 점이 이 완화된 개선폭의 유력한 원인이다. `sfc_role`(0.53–0.58)이 세 조건에서
거의 개선되지 않는 것도 §4의 구조적 붕괴와 같은 원인을 공유한다 — 애초에 `sfc_role`이
등장하는 예측 자체가 드물다.

## 7. RQ1 재해석: 확장 범위에서 무엇이 남는가

원본 RQ1 결론("IR 형식이 direct output 대비 상대적으로 개선된 구조적 신뢰성을 준다")은
base 4-category(§3)에서 그대로 유지된다. 그러나 sfc/reroute라는 **다중 rule·비-forwarding
placement 의미론**을 요구하는 확장에서는, 현재 개입 집합(few-shot + state-grounding)만으로는
정확한 IR 생성이 달성되지 않는다:

1. **Few-shot과 grounding은 "형식이 안정된 단일 rule" 과제에서만 검증된 개입이다.** 이
   확장은 그 검증 범위를 넘어서는 다중 rule 구조(sfc)와 gold 인코딩 관례(reroute의
   `avoid_device` 미사용)를 요구하며, 두 경우 모두 원본에서 관찰된 개선이 재현되지 않는다.
2. **실패 원인이 카테고리마다 질적으로 다르다** — sfc는 구조 자체를 만들지 못하는 구조적
   붕괴, reroute는 gold 인코딩 관례와의 불일치. 이는 RQ2(정적 검증)에서 "번역 오류를
   validator가 어떻게 잡아내는가"를 설계할 때 두 실패 유형에 서로 다른 finding category가
   필요하다는 근거가 된다 — 실제로 `safe_intent_sdn/validator.py`의 `path` finding
   category(§2 유형의 chain 불연속·structural 오류 탐지)가 이 확장을 위해 신설되었다
   (`paper/experiment_protocol/e2_rationale_sfc_reroute_addendum.md` §2.2).
3. 이는 독립적인 후속 validator의 필요성(원본 RQ1 결론 (c))을 오히려 더 강하게 뒷받침한다
   — LLM은 새로운 IR 구조(sfc의 다중 rule)를 스스로 안정적으로 생성하지 못하므로, 그
   구조적 정합성을 사후에 검증하는 단계가 없다면 이런 실패는 무자각 상태로 배포될 수 있다.

## 8. Threats to validity

- **Provisional gold**: 원본과 동일하게 독립 이중 annotation이 완료되지 않았다. 특히
  §5에서 지적한 reroute의 `avoid_device` 미사용 관례는 gold 저작자(연구자 본인)의 설계
  선택이며, 독립 adjudication을 거치면 "회피 표현에는 avoid_device를 허용한다"는 대안
  gold 규칙이 채택될 수 있다 — 그 경우 reroute exact match는 현재 수치보다 유의미하게
  높아질 것이다.
- **Rule 순서 매칭 미해결**: `e1_rationale.md`/`plan_review.md` §A에서 이미 지적된 구조적
  이슈(위치 기반 slot 비교)가 이 확장에도 동일하게 적용된다. sfc의 2-rule 프로그램에서
  ingress/egress 순서가 뒤바뀌면 실제로는 부분적으로 맞은 예측도 전부 mismatch로
  집계된다 — 다만 §4에서 확인했듯 이번 관찰의 압도적 다수는 순서 문제가 아니라 애초에
  2-rule 구조 자체가 생성되지 않은 경우이므로, 순서 매칭을 도입해도 sfc exact match가
  크게 개선되지는 않을 것으로 예상한다.
- **모델 단일성**: 원본과 동일하게 `qwen3:8b` 1개 모델, 1개 온도(0.2) 설정에서만 얻어진
  결과다. 다중 rule 구조 생성 실패가 이 모델 특유의 한계인지, 더 큰 모델에서도 재현되는
  일반적 패턴인지는 이 실험만으로 판단할 수 없다.
- **Few-shot 예시 공백**: `demonstrations.json`은 sfc/reroute 예시를 포함하지 않는다(원본
  100-case 벤치마크의 예시를 그대로 재사용했기 때문). §4의 구조적 붕괴가 few-shot의
  근본적 한계인지, 단순히 sfc 예시가 few-shot 세트에 없었기 때문인지는 분리되지 않았다 —
  sfc 예시를 포함한 few-shot 세트로 재실행하면 이 confound를 제거할 수 있다(향후 과제).
- **Run-to-run 변동**: `required_rejection_rate`가 E1-D에서 sd=0.0447로 원본과 유사하게
  가장 큰 변동을 보이는 지표다. 나머지 지표는 대부분 sd<0.02로 낮다. n=5는 원본과 동일한
  이유로 강한 통계적 추론에는 부족하며, 위 수치는 서술적 비교로만 다룬다.
