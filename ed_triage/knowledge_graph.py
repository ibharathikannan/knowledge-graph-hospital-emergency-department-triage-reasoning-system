"""
Clinical Knowledge Graph for the ED Triage Reasoning System.
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

ACUITY_RANK = {
    "ImmediateTreatment": 0,
    "DoctorReview": 1,
    "HomeCare": 2,
}

DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "rules.json"


def load_rules(path: Path = DEFAULT_RULES_PATH) -> dict:
    return json.loads(Path(path).read_text())

def build_graph(spec: dict | None = None) -> nx.DiGraph:
    if spec is None:
        spec = load_rules()

    g = nx.DiGraph()

    # ---- dispositions ---------------------------------------------------
    for disposition in ACUITY_RANK:
        g.add_node(disposition, kind="disposition")

    # ---- rules + their conditions ----------------------------------------
    for rule_id, rule_spec in spec["rules"].items():
        g.add_node(
            rule_id,
            kind="rule",
            priority=rule_spec["priority"],
            description=rule_spec["description"],
        )
        g.add_edge(rule_id, rule_spec["disposition"], type="recommends")
        for i, cond in enumerate(rule_spec["conditions"]):
            cond_id = f"{rule_id}::cond{i}"
            g.add_node(cond_id, kind="condition", **cond)
            g.add_edge(rule_id, cond_id, type="requires")

    # ---- explicit priority overrides --------------------------------------
    for winner, loser in spec["overrides"]:
        g.add_edge(winner, loser, type="overrides")

    return g


def rule_ids(g: nx.DiGraph) -> list[str]:
    return [n for n, d in g.nodes(data=True) if d.get("kind") == "rule"]


def conditions_of(g: nx.DiGraph, rule_id: str) -> list[dict]:
    return [
        {"id": n, **g.nodes[n]}
        for n in g.successors(rule_id)
        if g[rule_id][n]["type"] == "requires"
    ]


def disposition_of(g: nx.DiGraph, rule_id: str) -> str:
    return next(n for n in g.successors(rule_id) if g[rule_id][n]["type"] == "recommends")


def overrides(g: nx.DiGraph, a: str, b: str) -> bool:
    """True if rule `a` explicitly wins over rule `b`."""
    return g.has_edge(a, b) and g[a][b].get("type") == "overrides"