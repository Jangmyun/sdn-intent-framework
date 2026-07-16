# E1 실험 설계 근거 (RQ1)

## RQ1

**LLM/RAG는 자연어 네트워크 intent를 얼마나 정확하고 일관된 Intent IR로 변환할 수 있는가?**

## 1. 왜 번역 단계를 독립적으로 검증해야 하는가

본 연구가 제안하는 파이프라인은 자연어 intent를 controller-neutral Intent IR로 변환한
뒤, 이를 정적 검증(Static Validator), Digital Twin 실행 검증, 실패 evidence 기반
repair를 거쳐 최종 배포 여부를 결정하는 다단계 구조다. 이 구조에서 Intent IR은
파이프라인 전체가 공유하는 유일한 입력이며, 이후의 모든 검증·수정·설명 단계는 이
IR이 실제로 운영자의 의도를 얼마나 충실히 담고 있는지를 전제로 동작한다.

따라서 번역 단계에서 발생하는 오류율과 오류 유형을 먼저 정량화하지 않으면, 이후
단계에서 관찰되는 실패(예: Twin에서의 reachability 실패, repair 반복 횟수 증가)가
번역 오류에서 기인한 것인지, 검증·수정 로직 자체의 결함에서 기인한 것인지를 분리할
수 없다. 즉 RQ2–RQ6에서 제시할 모든 비교(B1 vs B2, B2 vs B3, B3 vs B4 등)는 B1
단계, 즉 LLM 번역이 만들어내는 기저 오류 분포가 먼저 측정되어 있어야 그 위에서
성립하는 통제된 비교가 된다. E1은 이 기저선(baseline)을 확보하기 위한 실험이며,
동시에 연구 목적(0.3)에서 제시한 "LLM/RAG를 통한 controller-neutral Intent IR
변환"이라는 파이프라인의 첫 구성요소 자체가 유효한지를 검증하는 실험이다.

## 2. 왜 direct output과 Intent IR을 대조해야 하는가 (E1-A vs E1-B)

핵심 문제 정의(0.4)의 첫 번째 항목은 "자연어의 모호성과 LLM hallucination으로 인해
잘못된 entity 또는 정책이 생성될 수 있다"는 것이며, 본 연구 기여(0.8-1)는 "자연어
intent와 controller-specific flow rule 사이에 검증 가능한 중간 표현을 두어 LLM과
SDN 제어 로직의 역할을 분리한다"는 주장이다. 이 주장은 경험적으로 검증되지 않으면
설계상의 가정에 불과하다.

E1-A(LLM이 ONOS flow JSON을 직접 생성)와 E1-B(LLM이 controller-neutral Intent IR을
생성)는 동일한 모델, 동일한 100-case 데이터셋, 동일한 few-shot/grounding 조건(둘 다
없음) 아래에서 오직 출력 표현만 다르게 하여 비교한다. 이 대조가 없으면 "Intent IR이
direct output보다 낫다"는 주장은 반증 가능한 형태로 제시될 수 없다. 실제로 E1-A의
초기 실행 결과, 모델은 프로젝트가 정의한 필드명(`ip`, `protocol`, `port`) 대신 실제
ONOS REST API가 사용하는 필드명(`ipv4Dst`, `ipProto`, `outputPort`)을 상당수
사례에서 사용하여 스키마 검증에 실패했다. 이는 사전에 예상하지 못한 실패 양상이며,
direct output 방식이 통제되지 않은 controller-specific 세부사항에 얼마나 취약한지를
보여주는 구체적 증거로, E1-A라는 대조군 없이는 관찰될 수 없었던 결과다.

## 3. 왜 few-shot과 state-grounding을 단계적으로 분리해야 하는가 (E1-B/C/D)

RQ1은 정확도뿐 아니라 "일관된" 변환을 요구한다. Intent IR 형식을 채택하는 것만으로
충분한지, 아니면 예시 기반 학습(few-shot)이나 실제 topology/state 정보의 주입
(retrieval/state-grounding)이 추가로 필요한지는 서로 다른 개입이며 서로 다른
실패 유형을 겨냥한다. Few-shot은 출력 형식과 slot 채우기 관례를 안정시키는 데
주로 기여할 것으로 예상되고, state-grounding은 hallucinated entity(존재하지 않는
host/switch/port 참조)를 억제하는 데 주로 기여할 것으로 예상된다. 두 개입을
분리하지 않고 한 번에 결합하면 어느 메커니즘이 어떤 오류 유형을 줄이는지 귀속시킬
수 없다.

