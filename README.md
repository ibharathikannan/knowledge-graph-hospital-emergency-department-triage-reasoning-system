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

## Step 5 — helper functions (the graph's query interface)

These go at the very bottom of `knowledge_graph.py`, **outside**
`build_graph()` — free-standing functions that let `rule_engine.py` (and
anything else) query the graph without knowing networkx's edge-filtering
syntax by heart:

```python
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
```

What each one does:
- **`rule_ids`** — filters all nodes down to the ones tagged `kind="rule"`.
  This is the payoff for tagging every node back in Step 1.
- **`conditions_of`** — `g.successors(rule_id)` gives every node the rule
  points to; we keep only the ones reached by a `requires` edge, and merge
  each condition's own attributes (`feature`/`op`/`value`) with its `id`
  into one flat dict.
- **`disposition_of`** — same idea, but for the single `recommends` edge.
  `next()` grabs it because a rule only ever recommends one disposition.
- **`overrides`** — a readable wrapper around checking one specific edge's
  `type`.

**Verify:**

```bash
python -c "
from ed_triage.knowledge_graph import build_graph, rule_ids, conditions_of, disposition_of, overrides

g = build_graph()
print('rule_ids:', rule_ids(g))
print()
print('conditions_of(R5_mid_severity):', conditions_of(g, 'R5_mid_severity'))
print()
print('disposition_of(R3_low_oxygen):', disposition_of(g, 'R3_low_oxygen'))
print()
print('overrides(R3_low_oxygen, R2_low_severity):', overrides(g, 'R3_low_oxygen', 'R2_low_severity'))
print('overrides(R2_low_severity, R3_low_oxygen):', overrides(g, 'R2_low_severity', 'R3_low_oxygen'))
"
```

Expected:
```
rule_ids: ['R1_high_severity', 'R2_low_severity', 'R3_low_oxygen', 'R4_elderly_min_review', 'R5_mid_severity']

conditions_of(R5_mid_severity): [{'id': 'R5_mid_severity::cond0', 'kind': 'condition', 'feature': 'severity', 'op': '>=', 'value': 0.2}, {'id': 'R5_mid_severity::cond1', 'kind': 'condition', 'feature': 'severity', 'op': '<', 'value': 0.9}]

disposition_of(R3_low_oxygen): ImmediateTreatment

overrides(R3_low_oxygen, R2_low_severity): True
overrides(R2_low_severity, R3_low_oxygen): False
```

`knowledge_graph.py` is now complete.

---

## Step 6 — `rule_engine.py`, part 1: `fire()`

This is the simplest useful piece: given a patient, which rules trigger?
Create `ed_triage/rule_engine.py`:

```python
"""
Rule engine: evaluates a patient against the clinical knowledge graph.
"""
from __future__ import annotations

import operator

from ed_triage.knowledge_graph import conditions_of, rule_ids

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
```

Two things worth noticing:
- **`_OPS`** is the trick that lets conditions live as plain data
  (`op=">"`) in the graph instead of a Python `if/elif` chain — it turns
  the *string* `">"` into the actual `operator.gt` function, so
  `_OPS[cond["op"]](value, cond["value"])` becomes
  `operator.gt(patient_value, 0.9)`, i.e. `patient_value > 0.9`.
- **`_condition_holds`** treats a *missing* patient value as "condition
  not satisfied" rather than crashing or guessing — an incomplete patient
  record never accidentally triggers a rule.
- **`fire()`** is literally the AND logic from Step 2: `all(...)` is only
  `True` if every one of a rule's conditions holds.

**Verify** — run all four sample patients through it:

```bash
python -c "
from ed_triage.knowledge_graph import build_graph
from ed_triage.rule_engine import fire

g = build_graph()
patients = {
    'P001': {'severity': 0.94, 'spo2': 96, 'age': 58},
    'P002': {'severity': 0.18, 'spo2': 98, 'age': 45},
    'P007': {'severity': 0.43, 'spo2': 90, 'age': 52},
    'P010': {'severity': 0.15, 'spo2': 97, 'age': 82},
}
for pid, p in patients.items():
    print(pid, '->', fire(g, p))
"
```

