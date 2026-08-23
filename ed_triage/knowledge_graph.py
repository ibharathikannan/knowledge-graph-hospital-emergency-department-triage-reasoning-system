"""
Clinical Knowledge Graph for the ED Triage Reasoning System.
"""

#Step 1: Imports and Priority Setup
from __future__ import annotations
import networkx as nx

ACUITY_RANK = {
    "ImmediateTreatment": 0,
    "DoctorReview": 1,
    "HomeCare": 2,
}

#Step 2: Initialize Graph & Add Disposition Nodes
def build_graph() -> nx.DiGraph:
    g = nx.DiGraph()

    # ---- dispositions ---------------------------------------------------
    for disposition in ACUITY_RANK:
        g.add_node(disposition, kind="disposition")

        #Rule 1: High Severity Emergency
        g.add_node("R1_high_severity", kind="rule", priority=1, description="...")
        g.add_node("R1_high_severity::cond0", kind="condition", feature="severity", op=">", value=0.9)

        g.add_edge("R1_high_severity", "R1_high_severity::cond0", type="requires")
        g.add_edge("R1_high_severity", "ImmediateTreatment", type="recommends") 

        #Rule 2: Low Severity
        g.add_node("R2_low_severity", kind="rule", priority=3, description="...")
        g.add_node("R2_low_severity::cond0", kind="condition", feature="severity", op="<", value=0.2)

        g.add_edge("R2_low_severity", "R2_low_severity::cond0", type="requires")
        g.add_edge("R2_low_severity", "HomeCare", type="recommends")

        #Rule 3: Low Oxygen (SpO2)
        g.add_node("R3_low_oxygen", kind="rule", priority=1, description="...")
        g.add_node("R3_low_oxygen::cond0", kind="condition", feature="spo2", op="<", value=92)

        g.add_edge("R3_low_oxygen", "R3_low_oxygen::cond0", type="requires")
        g.add_edge("R3_low_oxygen", "ImmediateTreatment", type="recommends")

        #Rule 4: Elderly Minimum Review
        g.add_node("R4_elderly_min_review", kind="rule", priority=2, description="...")
        g.add_node("R4_elderly_min_review::cond0", kind="condition", feature="age", op=">", value=75)

        g.add_edge("R4_elderly_min_review", "R4_elderly_min_review::cond0", type="requires")
        g.add_edge("R4_elderly_min_review", "DoctorReview", type="recommends")

        #Rule 5: Mid-Range Severity (Multi-Condition AND logic)
        g.add_node("R5_mid_severity", kind="rule", priority=2, description="...")
        g.add_node("R5_mid_severity::cond0", kind="condition", feature="severity", op=">=", value=0.2)
        g.add_node("R5_mid_severity::cond1", kind="condition", feature="severity", op="<", value=0.9)

        g.add_edge("R5_mid_severity", "R5_mid_severity::cond0", type="requires")
        g.add_edge("R5_mid_severity", "R5_mid_severity::cond1", type="requires")
        g.add_edge("R5_mid_severity", "DoctorReview", type="recommends")

        overrides_ = [
        ("R3_low_oxygen", "R2_low_severity"),           # hypoxia beats a low score
        ("R1_high_severity", "R4_elderly_min_review"),  # very high severity beats "at least review"
        ("R3_low_oxygen", "R4_elderly_min_review"),     # hypoxia beats "at least review"
        ("R3_low_oxygen", "R5_mid_severity"),           # hypoxia beats the mid-severity default
        # (R4_elderly_min_review, R2_low_severity) is DELIBERATELY left
        # unresolved -- Step 6's static_inconsistencies() should catch this
    ]
    for winner, loser in overrides_:
        g.add_edge(winner, loser, type="overrides")

    return g