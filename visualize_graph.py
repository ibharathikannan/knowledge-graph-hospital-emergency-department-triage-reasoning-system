"""
Quick visual check of the clinical knowledge graph.
Run: python visualize_graph.py
"""
import matplotlib.pyplot as plt

from ed_triage.knowledge_graph import build_graph
from ed_triage.graph_viz import draw_graph


def main():
    g = build_graph()
    fig = draw_graph(g)
    fig.savefig("graph.png", dpi=150)
    print("Saved to graph.png")
    plt.show()


if __name__ == "__main__":
    main()