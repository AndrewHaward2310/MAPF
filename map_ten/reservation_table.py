from __future__ import annotations

from typing import Dict, List, Tuple

Coordinate = Tuple[int, int]


class ReservationTable:
    """Tracks occupied nodes over time to avoid conflicts."""

    def __init__(self) -> None:
        self._table: Dict[Tuple[Coordinate, int], str] = {}

    def reserve(self, agent: str, path: List[Coordinate]) -> None:
        for t, node in enumerate(path):
            self._table[(node, t)] = agent

    def is_reserved(self, node: Coordinate, time: int) -> bool:
        return (node, time) in self._table

    def lock_ahead(self, agent: str, path: List[Coordinate], steps: int) -> None:
        """Reserve a prefix of ``path`` for ``steps`` time steps."""

        for t, node in enumerate(path[:steps]):
            self._table[(node, t)] = agent