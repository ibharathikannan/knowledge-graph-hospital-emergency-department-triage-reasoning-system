"""
Draws the clinical knowledge graph with matplotlib. Shared by the
standalone visualize_graph.py script and the Streamlit app -- both just
call draw_graph() and do something different with the returned Figure.
"""
from __future__ import annotations
from streamlit_agraph import Node, Edge, Config

import matplotlib.pyplot as plt
import networkx as nx
import matplotlib.pyplot as plt
import networkx as nx
from streamlit_agraph import Node, Edge, Config



COLORS = {"rule": "#4FC7B8", "condition": "#8FB3DE", "disposition": "#E7B25C"}
NODE_SHAPES = {"rule": "dot", "condition": "dot", "disposition": "box"}
EDGE_COLORS = {"requires": "#999999", "recommends": "#E7B25C", "overrides": "#E4572E"}
EDGE_STYLES = {"requires": "solid", "recommends": "dashed", "overrides": "dotted"}
FIRED_COLOR = "#FFD54A"    # bright yellow -- fired, but didn't drive the final decision
WINNING_COLOR = "#E4572E"  # red-orange -- actually drove the decision


def draw_graph(g: nx.DiGraph, fired: list[str] | None = None, winning: list[str] | None = None):
    fired = fired or []
    winning = winning or []

    fig, ax = plt.subplots(figsize=(10, 7))
    pos = nx.spring_layout(g, seed=7, k=0.9)

    node_colors = []
    node_sizes = []
    for n in g.nodes:
        if n in winning:
            node_colors.append(WINNING_COLOR)
            node_sizes.append(2000)
        elif n in fired:
            node_colors.append(FIRED_COLOR)
            node_sizes.append(1700)
        else:
            node_colors.append(COLORS[g.nodes[n]["kind"]])
            node_sizes.append(1400)

    nx.draw_networkx_nodes(g, pos, node_color=node_colors, node_size=node_sizes, ax=ax)
    nx.draw_networkx_labels(g, pos, font_size=7, ax=ax)

    for edge_type, style in EDGE_STYLES.items():
        edges = [(u, v) for u, v, d in g.edges(data=True) if d["type"] == edge_type]
        nx.draw_networkx_edges(g, pos, edgelist=edges, style=style, connectionstyle="arc3,rad=0.08", ax=ax)

    ax.set_title("ED Triage Clinical Knowledge Graph")
    ax.axis("off")
    fig.tight_layout()
    return fig

def build_agraph(g: nx.DiGraph, fired: list[str] | None = None, winning: list[str] | None = None):
    fired = fired or []
    winning = winning or []

    # Explicit levels, not vis-network's automatic sortMethod inference --
    # the "overrides" edges (rule -> rule) mix into automatic level
    # computation alongside "requires"/"recommends" and produce an uneven
    # result. Fixed rows: rules on top, their conditions/dispositions below.
    LEVEL_BY_KIND = {"rule": 0, "condition": 1, "disposition": 1}

    nodes = []
    for n, data in g.nodes(data=True):
        kind = data["kind"]
        if n in winning:
            color, size, glow = WINNING_COLOR, 35, True
        elif n in fired:
            color, size, glow = FIRED_COLOR, 30, True
        else:
            color, size, glow = COLORS[kind], 20, False
        nodes.append(
            Node(
                id=n,
                label=n,
                size=size,
                shape=NODE_SHAPES[kind],
                color=color,
                shadow=glow,
                borderWidth=3 if glow else 1,
                level=LEVEL_BY_KIND[kind],
                font={"color": "#F5F5F5", "size": 14, "strokeWidth": 3, "strokeColor": "#000000"},
            )
        )

    edges = [
        Edge(
            source=u,
            target=v,
            color=EDGE_COLORS[d["type"]],
            dashes=(d["type"] != "requires"),
            width=2,
        )
        for u, v, d in g.edges(data=True)
    ]

    config = Config(
        width=1100,
        height=750,
        directed=True,
        physics=True,
        hierarchical=True,
    )
    # streamlit-agraph's Config correctly nests these into physics.solver /
    # layout.hierarchical.*, but ALSO dumps every extra kwarg as a flat
    # top-level duplicate -- vis-network's strict validator rejects the
    # whole options object when it hits those. Set them directly on the
    # already-correct nested dicts instead of passing them as kwargs above.
    config.physics["solver"] = "hierarchicalRepulsion"
    config.layout["hierarchical"]["direction"] = "LR"
    config.layout["hierarchical"]["sortMethod"] = "directed"
    config.groups = {}  # vis-network rejects groups=None as an invalid type

    # fit=False and parentCentralization=False were tried to chase
    # left-alignment and reverted: fit's whole job is zooming out so
    # everything stays in view, and disabling it caused real content to
    # get clipped off-canvas on narrow screens -- confirmed visually, not
    # just a pixel-alignment miss. Left at streamlit-agraph's defaults
    # (both True) so nothing gets cut off.

    return nodes, edges, config