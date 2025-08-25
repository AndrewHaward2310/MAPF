from __future__ import annotations

import networkx as nx
from typing import List, Tuple

Line = Tuple[Tuple[int, int], Tuple[int, int]]


def lines_to_graph(lines: List[Line]) -> nx.Graph:
    """Convert line segments into an undirected NetworkX graph."""

    graph = nx.Graph()
    for (x1, y1), (x2, y2) in lines:
        u = (x1, y1)
        v = (x2, y2)
        weight = abs(x1 - x2) + abs(y1 - y2)
        graph.add_edge(u, v, weight=weight)
    return graph