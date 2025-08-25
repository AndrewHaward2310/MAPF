from __future__ import annotations

import itertools
from typing import Dict, List, Set, Tuple

import networkx as nx

Line = Tuple[Tuple[int, int], Tuple[int, int]]
PathType = List[Tuple[int, int]]


def k_shortest_paths(
    graph: nx.Graph,
    start: Tuple[int, int],
    goal: Tuple[int, int],
    k: int,
) -> List[PathType]:
    """Return up to ``k`` shortest simple paths between ``start`` and ``goal``."""

    generator = nx.shortest_simple_paths(graph, start, goal, weight="weight")
    return list(itertools.islice(generator, k))


def build_ten(
    graph: nx.Graph, paths_per_agent: Dict[str, List[PathType]]
) -> Tuple[nx.DiGraph, int]:
    """Build a time-expanded network from candidate paths.

    Only edges that appear in at least one candidate path are expanded to keep
    the network compact.
    """

    allowed_edges: Set[Line] = set()
    max_len = 0
    for paths in paths_per_agent.values():
        for path in paths:
            max_len = max(max_len, len(path))
            allowed_edges.update(zip(path[:-1], path[1:]))
    horizon = max_len

    ten = nx.DiGraph()
    for t in range(horizon):
        for node in graph.nodes:
            ten.add_node((node, t))
            ten.add_edge((node, t), (node, t + 1), capacity=1, weight=1)
        for u, v, data in graph.edges(data=True):
            if (u, v) in allowed_edges or (v, u) in allowed_edges:
                cost = data.get("weight", 1)
                ten.add_edge((u, t), (v, t + 1), capacity=1, weight=cost)
                ten.add_edge((v, t), (u, t + 1), capacity=1, weight=cost)
    for node in graph.nodes:
        ten.add_node((node, horizon))
    return ten, horizon