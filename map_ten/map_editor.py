from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, simpledialog, colorchooser
from typing import Any, Dict, List, Tuple
from dataclasses import dataclass
from pathlib import Path

from .map_io import load_map, save_map


@dataclass
class Layer:
    name: str
    color: str
    visible: bool = True


class MapEditor:
    """Simple Tkinter-based editor for creating MAPF maps."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("MAPF Map Editor")

        self.mode = tk.StringVar(value="line")
        toolbar = tk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        for value, text in [
            ("select", "Select"),
            ("line", "Line"),
            ("node", "Node"),
            ("obstacle", "Obstacle"),
            ("start", "AGV Start"),
            ("goal", "Goal Cell"),
        ]:
            tk.Radiobutton(toolbar, text=text, variable=self.mode, value=value).pack(
                side=tk.LEFT
            )
        tk.Button(toolbar, text="Undo", command=self.undo).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Clear", command=self.clear).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Delete", command=self.delete_selected).pack(
            side=tk.LEFT
        )
        tk.Button(toolbar, text="Template", command=self.load_template).pack(
            side=tk.LEFT
        )
        tk.Button(toolbar, text="Import", command=self.import_map).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Export", command=self.export).pack(side=tk.LEFT)

        tk.Label(toolbar, text="Shape:").pack(side=tk.LEFT, padx=(10, 0))
        self.shape = tk.StringVar(value="None")
        tk.OptionMenu(
            toolbar,
            self.shape,
            "None",
            "H-Line",
            "V-Line",
            "Cross",
            "Obstacle",
        ).pack(side=tk.LEFT)
        tk.Label(toolbar, text="W:").pack(side=tk.LEFT, padx=(10, 0))
        self.shape_w = tk.IntVar(value=40)
        tk.Entry(toolbar, textvariable=self.shape_w, width=4).pack(side=tk.LEFT)
        tk.Label(toolbar, text="H:").pack(side=tk.LEFT)
        self.shape_h = tk.IntVar(value=40)
        tk.Entry(toolbar, textvariable=self.shape_h, width=4).pack(side=tk.LEFT)

        self.canvas = tk.Canvas(self.root, width=800, height=600, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.grid_size = 40
        self.zoom = 1.0
        self.grid_var = tk.IntVar(value=self.grid_size)
        tk.Label(toolbar, text="Grid:").pack(side=tk.LEFT, padx=(10, 0))
        grid_entry = tk.Entry(toolbar, textvariable=self.grid_var, width=4)
        grid_entry.pack(side=tk.LEFT)
        grid_entry.bind("<Return>", lambda _e: self.update_grid())
        self.show_grid = tk.BooleanVar(value=True)
        tk.Checkbutton(
            toolbar, text="Show Grid", variable=self.show_grid, command=self.update_grid
        ).pack(side=tk.LEFT)
        self.draw_grid()

        tk.Label(toolbar, text="Layer:").pack(side=tk.LEFT, padx=(10, 0))
        self.layers: List[Layer] = [Layer("Default", "#000000")]
        self.layer_var = tk.StringVar(value=self.layers[0].name)
        self.layer_menu = tk.OptionMenu(
            toolbar, self.layer_var, *(layer.name for layer in self.layers)
        )
        self.layer_menu.pack(side=tk.LEFT)
        tk.Button(toolbar, text="Layers", command=self.manage_layers).pack(
            side=tk.LEFT
        )
        tk.Button(toolbar, text="Props", command=self.edit_properties).pack(
            side=tk.LEFT
        )

        self.lines: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []
        self.line_meta: List[Dict[str, Any]] = []
        self.nodes: List[Tuple[int, int]] = []
        self.node_meta: List[Dict[str, Any]] = []
        self.obstacles: List[Tuple[int, int, int, int]] = []
        self.obstacle_meta: List[Dict[str, Any]] = []
        self.agents: Dict[str, Dict[str, Tuple[int, int]]] = {}
        self.history: List[Tuple[str, int, Any]] = []
        self.item_map: Dict[int, Tuple[str, Any]] = {}
        self.layer_items: Dict[str, List[int]] = {self.layers[0].name: []}
        self.next_id = 1

        self._line_start: Tuple[int, int] | None = None
        self._rect_start: Tuple[int, int] | None = None
        self.selected_item: int | None = None
        self._drag_start: Tuple[int, int] | None = None

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-2>", lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind(
            "<B2-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1)
        )
        self.canvas.bind("<ButtonRelease-2>", lambda _e: self.draw_grid())

    def refresh_layer_menu(self) -> None:
        menu = self.layer_menu["menu"]
        menu.delete(0, "end")
        for layer in self.layers:
            menu.add_command(
                label=layer.name, command=lambda n=layer.name: self.layer_var.set(n)
            )

    def get_layer(self, name: str) -> Layer:
        for layer in self.layers:
            if layer.name == name:
                return layer
        return self.layers[0]

    def add_layer(self) -> None:
        name = simpledialog.askstring("Layer", "Name:", parent=self.root)
        if not name:
            return
        color = colorchooser.askcolor()[1] or "#000000"
        self.layers.append(Layer(name, color))
        self.layer_items[name] = []
        self.refresh_layer_menu()

    def rename_layer(self, layer: Layer) -> None:
        new = simpledialog.askstring(
            "Rename Layer", "Name:", initialvalue=layer.name, parent=self.root
        )
        if not new:
            return
        old = layer.name
        layer.name = new
        if self.layer_var.get() == old:
            self.layer_var.set(new)
        self.layer_items[new] = self.layer_items.pop(old)
        for meta in self.line_meta:
            if meta["layer"] == old:
                meta["layer"] = new
        for meta in self.node_meta:
            if meta["layer"] == old:
                meta["layer"] = new
        for meta in self.obstacle_meta:
            if meta["layer"] == old:
                meta["layer"] = new
        self.refresh_layer_menu()

    def change_layer_color(self, layer: Layer) -> None:
        color = colorchooser.askcolor(color=layer.color)[1]
        if not color:
            return
        layer.color = color
        for item in self.layer_items.get(layer.name, []):
            kind, _ = self.item_map.get(item, (None, None))
            if kind == "line":
                self.canvas.itemconfigure(item, fill=color)
            elif kind == "node":
                self.canvas.itemconfigure(item, fill=color)
            elif kind == "obstacle":
                self.canvas.itemconfigure(item, outline=color, fill=color)
        for meta in self.line_meta:
            if meta["layer"] == layer.name:
                meta.setdefault("style", {})["color"] = color
        for meta in self.node_meta:
            if meta["layer"] == layer.name:
                meta.setdefault("style", {})["color"] = color
        for meta in self.obstacle_meta:
            if meta["layer"] == layer.name:
                meta.setdefault("style", {})["fill"] = color

    def set_layer_visibility(self, layer: Layer, visible: bool) -> None:
        layer.visible = visible
        state = tk.NORMAL if visible else tk.HIDDEN
        for item in self.layer_items.get(layer.name, []):
            self.canvas.itemconfigure(item, state=state)

    def manage_layers(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Layers")
        for layer in self.layers:
            row = tk.Frame(win)
            row.pack(fill=tk.X)
            var = tk.BooleanVar(value=layer.visible)
            tk.Checkbutton(
                row,
                text=layer.name,
                variable=var,
                command=lambda lyr=layer, v=var: self.set_layer_visibility(
                    lyr, v.get()
                ),
            ).pack(side=tk.LEFT)
            tk.Button(
                row,
                text="Color",
                command=lambda lyr=layer: self.change_layer_color(lyr),
            ).pack(side=tk.LEFT)
            tk.Button(
                row,
                text="Rename",
                command=lambda lyr=layer: self.rename_layer(lyr),
            ).pack(side=tk.LEFT)
        tk.Button(
            win,
            text="Add",
            command=lambda: [self.add_layer(), win.destroy(), self.manage_layers()],
        ).pack(fill=tk.X)

    def edit_properties(self) -> None:
        if self.selected_item is None:
            return
        kind, info = self.item_map.get(self.selected_item, (None, None))
        meta: Dict[str, Any] | None = None
        if kind == "line":
            meta = self.line_meta[info]
        elif kind == "node":
            meta = self.node_meta[info]
        elif kind == "obstacle":
            meta = self.obstacle_meta[info]
        if meta is None:
            return
        current = ",".join(f"{k}={v}" for k, v in meta.get("attributes", {}).items())
        result = simpledialog.askstring(
            "Attributes", "key=value,...", initialvalue=current, parent=self.root
        )
        if result is None:
            return
        attrs: Dict[str, Any] = {}
        for pair in result.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                attrs[k.strip()] = v.strip()
        meta["attributes"] = attrs
    def to_world(self, x: float, y: float) -> Tuple[float, float]:
        return self.canvas.canvasx(x) / self.zoom, self.canvas.canvasy(y) / self.zoom

    def to_screen(self, x: float, y: float) -> Tuple[int, int]:
        return int(round(x * self.zoom)), int(round(y * self.zoom))

    def on_click(self, event: tk.Event) -> None:  # type: ignore[override]
        wx, wy = self.to_world(event.x, event.y)
        x, y = self.snap(wx, wy)
        sx, sy = self.to_screen(x, y)
        if self.shape.get() != "None":
            self.place_shape(x, y)
            return
        mode = self.mode.get()
        if mode == "select":
            items = self.canvas.find_closest(event.x, event.y)
            if items:
                self.selected_item = items[0]
                self._drag_start = (event.x, event.y)
        elif mode == "line":
            if self._line_start is None:
                self._line_start = (x, y)
            else:
                sx1, sy1 = self.to_screen(*self._line_start)
                layer = self.get_layer(self.layer_var.get())
                item = self.canvas.create_line(
                    sx1,
                    sy1,
                    sx,
                    sy,
                    fill=layer.color,
                    state=tk.NORMAL if layer.visible else tk.HIDDEN,
                )
                self.lines.append((self._line_start, (x, y)))
                self.line_meta.append(
                    {
                        "id": self.next_id,
                        "layer": layer.name,
                        "attributes": {},
                        "style": {"color": layer.color},
                    }
                )
                index = len(self.lines) - 1
                self.layer_items.setdefault(layer.name, []).append(item)
                self.item_map[item] = ("line", index)
                self.history.append(("line", item, None))
                self.next_id += 1
                self._line_start = None
        elif mode == "node":
            r = 3
            layer = self.get_layer(self.layer_var.get())
            item = self.canvas.create_oval(
                sx - r,
                sy - r,
                sx + r,
                sy + r,
                fill=layer.color,
                state=tk.NORMAL if layer.visible else tk.HIDDEN,
            )
            self.nodes.append((x, y))
            self.node_meta.append(
                {
                    "id": self.next_id,
                    "layer": layer.name,
                    "attributes": {},
                    "style": {"color": layer.color},
                }
            )
            self.layer_items.setdefault(layer.name, []).append(item)
            self.item_map[item] = ("node", len(self.nodes) - 1)
            self.history.append(("node", item, None))
            self.next_id += 1
        elif mode == "obstacle":
            self._rect_start = (x, y)
        elif mode in {"start", "goal"}:
            name = simpledialog.askstring("Agent", "Name:", parent=self.root)
            if name:
                size = 4
                color = "green" if mode == "start" else "red"
                item = self.canvas.create_rectangle(
                    sx - size,
                    sy - size,
                    sx + size,
                    sy + size,
                    fill=color,
                )
                self.agents.setdefault(name, {})[mode] = (x, y)
                self.item_map[item] = (mode, name)
                self.history.append((mode, item, name))

    def on_release(self, event: tk.Event) -> None:  # type: ignore[override]
        mode = self.mode.get()
        if mode == "obstacle" and self._rect_start is not None:
            x1, y1 = self._rect_start
            wx, wy = self.to_world(event.x, event.y)
            x2, y2 = self.snap(wx, wy)
            sx1, sy1 = self.to_screen(x1, y1)
            sx2, sy2 = self.to_screen(x2, y2)
            layer = self.get_layer(self.layer_var.get())
            item = self.canvas.create_rectangle(
                sx1,
                sy1,
                sx2,
                sy2,
                outline=layer.color,
                fill=layer.color,
                state=tk.NORMAL if layer.visible else tk.HIDDEN,
            )
            rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            self.obstacles.append(rect)
            self.obstacle_meta.append(
                {
                    "id": self.next_id,
                    "layer": layer.name,
                    "attributes": {},
                    "style": {"fill": layer.color},
                }
            )
            index = len(self.obstacles) - 1
            self.layer_items.setdefault(layer.name, []).append(item)
            self.item_map[item] = ("obstacle", index)
            self.history.append(("obstacle", item, None))
            self.next_id += 1
            self._rect_start = None
        elif mode == "select" and self.selected_item is not None:
            coords = self.canvas.coords(self.selected_item)
            kind, info = self.item_map.get(self.selected_item, (None, None))
            if kind == "line":
                x1, y1, x2, y2 = coords
                x1w, y1w = self.to_world(x1, y1)
                x2w, y2w = self.to_world(x2, y2)
                x1s, y1s = self.snap(x1w, y1w)
                x2s, y2s = self.snap(x2w, y2w)
                sx1, sy1 = self.to_screen(x1s, y1s)
                sx2, sy2 = self.to_screen(x2s, y2s)
                self.canvas.coords(self.selected_item, sx1, sy1, sx2, sy2)
                self.lines[info] = ((x1s, y1s), (x2s, y2s))
            elif kind == "node":
                x1, y1, x2, y2 = coords
                r = (x2 - x1) / 2
                cxw, cyw = self.to_world(x1 + r, y1 + r)
                cxs, cys = self.snap(cxw, cyw)
                sxc, syc = self.to_screen(cxs, cys)
                self.canvas.coords(
                    self.selected_item, sxc - r, syc - r, sxc + r, syc + r
                )
                self.nodes[info] = (int(cxs), int(cys))
            elif kind == "obstacle":
                x1, y1, x2, y2 = coords
                x1w, y1w = self.to_world(x1, y1)
                x2w, y2w = self.to_world(x2, y2)
                x1s, y1s = self.snap(x1w, y1w)
                x2s, y2s = self.snap(x2w, y2w)
                sx1, sy1 = self.to_screen(x1s, y1s)
                sx2, sy2 = self.to_screen(x2s, y2s)
                self.canvas.coords(self.selected_item, sx1, sy1, sx2, sy2)
                self.obstacles[info] = (
                    min(x1s, x2s),
                    min(y1s, y2s),
                    max(x1s, x2s),
                    max(y1s, y2s),
                )
            elif kind in {"start", "goal"}:
                x1, y1, x2, y2 = coords
                size = (x2 - x1) / 2
                cxw, cyw = self.to_world(x1 + size, y1 + size)
                cxs, cys = self.snap(cxw, cyw)
                sxc, syc = self.to_screen(cxs, cys)
                self.canvas.coords(
                    self.selected_item, sxc - size, syc - size, sxc + size, syc + size
                )
                name = info
                self.agents.setdefault(name, {})[kind] = (int(cxs), int(cys))
            self.selected_item = None
            self._drag_start = None

    def place_shape(self, x: int, y: int) -> None:
        g = self.grid_size
        try:
            w = max(1, int(self.shape_w.get()))
        except tk.TclError:
            w = g
        try:
            h = max(1, int(self.shape_h.get()))
        except tk.TclError:
            h = g
        shape = self.shape.get()
        if shape == "H-Line":
            x2 = x + w
            sx1, sy1 = self.to_screen(x, y)
            sx2, sy2 = self.to_screen(x2, y)
            layer = self.get_layer(self.layer_var.get())
            item = self.canvas.create_line(
                sx1,
                sy1,
                sx2,
                sy2,
                fill=layer.color,
                state=tk.NORMAL if layer.visible else tk.HIDDEN,
            )
            self.lines.append(((x, y), (x2, y)))
            self.line_meta.append(
                {
                    "id": self.next_id,
                    "layer": layer.name,
                    "attributes": {},
                    "style": {"color": layer.color},
                }
            )
            self.layer_items.setdefault(layer.name, []).append(item)
            self.item_map[item] = ("line", len(self.lines) - 1)
            self.history.append(("line", item, None))
            self.next_id += 1
        elif shape == "V-Line":
            y2 = y + h
            sx1, sy1 = self.to_screen(x, y)
            sx2, sy2 = self.to_screen(x, y2)
            layer = self.get_layer(self.layer_var.get())
            item = self.canvas.create_line(
                sx1,
                sy1,
                sx2,
                sy2,
                fill=layer.color,
                state=tk.NORMAL if layer.visible else tk.HIDDEN,
            )
            self.lines.append(((x, y), (x, y2)))
            self.line_meta.append(
                {
                    "id": self.next_id,
                    "layer": layer.name,
                    "attributes": {},
                    "style": {"color": layer.color},
                }
            )
            self.layer_items.setdefault(layer.name, []).append(item)
            self.item_map[item] = ("line", len(self.lines) - 1)
            self.history.append(("line", item, None))
            self.next_id += 1
        elif shape == "Cross":
            half_w = w // 2
            half_h = h // 2
            # Horizontal
            hx1, hy1 = x - half_w, y
            hx2, hy2 = x + half_w, y
            sx1, sy1 = self.to_screen(hx1, hy1)
            sx2, sy2 = self.to_screen(hx2, hy2)
            layer = self.get_layer(self.layer_var.get())
            item = self.canvas.create_line(
                sx1,
                sy1,
                sx2,
                sy2,
                fill=layer.color,
                state=tk.NORMAL if layer.visible else tk.HIDDEN,
            )
            self.lines.append(((hx1, hy1), (hx2, hy2)))
            self.line_meta.append(
                {
                    "id": self.next_id,
                    "layer": layer.name,
                    "attributes": {},
                    "style": {"color": layer.color},
                }
            )
            self.layer_items.setdefault(layer.name, []).append(item)
            self.item_map[item] = ("line", len(self.lines) - 1)
            self.history.append(("line", item, None))
            self.next_id += 1
            # Vertical
            vx1, vy1 = x, y - half_h
            vx2, vy2 = x, y + half_h
            sx1, sy1 = self.to_screen(vx1, vy1)
            sx2, sy2 = self.to_screen(vx2, vy2)
            item = self.canvas.create_line(
                sx1,
                sy1,
                sx2,
                sy2,
                fill=layer.color,
                state=tk.NORMAL if layer.visible else tk.HIDDEN,
            )
            self.lines.append(((vx1, vy1), (vx2, vy2)))
            self.line_meta.append(
                {
                    "id": self.next_id,
                    "layer": layer.name,
                    "attributes": {},
                    "style": {"color": layer.color},
                }
            )
            self.layer_items.setdefault(layer.name, []).append(item)
            self.item_map[item] = ("line", len(self.lines) - 1)
            self.history.append(("line", item, None))
            self.next_id += 1
        elif shape == "Obstacle":
            x2 = x + w
            y2 = y + h
            sx1, sy1 = self.to_screen(x, y)
            sx2, sy2 = self.to_screen(x2, y2)
            layer = self.get_layer(self.layer_var.get())
            item = self.canvas.create_rectangle(
                sx1,
                sy1,
                sx2,
                sy2,
                outline=layer.color,
                fill=layer.color,
                state=tk.NORMAL if layer.visible else tk.HIDDEN,
            )
            self.obstacles.append((x, y, x2, y2))
            self.obstacle_meta.append(
                {
                    "id": self.next_id,
                    "layer": layer.name,
                    "attributes": {},
                    "style": {"fill": layer.color},
                }
            )
            self.layer_items.setdefault(layer.name, []).append(item)
            self.item_map[item] = ("obstacle", len(self.obstacles) - 1)
            self.history.append(("obstacle", item, None))
            self.next_id += 1

    def on_drag(self, event: tk.Event) -> None:  # type: ignore[override]
        if (
            self.mode.get() == "select"
            and self.selected_item is not None
            and self._drag_start is not None
        ):
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            self.canvas.move(self.selected_item, dx, dy)
            self._drag_start = (event.x, event.y)

    def on_zoom(self, event: tk.Event) -> None:  # type: ignore[override]
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom *= factor
        self.canvas.delete("grid")
        self.canvas.scale("all", 0, 0, factor, factor)
        self.draw_grid()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def snap(self, x: int, y: int) -> Tuple[int, int]:
        g = self.grid_size
        return int(g * round(x / g)), int(g * round(y / g))

    def draw_grid(self) -> None:
        if not self.show_grid.get():
            return
        self.canvas.delete("grid")
        g = self.grid_size
        left = int(self.canvas.canvasx(0) / self.zoom)
        right = int(self.canvas.canvasx(self.canvas.winfo_width()) / self.zoom) + g
        top = int(self.canvas.canvasy(0) / self.zoom)
        bottom = int(
            self.canvas.canvasy(self.canvas.winfo_height()) / self.zoom
        ) + g
        for x in range(left - left % g, right, g):
            sx1, sy1 = self.to_screen(x, top)
            sx2, sy2 = self.to_screen(x, bottom)
            self.canvas.create_line(sx1, sy1, sx2, sy2, fill="#eee", tags="grid")
        for y in range(top - top % g, bottom, g):
            sx1, sy1 = self.to_screen(left, y)
            sx2, sy2 = self.to_screen(right, y)
            self.canvas.create_line(sx1, sy1, sx2, sy2, fill="#eee", tags="grid")

    def update_grid(self) -> None:
        try:
            self.grid_size = max(5, int(self.grid_var.get()))
        except tk.TclError:
            return
        self.canvas.delete("grid")
        self.draw_grid()

    def clear(self) -> None:
        self.canvas.delete("all")
        self.draw_grid()
        self.lines.clear()
        self.line_meta.clear()
        self.nodes.clear()
        self.node_meta.clear()
        self.obstacles.clear()
        self.obstacle_meta.clear()
        self.agents.clear()
        self.history.clear()
        self.item_map.clear()
        self.layer_items = {layer.name: [] for layer in self.layers}
        self.next_id = 1
        self._line_start = None
        self._rect_start = None
        self.selected_item = None

    def undo(self) -> None:
        if not self.history:
            return
        kind, item, info = self.history.pop()
        self.canvas.delete(item)
        self.item_map.pop(item, None)
        if kind == "line" and self.lines:
            meta = self.line_meta.pop()
            self.lines.pop()
            self.layer_items.get(meta["layer"], []).remove(item)
        elif kind == "node" and self.nodes:
            meta = self.node_meta.pop()
            self.nodes.pop()
            self.layer_items.get(meta["layer"], []).remove(item)
        elif kind == "obstacle" and self.obstacles:
            meta = self.obstacle_meta.pop()
            self.obstacles.pop()
            self.layer_items.get(meta["layer"], []).remove(item)
        elif kind in {"start", "goal"}:
            name = info  # type: ignore[assignment]
            agent = self.agents.get(name, {})
            agent.pop(kind, None)
            if not agent:
                self.agents.pop(name, None)

    def delete_selected(self) -> None:
        if self.selected_item is None:
            return
        kind, info = self.item_map.pop(self.selected_item, (None, None))
        self.canvas.delete(self.selected_item)
        if kind == "line":
            index = info
            meta = self.line_meta.pop(index)
            self.lines.pop(index)
            self.layer_items.get(meta["layer"], []).remove(self.selected_item)
            for item, (k, idx) in list(self.item_map.items()):
                if k == "line" and idx > index:
                    self.item_map[item] = (k, idx - 1)
        elif kind == "node":
            index = info
            meta = self.node_meta.pop(index)
            self.nodes.pop(index)
            self.layer_items.get(meta["layer"], []).remove(self.selected_item)
            for item, (k, idx) in list(self.item_map.items()):
                if k == "node" and idx > index:
                    self.item_map[item] = (k, idx - 1)
        elif kind == "obstacle":
            index = info
            meta = self.obstacle_meta.pop(index)
            self.obstacles.pop(index)
            self.layer_items.get(meta["layer"], []).remove(self.selected_item)
            for item, (k, idx) in list(self.item_map.items()):
                if k == "obstacle" and idx > index:
                    self.item_map[item] = (k, idx - 1)
        elif kind in {"start", "goal"}:
            name = info
            agent = self.agents.get(name, {})
            agent.pop(kind, None)
            if not agent:
                self.agents.pop(name, None)
        self.selected_item = None

    def export(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")]
        )
        if path:
            data = {
                "layers": [layer.__dict__ for layer in self.layers],
                "lines": self.lines,
                "line_meta": self.line_meta,
                "nodes": self.nodes,
                "node_meta": self.node_meta,
                "obstacles": self.obstacles,
                "obstacle_meta": self.obstacle_meta,
                "agents": self.agents,
            }
            save_map(data, path)

    def load(self, path: str | Path) -> None:
        data = load_map(path)
        self.clear()
        self.layers = [
            Layer(**layer_spec)
            for layer_spec in data.get(
                "layers",
                [{"name": "Default", "color": "#000000", "visible": True}],
            )
        ]
        self.layer_var.set(self.layers[0].name)
        self.layer_items = {layer.name: [] for layer in self.layers}
        self.refresh_layer_menu()
        metas = (
            data.get("line_meta", [])
            + data.get("node_meta", [])
            + data.get("obstacle_meta", [])
        )
        if metas:
            self.next_id = max(m.get("id", 0) for m in metas) + 1
        for line, meta in zip(data.get("lines", []), data.get("line_meta", [])):
            (x1, y1), (x2, y2) = line
            layer = self.get_layer(meta.get("layer", "Default"))
            sx1, sy1 = self.to_screen(x1, y1)
            sx2, sy2 = self.to_screen(x2, y2)
            item = self.canvas.create_line(
                sx1,
                sy1,
                sx2,
                sy2,
                fill=layer.color,
                state=tk.NORMAL if layer.visible else tk.HIDDEN,
            )
            self.lines.append(((x1, y1), (x2, y2)))
            self.line_meta.append(meta)
            self.layer_items.setdefault(layer.name, []).append(item)
            self.item_map[item] = ("line", len(self.lines) - 1)
            self.history.append(("line", item, None))
        for (x, y), meta in zip(data.get("nodes", []), data.get("node_meta", [])):
            r = 3
            layer = self.get_layer(meta.get("layer", "Default"))
            sx, sy = self.to_screen(x, y)
            item = self.canvas.create_oval(
                sx - r,
                sy - r,
                sx + r,
                sy + r,
                fill=layer.color,
                state=tk.NORMAL if layer.visible else tk.HIDDEN,
            )
            self.nodes.append((x, y))
            self.node_meta.append(meta)
            self.layer_items.setdefault(layer.name, []).append(item)
            self.item_map[item] = ("node", len(self.nodes) - 1)
            self.history.append(("node", item, None))
        for (x1, y1, x2, y2), meta in zip(
            data.get("obstacles", []), data.get("obstacle_meta", [])
        ):
            layer = self.get_layer(meta.get("layer", "Default"))
            sx1, sy1 = self.to_screen(x1, y1)
            sx2, sy2 = self.to_screen(x2, y2)
            item = self.canvas.create_rectangle(
                sx1,
                sy1,
                sx2,
                sy2,
                outline=layer.color,
                fill=layer.color,
                state=tk.NORMAL if layer.visible else tk.HIDDEN,
            )
            self.obstacles.append((x1, y1, x2, y2))
            self.obstacle_meta.append(meta)
            self.layer_items.setdefault(layer.name, []).append(item)
            self.item_map[item] = ("obstacle", len(self.obstacles) - 1)
            self.history.append(("obstacle", item, None))
        for name, agent in data.get("agents", {}).items():
            size = 4
            self.agents[name] = {}
            if "start" in agent:
                sx, sy = agent["start"]
                ssx, ssy = self.to_screen(sx, sy)
                s_item = self.canvas.create_rectangle(
                    ssx - size, ssy - size, ssx + size, ssy + size, fill="green"
                )
                self.agents[name]["start"] = (sx, sy)
                self.item_map[s_item] = ("start", name)
                self.history.append(("start", s_item, name))
            if "goal" in agent:
                gx, gy = agent["goal"]
                sgx, sgy = self.to_screen(gx, gy)
                g_item = self.canvas.create_rectangle(
                    sgx - size, sgy - size, sgx + size, sgy + size, fill="red"
                )
                self.agents[name]["goal"] = (gx, gy)
                self.item_map[g_item] = ("goal", name)
                self.history.append(("goal", g_item, name))

    def load_template(self, name: str | None = None) -> None:
        templates_dir = Path(__file__).with_name("templates")
        if name is None:
            path = filedialog.askopenfilename(
                initialdir=templates_dir, filetypes=[("JSON", "*.json")]
            )
            if not path:
                return
        else:
            path = templates_dir / f"{name}.json"
            if not Path(path).exists():
                return
        self.load(path)

    def import_map(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Map files", "*.json *.yml *.yaml")]
        )
        if path:
            self.load(path)

    def run(self) -> None:
        self.root.mainloop()


__all__ = ["MapEditor"]