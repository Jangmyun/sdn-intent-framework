"""
tests/test_conflict_detector.py — Stage 3 충돌 탐지기 단위 테스트
"""
import sys
from pathlib import Path

import pytest

_BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE))
sys.path.insert(0, str(_BASE / "pipeline"))

from stage3_static.conflict_detector import (
    criteria_overlap,
    get_action_key,
    get_criteria_dict,
    ip_is_subset,
    ip_overlaps,
    normalize_hex,
)
from stage3_static.static_validator import validate


# ── 유틸리티 ────────────────────────────────────────────────────────────────────

class TestNormalizeHex:
    def test_leading_zeros(self):
        assert normalize_hex("0x0800") == "0x800"

    def test_already_normalized(self):
        assert normalize_hex("0x800") == "0x800"

    def test_uppercase(self):
        assert normalize_hex("0X800") == "0x800"


class TestIpOverlaps:
    def test_same_host(self):
        assert ip_overlaps("10.0.0.1/32", "10.0.0.1/32")

    def test_host_in_subnet(self):
        assert ip_overlaps("10.0.0.1/32", "10.0.0.0/24")

    def test_non_overlapping(self):
        assert not ip_overlaps("10.0.0.1/32", "10.0.0.2/32")

    def test_different_subnets(self):
        assert not ip_overlaps("192.168.0.0/24", "10.0.0.0/24")


class TestIpIsSubset:
    def test_host_in_subnet(self):
        assert ip_is_subset("10.0.0.1/32", "10.0.0.0/24")

    def test_same_subnet(self):
        assert ip_is_subset("10.0.0.0/24", "10.0.0.0/24")

    def test_not_subset(self):
        assert not ip_is_subset("10.0.0.0/24", "10.0.0.1/32")


class TestGetActionKey:
    def test_noaction_is_drop(self):
        flow = {"treatment": {"instructions": [{"type": "NOACTION"}]}}
        assert get_action_key(flow) == "DROP"

    def test_no_treatment_is_drop(self):
        assert get_action_key({}) == "DROP"

    def test_output_not_drop(self):
        flow = {"treatment": {"instructions": [{"type": "OUTPUT", "port": "3"}]}}
        assert get_action_key(flow) != "DROP"


# ── validate() 통합 테스트 ────────────────────────────────────────────────────────

def _make_flowrule(device="of:0000000000000001", priority=50000,
                   src=None, dst=None, action="DROP") -> dict:
    criteria = [{"type": "ETH_TYPE", "ethType": "0x800"}]
    if src:
        criteria.append({"type": "IPV4_SRC", "ip": src})
    if dst:
        criteria.append({"type": "IPV4_DST", "ip": dst})

    if action == "DROP":
        treatment = {"instructions": [{"type": "NOACTION"}]}
    else:
        treatment = {"instructions": [{"type": "OUTPUT", "port": str(action)}]}

    return {
        "intent_action": "block" if action == "DROP" else "forward",
        "flows": [{
            "priority": priority,
            "timeout": 0,
            "isPermanent": "true",
            "deviceId": device,
            "selector": {"criteria": criteria},
            "treatment": treatment,
        }],
    }


class TestValidateSchema:
    def test_valid_block_passes(self):
        fr = _make_flowrule(src="10.0.0.1/32", dst="10.0.0.2/32")
        result = validate(fr, existing_flows=None)
        assert result.schema_errors == []

    def test_missing_flows_key_fails(self):
        result = validate({}, existing_flows=None)
        assert not result.passed
        assert result.schema_errors

    def test_empty_flows_list_fails(self):
        result = validate({"flows": []}, existing_flows=None)
        assert not result.passed


class TestConflictDetection:
    def test_no_conflict_different_devices(self):
        new_fr = _make_flowrule(device="of:0000000000000001",
                                 src="10.0.0.1/32", dst="10.0.0.2/32")
        existing = _make_flowrule(device="of:0000000000000002",
                                   src="10.0.0.1/32", dst="10.0.0.2/32")["flows"]
        result = validate(new_fr, existing_flows=existing)
        assert result.conflicts == []

    def test_shadowing_detected(self):
        # 기존 고우선순위 DROP 룰이 새 low-priority FORWARD를 완전히 덮음
        new_fr = _make_flowrule(priority=32768, src="10.0.0.1/32",
                                 dst="10.0.0.2/32", action=3)
        existing_flow = _make_flowrule(priority=50000, src="10.0.0.1/32",
                                        dst="10.0.0.2/32", action="DROP")["flows"]
        result = validate(new_fr, existing_flows=existing_flow)
        conflict_types = {c.get("conflict_type") for c in result.conflicts}
        assert "Shadowing" in conflict_types

    def test_redundancy_is_warning_not_conflict(self):
        # Redundancy = 동일 match + 동일 action → 무해하므로 경고로만 처리 (REJECT 사유 아님)
        fr = _make_flowrule(priority=50000, src="10.0.0.1/32",
                             dst="10.0.0.2/32", action="DROP")
        existing = _make_flowrule(priority=50000, src="10.0.0.1/32",
                                   dst="10.0.0.2/32", action="DROP")["flows"]
        result = validate(fr, existing_flows=existing)
        # Redundancy는 warnings에 기록, conflicts는 비어 있어야 함
        assert result.conflicts == []
        assert any("Redundancy" in w for w in result.warnings)

    def test_no_conflict_when_no_existing(self):
        fr = _make_flowrule(src="10.0.0.1/32", dst="10.0.0.2/32")
        result = validate(fr, existing_flows=None)
        assert result.conflicts == []

    def test_passed_false_on_schema_error(self):
        result = validate({"flows": []}, existing_flows=None)
        assert not result.passed
