from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import networkx as nx

from .ten_builder import build_ten, k_shortest_paths
from .reservation_table import ReservationTable

Coordinate = Tuple[int, int]
AgentSpec = Tuple[Coordinate, Coordinate]
PathType = List[Coordinate]


def _extract_paths(
    flow: Dict[Tuple[Coordinate, int], Dict[Tuple[Coordinate, int], int]],
    agents: Dict[str, AgentSpec],
    horizon: int,
) -> Dict[str, PathType]:
    paths: Dict[str, PathType] = {}
    for agent, (start, _goal) in agents.items():
        node = (start, 0)
        path: PathType = [start]
        for _ in range(horizon):
            edges = flow.get(node, {})
            next_node = None
            for v, f in edges.items():
                if f > 0:
                    next_node = v
                    edges[v] -= 1
                    break
            if next_node is None:
                break
            path.append(next_node[0])
            node = next_node
        paths[agent] = path
    return paths


def _detect_conflict(
    paths: Dict[str, PathType],
) -> Optional[Tuple[str, str, Coordinate, int]]:
    max_len = max(len(p) for p in paths.values())
    for t in range(max_len):
        occupancy: Dict[Coordinate, str] = {}
        for agent, path in paths.items():
            node = path[t] if t < len(path) else path[-1]
            if node in occupancy:
                return occupancy[node], agent, node, t
            occupancy[node] = agent
    return None


def solve_mcf(
    ten: nx.DiGraph,
    agents: Dict[str, AgentSpec],
    horizon: int,
) -> Dict[str, PathType]:
    graph = ten.copy()
    for n in graph.nodes:
        graph.nodes[n]["demand"] = 0
    for agent, (start, goal) in agents.items():
        graph.nodes[(start, 0)]["demand"] -= 1
        graph.nodes[(goal, horizon)]["demand"] += 1
    _cost, flow = nx.network_simplex(graph)
    return _extract_paths(flow, agents, horizon)


def cbm_solve(
    graph: nx.Graph,
    agents: Dict[str, AgentSpec],
    k: int = 3,
) -> Dict[str, PathType]:
    """Conflict-based min-cost flow planning."""

    constraints: Dict[str, set[Tuple[Coordinate, int]]] = {a: set() for a in agents}
    reservation = ReservationTable()
    while True:
        paths_per_agent = {
            a: k_shortest_paths(graph, start, goal, k)
            for a, (start, goal) in agents.items()
        }
        ten, horizon = build_ten(graph, paths_per_agent)
        for agent, forbidden in constraints.items():
            for node, t in forbidden:
                if (node, t) in ten:
                    ten.remove_node((node, t))
        paths = solve_mcf(ten, agents, horizon)
        conflict = _detect_conflict(paths)
        if conflict is None:
            for agent, path in paths.items():
                reservation.reserve(agent, path)
            return paths
        a1, a2, node, time = conflict
        constraints[a2].add((node, time))