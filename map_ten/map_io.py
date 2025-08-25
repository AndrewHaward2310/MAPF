from __future__ import annotations

from pathlib import Path
import json
import yaml
from typing import Any, Dict, List, Tuple

Line = Tuple[Tuple[int, int], Tuple[int, int]]
PathType = List[Tuple[int, int]]
Rect = Tuple[int, int, int, int]


def load_map(path: str | Path) -> Dict[str, Any]:
    """Load map description from a JSON or YAML file.

    The returned dictionary contains geometry lists (``lines``, ``nodes`` and
    ``obstacles``) alongside optional ``*_meta`` lists that mirror the geometry
    ordering and include ``id``, ``layer`` and ``attributes`` information. If
    the file lacks these lists, defaults are generated so older maps remain
    compatible. ``layers`` holds style information for each layer.
    """

    file_path = Path(path)
    if file_path.suffix in {".yml", ".yaml"}:
        data = yaml.safe_load(file_path.read_text())
    elif file_path.suffix == ".json":
        data = json.loads(file_path.read_text())
    else:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")

    layers = data.get(
        "layers", [{"name": "Default", "color": "#000000", "visible": True}]
    )

    lines: List[Line] = []
    line_meta: List[Dict[str, Any]] = []
    raw_lines = data.get("lines", [])
    if raw_lines and isinstance(raw_lines[0], dict):
        for entry in raw_lines:
            p1, p2 = entry.get("points", [[0, 0], [0, 0]])
            lines.append((tuple(p1), tuple(p2)))
            line_meta.append(
                {
                    "id": entry.get("id"),
                    "layer": entry.get("layer", "Default"),
                    "attributes": entry.get("attributes", {}),
                    "style": entry.get("style", {}),
                }
            )
    else:
        for idx, line in enumerate(raw_lines):
            lines.append(tuple(map(tuple, line)))
            line_meta.append(
                {
                    "id": idx + 1,
                    "layer": "Default",
                    "attributes": {},
                    "style": {},
                }
            )

    nodes: List[Tuple[int, int]] = []
    node_meta: List[Dict[str, Any]] = []
    raw_nodes = data.get("nodes", [])
    if raw_nodes and isinstance(raw_nodes[0], dict):
        for entry in raw_nodes:
            pt = entry.get("point", [0, 0])
            nodes.append(tuple(pt))
            node_meta.append(
                {
                    "id": entry.get("id"),
                    "layer": entry.get("layer", "Default"),
                    "attributes": entry.get("attributes", {}),
                    "style": entry.get("style", {}),
                }
            )
    else:
        for idx, pt in enumerate(raw_nodes):
            nodes.append(tuple(pt))
            node_meta.append(
                {
                    "id": idx + 1,
                    "layer": "Default",
                    "attributes": {},
                    "style": {},
                }
            )

    obstacles: List[Rect] = []
    obstacle_meta: List[Dict[str, Any]] = []
    raw_obs = data.get("obstacles", [])
    if raw_obs and isinstance(raw_obs[0], dict):
        for entry in raw_obs:
            rect = entry.get("rect", [0, 0, 0, 0])
            obstacles.append(tuple(rect))
            obstacle_meta.append(
                {
                    "id": entry.get("id"),
                    "layer": entry.get("layer", "Default"),
                    "attributes": entry.get("attributes", {}),
                    "style": entry.get("style", {}),
                }
            )
    else:
        for idx, rect in enumerate(raw_obs):
            obstacles.append(tuple(rect))
            obstacle_meta.append(
                {
                    "id": idx + 1,
                    "layer": "Default",
                    "attributes": {},
                    "style": {},
                }
            )

    agents = {
        name: {k: tuple(v[k]) for k in ("start", "goal") if k in v}
        for name, v in data.get("agents", {}).items()
    }

    return {
        "layers": layers,
        "lines": lines,
        "line_meta": line_meta,
        "nodes": nodes,
        "node_meta": node_meta,
        "obstacles": obstacles,
        "obstacle_meta": obstacle_meta,
        "agents": agents,
    }


def save_paths(paths: Dict[str, PathType], path: str | Path) -> None:
    """Save agent paths to a JSON file.

    Parameters
    ----------
    paths:
        Mapping of agent identifiers to a list of ``(x, y)`` coordinates.
    path:
        Destination file name.
    """

    file_path = Path(path)
    serialised = {k: [list(coord) for coord in v] for k, v in paths.items()}
    file_path.write_text(json.dumps({"paths": serialised}, indent=2))


def save_map(data: Dict[str, Any], path: str | Path) -> None:
    """Save map description to a JSON file including metadata and layers."""

    file_path = Path(path)

    def _combine_collection(
        geom: List[Any], meta: List[Dict[str, Any]], key: str
    ) -> List[Dict[str, Any]]:
        combined: List[Dict[str, Any]] = []
        for g, m in zip(geom, meta):
            if key == "points":
                entry = {key: [list(pt) for pt in g]}
            else:
                entry = {key: list(g)}
            entry.update(m)
            combined.append(entry)
        return combined

    serialised = {
        "layers": data.get("layers", []),
        "lines": _combine_collection(
            data.get("lines", []), data.get("line_meta", []), "points"
        ),
        "nodes": _combine_collection(
            data.get("nodes", []), data.get("node_meta", []), "point"
        ),
        "obstacles": _combine_collection(
            data.get("obstacles", []), data.get("obstacle_meta", []), "rect"
        ),
        "agents": {
            k: {key: list(coords) for key, coords in v.items()}
            for k, v in data.get("agents", {}).items()
        },
    }

    file_path.write_text(json.dumps(serialised, indent=2))


def export_occupancy_grid(
    map_data: Dict[str, Any], resolution: int
) -> List[List[int]]:
    """Return a grid of ``0`` (free) and ``1`` (occupied) cells."""

    max_x = max_y = 0
    for (x1, y1), (x2, y2) in map_data.get("lines", []):
        max_x = max(max_x, x1, x2)
        max_y = max(max_y, y1, y2)
    for x, y in map_data.get("nodes", []):
        max_x = max(max_x, x)
        max_y = max(max_y, y)
    for x1, y1, x2, y2 in map_data.get("obstacles", []):
        max_x = max(max_x, x1, x2)
        max_y = max(max_y, y1, y2)

    width = int(max_x / resolution) + 1
    height = int(max_y / resolution) + 1
    grid = [[0 for _ in range(width)] for _ in range(height)]

    for x1, y1, x2, y2 in map_data.get("obstacles", []):
        x_start = int(x1 / resolution)
        y_start = int(y1 / resolution)
        x_end = int(x2 / resolution)
        y_end = int(y2 / resolution)
        for gx in range(x_start, x_end + 1):
            for gy in range(y_start, y_end + 1):
                if 0 <= gy < height and 0 <= gx < width:
                    grid[gy][gx] = 1

    return grid