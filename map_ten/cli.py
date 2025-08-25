from __future__ import annotations

import argparse
import json
from pathlib import Path

from .graph_builder import lines_to_graph
from .map_editor import MapEditor
from .map_io import load_map, save_paths, save_map, export_occupancy_grid
from .mcf_solver import cbm_solve


def main() -> None:
    parser = argparse.ArgumentParser(description="MAPF utilities")
    sub = parser.add_subparsers(dest="cmd")

    plan_p = sub.add_parser("plan", help="Plan paths and export to JSON")
    plan_p.add_argument("input", type=Path, help="Input map file (JSON/YAML)")
    plan_p.add_argument("output", type=Path, help="Output paths JSON file")
    plan_p.add_argument(
        "-k",
        type=int,
        default=3,
        dest="k",
        help="Number of k-shortest paths",
    )

    edit_p = sub.add_parser("edit", help="Launch interactive map editor")
    edit_p.add_argument(
        "--open", dest="open", type=Path, help="Load map file on start"
    )
    edit_p.add_argument(
        "--template", dest="template", type=str, help="Load named template on start"
    )

    dataset_p = sub.add_parser(
        "dataset", help="Export geometry, grid, and graph for training"
    )
    dataset_p.add_argument("input", type=Path, help="Input map file")
    dataset_p.add_argument("output", type=Path, help="Output dataset directory")
    dataset_p.add_argument(
        "--resolution", type=int, default=40, help="Grid cell size"
    )

    args = parser.parse_args()

    if args.cmd == "plan":
        data = load_map(args.input)
        graph = lines_to_graph(data["lines"])
        agents = {
            name: (spec["start"], spec["goal"])
            for name, spec in data.get("agents", {}).items()
            if "start" in spec and "goal" in spec
        }
        paths = cbm_solve(graph, agents, k=args.k)
        save_paths(paths, args.output)
    elif args.cmd == "edit":
        editor = MapEditor()
        if getattr(args, "open", None):
            editor.load(args.open)
        elif getattr(args, "template", None):
            editor.load_template(args.template)
        editor.run()
    elif args.cmd == "dataset":
        data = load_map(args.input)
        args.output.mkdir(parents=True, exist_ok=True)
        save_map(data, args.output / "map.json")
        grid = export_occupancy_grid(data, args.resolution)
        (args.output / "grid.json").write_text(
            json.dumps({"grid": grid}, indent=2)
        )
        graph = lines_to_graph(data["lines"])
        graph_data = {
            "nodes": [list(n) for n in graph.nodes()],
            "edges": [list(e) for e in graph.edges()],
        }
        (args.output / "graph.json").write_text(
            json.dumps(graph_data, indent=2)
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()