# Confidence Score & Repair Loop — 세션 기록 (2026-07-22)

> `docs/design/IMPLEMENTATION.md`에서 분리됨. 핵심 파이프라인 아키텍처(Stage 1~6)는
> 그 문서를 참고하고, 이 문서는 XAI 신뢰도 점수와 자동 복구 루프 기능 추가 세션을
> 기록한다.

## Confidence Score (`stage5_xai/explainer.py`)

### 목적

각 파이프라인 실행 결과에 대해 운영자가 판정 신뢰도를 한눈에 파악할 수 있도록
`0.0 ~ 1.0` 범위의 수치 점수를 XAI 보고서에 추가한다.

### 설계 결정: Logprob 대신 Stage 결과 기반

Gemini API는 logprob를 지원하지 않아 LLM의 토큰 확률을 직접 추출할 수 없다.
대신 결정론적으로 판별 가능한 두 Stage의 결과를 조합한다.

| 소스 | 가중치 | 이유 |
|------|--------|------|
| Stage 3 Static Validation | 50% | 스키마·충돌 여부는 확실한 이진 판정 가능 |
| Stage 4 Digital Twin | 50% | 실제 트래픽 동작 확인 결과 |

Twin이 `skipped` 상태일 때는 Static 단독으로 점수를 결정한다 (가중치 합산 방식 미사용).

### 점수 계산 로직 (`_compute_confidence()`)

```python
def _compute_confidence(self, static_result, twin_result):
    # Static score
    if static_result.schema_errors:
        static_score = 0.0   # 스키마 오류: 신뢰 불가
    elif static_result.conflicts:
        static_score = 0.3   # 충돌 감지: 낮은 신뢰
    elif static_result.warnings:
        static_score = 0.8   # 경고만 있음: 높은 신뢰
    else:
        static_score = 1.0   # 완전 통과

    # Twin score
    twin_score_map = {"passed": 1.0, "skipped": 0.7, "failed": 0.0, "error": 0.0}
    twin_score = twin_score_map.get(twin_result.status, 0.0)

    # 최종 합산
    if twin_result.status == "skipped":
        confidence = static_score          # Twin 스킵 시 Static만 사용
    else:
        confidence = static_score * 0.5 + twin_score * 0.5

    return round(confidence, 4), {"static": static_score, "twin": twin_score}
```

### XAIReport 변경

```python
@dataclass
class XAIReport:
    intent: str
    ir_summary: str
    flowrule_summary: str
    static_summary: str
    twin_summary: str
    decision: str
    confidence: float = 0.0                    # 추가
    confidence_breakdown: dict = field(default_factory=dict)  # 추가
    evidence: list[dict] = field(default_factory=list)
```

`to_dict()` 출력에 `confidence`, `confidence_breakdown` 필드가 포함되어
SSE 이벤트와 로그 JSON에도 전달된다.

---

## UI Confidence 배지 (`static/app.js`, `static/style.css`)

### 목적

Stage 3 (Static Validation), Stage 4 (Digital Twin) 카드 헤더 우측에
Confidence 점수를 퍼센트 배지로 실시간 표시한다.

### 구현

#### 상태 추가 (`app.js`)

```javascript
const state = {
  ...
  confidenceBreakdown: {},  // { static: 0.8, twin: 1.0 }
};
```

#### 배지 HTML (카드 헤더)

Stage 3, 4 카드 헤더에 `<div class="stage-conf" id="conf-3">` / `id="conf-4"` 추가.
초기 상태에서는 비어 있다가 XAI 단계 완료 후 값이 채워진다.

#### `renderConfidenceBadges()` 함수

```javascript
function renderConfidenceBadges() {
  const bd = state.confidenceBreakdown;
  const vals = { 3: bd.static, 4: bd.twin };

  for (const [stageNum, score] of Object.entries(vals)) {
    if (score == null) continue;
    const el = document.getElementById(`conf-${stageNum}`);
    if (!el) continue;
    const pct = Math.round(score * 100);
    const color = pct >= 80 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444';
    el.textContent = `${pct}%`;
    el.style.color = color;
    el.style.borderColor = color;
  }
}
```

SSE `stage` 이벤트에서 `stage === 5 && status === 'done'` 시 호출된다.
새 파이프라인 실행 시 배지를 초기화(숨김)한다.

#### CSS (`.stage-conf`)

