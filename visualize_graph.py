"""
Quick visual check of the clinical knowledge graph.
Run: python visualize_graph.py
"""
import matplotlib.pyplot as plt
import networkx as nx

from ed_triage.knowledge_graph import build_graph

COLORS = {
    "rule": "#4FC7B8",         # teal
    "condition": "#8FB3DE",    # blue
    "disposition": "#E7B25C",  # amber
}
EDGE_STYLES = {"requires": "solid", "recommends": "dashed", "overrides": "dotted"}


def main():
    g = build_graph()
    pos = nx.spring_layout(g, seed=7, k=0.9)

    node_colors = [COLORS[g.nodes[n]["kind"]] for n in g.nodes]
    nx.draw_networkx_nodes(g, pos, node_color=node_colors, node_size=1400)
    nx.draw_networkx_labels(g, pos, font_size=7)

    for edge_type, style in EDGE_STYLES.items():
        edges = [(u, v) for u, v, d in g.edges(data=True) if d["type"] == edge_type]
        nx.draw_networkx_edges(g, pos, edgelist=edges, style=style, connectionstyle="arc3,rad=0.08")

    plt.title("ED Triage Clinical Knowledge Graph")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig("graph.png", dpi=150)
    print("Saved to graph.png")
    plt.show()


if __name__ == "__main__":
    main()