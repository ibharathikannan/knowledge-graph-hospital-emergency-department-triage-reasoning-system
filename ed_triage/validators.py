"""
Validator Chain: runs after resolve() to sanity-check a Decision before
it's shown to a clinician.
"""
from __future__ import annotations
from dataclasses import dataclass
from ed_triage.knowledge_graph import disposition_of


@dataclass
class CheckResult:
    name: str
    passed: bool
    reason: str


def check_missing_explanation(g, decision) -> CheckResult:
    if decision.disposition is None:
        return CheckResult("missing_explanation", False, "No rule fired -- nothing to explain.")
    for rule_id in decision.winning_rules:
        description = g.nodes[rule_id].get("description", "")
        if not description:
            return CheckResult("missing_explanation", False, f"{rule_id} has no description.")
    return CheckResult("missing_explanation", True, "Every winning rule has a description.")


def check_rule_inconsistency(decision) -> CheckResult:
    if decision.has_conflict:
        return CheckResult(
            "rule_inconsistency",
            False,
            f"Unresolved rule conflict: {decision.unresolved_conflicts}",
        )
    return CheckResult("rule_inconsistency", True, "No unresolved rule conflicts.")


def check_conflicting_reasons(g, decision) -> CheckResult:
    if decision.disposition is None:
        return CheckResult("conflicting_reasons", True, "No decision to check.")
    for rule_id in decision.winning_rules:
        cited = disposition_of(g, rule_id)
        if cited != decision.disposition:
            return CheckResult(
                "conflicting_reasons",
                False,
                f"{rule_id} recommends {cited}, not {decision.disposition}.",
            )
    return CheckResult("conflicting_reasons", True, "Every cited rule agrees with the decision.")


RESOURCE_FOR_DISPOSITION = {
    "ImmediateTreatment": "ICU",
    "DoctorReview": "Ward",
    "HomeCare": None,
}


def check_resource_validation(decision, bed_state: dict) -> CheckResult:
    if decision.disposition is None:
        return CheckResult("resource_validation", True, "No decision to check.")
    resource = RESOURCE_FOR_DISPOSITION.get(decision.disposition)
    if resource is None:
        return CheckResult("resource_validation", True, f"{decision.disposition} needs no bed.")
    available = bed_state.get(resource, 0)
    if available <= 0:
        return CheckResult("resource_validation", False, f"No {resource} beds available.")
    return CheckResult("resource_validation", True, f"{resource} bed available ({available} free).")


def run_all(g, decision, bed_state: dict) -> list[CheckResult]:
    return [
        check_missing_explanation(g, decision),
        check_rule_inconsistency(decision),
        check_conflicting_reasons(g, decision),
        check_resource_validation(decision, bed_state),
    ]