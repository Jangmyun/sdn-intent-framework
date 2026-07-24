# E3 근거 — Digital Twin 결정 충실도 (RQ3)

## RQ3

**Digital Twin의 자동 PASS/FAIL 판정은, 동일 정책을 실제로 배포했을 때의 행위적
결과와 얼마나 일치하는가?** 그리고 그 충실도는 인텐트 카테고리에 따라 어떻게
달라지는가?

## 왜 Twin의 유효성을 먼저 세워야 하는가

파이프라인은 Stage 4에서 후보 FlowRule을 Twin에 배포·검증하고, 그 결과를 근거로
배포 여부(APPROVE/REJECT)를 결정한다. 즉 **Twin은 배포 전 게이트(gate)**다. 게이트의
판정을 신뢰하려면, 그 판정이 실제 결과와 일치한다는 것 — 즉 게이트가 *유효한 계측
도구*라는 것 — 이 먼저 입증되어야 한다. E1(번역 정확도)과 E2(정적 검증 경계)는 Twin
*이전* 단계를 다루므로, Twin 자체의 유효성은 별도의 실험으로만 확립할 수 있다.

이는 E1/E2와 같은 논리다: 파이프라인의 각 구성요소는 그것이 기여한다고 주장하는
바를 독립적으로 측정해야 하며, Twin의 기여는 "정책의 행위적 결함을 배포 전에
정확히 판정한다"는 것이다.

## 왜 결정 정합도(혼동행렬)인가

Twin의 유효성은 **판정의 정합도**로 측정한다. 세 arm을 같은 케이스 집합에 실행한다:

- `ground_truth` — 배경 부하 하에서 배포하여 *참* 결과(도달성 AND 실측 대역폭 ≥ 목표
  AND 회귀)를 측정. PASS는 정책이 실제로 인텐트를 달성함(SHOULD_PASS)을 뜻한다.
- `twin_nobw` — 도달성 검사만으로 내린 Twin 판정.
- `twin_bw` — 여기에 iperf3 대역폭 프로브를 더한 Twin 판정.

positive class를 "승인되어야 할 정책"(ground truth PASS)으로 두면, **false positive는
위험한 오승인**(Twin은 PASS, 실제는 FAIL)이고, `fpr`이 곧 안전성 지표가 된다. 이는
E2가 혼동행렬로 정적 검증을 평가한 방식과 일관되며, 단순 성공/실패 비율보다 "Twin이
어떤 종류의 오류를 내는가"를 드러낸다.

## 왜 대역폭 프로브 대조(twin_nobw vs twin_bw)인가

포팅된 기준 Twin은 **도달성만** 검사한다. 그 결과 QoS 인텐트는 "도달 가능하면 통과"로
판정되어, 요청한 대역폭이 링크의 물리적 한계를 넘어 어떤 큐 예약으로도 달성 불가능한
정책도 승인된다 — 이것이 Twin의 사각지대다. `twin_nobw`와 `twin_bw`를 같은 케이스에서
대조하면, 이 사각지대가 **어느 카테고리에서 얼마나 발생하는지**, 그리고 대역폭 프로브가
그것을 어느 정도 메우는지를 정량적으로 보일 수 있다. forwarding/security/reroute는
도달성 판정으로 충실하므로 대조군 역할을 하고, 사각지대는 qos(용량 초과 요청) 케이스에
집중된다. (초기 설계는 "예약 없는 배경 트래픽이 큐를 밀어낸다"는 혼잡 시나리오였으나,
실제 OVS 큐를 프로비저닝하면 예약된 흐름이 정확히 그런 경쟁으로부터 보호받는 게 정상
동작이라 그 설계로는 실패 케이스가 재현되지 않았다 — 자세한 경위는
experiments/e3/DATASET_CARD.md 참조.)

## 모든 arm이 같은 부하를 재생하는 이유

세 arm 모두 동일한 배경 트래픽을 재생한다. 그래야 arm 간 차이가 **Twin의 검사 논리**
(도달성 only vs 도달성+대역폭)에서만 비롯되고, "Twin이 운영 부하를 갖지 못해서" 생기는
차이로 오염되지 않는다. 이는 앞선 논의의 "telemetry 기반 behavioral replay" 관점과도
일치한다 — Twin은 트래픽 패턴을 재생하고, 검증은 그 위에서 이루어진다.

## 스코프 한계 (E2의 caveat 기술 방식과 동일)

- E3는 **Twin이라는 판정 도구가 에뮬레이트된 배포의 실제 행위 결과와 일치하는가**를
  검증한다. **"Mininet 에뮬레이션이 물리 장비와 동일한가"는 검증 대상이 아니다.**
  Ground truth는 배경 부하 하에서 *종합 측정된 에뮬레이트 배포*이며, 물리 네트워크
  실측이 아니다.
- ground_truth와 twin_bw는 동일한 측정 절차를 밟는다. 따라서 이 둘의 높은 일치는
  "대역폭을 검사하는 Twin은 충실하다"를 뜻하고, 대조의 실질적 정보는 `twin_nobw`와의
  차이에 있다. 두 arm을 독립 실행으로 유지하는 것은 측정 노이즈(run-to-run 변동)를
  드러내기 위함이다.
- `expected_ground_truth`는 저자가 조정한 독립 앵커다. 측정된 ground truth가 이와
  불일치하면(`ground_truth_label_mismatch`) 에뮬레이트 시나리오가 의도한 조건을
  재현하지 못한 것이므로, 그 경우 충실도 수치를 신뢰하기 전에 부하 파라미터를
  조정해야 한다.
- 데이터셋은 카테고리별 대조를 실행하기 위한 소규모 수기 벤치마크(E2 fixture와 동급)
  이며, 대규모 표본 corpus가 아니다.

## 재현 절차

Linux + root + Mininet + 실행 중인 ONOS(`./scripts/onos.sh start`) 필요:

```bash
# 세 arm을 순차 실행 (각 케이스 수 분 소요, 재실행 시 이어서 진행)
sudo -E env "PATH=$PATH" uv run python experiments/e3/run_twin_fidelity.py --arm ground_truth --output logs/e3/ground_truth.jsonl
sudo -E env "PATH=$PATH" uv run python experiments/e3/run_twin_fidelity.py --arm twin_nobw   --output logs/e3/twin_nobw.jsonl
sudo -E env "PATH=$PATH" uv run python experiments/e3/run_twin_fidelity.py --arm twin_bw     --output logs/e3/twin_bw.jsonl

# 채점 → 집계 JSON
uv run python experiments/e3/score.py --output logs/e3/e3_fidelity.json \
  logs/e3/ground_truth.jsonl logs/e3/twin_nobw.jsonl logs/e3/twin_bw.jsonl

# 그림 (영문 + _ko)
uv run --group plots python paper/scripts/plot_e3_fidelity.py
```

데이터셋·채점 로직은 Mininet 없이 CI에서 검증된다
(`tests/test_e3_dataset.py`, `tests/test_e3_evaluation.py`). Twin arm은 root/Mininet이
필요하므로 유닛테스트 대상이 아니며, 대신 `scripts/e3_twin_smoke.sh`로 통합 확인한다.