Expected:
```
P001 -> ['R1_high_severity']
P002 -> ['R2_low_severity']
P007 -> ['R3_low_oxygen', 'R5_mid_severity']
P010 -> ['R2_low_severity', 'R4_elderly_min_review']
```

P007 and P010 each fired two rules — the conflict case from Step 4 now
showing up for real. `fire()` deliberately stops here; it doesn't pick a
winner yet. That's Step 7: `resolve()`.

---

## Step 7 — `resolve()`: turning fired rules into one decision

First, update the imports at the top of `rule_engine.py`:

```python
"""
Rule engine: evaluates a patient against the clinical knowledge graph.
"""
from __future__ import annotations

import itertools
import operator
from dataclasses import dataclass, field
from typing import Optional

from ed_triage.knowledge_graph import ACUITY_RANK, conditions_of, disposition_of, overrides, rule_ids
```

Now add this below `fire()`:

```python
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
```

Walking through the logic:

- **No rules fired** → `disposition=None`. Nothing to recommend, and the
  caller has to handle that explicitly rather than us guessing.
- **All fired rules agree** (one disposition group) → done, no
  conflict-resolution needed.
- **They disagree** → for every pair of rules from *different*
  disposition groups, check `overrides()` in both directions: one wins →
  the loser goes into `beaten` and is dropped; neither has an edge → the
  pair goes into `unresolved` — the runtime, per-patient sibling of the
  build-time check we'll write in Step 8.
- After removing everything `beaten`, if survivors **still** disagree
  (like P010), we don't crash or pick arbitrarily — `min(..., key=ACUITY_RANK)`
  always takes the *more urgent* option. Care is never silently downgraded.

`fired_rules` keeps everything that triggered (for audit); `winning_rules`
is just the rule(s) behind the final disposition; `unresolved_conflicts`
is empty unless something genuinely couldn't be resolved.

**Verify:**

```bash
python -c "
from ed_triage.knowledge_graph import build_graph
from ed_triage.rule_engine import fire, resolve

g = build_graph()
patients = {
    'P001': {'severity': 0.94, 'spo2': 96, 'age': 58},
    'P002': {'severity': 0.18, 'spo2': 98, 'age': 45},
    'P007': {'severity': 0.43, 'spo2': 90, 'age': 52},
    'P010': {'severity': 0.15, 'spo2': 97, 'age': 82},
}
for pid, p in patients.items():
    d = resolve(g, fire(g, p))
    print(pid, '-> disposition:', d.disposition, '| winning:', d.winning_rules, '| conflict:', d.has_conflict, d.unresolved_conflicts)
"
```

Expected:
```
P001 -> disposition: ImmediateTreatment | winning: ['R1_high_severity'] | conflict: False []
P002 -> disposition: HomeCare | winning: ['R2_low_severity'] | conflict: False []
P007 -> disposition: ImmediateTreatment | winning: ['R3_low_oxygen'] | conflict: False []
P010 -> disposition: DoctorReview | winning: ['R4_elderly_min_review'] | conflict: True [('R2_low_severity', 'R4_elderly_min_review')]
```

P007's conflict resolved silently via the override edge (correct, no flag
needed). P010's didn't — the deliberate gap surfacing exactly where
designed.

---

## Step 8 — `static_inconsistencies()`: the build-time graph query

This is the payoff for encoding rules as a graph instead of `if/elif`
chains: we can ask "which rule pairs could ever disagree?" as a
structural query — no patient required, no test run needed to discover
it.

**The core idea:** two rules can only conflict on a *real* patient if
some patient could satisfy both simultaneously. R1 (`severity > 0.9`)
and R2 (`severity < 0.2`) can never both fire — the ranges don't
overlap — so they're not a risk no matter what disposition they
recommend. We only need to worry about pairs whose conditions are
**jointly satisfiable**.

Add `import math` to your imports at the top, then add this at the
bottom of `rule_engine.py`:

```python
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
    a genuine gap in the rule base, found without needing a patient.
    Returns (rule_a, rule_b, disposition_a, disposition_b) tuples."""
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
```

Walking through it:

