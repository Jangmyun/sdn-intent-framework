"""
tests/test_compiler.py — Stage 2 FlowRule 컴파일러 단위 테스트
"""
import sys
from pathlib import Path

import pytest

_BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE))
sys.path.insert(0, str(_BASE / "pipeline"))

from models.intent_ir import IntentEnforcement, IntentIR, IntentRouting, IntentSelector, EndpointRef
from stage2_flowrule.compiler import CompileError, compile_flowrule, extract_device_id


# ── 헬퍼 ───────────────────────────────────────────────────────────────────────

def _ir(action: str, device: str = "switch 1", **kw) -> IntentIR:
    """테스트용 IntentIR 빠른 생성 헬퍼"""
    enforcement = IntentEnforcement(
        device=device,
        egress_port=kw.pop("out_port", None),
        alt_egress_port=kw.pop("alt_out_port", None),
    )
    selector = IntentSelector(
        source=EndpointRef(ip=kw.pop("src_ip", None)),
        destination=EndpointRef(ip=kw.pop("dst_ip", None)),
        protocol=kw.pop("ip_proto", None),
        dst_port=kw.pop("dst_port", None),
    )
    routing_kw = {k: kw.pop(k) for k in ("waypoints",) if k in kw}
    routing = IntentRouting(**routing_kw) if routing_kw else None
    return IntentIR(action=action, enforcement=enforcement, selector=selector,
                    routing=routing, **kw)


# ── extract_device_id ───────────────────────────────────────────────────────────

class TestExtractDeviceId:
    def test_switch_n(self):
        assert extract_device_id("switch 4") == "of:0000000000000004"

    def test_s_shorthand(self):
        assert extract_device_id("s2") == "of:0000000000000002"

    def test_sw_shorthand(self):
        assert extract_device_id("sw3") == "of:0000000000000003"

    def test_node_keyword(self):
        assert extract_device_id("node 5") == "of:0000000000000005"

    def test_onos_id_passthrough(self):
        assert extract_device_id("of:0000000000000001") == "of:0000000000000001"

    def test_onos_id_case_insensitive(self):
        assert extract_device_id("of:000000000000000A") == "of:000000000000000a"

    def test_ordinal_second(self):
        assert extract_device_id("switch second") == "of:0000000000000002"

    def test_ordinal_third(self):
        assert extract_device_id("third node") == "of:0000000000000003"

    def test_bare_digit_fallback(self):
        assert extract_device_id("4") == "of:0000000000000004"

    def test_specific_pattern_wins_over_bare_digit(self):
        # "switches 10 and 2" — switch 키워드 뒤 10이 첫 번째 추출되어야 함
        assert extract_device_id("switches 10 and 2") == "of:000000000000000a"

    def test_switch_with_large_number(self):
        assert extract_device_id("switch 14") == "of:000000000000000e"

    def test_unknown_raises(self):
        with pytest.raises(CompileError):
            extract_device_id("firewall-primary")


# ── block ───────────────────────────────────────────────────────────────────────

class TestCompileBlock:
    def test_intent_action(self):
        assert compile_flowrule(_ir("block"))["intent_action"] == "block"

    def test_single_flow(self):
        assert len(compile_flowrule(_ir("block"))["flows"]) == 1

    def test_noaction_instruction(self):
        result = compile_flowrule(_ir("block"))
        instr = result["flows"][0]["treatment"]["instructions"]
        assert any(i["type"] == "NOACTION" for i in instr)

    def test_default_priority(self):
        assert compile_flowrule(_ir("block"))["flows"][0]["priority"] == 50000

    def test_custom_priority(self):
        ir = _ir("block", priority=60000)
        assert compile_flowrule(ir)["flows"][0]["priority"] == 60000

    def test_src_dst_criteria(self):
        ir = _ir("block", src_ip="10.0.0.1", dst_ip="10.0.0.2")
        criteria = compile_flowrule(ir)["flows"][0]["selector"]["criteria"]
        types = {c["type"] for c in criteria}
        assert "IPV4_SRC" in types
        assert "IPV4_DST" in types

    def test_eth_type_added_with_ip(self):
        ir = _ir("block", src_ip="10.0.0.1")
        criteria = compile_flowrule(ir)["flows"][0]["selector"]["criteria"]
        types = {c["type"] for c in criteria}
        assert "ETH_TYPE" in types

    def test_device_id_in_flow(self):
        ir = _ir("block", device="switch 3")
        flow = compile_flowrule(ir)["flows"][0]
        assert flow["deviceId"] == "of:0000000000000003"

    def test_is_permanent(self):
        flow = compile_flowrule(_ir("block"))["flows"][0]
        assert flow["isPermanent"] == "true"


