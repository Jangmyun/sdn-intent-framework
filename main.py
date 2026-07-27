"""
End-to-End XAI SDN Pipeline

자연어 인텐트를 받아 LLM/RAG 기반 파싱 → FlowRule 컴파일 → 정적 검증
→ Digital Twin 검증 → XAI 설명 → ONOS 배포까지 전 과정을 수행한다.

사용법:
    python main.py --intent "block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1"
    python main.py --intent "..." --model gemini-3.1-flash-lite --skip-twin
    python main.py --intent "..." --rag-k 5 --verbose
    python main.py --intent "..." --skip-twin --skip-deploy
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))
if str(_BASE_DIR / 'pipeline') not in sys.path:
    sys.path.insert(0, str(_BASE_DIR / 'pipeline'))

import config


def _print_header(run_id: str, intent: str) -> None:
    print("=" * 60)
    print(f"  XAI SDN Pipeline  run_id={run_id}")
    print(f'  Intent: "{intent}"')
    print("=" * 60)


def _print_stage(n: int, title: str, content: str = "") -> None:
    print(f"\n[Stage {n}] {title}")
    if content:
        for line in content.strip().split("\n"):
            print(f"  {line}")


def _print_footer(decision: str, log_path: Path) -> None:
    print()
    print("=" * 60)
    print(f"  최종 결정: {decision}")
    print(f"  결과 저장: {log_path.relative_to(_BASE_DIR)}")
    print("=" * 60)


from repair_utils import MAX_REPAIR_ATTEMPTS, build_repair_feedback as _build_repair_feedback


def main() -> int:
    parser = argparse.ArgumentParser(
        description="End-to-End XAI SDN Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--intent", required=True, help="처리할 네트워크 인텐트")
    parser.add_argument(
        "--model",
        default=None,
        help=f"LLM 모델 이름 (기본: {config.LLM_MODEL})",
    )
    parser.add_argument("--rag-k", type=int, default=3, help="RAG 유사 예시 수 (기본: 3)")
    parser.add_argument("--no-rag", action="store_true", help="RAG 인덱스 구축 스킵 (LLM 직접 호출)")
    parser.add_argument("--skip-twin", action="store_true", help="Digital Twin 검증 스킵")
    parser.add_argument("--skip-deploy", action="store_true", help="ONOS 실제 배포 스킵")
    parser.add_argument("--verbose", action="store_true", help="상세 출력")
    args = parser.parse_args()

    intent: str = args.intent.strip()
    if not intent:
        print("오류: 인텐트가 비어 있습니다.")
        return 3
    model: str = args.model or config.LLM_MODEL
    rag_k: int = args.rag_k
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    _print_header(run_id, intent)

    # 파이프라인 전체 결과 (로그 저장용)
    pipeline_result: dict = {
        "run_id": run_id,
        "intent": intent,
        "model": model,
        "rag_k": rag_k,
        "timestamp": run_id,
    }

    # ── Stage 1: LLM/RAG → IntentIR ───────────────────────────
    _print_stage(1, "인텐트 해석 (LLM/RAG)")

    try:
        from stage1_intent.llm_client import LLMClient
        from stage1_intent.intent_parser import IntentParser
        from stage1_intent.rag import build_index

        client = LLMClient(model=model)

        # RAG 인덱스 구축
        rag_index = rag_texts = rag_outputs = None
        if not args.no_rag and config.DATASET_PATH.exists() and rag_k > 0:
            try:
                print("  RAG 인덱스 구축 중...")
                rag_index, rag_texts, rag_outputs = build_index(config.DATASET_PATH, client)
            except (ImportError, RuntimeError) as exc:
                print(f"  RAG 스킵 (의존성 누락: {exc})")
            except ValueError as exc:
                print(f"  RAG 스킵 (데이터셋 형식 오류: {exc})")
            except Exception as exc:
                print(f"  RAG 스킵 (임베딩 오류: {exc})")
        elif args.no_rag:
            print("  RAG 스킵 (--no-rag 플래그)")

        # 토폴로지 그라운딩 — 커스텀 파일 우선, ONOS 폴백, 정적 다이아몬드 최종 폴백
        import json as _json
        from models.topology import NetworkTopology
        _custom_topo_path = _BASE_DIR / "data" / "custom_topology.json"
        if _custom_topo_path.exists():
            topology = NetworkTopology.from_custom_file(
                _json.loads(_custom_topo_path.read_text(encoding="utf-8"))
            )
            print("  토폴로지: 커스텀 파일 로드")
        else:
            try:
                from stage4_twin.onos_client import OnosClient
                topology = NetworkTopology.from_onos(OnosClient())
                print("  토폴로지: ONOS 실시간 조회")
            except Exception:
                topology = NetworkTopology.diamond()
                print("  토폴로지: 정적 다이아몬드 (ONOS 연결 없음)")

        parser_obj = IntentParser(
            client=client,
            rag_index=rag_index,
            rag_texts=rag_texts,
            rag_outputs=rag_outputs,
            k=rag_k,
            topology=topology,
        )
    except Exception as exc:
        print(f"  오류: {exc}")
        pipeline_result["stage1"] = {"error": str(exc)}
        _save_log(run_id, pipeline_result)
        print(f"\n파이프라인 오류로 중단. 결과: logs/{run_id}.json")
        return 3

    # ── Repair Loop: Stage 1 → 2 → 3 ─────────────────────────
    from stage2_flowrule.compiler import compile_flowrule
    from stage3_static.static_validator import validate as static_validate

    repair_feedback: str | None = None
    flowrule = ir = compound = static_result = None
    existing_flows: list | None = None

    # ONOS 기존 플로우 조회 (첫 번째 시도에서만)
    try:
        from stage4_twin.onos_client import OnosClient
        existing_flows = OnosClient().flows()
    except Exception as _onos_exc:
        if args.verbose:
            print(f"  ONOS 기존 플로우 조회 실패 (충돌 탐지 스킵): {_onos_exc}")

    for repair_iter in range(MAX_REPAIR_ATTEMPTS + 1):
        is_retry = repair_iter > 0
        if is_retry:
            _print_stage(1, f"인텐트 해석 (Repair {repair_iter}/{MAX_REPAIR_ATTEMPTS})")

        # Stage 1
        try:
            prediction = parser_obj.parse(intent, repair_feedback=repair_feedback)
        except Exception as exc:
            print(f"  오류: {exc}")
            pipeline_result["stage1"] = {"error": str(exc)}
            _save_log(run_id, pipeline_result)
            return 3

        if prediction.status == "rejected":
            reason = prediction.rejection_reason or "unknown"
            detail = prediction.rejection_detail or ""
            print(f"  거부: [{reason}] {detail}")
            pipeline_result["stage1"] = {
                "status": "rejected",
                "rejection_reason": reason,
                "rejection_detail": detail,
            }
            pipeline_result["decision"] = "REJECT"
            log_path = _save_log(run_id, pipeline_result)
            _print_footer("REJECT", log_path)
            return 2

        if prediction.compound:
            compound = prediction.compound
            ir = None
            n = len(compound.rules)
            print(f"  복합 인텐트 → {n}개 룰: "
                  + ", ".join(f"rule[{i}]={r.action}" for i, r in enumerate(compound.rules)))
            pipeline_result["stage1"] = compound.to_dict()
        else:
            ir = prediction.program
            compound = None
            stage1_content = (
                f"action={ir.action} | src={ir.src_ip or '-'} | dst={ir.dst_ip or '-'} "
                f"| device={ir.device_hint}"
            )
            if ir.ip_proto:
                stage1_content += f" | proto={ir.ip_proto}"
            if ir.dst_port:
                stage1_content += f" | dport={ir.dst_port}"
            print(f"  {stage1_content}")
            pipeline_result["stage1"] = ir.to_dict()

        # Stage 2
        if is_retry:
            _print_stage(2, "FlowRule 컴파일")
        else:
            _print_stage(2, "FlowRule 컴파일")

        try:
            if compound:
                from stage2_flowrule.compiler import compile_compound
                flowrule = compile_compound(compound)
            else:
                flowrule = compile_flowrule(ir)
        except Exception as exc:
            print(f"  오류: {exc}")
            pipeline_result["stage2"] = {"error": str(exc)}
            _save_log(run_id, pipeline_result)
            return 3

        flows = flowrule.get("flows", [])
        flow = flows[0] if flows else {}
        criteria_count = len(flow.get("selector", {}).get("criteria", []))
        stage2_content = (
            f"deviceId={flow.get('deviceId', '?')} | "
            f"priority={flow.get('priority', '?')} | "
            f"criteria={criteria_count}개"
        )
        if flow.get("treatment"):
            instructions = flow["treatment"].get("instructions", [])
            has_output = any(i.get("type") == "OUTPUT" for i in instructions)
            if has_output:
                stage2_content += f" | instructions={len(instructions)}개"
            else:
                stage2_content += " | action=DROP(차단)"
        else:
            stage2_content += " | action=DROP(차단)"
        print(f"  {stage2_content}")

        if args.verbose:
            print(f"  FlowRule JSON:\n  {json.dumps(flowrule, indent=2, ensure_ascii=False)}")
        pipeline_result["stage2"] = flowrule

        # Stage 3
        _print_stage(3, "정적 검증" + (f" (Repair {repair_iter})" if is_retry else ""))

        try:
            static_result = static_validate(flowrule, existing_flows=existing_flows)
        except Exception as exc:
            print(f"  오류: {exc}")
            pipeline_result["stage3"] = {"error": str(exc)}
            _save_log(run_id, pipeline_result)
            return 3

        stage3_summary = static_result.summary()
        print(f"  {stage3_summary}")
        if args.verbose and static_result.schema_errors:
            for err in static_result.schema_errors:
                print(f"    스키마 오류: {err}")
        if args.verbose and static_result.conflicts:
            for c in static_result.conflicts:
                print(f"    충돌: [{c.get('conflict_type')}] {c.get('reason', '')}")

        pipeline_result["stage3"] = {
            "passed": static_result.passed,
            "schema_errors": static_result.schema_errors,
            "conflicts": static_result.conflicts,
            "warnings": static_result.warnings,
            "summary": stage3_summary,
            "repair_attempts": repair_iter,
        }

        if static_result.passed:
            break

        if repair_iter >= MAX_REPAIR_ATTEMPTS:
            print(f"  [Repair] {MAX_REPAIR_ATTEMPTS}회 재시도 후에도 검증 실패 — REJECT")
            pipeline_result["decision"] = "REJECT"
            log_path = _save_log(run_id, pipeline_result)
            _print_footer("REJECT", log_path)
            return 2

        repair_feedback = _build_repair_feedback(static_result, repair_iter + 1, MAX_REPAIR_ATTEMPTS)
        print(f"  [Repair {repair_iter + 1}/{MAX_REPAIR_ATTEMPTS}] 피드백 생성 — LLM 재시도...")

    # ── Stage 4: Digital Twin 검증 ────────────────────────────
    _print_stage(4, "Digital Twin 검증")

    if args.skip_twin:
        from stage4_twin.twin_verifier import TwinResult
        twin_result = TwinResult(
            status="skipped",
            reason="--skip-twin flag",
        )
        print("  (skipped: --skip-twin 플래그)")
        print("  ⚠ 경고: Digital Twin 검증 없이 진행합니다. "
              "최종 결정은 APPROVE_WITHOUT_TWIN으로 격하될 수 있습니다.")
    else:
        try:
            from stage4_twin.twin_verifier import TwinVerifier
            verifier = TwinVerifier()
            twin_result = verifier.verify(flowrule)
        except Exception as exc:
            from stage4_twin.twin_verifier import TwinResult
            twin_result = TwinResult(status="error", reason=str(exc))
            print(f"  오류: {exc}")

    twin_summary = twin_result.summary()
    print(f"  {twin_summary}")
    if args.verbose and twin_result.checks:
        for check, ok in twin_result.checks.items():
            status_str = "OK" if ok else "FAIL"
            print(f"    [{status_str}] {check}")

    pipeline_result["stage4"] = {
        "status": twin_result.status,
        "reason": twin_result.reason,
        "checks": twin_result.checks,
        "evidence": twin_result.evidence,
        "summary": twin_summary,
    }

    # ── Stage 5: XAI 설명 ────────────────────────────────────
    _print_stage(5, "XAI 설명")

    try:
        from stage5_xai.explainer import XAIExplainer
        # LLM은 선택적으로 decision_reason 생성에 사용
        explainer = XAIExplainer(client=client)
        xai_report = explainer.explain(
            intent=intent,
            ir=ir,
            flowrule=flowrule,
            static_result=static_result,
            twin_result=twin_result,
        )
    except Exception as exc:
        print(f"  오류: {exc}")
        pipeline_result["stage5"] = {"error": str(exc)}
        _save_log(run_id, pipeline_result)
        return 3

    # XAI 설명 출력 (들여쓰기 포함)
    xai_text_lines = xai_report.to_text().strip().split("\n")
    for line in xai_text_lines:
        print(f"  {line}")

    pipeline_result["stage5"] = xai_report.to_dict()
    decision = xai_report.decision

    # ── Stage 6: ONOS 배포 ───────────────────────────────────
    if decision in ("APPROVE", "APPROVE_WITHOUT_TWIN") and not args.skip_deploy:
        _print_stage(6, "ONOS 배포")
        try:
            from stage6_deploy.deployer import Deployer
            deployer = Deployer()
            deploy_result = deployer.deploy(flowrule)
            print(f"  {deploy_result.summary()}")
            pipeline_result["stage6"] = {
                "success": deploy_result.success,
                "flow_ids": deploy_result.flow_ids,
                "error": deploy_result.error,
            }
        except Exception as exc:
            print(f"  배포 오류: {exc}")
            pipeline_result["stage6"] = {"success": False, "error": str(exc)}

    elif decision in ("APPROVE", "APPROVE_WITHOUT_TWIN") and args.skip_deploy:
        _print_stage(6, "ONOS 배포")
        print("  (skipped: --skip-deploy 플래그)")
        pipeline_result["stage6"] = {"status": "skipped", "reason": "--skip-deploy 플래그"}

    else:
        # REJECT: 배포 안 함
        pipeline_result["stage6"] = {
            "status": "skipped",
            "reason": f"REJECT 판정으로 배포 안 함",
        }

    # ── 결과 저장 ────────────────────────────────────────────
    pipeline_result["decision"] = decision
    log_path = _save_log(run_id, pipeline_result)

    # ── 최종 출력 ────────────────────────────────────────────
    _print_footer(decision, log_path)

    # 배포가 실제로 시도됐는데 실패했으면 승인 판정과 무관하게 이를 반영한다
    # (그렇지 않으면 exit code만 보는 자동화 스크립트가 배포 실패를 성공으로 오인함)
    stage6 = pipeline_result.get("stage6", {})
    deploy_failed = (
        stage6.get("status") != "skipped"
        and "success" in stage6
        and stage6["success"] is False
    )

    # 종료 코드 (0=APPROVE, 1=APPROVE_WITHOUT_TWIN, 2=REJECT, 3=ERROR(파이프라인 중단), 4=DEPLOY_FAILED)
    if deploy_failed:
        return 4
    elif decision == "APPROVE":
        return 0
    elif decision == "APPROVE_WITHOUT_TWIN":
        return 1
    else:
        return 2


def _save_log(run_id: str, result: dict) -> Path:
    """파이프라인 결과를 logs/{run_id}.json 에 저장"""
    log_path = config.LOGS_DIR / f"{run_id}.json"
    log_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return log_path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