- **`_feature_ranges`** collapses a rule's conditions on one feature into
  a single interval. R5's two conditions (`severity>=0.2`,
  `severity<0.9`) become one range `[0.2, 0.9)`. The
  `lo_inclusive`/`hi_inclusive` flags matter — without them, R2's
  `severity<0.2` and R5's `severity>=0.2` would look like they "touch"
  at 0.2 and falsely register as overlapping, when really only R5 is
  satisfied at exactly 0.2.
- **`_ranges_overlap`** compares two such intervals precisely, boundary
  inclusivity included.
- **`_jointly_satisfiable`** only checks features **both** rules
  constrain. R1 (`severity`) and R4 (`age`) share nothing, so nothing
  stops them co-firing — correctly matches the override edge we
  deliberately added for that pair back in Step 4.
- **`static_inconsistencies`** ties it together: skip same-disposition
  pairs (no conflict possible), skip pairs already resolved by an
  override edge, and flag anything left that could still genuinely
  co-fire and disagree.

**Verify:**

```bash
python -c "
from ed_triage.knowledge_graph import build_graph
from ed_triage.rule_engine import static_inconsistencies

g = build_graph()
issues = static_inconsistencies(g)
for r1, r2, d1, d2 in issues:
    print(f'{r1} -> {d1}   vs   {r2} -> {d2}   (no override edge)')
print()
print('total issues:', len(issues))
"
```

Expected:
```
R2_low_severity -> HomeCare   vs   R4_elderly_min_review -> DoctorReview   (no override edge)

total issues: 1
```

Exactly the one deliberate gap — same one P010 tripped at runtime in
Step 7, now caught structurally, before any patient ever exists.

**Bonus check:** `tests/test_rule_engine.py` (which survived the cleanup)
was written against exactly this code:

```bash
pytest -q
```

If everything above matches, all 6 tests should pass — that's the real
"done" signal for `rule_engine.py`.

---

## Aside — rules-to-JSON refactor

Originally deferred here (rules stayed hardcoded in `build_graph()` while
`rule_engine.py` and `validators.py` got built). Now actually done — see
**Step 13** at the end of this log, after the numbering below finishes
the validator chain.

---

## Step 9 — `CheckResult` + the Missing Explanation Check

New file: `ed_triage/validators.py`. Every validator answers the same
question in the same shape: did this check pass, and why? One small
dataclass covers all four checks:

```python
"""
Validator Chain: runs after resolve() to sanity-check a Decision before
it's shown to a clinician.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    passed: bool
    reason: str
```

Now the first check. It answers one question: can we actually point to
something that justifies this decision?

```python
def check_missing_explanation(g, decision) -> CheckResult:
    if decision.disposition is None:
        return CheckResult("missing_explanation", False, "No rule fired -- nothing to explain.")
    for rule_id in decision.winning_rules:
        description = g.nodes[rule_id].get("description", "")
        if not description:
            return CheckResult("missing_explanation", False, f"{rule_id} has no description.")
    return CheckResult("missing_explanation", True, "Every winning rule has a description.")
```

Two failure modes, both simple: nothing fired at all (no decision to
explain), or a winning rule exists but its `description` field in the
graph is empty. Either way, we never show a clinician a decision we
can't back up in words.

**Verify:**

```bash
python -c "
from ed_triage.knowledge_graph import build_graph
from ed_triage.rule_engine import fire, resolve
from ed_triage.validators import check_missing_explanation

g = build_graph()
p = {'severity': 0.94, 'spo2': 96, 'age': 58}
decision = resolve(g, fire(g, p))
result = check_missing_explanation(g, decision)
print(result)
"
```

Expected:
```
CheckResult(name='missing_explanation', passed=True, reason='Every winning rule has a description.')
```

---

## Step 10 — the Rule Inconsistency Check

This one's almost free — you built all the real logic back in Step 7.
It just wraps `decision.has_conflict` in the same `CheckResult` shape:

```python
def check_rule_inconsistency(decision) -> CheckResult:
    if decision.has_conflict:
        return CheckResult(
            "rule_inconsistency",
            False,
            f"Unresolved rule conflict: {decision.unresolved_conflicts}",
        )
    return CheckResult("rule_inconsistency", True, "No unresolved rule conflicts.")
```

Add it below `check_missing_explanation`.

**Verify** — one patient whose conflict got resolved by an override
(P007), one that didn't (P010):

