"""
Rule engine: evaluates a patient against the clinical knowledge graph.
"""
from __future__ import annotations

import itertools
import operator
from dataclasses import dataclass, field
from typing import Optional

from ed_triage.knowledge_graph import ACUITY_RANK, conditions_of, disposition_of, overrides, rule_ids

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
    for rid in rule_ids(g):
        conds = conditions_of(g, rid)
        if conds and all(_condition_holds(c, patient) for c in conds):
            fired.append(rid)
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