# ── forward ─────────────────────────────────────────────────────────────────────

class TestCompileForward:
    def test_intent_action(self):
        assert compile_flowrule(_ir("forward"))["intent_action"] == "forward"

    def test_output_instruction(self):
        ir = _ir("forward", out_port=3)
        instr = compile_flowrule(ir)["flows"][0]["treatment"]["instructions"]
        assert any(i["type"] == "OUTPUT" and i["port"] == "3" for i in instr)

    def test_no_port_uses_normal(self):
        instr = compile_flowrule(_ir("forward"))["flows"][0]["treatment"]["instructions"]
        assert any(i["port"] == "NORMAL" for i in instr)

    def test_default_priority(self):
        assert compile_flowrule(_ir("forward"))["flows"][0]["priority"] == 32768

    def test_proto_tcp_criteria(self):
        ir = _ir("forward", ip_proto="tcp", dst_port=80)
        criteria = compile_flowrule(ir)["flows"][0]["selector"]["criteria"]
        types = {c["type"] for c in criteria}
        assert "IP_PROTO" in types
        assert "TCP_DST" in types


# ── reroute ─────────────────────────────────────────────────────────────────────

class TestCompileReroute:
    def test_intent_action(self):
        assert compile_flowrule(_ir("reroute"))["intent_action"] == "reroute"

    def test_alt_out_port_preferred(self):
        ir = _ir("reroute", out_port=2, alt_out_port=5)
        instr = compile_flowrule(ir)["flows"][0]["treatment"]["instructions"]
        assert any(i["port"] == "5" for i in instr)

    def test_falls_back_to_out_port(self):
        ir = _ir("reroute", out_port=2)
        instr = compile_flowrule(ir)["flows"][0]["treatment"]["instructions"]
        assert any(i["port"] == "2" for i in instr)

    def test_neither_port_uses_normal(self):
        instr = compile_flowrule(_ir("reroute"))["flows"][0]["treatment"]["instructions"]
        assert any(i["port"] == "NORMAL" for i in instr)


# ── sfc ─────────────────────────────────────────────────────────────────────────

class TestCompileSfc:
    def test_requires_alt_out_port(self):
        with pytest.raises(CompileError, match="alt_out_port"):
            compile_flowrule(_ir("sfc", out_port=9))

    def test_generates_two_flows(self):
        ir = _ir("sfc", out_port=9, alt_out_port=3,
                 src_ip="10.0.0.1", dst_ip="10.0.0.2")
        assert len(compile_flowrule(ir)["flows"]) == 2

    def test_egress_priority_higher_than_ingress(self):
        ir = _ir("sfc", out_port=9, alt_out_port=3)
        flows = compile_flowrule(ir)["flows"]
        assert flows[1]["priority"] > flows[0]["priority"]

    def test_intent_action(self):
        ir = _ir("sfc", out_port=9, alt_out_port=3)
        assert compile_flowrule(ir)["intent_action"] == "sfc"

    def test_requires_waypoint_or_out_port(self):
        with pytest.raises(CompileError):
            compile_flowrule(_ir("sfc", alt_out_port=3))  # out_port=None, no waypoints