```bash
python -c "
from ed_triage.knowledge_graph import build_graph
from ed_triage.rule_engine import fire, resolve
from ed_triage.validators import check_rule_inconsistency

g = build_graph()
for pid, p in {
    'P007': {'severity': 0.43, 'spo2': 90, 'age': 52},
    'P010': {'severity': 0.15, 'spo2': 97, 'age': 82},
}.items():
    decision = resolve(g, fire(g, p))
    print(pid, check_rule_inconsistency(decision))
"
```

Expected:
```
P007 CheckResult(name='rule_inconsistency', passed=True, reason='No unresolved rule conflicts.')
P010 CheckResult(name='rule_inconsistency', passed=False, reason="Unresolved rule conflict: [('R2_low_severity', 'R4_elderly_min_review')]")
```

---

## Step 11 — the Conflicting Reasons Check

This one doesn't trust `resolve()`'s bookkeeping — it independently
re-derives each winning rule's disposition straight from the graph and
checks it actually matches what we're about to tell the clinician.

Add `disposition_of` to your imports at the top of `validators.py`:

```python
from ed_triage.knowledge_graph import disposition_of
```

Then add the check:

```python
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
```

Right now this will always pass — `resolve()` is built so `winning_rules`
can never actually disagree with `decision.disposition`. That's not this
check being pointless: it's "trust but verify." It exists to catch a
*future* bug — someone edits `resolve()` later and breaks that guarantee
without realizing it. The verify command proves that by faking exactly
that bug:

```bash
python -c "
from ed_triage.knowledge_graph import build_graph
from ed_triage.rule_engine import fire, resolve, Decision
from ed_triage.validators import check_conflicting_reasons

g = build_graph()

# normal case -- should pass
p = {'severity': 0.94, 'spo2': 96, 'age': 58}
decision = resolve(g, fire(g, p))
print('normal:  ', check_conflicting_reasons(g, decision))

# simulate a future bug: winning_rules doesn't actually match the disposition
bad_decision = Decision(disposition='HomeCare', fired_rules=['R1_high_severity'], winning_rules=['R1_high_severity'])
print('bug case:', check_conflicting_reasons(g, bad_decision))
"
```

Expected:
```
normal:   CheckResult(name='conflicting_reasons', passed=True, reason='Every cited rule agrees with the decision.')
bug case: CheckResult(name='conflicting_reasons', passed=False, reason='R1_high_severity recommends ImmediateTreatment, not HomeCare.')
```

That second line is the check actually earning its keep — it caught a
corrupted decision that `resolve()` itself would never produce, but some
future code change might.

---

## Step 12 — the Resource Validation Check + tying it all together

