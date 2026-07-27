# Runtime Logs

각 실험은 `logs/runs/YYYYMMDD/<run_id>/` 아래에 다음과 함께 저장됩니다:

- `manifest.json`: 재현성 메타데이터 및 artifact 참조
- `events.jsonl`: append-only 구조화 이벤트
- `artifacts/`: intent, IR, validation, policy, twin, repair, report payload

원본 run 데이터는 Git에서 무시됩니다. `schemas/`의 JSON Schema와 sanitized 예시는 커밋될 수 있습니다. 실패한 run은 `status: failed`로 보존됩니다.

## Basic Usage

```python
from safe_intent_sdn import create_run_context, load_settings

settings = load_settings()
with create_run_context(settings, intent_id="intent-001") as run:
    run.log_event("intent_received", stage="ingestion", source="cli")
    run.save_artifact("input_intent", "allow h1 to reach h2")

    with run.stage("translation"):
        generated_ir = {"source": "h1", "destination": "h2"}
        run.save_artifact("generated_ir", generated_ir)

    run.finish(
        "APPROVE",
        token_usage={"input": 10, "output": 5, "total": 15},
    )
```

`topology_id`는 기본적으로 `settings.topology.topology_id`를 따릅니다. `finish()`를 호출하지 않고 context를 벗어나면 decision 없이 성공한 run으로 표시됩니다. 예외가 발생하면 실패로 표시되고 다시 raise됩니다.

## Events and Levels

`logging.level`은 `events.jsonl`과 콘솔 양쪽에 기록되는 최소 level입니다. 지원되는 level은 `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`입니다. 모든 이벤트가 필터링되더라도 event 파일은 생성됩니다.

`run.stage(name)`은 중첩된 이벤트에 stage를 바인딩하고 경과 시간과 함께 `stage_started`, `stage_completed`, 또는 `stage_failed`를 발생시킵니다. 이벤트에 명시적으로 지정된 `stage=`는 바인딩된 stage보다 우선합니다.

## Artifacts

- Pydantic model, dataclass, enum, path, date, UUID, JSON 값은 JSON으로 정규화됩니다.
- 구조화된 값은 `.json`을 사용하며, 문자열과 bytes는 제공된 확장자를 유지하거나 기본값으로 `.txt`와 `.bin`을 사용합니다.
- 이름이 중복되면 `result.json`, `result_2.json` 등으로 보존됩니다. 전용 manifest 필드는 최신 버전을 가리킵니다.
- 설정된 secret과 민감한 필드는 저장 전에 redact됩니다.

완료되었거나 실패한 run은 닫힙니다. 이후의 이벤트, artifact, terminal state 변경은 `RuntimeError`를 발생시킵니다.

이전 형태의 nested metrics도 계속 지원됩니다:

```python
run.finish("APPROVE", {
    "execution_time": {"translation_ms": 12.5},
    "token_usage": {"total": 15},
})
```
