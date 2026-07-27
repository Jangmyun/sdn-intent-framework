"""
config.py — End-to-End XAI SDN 파이프라인 전역 설정

모든 파이프라인 모듈은 이 파일에서 설정을 임포트한다.

BASE_DIR은 현재 작업 디렉터리(cwd) 기준이다 — 이 파일 자체는 src/xai_pipeline/
아래 설치된 패키지 코드이므로 __file__ 기준으로 잡으면 안 된다(설치 위치와
사용자가 데이터를 두는 위치가 다르다). 모든 문서가 "레포 루트에서 실행"을
전제하므로, cwd == 레포 루트다.

논문 재현 트랙(research/)은 별도 설정 체계(research/config/, SAFE_SDN_* 환경변수)를
사용하며 이 파일과 무관하다.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── 경로 설정 ─────────────────────────────────────────────────
BASE_DIR: Path = Path.cwd()
ROOT_DIR: Path = BASE_DIR

load_dotenv(BASE_DIR / ".env")

# ── LLM 설정 ─────────────────────────────────────────────────
LLM_BASE_URL: str = os.environ.get("LLM_BASE_URL", "https://ollama.jangmyun.dev/v1")
LLM_MODEL: str = os.environ.get("LLM_MODEL", "gemini-3.1-flash-lite")
EMBED_MODEL: str = os.environ.get("EMBED_MODEL", "nomic-embed-text")
LLM_API_KEY: str = os.environ.get("LLM_API_KEY", "ollama")
GOOGLE_API_KEY: str = os.environ.get("GOOGLE_API_KEY", "")
OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# ── ONOS 설정 ─────────────────────────────────────────────────
ONOS_URL: str = os.environ.get("ONOS_URL", "http://127.0.0.1:8181/onos/v1")
ONOS_USER: str = os.environ.get("ONOS_USER", "onos")
ONOS_PASSWORD: str = os.environ.get("ONOS_PASSWORD", "rocks")

# Mininet RemoteController가 연결할 OpenFlow 컨트롤러 주소 (ONOS_URL과 별개 —
# REST API(8181)가 아닌 raw OpenFlow control channel(기본 6653)).
ONOS_CONTROLLER_IP: str = os.environ.get("ONOS_CONTROLLER_IP", "127.0.0.1")
ONOS_CONTROLLER_PORT: int = int(os.environ.get("ONOS_CONTROLLER_PORT", "6653"))

# ── API 서버 설정 ─────────────────────────────────────────────
# CORS_ORIGINS: 쉼표 구분 허용 출처. 기본값 "*" (개발용).
# 운영 배포 시 .env에서 "https://your-domain.com" 등으로 지정할 것.
CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "*").split(",")
    if o.strip()
] or ["*"]

# API_KEY: X-API-Key 헤더 인증. 빈 문자열이면 인증 비활성화 (개발용).
# 운영 배포 시 .env에서 강력한 랜덤 키로 반드시 설정할 것.
API_KEY: str = os.environ.get("API_KEY", "")

# ── 로컬 디렉토리 ─────────────────────────────────────────────
LOGS_DIR: Path = BASE_DIR / "logs"
RESULTS_DIR: Path = BASE_DIR / "results"
DATA_DIR: Path = BASE_DIR / "data"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── 데이터셋 경로 ─────────────────────────────────────────────
# 외부 실험 데이터셋(우선) → 로컬 data/ 폴백
_external_dataset: Path = (
    ROOT_DIR
    / "experiments"
    / "1_netintent_baseline"
    / "NetIntent"
    / "GitHub NetIntent"
    / "Datasets"
    / "Intent2Flow-ONOS.csv"
)
DATASET_PATH: Path = (
    _external_dataset
    if _external_dataset.exists()
    else BASE_DIR / "data" / "intents_v2.jsonl"
)


def is_gemini(model: str) -> bool:
    """Gemini 모델 여부 판단"""
    return model.lower().startswith("gemini")


def validate_config() -> list[str]:
    """
    설정 유효성 검사. 경고 메시지 목록을 반환한다.
    서버/CLI 시작 시 호출하여 문제를 조기에 알린다.
    """
    warnings: list[str] = []

    if ONOS_PASSWORD == "rocks":
        warnings.append(
            "ONOS_PASSWORD가 기본값 'rocks'입니다. 운영 환경에서는 반드시 변경하세요."
        )

    if not API_KEY:
        warnings.append(
            "API_KEY가 설정되지 않았습니다. /api/run 엔드포인트에 인증이 없습니다. "
            "운영 배포 시 .env에서 API_KEY를 설정하세요."
        )

    if CORS_ORIGINS == ["*"]:
        warnings.append(
            "CORS_ORIGINS='*' — 모든 출처의 요청을 허용합니다. "
            "운영 배포 시 .env에서 CORS_ORIGINS를 명시적으로 지정하세요."
        )

    return warnings