Last check: does a bed actually exist for this disposition? We need a
lookup from disposition → required resource (same "map data to behavior
instead of `if/elif`" trick as `_OPS` in Step 6), and a stand-in for the
real Bed Management Feed — just a plain dict of counts for now.

```python
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
```

And the piece that turns four separate functions into an actual
Validator Chain — one call, one report:

```python
def run_all(g, decision, bed_state: dict) -> list[CheckResult]:
    return [
        check_missing_explanation(g, decision),
        check_rule_inconsistency(decision),
        check_conflicting_reasons(g, decision),
        check_resource_validation(decision, bed_state),
    ]
```

`HomeCare` needs no bed, so it auto-passes — only `ImmediateTreatment`
and `DoctorReview` actually get checked against `bed_state`.

**Verify** — same decision, two different bed states, to see both a PASS
and a FAIL:

```bash
python -c "
from ed_triage.knowledge_graph import build_graph
from ed_triage.rule_engine import fire, resolve
from ed_triage.validators import run_all

g = build_graph()
p = {'severity': 0.94, 'spo2': 96, 'age': 58}
decision = resolve(g, fire(g, p))

print('--- ICU available ---')
for r in run_all(g, decision, {'ICU': 2, 'Ward': 5}):
    print(r)

print()
print('--- ICU full ---')
for r in run_all(g, decision, {'ICU': 0, 'Ward': 5}):
    print(r)
"
```

Expected:
```
--- ICU available ---
CheckResult(name='missing_explanation', passed=True, reason='Every winning rule has a description.')
CheckResult(name='rule_inconsistency', passed=True, reason='No unresolved rule conflicts.')
CheckResult(name='conflicting_reasons', passed=True, reason='Every cited rule agrees with the decision.')
CheckResult(name='resource_validation', passed=True, reason='ICU bed available (2 free).')

--- ICU full ---
CheckResult(name='missing_explanation', passed=True, reason='Every winning rule has a description.')
CheckResult(name='rule_inconsistency', passed=True, reason='No unresolved rule conflicts.')
CheckResult(name='conflicting_reasons', passed=True, reason='Every cited rule agrees with the decision.')
CheckResult(name='resource_validation', passed=False, reason='No ICU beds available.')
```

That's the full Validator Chain from the architecture doc, now real,
working code.

---

## Step 13 — separating rule content from rule construction

Pulling the rule *content* out of Python into `data/rules.json`, and
making `build_graph()` generic — it stops knowing about R1–R5
specifically and just reads whatever's in the file.

### Part A — `data/rules.json`

A straight data transcription of what was hardcoded in `build_graph()`
— nothing new to understand, just moving it:

```json
{
  "rules": {
    "R1_high_severity": {
      "priority": 1,
      "description": "Severity score above 0.9 is a top-priority emergency.",
      "disposition": "ImmediateTreatment",
      "conditions": [{"feature": "severity", "op": ">", "value": 0.9}]
    },
    "R2_low_severity": {
      "priority": 3,
      "description": "Severity score below 0.2, no other red flags.",
      "disposition": "HomeCare",
      "conditions": [{"feature": "severity", "op": "<", "value": 0.2}]
    },
    "R3_low_oxygen": {
      "priority": 1,
      "description": "SpO2 below 92% is emergent regardless of composite score.",
      "disposition": "ImmediateTreatment",
      "conditions": [{"feature": "spo2", "op": "<", "value": 92}]
    },
    "R4_elderly_min_review": {
      "priority": 2,
      "description": "Patients over 75 get at least a doctor review.",
      "disposition": "DoctorReview",
      "conditions": [{"feature": "age", "op": ">", "value": 75}]
    },
    "R5_mid_severity": {
      "priority": 2,
      "description": "Mid-range severity score defaults to a doctor review.",
      "disposition": "DoctorReview",
      "conditions": [
        {"feature": "severity", "op": ">=", "value": 0.2},
        {"feature": "severity", "op": "<", "value": 0.9}
      ]
    }
  },
  "overrides": [
    ["R3_low_oxygen", "R2_low_severity"],
    ["R1_high_severity", "R4_elderly_min_review"],
    ["R3_low_oxygen", "R4_elderly_min_review"],
    ["R3_low_oxygen", "R5_mid_severity"]
  ]
}
```

(`R4_elderly_min_review` / `R2_low_severity` still has no entry in
`"overrides"` — the deliberate gap moves with the data.)

### Part B — `build_graph()` becomes a loader

Replace the imports at the top of `knowledge_graph.py` with:

```python
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
```

Then replace the entire `build_graph()` function with:

```python
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
```

**What changed conceptually:** `build_graph()` no longer mentions
R1–R5 anywhere. It only knows the *shape* a rule spec has (`priority`,
`description`, `disposition`, `conditions`) — not what any particular
rule says. Adding rule #6 tomorrow is a `rules.json` edit;
`knowledge_graph.py` never changes. `spec: dict | None = None` also
means tests can hand it a small in-memory dict directly, without
touching the file at all.

`rule_ids`, `conditions_of`, `disposition_of`, `overrides` from Step 5
don't change — they just read whatever graph they're given, regardless
of where it came from.

**Verify** — should print exactly what it did before the refactor,
proving the swap was behavior-preserving:

```bash
python -c "
from ed_triage.knowledge_graph import build_graph, rule_ids
from ed_triage.rule_engine import fire, resolve, static_inconsistencies

g = build_graph()
print('rule count:', len(rule_ids(g)))
print('inconsistencies:', static_inconsistencies(g))
print()

for pid, p in {
    'P001': {'severity': 0.94, 'spo2': 96, 'age': 58},
    'P002': {'severity': 0.18, 'spo2': 98, 'age': 45},
    'P007': {'severity': 0.43, 'spo2': 90, 'age': 52},
    'P010': {'severity': 0.15, 'spo2': 97, 'age': 82},
}.items():
    d = resolve(g, fire(g, p))
    print(pid, d.disposition, d.winning_rules, d.has_conflict)
"
```

Expected — identical to every earlier run:
```
rule count: 5
inconsistencies: [('R2_low_severity', 'R4_elderly_min_review', 'HomeCare', 'DoctorReview')]

P001 ImmediateTreatment ['R1_high_severity'] False
P002 HomeCare ['R2_low_severity'] False
P007 ImmediateTreatment ['R3_low_oxygen'] False
P010 DoctorReview ['R4_elderly_min_review'] True
```

---

## Step 14 — `tests/test_rule_engine.py`, part 1: setup + `knowledge_graph.py` tests

You've already done every one of these checks by hand, over and over,
with the verify commands. A test is just one of those checks made
permanent — `print(...)` becomes `assert ...`, so it checks itself
forever instead of you re-reading output each time.

Start `tests/test_rule_engine.py` with the setup boilerplate and one
shared dict of sample patients (used by every test in this file, so we
don't retype it four times):

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ed_triage.knowledge_graph import build_graph, rule_ids, overrides
from ed_triage.rule_engine import fire, resolve, static_inconsistencies

PATIENTS = {
    "P001": {"severity": 0.94, "spo2": 96, "age": 58},
    "P002": {"severity": 0.18, "spo2": 98, "age": 45},
    "P007": {"severity": 0.43, "spo2": 90, "age": 52},
    "P010": {"severity": 0.15, "spo2": 97, "age": 82},
}
```

`sys.path.insert(...)` just makes sure Python can find the `ed_triage`
package no matter which folder you run `pytest` from — a safety net,
not something specific to this project.

Now the first two tests, covering `knowledge_graph.py`:

```python
def test_build_graph_loads_five_rules_by_default():
    g = build_graph()
    assert len(rule_ids(g)) == 5


def test_deliberate_gap_has_no_override_edge():
    g = build_graph()
    assert not overrides(g, "R4_elderly_min_review", "R2_low_severity")
    assert not overrides(g, "R2_low_severity", "R4_elderly_min_review")
```

These are exactly the two facts confirmed by hand back in Step 4 —
"5 rules exist" and "the gap really has no edge either direction" — now
written as `assert` instead of `print`.

**Verify:**

```bash
pytest tests/test_rule_engine.py -v
```

Expected:
```
tests/test_rule_engine.py::test_build_graph_loads_five_rules_by_default PASSED
tests/test_rule_engine.py::test_deliberate_gap_has_no_override_edge PASSED

2 passed
```

---

## Step 15 — `rule_engine.py` tests

These six are the ones verified the most already — each is a patient
scenario run by hand multiple times. Add them after the two from
Step 14:

```python
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
```

Nothing here is new — `test_static_inconsistency_found` is literally
the Step 8 verify command turned into an assertion, and
`test_unresolved_conflict_falls_back_conservatively` is P010 from
Step 7.

**Verify:**

```bash
pytest tests/test_rule_engine.py -v
```

Expected — all 8 now (the 2 from Step 14 plus these 6):
```
8 passed
```

---

## Step 16 — `validators.py` tests (the last one)

First, update the `rule_engine` import line to add `Decision`, and add a
new import line for `validators`:

```python
from ed_triage.knowledge_graph import build_graph, rule_ids, overrides
from ed_triage.rule_engine import Decision, fire, resolve, static_inconsistencies
from ed_triage.validators import (
    check_conflicting_reasons,
    check_missing_explanation,
    check_resource_validation,
    check_rule_inconsistency,
    run_all,
)
```

Now the tests — nine of them, but each is short:

```python
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
```

`test_conflicting_reasons_catches_a_corrupted_decision` is the exact
"fake a future bug" trick from Step 11's verify command — same idea,
now permanent.

**Verify — the whole suite:**

```bash
pytest tests/test_rule_engine.py -v
```

Expected: **17 passed** (8 from Steps 14–15, plus these 9).

---

## Step 17 — a UI, part 1: the skeleton

Streamlit turns a plain script into a web app with almost no new
syntax — no HTML/JS, no routes to wire up.

Install it:
```bash
pip install streamlit
```
(and add `streamlit>=1.35` to `requirements.txt`)

Create `app.py` in the project root:

```python
"""
Streamlit UI: input a patient, see the knowledge graph reason about them.
Run: streamlit run app.py
"""
import streamlit as st

from ed_triage.knowledge_graph import build_graph
from ed_triage.rule_engine import fire, resolve

st.set_page_config(page_title="ED Triage Reasoning", layout="wide")
st.title("ED Triage Reasoning System")

st.header("Patient")
severity = st.slider("Severity score", 0.0, 1.0, 0.5, 0.01)
spo2 = st.number_input("SpO2 (%)", min_value=50, max_value=100, value=97)
age = st.number_input("Age", min_value=0, max_value=120, value=50)

patient = {"severity": severity, "spo2": spo2, "age": age}

g = build_graph()
fired = fire(g, patient)
decision = resolve(g, fired)

st.header("Result")
st.write("Fired rules:", fired)
st.write("Decision:", decision.disposition)
```

The one new concept that matters: there's no "submit button" or event
handler. Streamlit reruns the **entire script, top to bottom**, every
time you touch a widget. Move the slider → the whole file executes
again with the new value → `patient`/`fired`/`decision` all recompute →
the page updates. No callbacks to wire up, the code stays linear.

**Verify:**

```bash
streamlit run app.py
```

Opens a browser tab automatically. Move the severity slider — "Fired
rules" and "Decision" should update live. Try 0.95 (→
`R1_high_severity` → `ImmediateTreatment`), then 0.1 (→
`R2_low_severity` → `HomeCare`).

---

## Step 18 — bed availability inputs + the validator results

`{"ICU": 2, "Ward": 5}` had only ever existed in verify commands and
tests typed by hand — nowhere in `app.py`. Fixing that: same three-line
pattern as `patient` from Step 17, just two more widgets.

Add this to `app.py`, right after the patient inputs:

```python
st.header("Bed availability")
icu_beds = st.number_input("ICU beds free", min_value=0, max_value=20, value=2)
ward_beds = st.number_input("Ward beds free", min_value=0, max_value=50, value=5)

bed_state = {"ICU": icu_beds, "Ward": ward_beds}
```

Two widgets holding the *current* value, one dict built fresh from
them on every rerun — no different from how `severity` worked.

Add the `run_all` import at the top:

```python
from ed_triage.validators import run_all
```

Then replace the whole `st.header("Result")` block at the bottom with:

```python
st.header("Result")
if decision.disposition:
    st.subheader(decision.disposition)
    for rule_id in decision.winning_rules:
        st.write(f"- **{rule_id}**: {g.nodes[rule_id]['description']}")
else:
    st.subheader("No rule fired")

st.header("Validation")
checks = run_all(g, decision, bed_state)
for check in checks:
    icon = "✅" if check.passed else "❌"
    st.write(f"{icon} **{check.name}** — {check.reason}")
```

Two new things, both small: `g.nodes[rule_id]['description']` pulls
the same human-readable text seen in every rule since Step 2 — the
"explanation," now displayed instead of printed. The ✅/❌ loop is
`run_all()` from Step 12, rendered instead of printed.

**Verify:**

```bash
streamlit run app.py
```

Try severity 0.95 with ICU beds at 0 — you should see
`ImmediateTreatment`, the `R1_high_severity` description, and a ❌ next
to `resource_validation`. Bump ICU beds back up to 1+ and it should
flip to ✅ live, no page reload.

---

## Where things stand

- `knowledge_graph.py` — clinical knowledge graph, rules loaded from
  `data/rules.json` (5 rules, override edges, 1 deliberate gap), done.
- `rule_engine.py` — `fire()`, `resolve()`, `static_inconsistencies()`,
  done.
- `validators.py` — all 4 checks from the architecture doc's Validator
  Chain, done.
- `tests/test_rule_engine.py` — 17 tests covering all three modules
  above, done (Steps 14–16).
- Not built yet: `demo.py`, severity model (ML), retrieval, bed
  optimizer, orchestrator, Azure deployment.
