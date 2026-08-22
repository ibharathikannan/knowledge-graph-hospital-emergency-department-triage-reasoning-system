# ED Triage MVP — Build Log

A step-by-step recreation guide for the knowledge graph + rule engine slice
of the ED Triage Reasoning System. Follow it top to bottom; each step says
what to paste and how to verify it before moving on.

## Setup

```bash
conda create -p venv python==3.11 -y
conda activate venv
pip install -r requirements.txt
```

`requirements.txt`:
```
networkx>=3.0
pytest>=7.0
```

---

## Step 1 — the graph skeleton

We're using `networkx.DiGraph` — a directed graph where every node and edge
can carry a plain Python dict of attributes. We'll represent:

- **dispositions** (`ImmediateTreatment`, `DoctorReview`, `HomeCare`) as nodes
- **rules** as nodes that point to the conditions they need and the
  disposition they recommend

Paste into `ed_triage/knowledge_graph.py`:

```python
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

    return g
```

**Verify** (run from the `ed-triage-mvp` folder, with the conda env active):

```bash
python -c "from ed_triage.knowledge_graph import build_graph; print(list(build_graph().nodes(data=True)))"
```

Expected:
```
[('ImmediateTreatment', {'kind': 'disposition'}), ('DoctorReview', {'kind': 'disposition'}), ('HomeCare', {'kind': 'disposition'})]
```

`kind` is just a tag we invented — networkx doesn't care what's in the
dict, it's how *we'll* tell rules apart from dispositions later when we
search the graph.

---

## Step 2 — one rule, fully wired

A rule isn't just a node — it's a node **connected** to its conditions and
its disposition. Three pieces:

1. The **rule node** itself — carries `priority` and a human-readable
   `description` (useful later for audit logs and explanations).
2. A **condition node** — the actual evaluatable predicate: `feature`,
   `op`, `value`.
3. Two **edges**: `requires` (rule → condition) and `recommends`
   (rule → disposition). If a rule has *multiple* `requires` edges, all of
   them must hold — that's how we get AND logic.

Add this inside `build_graph()`, right before `return g`:

```python
    # ---- rule 1: severity above 0.9 -------------------------------------
    # A rule is a node. It's linked to its condition(s) with a "requires"
    # edge, and to the disposition it recommends with a "recommends" edge.
    # ALL of a rule's "requires" conditions must hold for it to fire (AND).
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
```

The condition node is named `R1_high_severity::cond0` — namespaced under
the rule so condition IDs never collide once we have five rules with
several conditions each.

**Verify:**

```bash
python -c "
from ed_triage.knowledge_graph import build_graph
g = build_graph()
print('RULE NODE:', g.nodes['R1_high_severity'])
print('CONDITION NODE:', g.nodes['R1_high_severity::cond0'])
print('EDGES OUT OF RULE:', list(g.edges('R1_high_severity', data=True)))
"
```

Expected:
```
RULE NODE: {'kind': 'rule', 'priority': 1, 'description': 'Severity score above 0.9 is a top-priority emergency.'}
CONDITION NODE: {'kind': 'condition', 'feature': 'severity', 'op': '>', 'value': 0.9}
EDGES OUT OF RULE: [('R1_high_severity', 'R1_high_severity::cond0', {'type': 'requires'}), ('R1_high_severity', 'ImmediateTreatment', {'type': 'recommends'})]
```

---

## Step 3 — (next)

*to be added*
