"""
Clinical Knowledge Graph for the ED Triage Reasoning System.
"""
from __future__ import annotations

import networkx as nx

# Lower number = more urgent. We'll use this later to pick the safe
# (most urgent) option whenever two rules disagree.
ACUITY_RANK = {
    "ImmediateTreatment": 0,
    "DoctorReview": 1,
    "HomeCare": 2,
}


def build_graph() -> nx.DiGraph:
    g = nx.DiGraph()

    # ---- dispositions ---------------------------------------------------
    for disposition in ACUITY_RANK:
        g.add_node(disposition, kind="disposition")

    # ---- rule 1: severity above 0.9 -------------------------------------
    g.add_node(
        "R1_high_severity",
        kind="rule",
        priority=1,
        description="Severity score above 0.9 is a top-priority emergency.",
    )
    g.add_node(
        "R1_high_severity::cond0",
        kind="condition",
        feature="severity",
        op=">",
        value=0.9,
    )
    g.add_edge("R1_high_severity", "R1_high_severity::cond0", type="requires")
    g.add_edge("R1_high_severity", "ImmediateTreatment", type="recommends")    

    return g