E1-C(few-shot 추가)와 E1-D(few-shot + topology 기반 grounding 추가)를 누적적으로
설계한 것은 이 때문이며, 이 설계는 §6(연구 질문과 결과 연결)에서 예고한 "Proposed
− retrieval" ablation 및 Table 4(intent translation 성능)의 전신에 해당한다. E1의
네 조건(A/B/C/D)은 이후 실험에서 다룰 B0–Proposed 누적 비교 축의 번역 단계
버전이며, 여기서 확립한 비교 방법론(동일 case 순서, paired repetition, run-aware
집계)은 뒤따르는 정적 검증·Digital Twin 실험에도 그대로 재사용된다.

## 4. 왜 정확도 지표만으로는 부족한가

핵심 문제 정의의 다섯 항목 중 최소 세 항목(모호성/hallucination, 잘못된 거절 또는
승인, 자유 형식 설명의 근거 없는 주장)은 "정답과 얼마나 같은가"로는 포착되지 않는다.
이 때문에 E1은 단일 exact-match 지표 대신 다음을 함께 측정하도록 설계되었다.

- **response schema validity**: 구조적으로 파싱 가능한 출력을 만드는가.
- **normalized rule/type/slot accuracy**: 의미적으로 올바른 rule을 만드는가.
- **hallucinated entity rate**: 존재하지 않는 inventory entity를 참조하는가.
- **required/unsupported rejection rate**: 반드시 거절해야 하는 요청(모호, 모순,
  미지의 entity, 미지원 기능)을 실제로 거절하는가.

특히 마지막 지표는 프로젝트 저작 50개 사례 중 10개를 의도적으로 "거절되어야 하는"
사례로 구성했기 때문에 측정 가능하다. 이는 벤치마크가 "정답을 맞히는 능력"뿐 아니라
"모르는 것을 모른다고 말하는 능력"을 요구하도록 의도적으로 설계된 것이며, 후속
연구 기여(0.8-1, 0.8-4)에서 주장할 안전성·설명가능성 논지의 정량적 근거가 된다.

## 5. 왜 반복 실행과 paired 비교가 필요한가

LLM 출력은 확률적이므로 단일 실행에서 관찰된 조건 간 차이가 실제 treatment 효과인지
표본 변동인지 구분할 수 없다. E1은 조건별 최소 5회의 완전한 100-case 반복을
요구하고, 모든 조건에서 동일한 case 순서와 반복 번호(seed 42–46)를 사용하여
paired same-repetition 비교를 가능하게 한다. 이는 향후 통계적 검정력이 부족한
소표본(n=5)에서도 "이 차이가 우연이 아니라 동일 조건 쌍에서 반복적으로 관찰되는
차이인가"를 최소한의 근거로 판단할 수 있게 한다. 다만 n=5는 강한 모집단 추론에는
부족하므로, E1의 보고 방식은 bootstrap 신뢰구간을 서술적(descriptive) 참고치로만
제시하고 논문의 핵심 주장은 paired 비교와 사례 분석에 둔다.

## 6. 요약: E1이 필요한 이유

1. Intent IR 기반 파이프라인이라는 설계 자체의 타당성(direct output 대비 우위)을
   경험적으로 입증하기 위해 필요하다.
2. RQ2 이후 모든 단계(정적 검증, Digital Twin, repair)의 비교 실험이 성립하기 위한
   번역 단계 오류 기저선을 제공하기 위해 필요하다.
3. Few-shot과 retrieval/state-grounding이라는 서로 다른 개입의 효과를 분리하여
   귀속시키기 위해 필요하다.
4. 정확도만으로 포착되지 않는 hallucination과 필수 거절 행동을 정량화하여, 안전한
   자동화라는 연구 목적(0.3)과 직접 연결된 증거를 만들기 위해 필요하다.
5. LLM 출력의 확률적 변동을 반복 실행으로 통제하여, 조건 간 비교가 재현 가능하고
   반증 가능한 형태로 제시되도록 하기 위해 필요하다.

> **주의(provisional gold)**: 본 문서 작성 시점 기준 E1 gold annotation은 두 명의
> 독립 annotator agreement가 완료되지 않은 `provisional_gold` 상태이며, 최종
> 논문 수치는 독립 annotation과 adjudication이 끝난 뒤 확정한다.
