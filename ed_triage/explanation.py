"""
Turns a Decision into a structured, patient-specific explanation --
not the rule's static description, but which actual values triggered it.
"""
from __future__ import annotations

from dataclasses import dataclass

from ed_triage.knowledge_graph import conditions_of

_OP_WORDS = {
    ">": "above",
    ">=": "at or above",
    "<": "below",
    "<=": "at or below",
    "==": "equal to",
}


@dataclass
class Factor:
    rule_id: str
    feature: str
    patient_value: float
    op: str
    threshold: float

    def as_text(self) -> str:
        word = _OP_WORDS.get(self.op, self.op)
        return f"{self.feature} = {self.patient_value} is {word} the threshold of {self.threshold} ({self.rule_id})"


def explain(g, patient: dict, decision) -> list[Factor]:
    """One Factor per condition of every winning rule."""
    factors = []
    for rule_id in decision.winning_rules:
        for cond in conditions_of(g, rule_id):
            factors.append(
                Factor(
                    rule_id=rule_id,
                    feature=cond["feature"],
                    patient_value=patient.get(cond["feature"]),
                    op=cond["op"],
                    threshold=cond["value"],
                )
            )
    return factors


def summarize(decision, factors: list[Factor]) -> str:
    if decision.disposition is None:
        return "No rule matched this patient -- nothing to explain."
    factor_texts = "; ".join(f.as_text() for f in factors)
    return f"{decision.disposition} because {factor_texts}."