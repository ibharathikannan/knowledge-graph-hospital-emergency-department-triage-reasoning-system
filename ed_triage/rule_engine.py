"""
Rule engine: evaluates a patient against the clinical knowledge graph.
"""
from __future__ import annotations

import itertools
import operator
from dataclasses import dataclass, field
from typing import Optional

from ed_triage.knowledge_graph import ACUITY_RANK, conditions_of, disposition_of, overrides, rule_ids

import math

_OPS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
}


def _condition_holds(cond: dict, patient: dict) -> bool:
    value = patient.get(cond["feature"])
    if value is None:
        return False
    return _OPS[cond["op"]](value, cond["value"])


def fire(g, patient: dict) -> list[str]:
    """Rules whose conditions ALL hold (AND) for this patient."""
    fired = []
    for rule_id in rule_ids(g):
        conds = conditions_of(g, rule_id)
        if conds and all(_condition_holds(c, patient) for c in conds):
            fired.append(rule_id)
    return fired


@dataclass
class Decision:
    disposition: Optional[str]
    fired_rules: list
    winning_rules: list
    unresolved_conflicts: list = field(default_factory=list)

    @property
    def has_conflict(self) -> bool:
        return bool(self.unresolved_conflicts)


def resolve(g, fired_rules: list[str]) -> Decision:
    """Combine fired rules into one decision, applying override edges and
    falling back to the most conservative (most urgent) disposition for
    anything left unresolved -- never a silent guess."""
    if not fired_rules:
        return Decision(disposition=None, fired_rules=[], winning_rules=[])

    groups: dict[str, list[str]] = {}
    for rid in fired_rules:
        groups.setdefault(disposition_of(g, rid), []).append(rid)

    if len(groups) == 1:
        disposition = next(iter(groups))
        return Decision(disposition, fired_rules, groups[disposition])

    beaten: set[str] = set()
    unresolved: set[tuple[str, str]] = set()
    for d1, d2 in itertools.combinations(groups, 2):
        for r1 in groups[d1]:
            for r2 in groups[d2]:
                if overrides(g, r1, r2):
                    beaten.add(r2)
                elif overrides(g, r2, r1):
                    beaten.add(r1)
                else:
                    unresolved.add(tuple(sorted((r1, r2))))

    surviving = [r for r in fired_rules if r not in beaten]
    surviving_groups: dict[str, list[str]] = {}
    for r in surviving:
        surviving_groups.setdefault(disposition_of(g, r), []).append(r)

    decision_disposition = min(surviving_groups, key=lambda d: ACUITY_RANK[d])
    return Decision(
        disposition=decision_disposition,
        fired_rules=fired_rules,
        winning_rules=surviving_groups[decision_disposition],
        unresolved_conflicts=sorted(unresolved),
    )


def _feature_ranges(conditions: list[dict]) -> dict[str, tuple]:
    """Intersect every condition on the same feature into one
    (lower_bound, lower_inclusive, upper_bound, upper_inclusive) interval."""
    ranges: dict[str, tuple] = {}
    for condition in conditions:
        feature = condition["feature"]
        lower_bound, lower_inclusive, upper_bound, upper_inclusive = ranges.get(
            feature, (-math.inf, True, math.inf, True)
        )
        op, threshold = condition["op"], condition["value"]
        if op == ">" and (threshold > lower_bound or (threshold == lower_bound and lower_inclusive)):
            lower_bound, lower_inclusive = threshold, False
        elif op == ">=" and (threshold > lower_bound or (threshold == lower_bound and lower_inclusive)):
            lower_bound, lower_inclusive = threshold, True
        elif op == "<" and (threshold < upper_bound or (threshold == upper_bound and upper_inclusive)):
            upper_bound, upper_inclusive = threshold, False
        elif op == "<=" and (threshold < upper_bound or (threshold == upper_bound and upper_inclusive)):
            upper_bound, upper_inclusive = threshold, True
        elif op == "==":
            lower_bound, lower_inclusive, upper_bound, upper_inclusive = threshold, True, threshold, True
        ranges[feature] = (lower_bound, lower_inclusive, upper_bound, upper_inclusive)
    return ranges


def _ranges_overlap(range_a: tuple, range_b: tuple) -> bool:
    lower_a, lower_a_inclusive, upper_a, upper_a_inclusive = range_a
    lower_b, lower_b_inclusive, upper_b, upper_b_inclusive = range_b
    if lower_a > upper_b or lower_b > upper_a:
        return False
    if lower_a == upper_b and not (lower_a_inclusive and upper_b_inclusive):
        return False
    if lower_b == upper_a and not (lower_b_inclusive and upper_a_inclusive):
        return False
    return True


def _jointly_satisfiable(g, rule_a: str, rule_b: str) -> bool:
    """Could one patient make both rules fire at once? True unless they
    share a feature whose required ranges don't overlap."""
    ranges_a = _feature_ranges(conditions_of(g, rule_a))
    ranges_b = _feature_ranges(conditions_of(g, rule_b))
    shared_features = set(ranges_a) & set(ranges_b)
    return all(_ranges_overlap(ranges_a[feature], ranges_b[feature]) for feature in shared_features)


def static_inconsistencies(g) -> list[tuple[str, str, str, str]]:
    """Every pair of rules that CAN fire on the same patient, recommend
    DIFFERENT dispositions, and have no override edge resolving them --
    a genuine gap in the rule base, found without needing a patient."""
    issues = []
    for rule_a, rule_b in itertools.combinations(rule_ids(g), 2):
        disposition_a, disposition_b = disposition_of(g, rule_a), disposition_of(g, rule_b)
        if disposition_a == disposition_b:
            continue
        if overrides(g, rule_a, rule_b) or overrides(g, rule_b, rule_a):
            continue
        if _jointly_satisfiable(g, rule_a, rule_b):
            issues.append((rule_a, rule_b, disposition_a, disposition_b))
    return issues