```css
.stage-conf {
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 999px;
  border: 1px solid transparent;
  flex-shrink: 0;
  transition: color 0.3s, border-color 0.3s;
}
```

#### 색상 기준

| 범위 | 색상 | 의미 |
|------|------|------|
| ≥ 80% | `#10b981` (초록) | 높은 신뢰 |
| 50–79% | `#f59e0b` (앰버) | 중간 신뢰 |
| < 50% | `#ef4444` (빨강) | 낮은 신뢰 |

---

## Repair Loop (`api.py`, `main.py`, `stage1_intent/intent_parser.py`)

### 목적

Stage 3 Static Validation 실패 시 즉시 REJECT하지 않고,
오류 피드백을 LLM에 전달해 재파싱을 시도하는 자동 복구 루프를 구현한다.

```
Stage 1 → Stage 2 → Stage 3
                        │ PASS → 진행
                        │ FAIL ← 피드백 생성
                            ↓
                        Stage 1 (재시도)
                        → Stage 2 → Stage 3
                        (최대 3회 반복)
                        │ 3회 소진 후 FAIL → REJECT
```

### `intent_parser.py` 변경

`parse()` 에 `repair_feedback` 파라미터 추가.
피드백이 있으면 LLM user message에 오류 내용을 주입한다.

```python
def parse(self, intent: str, repair_feedback: str | None = None) -> IntentPrediction:
    system = self._build_system_prompt(intent)
    user_msg = intent if not repair_feedback else f"{intent}\n\n{repair_feedback}"
    raw = self.client.call(system, user_msg)
    ...
```

### `_build_repair_feedback()` 헬퍼

```python
MAX_REPAIR_ATTEMPTS = 3

def _build_repair_feedback(static_result, attempt: int, max_attempts: int) -> str:
    lines = [
        f"[Repair attempt {attempt}/{max_attempts} — previous output was rejected by static validation]"
    ]
    if static_result.schema_errors:
        lines.append("Schema errors:")
        for e in static_result.schema_errors:
            lines.append(f"  - {e}")
    if static_result.conflicts:
        lines.append("Conflicts:")
        for c in static_result.conflicts:
            lines.append(f"  - [{c.get('conflict_type', '?')}] {c.get('reason', '')}")
    lines.append("Please revise the intent representation to fix these issues.")
    return "\n".join(lines)
```

### Repair Loop 구조 (`api.py`, `main.py`)

```python
repair_feedback: str | None = None

for repair_iter in range(MAX_REPAIR_ATTEMPTS + 1):
    # Stage 1: parse (repair_feedback 전달)
    prediction = parser_obj.parse(req.intent, repair_feedback=repair_feedback)
    if prediction.status == "rejected":
        finish("REJECT"); return

    # Stage 2: compile
    flowrule = compile_flowrule(ir) or compile_compound(compound)

    # Stage 3: validate
    static_result = static_validate(flowrule, existing_flows=existing)

    if static_result.passed:
        break  # 성공 → 루프 탈출

    if repair_iter >= MAX_REPAIR_ATTEMPTS:
        # 재시도 소진 → REJECT
        finish("REJECT"); return

    repair_feedback = _build_repair_feedback(static_result, repair_iter + 1, MAX_REPAIR_ATTEMPTS)
    # 다음 반복에서 Stage 1 재시도
```

### 세부 동작

- **ONOS 기존 플로우 조회**: 첫 번째 반복에서만 수행 (불필요한 반복 API 호출 방지)
- **stage3 결과**: `repair_attempts` 필드에 실제 재시도 횟수 기록
- **재시도 메시지**: SSE progress 이벤트로 `[Repair N/3] 피드백 생성 완료 — LLM 재시도` 스트리밍
- **LLM 거부 시**: 재시도 없이 즉시 REJECT (토폴로지·문법 오류는 재시도해도 의미 없음)

### 설계 결정

| 결정 | 이유 |
|------|------|
| Stage 3 실패만 트리거 | Stage 1 LLM 거부(ambiguous 등)는 피드백으로 해결 불가 |
| 최대 3회 | RPM 제한 내에서 합리적인 재시도 횟수 (API 비용 대비 효과) |
| 피드백에 errors/conflicts 모두 포함 | LLM이 어떤 필드를 수정해야 하는지 구체적으로 알 수 있도록 |
| ONOS 조회 첫 회만 | 루프 내 반복 조회는 불필요하고 ONOS 타임아웃 위험 증가 |
