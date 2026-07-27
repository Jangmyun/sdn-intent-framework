from __future__ import annotations

import pytest

from safe_intent_sdn.e2_evaluation import E2Case, E2Result, score_treatment, validate_results
from safe_intent_sdn.intent_ir import IntentProgram
from safe_intent_sdn.validator import ValidationFinding


def _finding() -> ValidationFinding:
    return ValidationFinding(category="reference", code="unknown_host", rule_indices=[0], message="x")


def _program() -> IntentProgram:
    return IntentProgram.model_validate(
        {
            "rules": [
                {
                    "intent_type": "forwarding",
                    "action": "forward",
                    "selector": {},
                    "enforcement": {"device": "s1", "egress_port": 1},
                }
            ]
        }
    )


def case(id_: str, *, defect: bool = False) -> E2Case:
    return E2Case(
        id=id_,
        category="reference" if defect else "clean",
        expected_findings=["reference"] if defect else [],
        expected_codes=["unknown_host"] if defect else [],
        program=_program(),
    )


def accepted(case_id: str, treatment: str = "B1") -> E2Result:
    return E2Result(case_id=case_id, treatment=treatment, outcome="accepted", duration_ms=0.1)


def rejected(case_id: str, treatment: str = "B1", *, stage: str = "compiler") -> E2Result:
    return E2Result(
        case_id=case_id, treatment=treatment, outcome="rejected",
        rejection_stage=stage, error="boom", duration_ms=0.1,
    )


def test_validate_results_accepts_complete_matching_log():
    cases = [case("a"), case("b")]
    results = [accepted("a"), accepted("b")]
    assert validate_results(cases, results) == results


def test_validate_results_rejects_missing_case():
    cases = [case("a"), case("b")]
    results = [accepted("a")]
    with pytest.raises(ValueError, match="missing"):
        validate_results(cases, results)


def test_validate_results_rejects_extra_result():
    cases = [case("a")]
    results = [accepted("a"), accepted("b")]
    with pytest.raises(ValueError, match="extra"):
        validate_results(cases, results)


def test_validate_results_rejects_duplicate_result_case_id():
    cases = [case("a")]
    results = [accepted("a"), accepted("a")]
    with pytest.raises(ValueError, match="duplicate case_id"):
        validate_results(cases, results)


def test_validate_results_rejects_duplicate_dataset_case_id():
    cases = [case("a"), case("a")]
    results = [accepted("a")]
    with pytest.raises(ValueError, match="duplicate case id"):
        validate_results(cases, results)


def test_validate_results_rejects_mixed_treatments_in_one_log():
    cases = [case("a"), case("b")]
    results = [accepted("a", treatment="B1"), accepted("b", treatment="B2")]
    with pytest.raises(ValueError, match="mixes treatments"):
        validate_results(cases, results)


def test_validate_results_rejects_accepted_result_carrying_rejection_metadata():
    cases = [case("a")]
    bad = E2Result(case_id="a", treatment="B1", outcome="accepted", rejection_stage="compiler", duration_ms=0.1)
    with pytest.raises(ValueError, match="rejection metadata"):
        validate_results(cases, [bad])


def test_validate_results_rejects_rejected_result_missing_stage():
    cases = [case("a")]
    bad = E2Result(case_id="a", treatment="B1", outcome="rejected", duration_ms=0.1)
    with pytest.raises(ValueError, match="missing rejection_stage"):
        validate_results(cases, [bad])


def test_validate_results_rejects_validator_stage_outside_b2():
    cases = [case("a", defect=True)]
    bad = E2Result(
        case_id="a", treatment="B1", outcome="rejected", rejection_stage="validator",
        findings=[_finding()], duration_ms=0.1,
    )
    with pytest.raises(ValueError, match="only B2 can reject"):
        validate_results(cases, [bad])


def test_validate_results_rejects_validator_rejection_with_no_findings():
    """A rejected+"validator" result with no findings could otherwise inflate
    any_defect recall from outcome alone, with nothing supporting the rejection."""
    cases = [case("a", defect=True)]
    bad = E2Result(case_id="a", treatment="B2", outcome="rejected", rejection_stage="validator", duration_ms=0.1)
    with pytest.raises(ValueError, match="must carry at least one finding"):
        validate_results(cases, [bad])


def test_validate_results_rejects_validator_rejection_with_compiler_error():
    cases = [case("a", defect=True)]
    bad = E2Result(
        case_id="a", treatment="B2", outcome="rejected", rejection_stage="validator",
        findings=[_finding()], error="compiler blew up", duration_ms=0.1,
    )
    with pytest.raises(ValueError, match="must not carry a compiler error"):
        validate_results(cases, [bad])


def test_validate_results_rejects_compiler_rejection_with_no_error():
    cases = [case("a", defect=True)]
    bad = E2Result(case_id="a", treatment="B1", outcome="rejected", rejection_stage="compiler", duration_ms=0.1)
    with pytest.raises(ValueError, match="must carry a non-empty error message"):
        validate_results(cases, [bad])


def test_validate_results_rejects_compiler_rejection_with_findings():
    cases = [case("a", defect=True)]
    bad = E2Result(
        case_id="a", treatment="B1", outcome="rejected", rejection_stage="compiler",
        findings=[_finding()], error="boom", duration_ms=0.1,
    )
    with pytest.raises(ValueError, match="must not carry categorized findings"):
        validate_results(cases, [bad])


def test_score_treatment_counts_confusion_matrix_correctly():
    cases = [case("clean-1"), case("defect-1", defect=True)]
    results = [accepted("clean-1"), rejected("defect-1")]
    report = score_treatment(cases, results)
    assert report["any_defect"] == {"tp": 1, "fp": 0, "fn": 0, "tn": 1, "precision": 1.0, "recall": 1.0}
    assert report["defect_positive_total"] == 1
    assert report["true_negative_total"] == 1
    assert report["rejected_count"] == 1


def test_score_treatment_raises_on_incomplete_log_instead_of_understating_defects():
    cases = [case("clean-1"), case("defect-1", defect=True)]
    results = [accepted("clean-1")]  # defect-1's result is missing entirely
    with pytest.raises(ValueError, match="missing"):
        score_treatment(cases, results)


def test_e2case_accepts_path_category():
    value = E2Case(
        id="path-1", category="path", expected_findings=["path"], expected_codes=["path_unknown_waypoint"],
        program=_program(),
    )
    assert value.category == "path"


def test_by_category_includes_path_without_a_second_hardcoded_edit():
    cases = [case("clean-1"), E2Case(
        id="path-1", category="path", expected_findings=["path"], expected_codes=["path_unknown_waypoint"],
        program=_program(),
    )]
    results = [
        accepted("clean-1", treatment="B2"),
        E2Result(
            case_id="path-1", treatment="B2", outcome="rejected", rejection_stage="validator",
            findings=[ValidationFinding(category="path", code="path_unknown_waypoint", rule_indices=[0], message="x")],
            duration_ms=0.1,
        ),
    ]
    report = score_treatment(cases, results)
    assert report["by_category"]["path"] == {"tp": 1, "fp": 0, "fn": 0, "tn": 1, "precision": 1.0, "recall": 1.0}
