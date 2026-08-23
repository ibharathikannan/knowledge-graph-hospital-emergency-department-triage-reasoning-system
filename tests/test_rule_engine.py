import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ed_triage.knowledge_graph import build_graph, rule_ids, overrides
from ed_triage.rule_engine import Decision, fire, resolve, static_inconsistencies
from ed_triage.validators import (
    check_conflicting_reasons,
    check_missing_explanation,
    check_resource_validation,
    check_rule_inconsistency,
    run_all,
)

PATIENTS = {
    "P001": {"severity": 0.94, "spo2": 96, "age": 58},
    "P002": {"severity": 0.18, "spo2": 98, "age": 45},
    "P007": {"severity": 0.43, "spo2": 90, "age": 52},
    "P010": {"severity": 0.15, "spo2": 97, "age": 82},
}


def test_build_graph_loads_five_rules_by_default():
    g = build_graph()
    assert len(rule_ids(g)) == 5


def test_deliberate_gap_has_no_override_edge():
    g = build_graph()
    assert not overrides(g, "R4_elderly_min_review", "R2_low_severity")
    assert not overrides(g, "R2_low_severity", "R4_elderly_min_review")


def test_high_severity_immediate():
    g = build_graph()
    decision = resolve(g, fire(g, PATIENTS["P001"]))
    assert decision.disposition == "ImmediateTreatment"
    assert not decision.has_conflict


def test_low_severity_home_care():
    g = build_graph()
    decision = resolve(g, fire(g, PATIENTS["P002"]))
    assert decision.disposition == "HomeCare"
    assert not decision.has_conflict


def test_low_oxygen_overrides_mid_severity():
    g = build_graph()
    decision = resolve(g, fire(g, PATIENTS["P007"]))
    assert decision.disposition == "ImmediateTreatment"
    assert decision.winning_rules == ["R3_low_oxygen"]
    assert not decision.has_conflict


def test_unresolved_conflict_falls_back_conservatively():
    g = build_graph()
    decision = resolve(g, fire(g, PATIENTS["P010"]))
    assert decision.disposition == "DoctorReview"  # more urgent of the two
    assert decision.has_conflict
    assert ("R2_low_severity", "R4_elderly_min_review") in decision.unresolved_conflicts


def test_no_data_no_fire():
    g = build_graph()
    decision = resolve(g, fire(g, {}))
    assert decision.disposition is None
    assert decision.fired_rules == []


def test_static_inconsistency_found():
    g = build_graph()
    issues = static_inconsistencies(g)
    pairs = [(a, b) for a, b, _, _ in issues]
    assert ("R2_low_severity", "R4_elderly_min_review") in pairs
    assert len(issues) == 1  # everything else is resolved by an override edge   

def test_missing_explanation_passes_for_a_normal_decision():
    g = build_graph()
    decision = resolve(g, fire(g, PATIENTS["P001"]))
    assert check_missing_explanation(g, decision).passed


def test_missing_explanation_fails_when_nothing_fired():
    g = build_graph()
    decision = resolve(g, fire(g, {}))
    assert not check_missing_explanation(g, decision).passed


def test_rule_inconsistency_check_mirrors_decision_conflict():
    g = build_graph()
    ok_decision = resolve(g, fire(g, PATIENTS["P007"]))
    conflicted_decision = resolve(g, fire(g, PATIENTS["P010"]))
    assert check_rule_inconsistency(ok_decision).passed
    assert not check_rule_inconsistency(conflicted_decision).passed


def test_conflicting_reasons_passes_normally():
    g = build_graph()
    decision = resolve(g, fire(g, PATIENTS["P001"]))
    assert check_conflicting_reasons(g, decision).passed


def test_conflicting_reasons_catches_a_corrupted_decision():
    g = build_graph()
    bad_decision = Decision(
        disposition="HomeCare",
        fired_rules=["R1_high_severity"],
        winning_rules=["R1_high_severity"],
    )
    assert not check_conflicting_reasons(g, bad_decision).passed


def test_resource_validation_passes_when_bed_available():
    g = build_graph()
    decision = resolve(g, fire(g, PATIENTS["P001"]))
    assert check_resource_validation(decision, {"ICU": 2, "Ward": 5}).passed


def test_resource_validation_fails_when_no_beds():
    g = build_graph()
    decision = resolve(g, fire(g, PATIENTS["P001"]))
    assert not check_resource_validation(decision, {"ICU": 0, "Ward": 5}).passed


def test_resource_validation_home_care_needs_no_bed():
    g = build_graph()
    decision = resolve(g, fire(g, PATIENTS["P002"]))  # HomeCare
    assert check_resource_validation(decision, {"ICU": 0, "Ward": 0}).passed


def test_run_all_reports_four_checks():
    g = build_graph()
    decision = resolve(g, fire(g, PATIENTS["P001"]))
    results = run_all(g, decision, {"ICU": 2, "Ward": 5})
    assert len(results) == 4
    assert all(r.passed for r in results)     