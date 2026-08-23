"""
Draws the clinical knowledge graph with matplotlib. Shared by the
standalone visualize_graph.py script and the Streamlit app -- both just
call draw_graph() and do something different with the returned Figure.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import networkx as nx

COLORS = {
    "rule": "#4FC7B8",         # teal
    "condition": "#8FB3DE",    # blue
    "disposition": "#E7B25C",  # amber
}
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