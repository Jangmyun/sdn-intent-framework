"""
FastAPI backend for XAI-SDN Pipeline
실행: uvicorn api:app --reload --port 8000
     (endTOend/ 디렉토리에서 실행)
"""
from __future__ import annotations

import asyncio
import json
import queue as std_queue
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# Windows 콘솔(cp949 등)에서 파이프라인 곳곳의 한글/이모지 print()가
# UnicodeEncodeError로 죽는 것을 방지 (uvicorn은 main.py와 달리 stdout을
# 재설정하지 않음 — 예: "—", "✓/✗" 문자가 포함된 로그에서 실제로 발생했었음).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

_BASE_DIR = Path(__file__).resolve().parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))
if str(_BASE_DIR / 'pipeline') not in sys.path:
    sys.path.insert(0, str(_BASE_DIR / 'pipeline'))

import config

app = FastAPI(title="XAI-SDN Pipeline API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Key 인증 ──────────────────────────────────────────────────────────────
# API_KEY가 설정된 경우에만 X-API-Key 헤더를 요구한다.
# 빈 문자열이면 인증 없이 허용 (개발 모드).
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _require_api_key(key: str | None = Security(_api_key_header)) -> None:
    if config.API_KEY and key != config.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing X-API-Key header")


# 서버 시작 시 설정 경고 출력
for _warn in config.validate_config():
    print(f"[config] WARNING: {_warn}")


_INTENT_MAX_LEN = 1000  # 프롬프트 인젝션 및 과도한 입력 방지


class RunRequest(BaseModel):
    intent: str
    model: str = config.LLM_MODEL
    rag_k: int = 3
    no_rag: bool = False
    skip_twin: bool = False
    skip_deploy: bool = False
    preloaded_flows: list = []        # UI "Load State"로 불러온 기존 FlowRule
    topology_id: str = ""             # 현재 선택된 토폴로지 ID (flow state 저장 키)

    def validate_intent(self) -> str | None:
        """입력 검증. 오류 메시지 반환, 정상이면 None."""
        stripped = self.intent.strip()
        if not stripped:
            return "인텐트가 비어 있습니다."
        if len(stripped) > _INTENT_MAX_LEN:
            return f"인텐트가 너무 깁니다 ({len(stripped)}자). 최대 {_INTENT_MAX_LEN}자."
        return None


# ── SSE helper ────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


# ── Repair Loop helper ────────────────────────────────────────────────────────

from repair_utils import MAX_REPAIR_ATTEMPTS, build_repair_feedback as _build_repair_feedback


# ── Pipeline runner (synchronous, called in thread) ───────────────────────────

def _run_pipeline(req: RunRequest, q: std_queue.Queue) -> None:
    # 빈 인텐트 조기 거부
    if err := req.validate_intent():
        q.put(_sse({"type": "error", "stage": 0, "error": err}))
        q.put(_sse({"type": "done"}))
        return

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result: dict = {
        "run_id": run_id,
        "intent": req.intent,
        "model": req.model,
        "rag_k": req.rag_k,
        "timestamp": run_id,
    }
    client = None

    def emit(data: dict) -> None:
        q.put(_sse(data))

    def progress(n: int, msg: str) -> None:
        emit({"type": "progress", "stage": n, "msg": msg})

    def start(n: int, name: str) -> float:
        emit({"type": "stage", "stage": n, "status": "running", "name": name})
        return time.time()

    def done(n: int, res: dict, t0: float) -> None:
        emit({"type": "stage", "stage": n, "status": "done",
              "result": res, "elapsed": round(time.time() - t0, 2)})

    def error(n: int, err: str) -> None:
        emit({"type": "stage", "stage": n, "status": "error", "error": err})

    def finish(decision: str, reason: str | None = None, deploy_failed: bool = False) -> None:
        result["decision"] = decision
        (config.LOGS_DIR / f"{run_id}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        # 조기 REJECT(예외/거부) 경로는 stage5가 채워지지 않으므로, 프론트 배너가
        # 빈 사유로 뜨지 않도록 reason을 최소한의 decision_reason으로 대체한다.
        report = result.get("stage5") or {}
        if not report and reason:
            report = {"decision_reason": reason}
        emit({"type": "decision", "decision": decision,
              "report": report, "deploy_failed": deploy_failed})
        emit({"type": "done", "run_id": run_id})

    # ── Stage 1: Intent Parsing ───────────────────────────────────────────────
    t = start(1, "Intent Parsing")
    try:
        from stage1_intent.llm_client import LLMClient
        from stage1_intent.intent_parser import IntentParser
        from stage1_intent.rag import build_index

        progress(1, f"LLM 클라이언트 초기화 중... (모델: {req.model})")
        client = LLMClient(model=req.model)

        rag_index = rag_texts = rag_outputs = None
        if not req.no_rag and config.DATASET_PATH.exists() and req.rag_k > 0:
            try:
                progress(1, f"RAG 인덱스 구축 중... (유사 예시 k={req.rag_k})")
                rag_index, rag_texts, rag_outputs = build_index(
                    config.DATASET_PATH, client
                )
                progress(1, f"RAG 완료 — {len(rag_texts) if rag_texts else 0}개 예시 임베딩됨")
            except (ImportError, RuntimeError) as rag_exc:
                progress(1, f"RAG 스킵 (의존성 누락: {str(rag_exc)[:80]})")
            except ValueError as rag_exc:
                progress(1, f"RAG 스킵 (데이터셋 형식 오류: {str(rag_exc)[:80]})")
            except Exception as rag_exc:
                progress(1, f"RAG 스킵 (임베딩 오류: {str(rag_exc)[:80]})")
        elif req.no_rag:
            progress(1, "RAG 비활성화 — LLM 직접 호출")
        else:
            progress(1, "데이터셋 없음 — RAG 스킵")

        from models.topology import NetworkTopology
        custom_topo = _load_custom_topology()
        if custom_topo:
            topology = NetworkTopology.from_custom_file(custom_topo)
            progress(1, "토폴로지: 커스텀 파일 로드")
        else:
            try:
                from stage4_twin.onos_client import OnosClient
                topology = NetworkTopology.from_onos(OnosClient())
                progress(1, "토폴로지: ONOS 실시간 조회")
            except Exception:
                topology = NetworkTopology.diamond()
                progress(1, "토폴로지: 정적 다이아몬드 (ONOS 연결 없음)")
        parser_obj = IntentParser(
            client=client,
            rag_index=rag_index,
            rag_texts=rag_texts,
            rag_outputs=rag_outputs,
            k=req.rag_k,
            topology=topology,
        )
    except Exception as exc:
        error(1, str(exc))
        finish("REJECT", reason=f"Stage1 초기화 실패: {exc}")
        return

    # ── Repair Loop: Stage 1 → 2 → 3 (최대 MAX_REPAIR_ATTEMPTS 재시도) ─────────
    from stage2_flowrule.compiler import compile_flowrule, compile_compound
    from stage3_static.static_validator import validate as static_validate

    repair_feedback: str | None = None
    flowrule = ir = compound = static_result = None

    for repair_iter in range(MAX_REPAIR_ATTEMPTS + 1):
        is_retry = repair_iter > 0

        # Stage 1 ──────────────────────────────────────────────────────────────
        if is_retry:
            progress(1, f"[Repair {repair_iter}/{MAX_REPAIR_ATTEMPTS}] LLM 재호출 중...")
            emit({"type": "stage", "stage": 1, "status": "running",
                  "name": f"Intent Parsing (Repair {repair_iter})"})
        else:
            progress(1, "인텐트 파싱 중... (LLM 호출)")

        try:
            prediction = parser_obj.parse(req.intent, repair_feedback=repair_feedback)
        except Exception as exc:
            error(1, str(exc))
            finish("REJECT", reason=f"인텐트 파싱 실패: {exc}")
            return

        if prediction.status == "rejected":
            reason = prediction.rejection_reason or "unknown"
            detail = prediction.rejection_detail or ""
            progress(1, f"인텐트 거부 [{reason}]: {detail}")
            result["stage1"] = {"status": "rejected", "rejection_reason": reason,
                                "rejection_detail": detail}
            error(1, f"[{reason}] {detail}")
            finish("REJECT", reason=f"[{reason}] {detail}")
            return

        if prediction.compound:
            compound = prediction.compound
            n = len(compound.rules)
            progress(1, f"복합 인텐트 파싱 완료 → {n}개 룰: "
                        + ", ".join(f"rule[{i}]={r.action}" for i, r in enumerate(compound.rules)))
            result["stage1"] = compound.to_dict()
            ir = None
        else:
            ir = prediction.program
            progress(1, f"파싱 완료 → action={ir.action}, device={ir.device_hint}"
                        + (f", src={ir.src_ip}" if ir.src_ip else "")
                        + (f", dst={ir.dst_ip}" if ir.dst_ip else ""))
            result["stage1"] = ir.to_dict()
            compound = None

        if not is_retry:
            done(1, result["stage1"], t)

        # Stage 2 ──────────────────────────────────────────────────────────────
        t2 = start(2, "FlowRule Compile") if not is_retry else time.time()
        if is_retry:
            emit({"type": "stage", "stage": 2, "status": "running", "name": "FlowRule Compile"})

        try:
            if compound:
                progress(2, f"복합 인텐트 컴파일 중... ({len(compound.rules)}개 sub-rule)")
                flowrule = compile_compound(compound)
                flows = flowrule.get("flows", [])
                progress(2, f"컴파일 완료 → 총 {len(flows)}개 FlowRule 생성")
            else:
                progress(2, f"device_hint 변환 중... ({ir.device_hint!r} → ONOS device ID)")
                progress(2, f"OpenFlow criteria 생성 중... (action={ir.action})")
                flowrule = compile_flowrule(ir)
                flows = flowrule.get("flows", [])
                f0 = flows[0] if flows else {}
                criteria_n = len(f0.get("selector", {}).get("criteria", []))
                priority = f0.get("priority", "?")
                device_id = f0.get("deviceId", "?")
                progress(2, f"컴파일 완료 → deviceId={device_id}, priority={priority}, criteria={criteria_n}개")
            result["stage2"] = flowrule
            done(2, flowrule, t2)
        except Exception as exc:
            error(2, str(exc))
            finish("REJECT", reason=f"FlowRule 컴파일 실패: {exc}")
            return

        # Stage 3 ──────────────────────────────────────────────────────────────
        t3 = start(3, "Static Validation") if not is_retry else time.time()
        if is_retry:
            emit({"type": "stage", "stage": 3, "status": "running", "name": "Static Validation"})

        try:
            if repair_iter == 0:
                # ONOS 기존 플로우 조회는 첫 번째 시도에서만
                progress(3, "ONOS 기존 플로우 조회 중...")
                existing = None
                try:
                    from stage4_twin.onos_client import OnosClient
                    existing = OnosClient().flows()
                    progress(3, f"기존 플로우 {len(existing) if existing else 0}개 수신")
                except Exception:
                    existing = None
                    progress(3, "ONOS 연결 실패 — 충돌 탐지 없이 스키마만 검증")

            progress(3, "스키마 검증 중... (ONOS FlowRule 형식 확인)")
            progress(3, "충돌 탐지 중... (Shadowing / Correlation / Imbrication)")
            static_result = static_validate(flowrule, existing_flows=existing)
            r3 = {
                "passed": static_result.passed,
                "schema_errors": static_result.schema_errors,
                "conflicts": static_result.conflicts,
                "warnings": static_result.warnings,
                "summary": static_result.summary(),
                "repair_attempts": repair_iter,
            }
            if static_result.warnings:
                for w in static_result.warnings:
                    progress(3, f"⚠ 경고: {w[:100]}")
            if static_result.conflicts:
                for c in static_result.conflicts:
                    progress(3, f"✗ 충돌: [{c.get('conflict_type')}] {c.get('reason','')[:80]}")
            progress(3, f"검증 결과: {'PASS' if static_result.passed else 'FAIL'}")
            result["stage3"] = r3
            done(3, r3, t3)
        except Exception as exc:
            error(3, str(exc))
            finish("REJECT", reason=f"정적 검증 중 오류: {exc}")
            return

        if static_result.passed:
            break

        # 최대 재시도 초과
        if repair_iter >= MAX_REPAIR_ATTEMPTS:
            progress(3, f"[Repair] {MAX_REPAIR_ATTEMPTS}회 재시도 후에도 검증 실패 — REJECT")
            error(3, f"정적 검증 실패 (repair {MAX_REPAIR_ATTEMPTS}회 소진): {static_result.summary()}")
            finish("REJECT", reason=f"정적 검증 실패 (repair {MAX_REPAIR_ATTEMPTS}회 소진): {static_result.summary()}")
            return

        repair_feedback = _build_repair_feedback(static_result, repair_iter + 1, MAX_REPAIR_ATTEMPTS)
        progress(3, f"[Repair {repair_iter + 1}/{MAX_REPAIR_ATTEMPTS}] 피드백 생성 완료 — LLM 재시도")


    # ── Stage 4: Digital Twin ─────────────────────────────────────────────────
    t = start(4, "Digital Twin")
    live_session = _get_live_session()
    # status가 "running"일 때만 세션 net을 재사용한다 — "starting"/"stopping"은
    # net 객체가 기동/종료 중이라 불안정할 수 있어 그대로 스킵한다("error"는 이미
    # _cleanup_best_effort()로 net이 정리된 뒤라 일반 Digital Twin을 그대로 진행해도
    # 안전하다).
    live_net = live_session.net if live_session.status == "running" else None
    live_custom_data = live_session.topo_data if live_net is not None else None

    if live_session.status in ("starting", "stopping"):
        progress(
            4,
            f"네트워크 프리셋 세션이 {live_session.status} 중 — 네트워크가 아직 안정적이지 "
            f"않아 Digital Twin을 생략합니다",
        )
        from stage4_twin.twin_verifier import TwinResult
        twin_result = TwinResult(
            status="skipped",
            reason=f"라이브 세션 {live_session.status} 중 — Digital Twin 생략",
        )
    elif req.skip_twin:
        progress(4, "Skip Digital Twin 옵션 활성화 — 건너뜀")
        from stage4_twin.twin_verifier import TwinResult
        twin_result = TwinResult(status="skipped", reason="skip_twin option")
    else:
        try:
            from stage4_twin.twin_verifier import TwinVerifier, TwinResult
            progress(4, "플랫폼 환경 확인 중... (Linux + root + Mininet 필요)")
            verifier = TwinVerifier()
            # 플랫폼 체크 결과 미리 확인
            skip_reason = verifier._check_platform()
            if skip_reason:
                progress(4, f"환경 조건 미충족 — {skip_reason}")
            else:
                if live_net is not None:
                    progress(
                        4,
                        f"네트워크 프리셋 라이브 세션(topology={live_session.topology_id}) 위에서 "
                        f"검증합니다 — 별도 Mininet 기동 없이 지금 보고 있는 그 네트워크를 그대로 씁니다",
                    )
                # 테스트 내용 사전 안내 (복합 인텐트는 sub_rules 순회)
                _is_compound = flowrule.get("intent_action") == "compound"
                _sub_rules   = flowrule.get("sub_rules", []) if _is_compound else [flowrule]

                def _emit_twin_info(sr):
                    _flows = sr.get("flows", [])
                    _flow  = _flows[0] if _flows else {}
                    _crit  = _flow.get("selector", {}).get("criteria", [])
                    _instr = _flow.get("treatment", {}).get("instructions", [])
                    _src   = next((c.get("ip","").split("/")[0] for c in _crit if c["type"]=="IPV4_SRC"), None)
                    _dst   = next((c.get("ip","").split("/")[0] for c in _crit if c["type"]=="IPV4_DST"), None)
                    _act   = sr.get("intent_action") or ("forward" if any(i.get("type")=="OUTPUT" for i in _instr) else "block")
                    _pnum  = next((c.get("protocol") for c in _crit if c["type"]=="IP_PROTO"), None)
                    _proto = {6:"TCP", 17:"UDP", 1:"ICMP"}.get(_pnum, "") if _pnum else ""
                    _port  = next((c.get("tcpPort") or c.get("udpPort") for c in _crit if c["type"] in ("TCP_DST","UDP_DST")), None)
                    _tdesc = f"{_src or '*'} → {_dst or '*'}"
                    if _proto: _tdesc += f"  [{_proto}"
                    if _port:  _tdesc += f"/{_port}"
                    if _proto: _tdesc += "]"
                    progress(4, f"테스트 트래픽: {_tdesc}")
                    progress(4, f"기대 동작: {'차단 (BLOCK)' if _act == 'block' else '전달 (FORWARD)'}")
                    emit({"type": "twin_info",
                          "test": _tdesc,
                          "action": _act,
                          "src_ip": _src or "",
                          "dst_ip": _dst or "",
                          "device_id": _flows[0].get("deviceId", "") if _flows else ""})

                progress(4, "─" * 36)
                for sr in _sub_rules:
                    _emit_twin_info(sr)
                progress(4, "─" * 36)

            twin_result = verifier.verify(
                flowrule,
                progress_cb=lambda msg: progress(4, msg),
                emit_cb=emit,
                preloaded_flows=req.preloaded_flows,
                external_net=live_net,
                external_custom_data=live_custom_data,
            )
            if twin_result.checks:
                progress(4, "─" * 36)
                for chk, ok in twin_result.checks.items():
                    progress(4, f"{'✓' if ok else '✗'} {chk}: {'통과' if ok else '실패'}")
        except Exception as exc:
            from stage4_twin.twin_verifier import TwinResult
            twin_result = TwinResult(status="error", reason=str(exc))
            progress(4, f"오류 발생: {str(exc)[:100]}")

    r4 = {
        "status": twin_result.status,
        "reason": twin_result.reason,
        "checks": twin_result.checks,
        "evidence": twin_result.evidence,
        "summary": twin_result.summary(),
    }
    result["stage4"] = r4
    s4_status = "skipped" if twin_result.status == "skipped" else "done"
    emit({"type": "stage", "stage": 4, "status": s4_status,
          "result": r4, "elapsed": round(time.time() - t, 2)})

    # ── Stage 5: XAI Explanation ──────────────────────────────────────────────
    t = start(5, "XAI Explanation")
    try:
        from stage5_xai.explainer import XAIExplainer

        progress(5, "각 단계 결과 종합 중...")
        progress(5, f"정적 검증: {'PASS' if static_result.passed else 'FAIL'} | "
                    f"Digital Twin: {twin_result.status}")
        progress(5, "최종 판정 계산 중...")
        progress(5, f"XAI 판정 근거 생성 중... (LLM 호출: {req.model})")
        xai = XAIExplainer(client=client).explain(
            intent=req.intent,
            ir=ir,
            flowrule=flowrule,
            static_result=static_result,
            twin_result=twin_result,
            compound=compound,
        )
        r5 = xai.to_dict()
        decision = xai.decision
        progress(5, f"최종 결정: {decision}")
        result["stage5"] = r5
        done(5, r5, t)
    except Exception as exc:
        error(5, str(exc))
        finish("REJECT", reason=f"XAI 설명 생성 실패: {exc}")
        return

    # ── Stage 6: ONOS Deploy ──────────────────────────────────────────────────
    t = start(6, "ONOS Deploy")
    deploy_failed = False
    if decision in ("APPROVE", "APPROVE_WITHOUT_TWIN") and not req.skip_deploy:
        try:
            from stage6_deploy.deployer import Deployer
            import flow_state_manager

            progress(6, "배포 전 ONOS 플로우 스냅샷 수집 중...")
            progress(6, f"FlowRule POST → {config.ONOS_URL}/flows")
            dep = Deployer().deploy(flowrule)
            r6 = {"success": dep.success, "flow_ids": dep.flow_ids, "error": dep.error}
            if dep.success:
                progress(6, f"배포 완료 — 신규 flow ID: {dep.flow_ids}")
                # 배포 성공 시 flow state 캐시에 저장
                if req.topology_id:
                    try:
                        new_flows = flowrule.get("flows", [])
                        if new_flows:
                            topo_hash = None
                            if req.topology_id == "custom":
                                custom = _load_custom_topology()
                                if custom:
                                    topo_hash = flow_state_manager.compute_topo_hash(custom)
                            flow_state_manager.save_flows(
                                topology_id=req.topology_id,
                                new_flows=new_flows,
                                intent_summary=req.intent[:80],
                                topo_hash=topo_hash,
                            )
                            progress(6, f"Flow state 저장 완료 ({req.topology_id}, {len(new_flows)}개 rule)")
                    except Exception as fs_exc:
                        progress(6, f"Flow state 저장 실패 (무시): {fs_exc}")
            else:
                progress(6, f"배포 실패: {dep.error}")
                deploy_failed = True
            done(6, r6, t)
        except Exception as exc:
            r6 = {"success": False, "error": str(exc)}
            error(6, str(exc))
            deploy_failed = True
    elif req.skip_deploy:
        progress(6, "Skip ONOS Deploy 옵션 활성화 — 건너뜀")
        r6 = {"status": "skipped", "reason": "skip_deploy option"}
        emit({"type": "stage", "stage": 6, "status": "skipped",
              "result": r6, "elapsed": 0})
    else:
        progress(6, f"decision={decision} — 배포 조건 미충족, 건너뜀")
        r6 = {"status": "skipped", "reason": f"decision={decision}"}
        emit({"type": "stage", "stage": 6, "status": "skipped",
              "result": r6, "elapsed": 0})
    result["stage6"] = r6

    finish(decision, deploy_failed=deploy_failed)


# ── API Routes ────────────────────────────────────────────────────────────────

@app.post("/api/run", dependencies=[Depends(_require_api_key)])
async def run_pipeline(req: RunRequest):
    q: std_queue.Queue = std_queue.Queue()

    async def stream():
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, _run_pipeline, req, q)
        while True:
            try:
                msg = q.get_nowait()
                yield msg
                if '"type": "done"' in msg:
                    break
            except std_queue.Empty:
                if fut.done():
                    # Thread finished — drain any remaining events
                    while True:
                        try:
                            msg = q.get_nowait()
                            yield msg
                            if '"type": "done"' in msg:
                                await fut
                                return
                        except std_queue.Empty:
                            break
                    # Thread ended without emitting "done" — emit error + done
                    try:
                        await fut
                    except Exception as exc:
                        yield _sse({"type": "error", "stage": 0,
                                    "error": f"파이프라인 스레드 오류: {exc}"})
                    yield _sse({"type": "done"})
                    return
                await asyncio.sleep(0.05)
                yield ": keepalive\n\n"
        await fut

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/topology")
def get_topology():
    try:
        from stage4_twin.onos_client import OnosClient

        c = OnosClient(timeout=2.0)  # short timeout — UI polls every second
        devices = c.devices() or []

        # Fall back to custom topology when no device has an active OpenFlow connection.
        # netcfg-pushed devices appear in the list but have available=False because
        # Mininet is not running.  Only available=True devices represent a real topology.
        available = [d for d in devices if d.get("available", False)]
        if not available:
            custom = _load_custom_topology()
            if custom:
                return _custom_topo_as_d3(custom)

        # Build label/position maps from custom topology so ONOS live data keeps
        # correct labels AND stable ids — e.g. of:0000000000000005 → "S5" (not
        # sequential "S1"). Hosts especially need this: ONOS's own host id is
        # "<mac>/<vlan>", completely different from the custom topology's "h1"
        # used while ONOS has no live devices yet (static fallback below). If we
        # don't remap back to "h1", the frontend's position cache (keyed by id)
        # misses on every transition between static↔live and hosts visibly jump
        # to new positions — looking like an entirely different topology.
        sw_label_map: dict[str, str] = {}     # ONOS device ID → switch label
        sw_pos_map: dict[str, tuple] = {}      # ONOS device ID → (x, y)
        host_id_by_ip: dict[str, str] = {}     # host IP → stable custom host id
        host_id_by_mac: dict[str, str] = {}    # host MAC(lower) → stable custom host id
        host_label_by_id: dict[str, str] = {}  # stable custom host id → label
        host_pos_by_id: dict[str, tuple] = {}  # stable custom host id → (x, y)
        _custom = _load_custom_topology()
        if _custom:
            for _sw in _custom.get("switches", []):
                _dpid = _sw.get("dpid", "0" * 16)
                _sw_dev_id = f"of:{_dpid}"
                sw_label_map[_sw_dev_id] = _sw.get("label", _sw["id"])
                if _sw.get("x") is not None and _sw.get("y") is not None:
                    sw_pos_map[_sw_dev_id] = (_sw["x"], _sw["y"])
            for _h in _custom.get("hosts", []):
                _hid = _h["id"]
                host_label_by_id[_hid] = _h.get("label", _hid)
                if _h.get("ip"):
                    host_id_by_ip[_h["ip"]] = _hid
                if _h.get("mac"):
                    host_id_by_mac[_h["mac"].lower()] = _hid
                if _h.get("x") is not None and _h.get("y") is not None:
                    host_pos_by_id[_hid] = (_h["x"], _h["y"])

        def _sw_label(dev_id: str) -> str:
            """Custom topology label → else extract number from DPID hex."""
            if dev_id in sw_label_map:
                return sw_label_map[dev_id]
            try:
                n = int(dev_id.split(":")[-1], 16)
                return f"S{n}"
            except Exception:
                return dev_id[-4:] if len(dev_id) > 4 else dev_id

        def _resolve_host_id(h: dict) -> str:
            """ONOS host id(mac/vlan)를 커스텀 토폴로지의 안정적인 id(h1 등)로
            역매핑한다. IP 학습 전에도 MAC은 즉시 알려지므로 MAC도 함께 시도.
            매칭 안 되면(커스텀 토폴로지 밖 호스트) ONOS 원본 id 그대로 사용."""
            ip = (h.get("ipAddresses") or [""])[0]
            if ip in host_id_by_ip:
                return host_id_by_ip[ip]
            mac = (h.get("mac") or "").lower()
            if mac in host_id_by_mac:
                return host_id_by_mac[mac]
            return h["id"]

        def _host_label(stable_id: str, h: dict) -> str:
            if stable_id in host_label_by_id:
                return host_label_by_id[stable_id]
            ip = (h.get("ipAddresses") or [""])[0]
            try:
                return f"H{int(ip.split('.')[-1])}"
            except Exception:
                return h.get("id", "H?")

        hosts_data = c.hosts() or []
        links_data = c.links() or []
        flows_data = c.flows() or []

        # Map device → action types from its flow rules
        dev_actions: dict[str, set] = {}
        for f in flows_data:
            did = f.get("deviceId", "")
            for inst in f.get("treatment", {}).get("instructions", []):
                dev_actions.setdefault(did, set()).add(inst.get("type", ""))

        def dev_state(did: str, avail: bool) -> str:
            if not avail:
                return "offline"
            acts = dev_actions.get(did, set())
            if "NOACTION" in acts:
                return "drop"
            if "OUTPUT" in acts:
                return "forward"
            return "idle"

        nodes = []
        for d in devices:
            node = {
                "id": d["id"],
                "label": _sw_label(d["id"]),
                "type": "switch",
                "state": dev_state(d["id"], d.get("available", False)),
            }
            pos = sw_pos_map.get(d["id"])
            if pos:
                node["x"], node["y"] = pos
            nodes.append(node)
        dev_label = {n["id"]: n["label"] for n in nodes}

        host_nodes = []
        seen_host_ids: set = set()
        for h in hosts_data:
            stable_id = _resolve_host_id(h)
            seen_host_ids.add(stable_id)
            node = {
                "id": stable_id,
                "label": _host_label(stable_id, h),
                "type": "host",
                "ip": (h.get("ipAddresses") or [""])[0],
                "switch": (h.get("locations") or [{}])[0].get("elementId", ""),
            }
            pos = host_pos_by_id.get(stable_id)
            if pos:
                node["x"], node["y"] = pos
            host_nodes.append(node)

        # ONOS의 host discovery는 ARP/미학습 패킷을 관찰해야 동작하는데, Mininet을
        # autoStaticArp=True로 띄우면(build_network_from_custom 기본값) ARP가 아예
        # 발생하지 않아 실제로 트래픽이 흐르고 flow가 잔뜩 깔려 있어도 hosts()가
        # 계속 빈 배열로 남는 경우가 실측 확인됨(네트워크 프리셋 라이브 세션에서
        # 100% 재현). 그래서 ONOS가 못 찾은 호스트도 커스텀 토폴로지에 선언된
        # 정보(고정 ip/mac/x/y)로 보완한다 — 단, 그 호스트가 붙은 스위치가 지금
        # 실제로 available일 때만(=해당 토폴로지가 진짜 라이브일 때만) 추가한다.
        if _custom:
            available_ids = {d["id"] for d in available} if available else {n["id"] for n in nodes}
            _sw_ids_set = {sw["id"] for sw in _custom.get("switches", [])}
            for _h in _custom.get("hosts", []):
                _hid = _h["id"]
                if _hid in seen_host_ids:
                    continue
                _peer_sw_id = next(
                    (l["target"] if l["source"] == _hid else l["source"]
                     for l in _custom.get("links", [])
                     if (l["source"] == _hid or l["target"] == _hid)
                     and (l["target"] if l["source"] == _hid else l["source"]) in _sw_ids_set),
                    None,
                )
                if _peer_sw_id is None:
                    continue
                _peer_sw = next((sw for sw in _custom.get("switches", []) if sw["id"] == _peer_sw_id), None)
                if _peer_sw is None:
                    continue
                _peer_dev_id = f"of:{_peer_sw.get('dpid', '0' * 16)}"
                if _peer_dev_id not in available_ids:
                    continue  # 이 호스트의 스위치가 지금 라이브가 아니면 표시 안 함
                node = {
                    "id": _hid,
                    "label": _h.get("label", _hid),
                    "type": "host",
                    "ip": _h.get("ip", ""),
                    "switch": _peer_dev_id,
                }
                if _h.get("x") is not None and _h.get("y") is not None:
                    node["x"], node["y"] = _h["x"], _h["y"]
                host_nodes.append(node)

        seen: set = set()
        links = []
        for lnk in links_data:
            src = lnk.get("src", {}).get("device", "")
            dst = lnk.get("dst", {}).get("device", "")
            k = tuple(sorted([src, dst]))
            if k not in seen:
                seen.add(k)
                links.append({"source": src, "target": dst})
        for h in host_nodes:
            if h["switch"]:
                links.append({"source": h["id"], "target": h["switch"]})

        # Flow table (first 20 rules)
        flow_table = []
        for f in flows_data[:20]:
            did = f.get("deviceId", "")
            criteria = f.get("selector", {}).get("criteria", [])
            match_parts = []
            for c in criteria[:2]:
                val = c.get("ip") or c.get("port") or c.get("mac") or c.get("ethType") or ""
                if val:
                    match_parts.append(f"{c.get('type', '?')}={val}")
            instructions = f.get("treatment", {}).get("instructions", [])
            is_drop = not instructions or all(
                i.get("type") in ("NOACTION", "DROP") for i in instructions
            )
            flow_table.append({
                "device": dev_label.get(did, did[-4:] if len(did) > 4 else did),
                "priority": f.get("priority", 0),
                "match": ", ".join(match_parts) or "—",
                "action": "DROP" if is_drop else "FORWARD",
            })

        return {
            "nodes": nodes + host_nodes,
            "links": links,
            "flow_table": flow_table,
            "rule_count": len(flows_data),
            "error": None,
        }
    except Exception as exc:
        # ONOS offline — try custom topology
        custom = _load_custom_topology()
        if custom:
            return _custom_topo_as_d3(custom)
        return {"nodes": [], "links": [], "flow_table": [], "rule_count": 0, "error": str(exc)}


# ── Custom topology endpoints ─────────────────────────────────────────────────

_CUSTOM_TOPO_PATH = _BASE_DIR / "data" / "custom_topology.json"


def _load_custom_topology() -> dict | None:
    if _CUSTOM_TOPO_PATH.exists():
        try:
            return json.loads(_CUSTOM_TOPO_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _custom_topo_as_d3(data: dict) -> dict:
    """Convert custom topology JSON → D3-compatible response."""
    sw_map: dict[str, str] = {}  # simple_id → of:dpid
    for sw in data.get("switches", []):
        dpid = sw.get("dpid", "0" * 16)
        sw_map[sw["id"]] = f"of:{dpid}"

    nodes = [
        {"id": sw_map[sw["id"]], "label": sw.get("label", sw["id"]),
         "type": "switch", "state": "idle",
         "x": sw.get("x"), "y": sw.get("y")}
        for sw in data.get("switches", [])
    ]
    for h in data.get("hosts", []):
        sw_id = next(
            (sw_map.get(l["target"]) if l["source"] == h["id"] else sw_map.get(l["source"])
             for l in data.get("links", [])
             if l["source"] == h["id"] or l["target"] == h["id"]),
            "",
        )
        nodes.append({
            "id": h["id"], "label": h.get("label", h["id"]),
            "type": "host", "ip": h.get("ip", ""), "switch": sw_id or "",
            "x": h.get("x"), "y": h.get("y"),
        })

    seen: set = set()
    links = []
    for lnk in data.get("links", []):
        src_d3 = sw_map.get(lnk["source"], lnk["source"])
        tgt_d3 = sw_map.get(lnk["target"], lnk["target"])
        k = tuple(sorted([src_d3, tgt_d3]))
        if k not in seen:
            seen.add(k)
            links.append({"source": src_d3, "target": tgt_d3, "bw": lnk.get("bw")})

    return {"nodes": nodes, "links": links, "flow_table": [], "rule_count": 0,
            "_source": "custom"}


@app.get("/api/topology/custom")
def get_custom_topology():
    data = _load_custom_topology()
    return data if data else {}


@app.post("/api/topology/custom", dependencies=[Depends(_require_api_key)])
async def save_custom_topology(request: Request):
    body = await request.json()
    _CUSTOM_TOPO_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CUSTOM_TOPO_PATH.write_text(
        json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {"ok": True}


def _build_netcfg(data: dict) -> dict:
    """
    custom_topology.json → ONOS Network Configuration 형식 변환.

    ONOS netcfg 구조:
      devices/<device-uri>/basic: { name, latitude, longitude, ... }
      hosts/<mac>/<vlan>/basic: { name, ipAddresses, locations, ... }
    """
    devices: dict = {}
    for sw in data.get("switches", []):
        dpid = sw.get("dpid", "0" * 16)
        uri = f"of:{dpid}"
        devices[uri] = {
            "basic": {
                "name": sw.get("label", sw["id"]),
                "driver": "ovs",
                "managementAddress": "127.0.0.1",
            }
        }

    # 스위치별 링크 순서로 포트 번호 계산 (Mininet 자동 포트 부여 방식과 동일)
    from collections import defaultdict as _dd
    _sw_ids_set = {sw["id"] for sw in data.get("switches", [])}
    _sw_port_counter: dict = _dd(int)
    _host_port: dict = {}  # (host_id, sw_simple_id) → port_number
    for _lnk in data.get("links", []):
        _src, _tgt = _lnk["source"], _lnk["target"]
        if _src in _sw_ids_set:
            _sw_port_counter[_src] += 1
            if _tgt not in _sw_ids_set:
                _host_port[(_tgt, _src)] = _sw_port_counter[_src]
        if _tgt in _sw_ids_set:
            _sw_port_counter[_tgt] += 1
            if _src not in _sw_ids_set:
                _host_port[(_src, _tgt)] = _sw_port_counter[_tgt]

    hosts_cfg: dict = {}
    for h in data.get("hosts", []):
        mac = h.get("mac", "")
        if not mac:
            continue
        # ONOS host key: <MAC>/<vlan>
        key = f"{mac}/-1"
        # Resolve connected switch
        location = None
        for lnk in data.get("links", []):
            peer = None
            if lnk["source"] == h["id"]:
                peer = lnk["target"]
            elif lnk["target"] == h["id"]:
                peer = lnk["source"]
            if peer:
                peer_sw = next(
                    (sw for sw in data.get("switches", []) if sw["id"] == peer), None
                )
                if peer_sw:
                    dpid = peer_sw.get("dpid", "0" * 16)
                    port = _host_port.get((h["id"], peer_sw["id"]), 1)
                    location = {"elementId": f"of:{dpid}", "port": str(port)}
                    break
        cfg: dict = {"name": h.get("label", h["id"])}
        if h.get("ip"):
            cfg["ipAddresses"] = [h["ip"]]
        if location:
            cfg["locations"] = [location]
        hosts_cfg[key] = {"basic": cfg}

    return {"devices": devices, "hosts": hosts_cfg}


@app.post("/api/topology/apply", dependencies=[Depends(_require_api_key)])
async def apply_topology_to_onos(request: Request):
    """
    저장된 커스텀 토폴로지를 ONOS netcfg API로 푸시한다.
    ONOS가 오프라인이면 오류를 반환하되, 저장된 파일은 유지한다.
    """
    # Save first (if body provided), else use existing file
    try:
        body = await request.json()
    except Exception:
        body = None

    if body:
        _CUSTOM_TOPO_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CUSTOM_TOPO_PATH.write_text(
            json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        data = body
    else:
        data = _load_custom_topology()
        if not data:
            return {"ok": False, "error": "저장된 커스텀 토폴로지가 없습니다."}

    netcfg = _build_netcfg(data)
    try:
        from stage4_twin.onos_client import OnosClient
        OnosClient().push_netcfg(netcfg)
        return {
            "ok": True,
            "pushed": {
                "devices": len(netcfg.get("devices", {})),
                "hosts": len(netcfg.get("hosts", {})),
            },
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Network Preset (Live Session) 엔드포인트 ─────────────────────────────────
# LIVE_NETWORK_PRESET_PLAN.md 6-3장. 단일 세션만 지원 — 두 번째 apply는 409.

_TRAFFIC_PRESETS_DIR = _BASE_DIR / "data" / "traffic_presets"
_live_session = None  # 지연 생성 (LiveNetworkSession import에 stage4_twin 체인이 딸려옴)


def _get_live_session():
    global _live_session
    if _live_session is None:
        from stage4_twin.live_session import LiveNetworkSession
        _live_session = LiveNetworkSession()
    return _live_session


def _load_traffic_preset(topology_id: str, traffic_preset_id: str) -> dict | None:
    path = _TRAFFIC_PRESETS_DIR / f"{topology_id}_{traffic_preset_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


@app.get("/api/traffic-presets")
def list_traffic_presets():
    """토폴로지별 사용 가능한 트래픽 프리셋 목록 (data/traffic_presets/*.json 스캔).

    반환되는 "id"는 apply 요청의 traffic_preset_id로 그대로 쓸 수 있는 접미사
    (파일명에서 "{topology_id}_" 접두사를 뺀 부분)다.
    """
    presets = []
    for f in sorted(_TRAFFIC_PRESETS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        topo_id = data.get("topology_id", "")
        full_id = data.get("id", f.stem)
        prefix = f"{topo_id}_"
        suffix = full_id[len(prefix):] if topo_id and full_id.startswith(prefix) else full_id
        presets.append({
            "id": suffix,
            "topology_id": topo_id,
            "label": data.get("label", full_id),
            "flow_count": len(data.get("flows", [])),
        })
    return presets


class NetworkPresetApplyRequest(BaseModel):
    topology_id: str
    traffic_preset_id: str = ""  # 비어있으면 배경 트래픽 없이 토폴로지만 기동


@app.post("/api/network-preset/apply", dependencies=[Depends(_require_api_key)])
async def apply_network_preset(req: NetworkPresetApplyRequest):
    session = _get_live_session()
    if session.is_active():
        raise HTTPException(status_code=409, detail="이미 실행 중인 네트워크 프리셋 세션이 있습니다.")

    from stage4_twin.topology import diamond_topology_data

    is_diamond = req.topology_id == "diamond"
    topo_data = diamond_topology_data() if is_diamond else _load_custom_topology()
    if topo_data is None:
        raise HTTPException(
            status_code=400,
            detail="토폴로지를 찾을 수 없습니다 (커스텀 토폴로지를 먼저 저장/적용하세요).",
        )

    traffic_preset = None
    if req.traffic_preset_id:
        traffic_preset = _load_traffic_preset(req.topology_id, req.traffic_preset_id)
        if traffic_preset is None:
            raise HTTPException(
                status_code=404,
                detail=f"트래픽 프리셋을 찾을 수 없습니다: {req.topology_id}_{req.traffic_preset_id}",
            )

    def _run() -> None:
        try:
            session.start(req.topology_id, topo_data, traffic_preset)
        except Exception as exc:
            print(f"[network-preset] 세션 시작 실패: {exc}")

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse(status_code=202, content={"ok": True, "status": "starting"})


@app.get("/api/network-preset/stream")
async def stream_network_preset():
    session = _get_live_session()

    async def stream():
        while True:
            snap = session.snapshot()
            yield _sse({"type": "link_stats", **snap})
            if snap["status"] not in ("starting", "running", "stopping"):
                break
            await asyncio.sleep(1.0)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/network-preset/stop", dependencies=[Depends(_require_api_key)])
async def stop_network_preset():
    session = _get_live_session()
    if session.status == "idle":
        return {"ok": True, "status": "idle"}
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, session.stop)
    return {"ok": True, "status": session.status}


@app.get("/api/network-preset/status")
def get_network_preset_status():
    return _get_live_session().snapshot()


# ── Flow State 엔드포인트 ─────────────────────────────────────────────────────

@app.get("/api/flow-state")
def get_all_flow_states():
    """모든 토폴로지의 저장된 state 목록 반환."""
    import flow_state_manager
    return flow_state_manager.list_states()


@app.get("/api/flow-state/{topology_id}")
def get_flow_state(topology_id: str):
    """
    특정 토폴로지의 저장된 FlowRule 목록 + ONOS Live와의 sync_status 반환.
    """
    import flow_state_manager
    state = flow_state_manager.get_state_detail(topology_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"'{topology_id}' 저장된 state 없음")

    cached_flows = state.get("flows", [])

    # ONOS Live와의 sync_status 계산 (ONOS 오프라인이면 skip)
    sync_status = {"in_cache_not_onos": 0, "in_onos_not_cache": 0, "matched": 0, "onos_available": False}
    try:
        from stage4_twin.onos_client import OnosClient
        onos_flows = OnosClient(timeout=2.0).flows() or []

        def _flow_key(f: dict) -> str:
            criteria = sorted(
                [f"{c.get('type')}={c.get('ip') or c.get('mac') or c.get('port') or ''}"
                 for c in f.get("selector", {}).get("criteria", [])],
            )
            return f"{f.get('deviceId')}|{f.get('priority')}|{','.join(criteria)}"

        onos_keys = {_flow_key(f) for f in onos_flows}
        cache_keys = {_flow_key(f) for f in cached_flows}

        sync_status = {
            "in_cache_not_onos": len(cache_keys - onos_keys),
            "in_onos_not_cache": len(onos_keys - cache_keys),
            "matched": len(cache_keys & onos_keys),
            "onos_available": True,
        }
    except Exception:
        pass

    return {**state, "sync_status": sync_status}


@app.delete("/api/flow-state/{topology_id}", dependencies=[Depends(_require_api_key)])
def clear_flow_state(topology_id: str):
    """특정 토폴로지의 state 전체 초기화."""
    import flow_state_manager
    deleted = flow_state_manager.clear_state(topology_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"'{topology_id}' 저장된 state 없음")
    return {"ok": True, "topology_id": topology_id}


@app.delete("/api/flow-state/{topology_id}/flows/{flow_index}", dependencies=[Depends(_require_api_key)])
def delete_flow_state_entry(topology_id: str, flow_index: int):
    """
    특정 flow(인덱스)를 state에서 제거.
    ONOS에 해당 flow가 있으면 동시 삭제 시도.
    """
    import flow_state_manager
    removed = flow_state_manager.remove_flow(topology_id, flow_index)
    if removed is None:
        raise HTTPException(status_code=404, detail=f"flow_index={flow_index} 없음")

    # ONOS에서도 삭제 시도 (실패해도 state 삭제는 유지)
    onos_deleted = False
    try:
        from stage4_twin.onos_client import OnosClient
        client = OnosClient(timeout=3.0)
        device_id = removed.get("deviceId", "")
        priority = removed.get("priority")
        if device_id and priority is not None:
            client.delete_flows_by_priority(priority, device_id=device_id)
            onos_deleted = True
    except Exception:
        pass

    return {"ok": True, "removed": removed, "onos_deleted": onos_deleted}


@app.get("/api/logs")
def get_logs():
    entries = []
    for f in sorted(config.LOGS_DIR.glob("*.json"), reverse=True)[:10]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            entries.append({
                "run_id": d.get("run_id", ""),
                "intent": d.get("intent", ""),
                "decision": d.get("decision", ""),
                "timestamp": d.get("timestamp", ""),
            })
        except Exception:
            continue
    return entries


@app.delete("/api/logs", dependencies=[Depends(_require_api_key)])
def clear_logs():
    """로그 파일 전체 삭제 (히스토리 초기화)"""
    deleted = 0
    for f in config.LOGS_DIR.glob("*.json"):
        try:
            f.unlink()
            deleted += 1
        except Exception:
            pass
    return {"ok": True, "deleted": deleted}


# ── Static files (must be last) ───────────────────────────────────────────────
_static = _BASE_DIR / "static"
_static.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
