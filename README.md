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

## Step 3 — the remaining four rules

Same pattern as R1, four more times. One thing to notice: **R5 has two
conditions** (`severity >= 0.2` AND `severity < 0.9`) — two separate
`requires` edges to two separate condition nodes. That's how AND-of-
multiple-conditions looks in the graph.

Add these four blocks after the R1 block, still before `return g`:

```python
    # ---- rule 2: severity below 0.2 ------------------------------------
    g.add_node(
        "R2_low_severity",
        kind="rule",
        priority=3,
        description="Severity score below 0.2, no other red flags.",
    )
    g.add_node("R2_low_severity::cond0", kind="condition", feature="severity", op="<", value=0.2)
    g.add_edge("R2_low_severity", "R2_low_severity::cond0", type="requires")
    g.add_edge("R2_low_severity", "HomeCare", type="recommends")

    # ---- rule 3: low oxygen ---------------------------------------------
    g.add_node(
        "R3_low_oxygen",
        kind="rule",
        priority=1,
        description="SpO2 below 92% is emergent regardless of composite score.",
    )
    g.add_node("R3_low_oxygen::cond0", kind="condition", feature="spo2", op="<", value=92)
    g.add_edge("R3_low_oxygen", "R3_low_oxygen::cond0", type="requires")
    g.add_edge("R3_low_oxygen", "ImmediateTreatment", type="recommends")

    # ---- rule 4: elderly minimum review ---------------------------------
    g.add_node(
        "R4_elderly_min_review",
        kind="rule",
        priority=2,
        description="Patients over 75 get at least a doctor review.",
    )
    g.add_node("R4_elderly_min_review::cond0", kind="condition", feature="age", op=">", value=75)
    g.add_edge("R4_elderly_min_review", "R4_elderly_min_review::cond0", type="requires")
    g.add_edge("R4_elderly_min_review", "DoctorReview", type="recommends")

    # ---- rule 5: mid-range severity (TWO conditions -- both must hold) --
    g.add_node(
        "R5_mid_severity",
        kind="rule",
        priority=2,
        description="Mid-range severity score defaults to a doctor review.",
    )
    g.add_node("R5_mid_severity::cond0", kind="condition", feature="severity", op=">=", value=0.2)
    g.add_node("R5_mid_severity::cond1", kind="condition", feature="severity", op="<", value=0.9)
    g.add_edge("R5_mid_severity", "R5_mid_severity::cond0", type="requires")
    g.add_edge("R5_mid_severity", "R5_mid_severity::cond1", type="requires")
    g.add_edge("R5_mid_severity", "DoctorReview", type="recommends")
```

**Verify** — lists every rule with its conditions and disposition:

```bash
python -c "
from ed_triage.knowledge_graph import build_graph
g = build_graph()
rules = [n for n, d in g.nodes(data=True) if d['kind'] == 'rule']
print('rule count:', len(rules))
for r in rules:
    disp = [v for _, v, d in g.out_edges(r, data=True) if d['type'] == 'recommends'][0]
    conds = [v for _, v, d in g.out_edges(r, data=True) if d['type'] == 'requires']
    print(f'{r:25s} -> {disp:20s} conditions: {conds}')
"
```

Expected:
```
rule count: 5
R1_high_severity          -> ImmediateTreatment   conditions: ['R1_high_severity::cond0']
R2_low_severity           -> HomeCare             conditions: ['R2_low_severity::cond0']
R3_low_oxygen             -> ImmediateTreatment   conditions: ['R3_low_oxygen::cond0']
R4_elderly_min_review     -> DoctorReview          conditions: ['R4_elderly_min_review::cond0']
R5_mid_severity           -> DoctorReview          conditions: ['R5_mid_severity::cond0', 'R5_mid_severity::cond1']
```

R1 and R3 both recommend `ImmediateTreatment`, and R4 and R5 both
recommend `DoctorReview` — fine, no conflict, since they never disagree.
The interesting case: a patient can be old (R4 fires → `DoctorReview`)
*and* have very low severity (R2 fires → `HomeCare`) at the same time —
two rules, same patient, different opinions. That's what Step 4
(override edges) handles.

---

## Step 4 — override edges (and one deliberate gap)

When two fired rules disagree on the disposition, an `overrides` edge
says who wins. We only need one for pairs that can **actually fire
together** *and* where we want an intentional answer — not every
possible pair.

For example, R1 (`severity > 0.9`) and R2 (`severity < 0.2`) can never
fire on the same patient — the ranges don't overlap — so no override
edge is needed there at all.

Add this after all five rules, before `return g`:

```python
    # ---- explicit priority overrides --------------------------------------
    # Only pairs of rules that can genuinely fire together AND recommend
    # different dispositions need an edge here. A pair that CAN co-fire,
    # disagrees, and has NO edge here is a real rule-base gap.
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
```

Why that specific gap: an 82-year-old patient with a low severity score
genuinely has two rules disagreeing — "elderly → at least review" vs
"low score → home care" — and nobody has ever written down which one
should win. That's a real hole in the rule base, not a bug in the code,
and it's exactly what a knowledge-graph-backed Rule Inconsistency Check
is supposed to surface (Step 6).

**Verify:**

```bash
python -c "
from ed_triage.knowledge_graph import build_graph
g = build_graph()
print('override edges:')
for u, v, d in g.edges(data=True):
    if d['type'] == 'overrides':
        print(f'  {u} beats {v}')

# sanity check: the deliberate gap has NO edge either direction
a, b = 'R4_elderly_min_review', 'R2_low_severity'
print()
print('R4 -> R2 edge exists?', g.has_edge(a, b))
print('R2 -> R4 edge exists?', g.has_edge(b, a))
"
```

Expected:
```
override edges:
  R3_low_oxygen beats R2_low_severity
  R1_high_severity beats R4_elderly_min_review
  R3_low_oxygen beats R4_elderly_min_review
  R3_low_oxygen beats R5_mid_severity

R4 -> R2 edge exists? False
R2 -> R4 edge exists? False
```

---

## Step 5 — (next)

*to be added*
