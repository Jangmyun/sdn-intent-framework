"""
pipeline/repair_utils.py — Repair Loop 공유 유틸리티

main.py와 api.py 양쪽에서 사용하는 MAX_REPAIR_ATTEMPTS 상수와
build_repair_feedback 함수를 중복 없이 공유한다.
"""
from __future__ import annotations

MAX_REPAIR_ATTEMPTS: int = 3


def build_repair_feedback(static_result, attempt: int, max_attempts: int) -> str:
    """
    정적 검증 실패 결과를 바탕으로 LLM 재시도용 피드백 문자열을 생성한다.

    Args:
        static_result: stage3_static.static_validator.validate() 반환값
        attempt: 현재 재시도 횟수 (1-based)
        max_attempts: 최대 재시도 횟수

    Returns:
        LLM repair_feedback으로 전달할 문자열
    """
    lines = [
        f"[Repair attempt {attempt}/{max_attempts}"
        " — previous output was rejected by static validation]"
    ]
    if static_result.schema_errors:
        lines.append("Schema errors:")
        for e in static_result.schema_errors:
            lines.append(f"  - {e}")
    if static_result.conflicts:
        lines.append("Conflicts:")
        for c in static_result.conflicts:
            lines.append(
                f"  - [{c.get('conflict_type', '?')}] {c.get('reason', '')}"
            )
    lines.append("Please revise the intent representation to fix these issues.")
    return "\n".join(lines)
