"""Small, dependency-free reader for the KiCad board data used by ForgeAgent."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import math
import re
from typing import Any


@dataclass
class PCBModel:
    file: str
    segments: list[dict[str, Any]] = field(default_factory=list)
    pads: list[dict[str, Any]] = field(default_factory=list)
    vias: list[dict[str, Any]] = field(default_factory=list)
    through_holes: list[dict[str, Any]] = field(default_factory=list)
    footprints: list[dict[str, Any]] = field(default_factory=list)
    zones: list[dict[str, Any]] = field(default_factory=list)
    nets: dict[int, str] = field(default_factory=dict)
    layers: set[str] = field(default_factory=set)
    board_outline: list[dict[str, Any]] = field(default_factory=list)
    bounds: dict[str, float] | None = None
    min_trace_mm: float | None = None
    min_drill_mm: float | None = None


def _blocks(text: str, token: str) -> list[str]:
    """Return complete s-expression blocks beginning with ``(token``."""
    blocks: list[str] = []
    start = 0
    needle = f"({token}"
    while (index := text.find(needle, start)) >= 0:
        depth = 0
        quoted = escaped = False
        for end in range(index, len(text)):
            char = text[end]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    blocks.append(text[index:end + 1])
                    start = end + 1
                    break
        else:
            break
    return blocks


def _atom(text: str, name: str, default: str = "") -> str:
    match = re.search(rf'\({re.escape(name)}\s+(?:"([^"]*)"|([^\s)]+))', text)
    return (match.group(1) or match.group(2)) if match else default


def _number(text: str, name: str, default: float = 0.0) -> float:
    try:
        return float(_atom(text, name))
    except ValueError:
        return default


def _point(text: str, name: str = "at") -> tuple[float, float]:
    match = re.search(rf'\({re.escape(name)}\s+(-?[\d.]+)\s+(-?[\d.]+)', text)
    return (float(match.group(1)), float(match.group(2))) if match else (0.0, 0.0)


def _at(text: str, name: str = "at") -> tuple[float, float, float]:
    """KiCad coordinate including its optional rotation in degrees."""
    match = re.search(rf'\({re.escape(name)}\s+(-?[\d.]+)\s+(-?[\d.]+)(?:\s+(-?[\d.]+))?', text)
    return (float(match.group(1)), float(match.group(2)), float(match.group(3) or 0)) if match else (0.0, 0.0, 0.0)


def _net(model: PCBModel, block: str) -> tuple[int, str]:
    match = re.search(r'\(net\s+(\d+)(?:\s+"([^"]*)")?', block)
    if not match:
        return 0, ""
    number = int(match.group(1))
    return number, match.group(2) if match.group(2) is not None else model.nets.get(number, "")


def _layers(block: str) -> list[str]:
    match = re.search(r'\(layers\s+([^)]*)\)', block)
    return [a or b for a, b in re.findall(r'"([^"]+)"|([^\s]+)', match.group(1))] if match else []


def _parse_kicad_text(name: str, text: str) -> PCBModel:
    model = PCBModel(file=name)
    for block in _blocks(text, "net"):
        match = re.match(r'\(net\s+(\d+)\s+"([^"]*)"', block)
        if match:
            model.nets[int(match.group(1))] = match.group(2)

    for index, block in enumerate(_blocks(text, "footprint"), 1):
        reference_match = re.search(r'\(fp_text\s+reference\s+"([^"]+)"', block) or re.search(r'\(property\s+"Reference"\s+"([^"]+)"', block)
        reference = reference_match.group(1) if reference_match else f"FP{index}"
        value_match = re.search(r'\(property\s+"Value"\s+"([^"]+)"', block) or re.search(r'\(fp_text\s+value\s+"([^"]+)"', block)
        x, y, footprint_angle = _at(block)
        model.footprints.append({"reference": reference, "value": value_match.group(1) if value_match else "", "x": x, "y": y, "rotation_deg": footprint_angle, "layer": _atom(block, "layer")})
        for pad_index, pad in enumerate(_blocks(block, "pad"), 1):
            head = re.match(r'\(pad\s+"([^"]*)"\s+([^\s)]+)', pad)
            if not head:
                continue
            number, pad_type = head.groups()
            local_x, local_y, pad_angle = _at(pad)
            radians = math.radians(footprint_angle)
            # KiCad board coordinates use a downward Y axis, so positive
            # footprint rotation is clockwise in this coordinate system.
            pad_x = x + local_x * math.cos(radians) + local_y * math.sin(radians)
            pad_y = y - local_x * math.sin(radians) + local_y * math.cos(radians)
            size = re.search(r'\(size\s+([\d.]+)\s+([\d.]+)', pad)
            net, net_name = _net(model, pad)
            drill = _number(pad, "drill")
            pad_layers = _layers(pad)
            raw_size_x, raw_size_y = (float(size.group(1)), float(size.group(2))) if size else (0.0, 0.0)
            orientation = math.radians(footprint_angle + pad_angle)
            # Axis-aligned envelope of a rotated rectangular pad.  It remains
            # conservative without pretending unsupported custom pads are exact.
            size_x = abs(raw_size_x * math.cos(orientation)) + abs(raw_size_y * math.sin(orientation))
            size_y = abs(raw_size_x * math.sin(orientation)) + abs(raw_size_y * math.cos(orientation))
            pad_id = f"{reference}.{number or pad_index}"
            if any(existing["id"] == pad_id for existing in model.pads):
                pad_id = f"{pad_id}:{pad_index}"
            item = {"id": pad_id, "reference": reference, "number": number, "type": pad_type,
                    "x": pad_x, "y": pad_y, "size_x_mm": size_x,
                    "size_y_mm": size_y, "drill_mm": drill, "layers": pad_layers,
                    "layer": pad_layers[0] if pad_layers else "", "net": net, "net_name": net_name}
            model.pads.append(item)
            model.layers.update(pad_layers)
            if drill > 0:
                model.through_holes.append(item)

    for index, block in enumerate(_blocks(text, "via"), 1):
        if re.match(r'\(via\s+from', block):
            continue
        x, y = _point(block)
        net, net_name = _net(model, block)
        layers = _layers(block)
        # KiCad encodes a through-via span as F.Cu/B.Cu endpoints.  Mark it
        # explicitly so rules can compare it with pads on any copper layer.
        if "F.Cu" in layers and "B.Cu" in layers:
            layers = [*layers, "*.Cu"]
        model.vias.append({"id": f"via-{index}", "x": x, "y": y, "size_mm": _number(block, "size"), "drill_mm": _number(block, "drill"), "layers": layers, "net": net, "net_name": net_name})
        model.layers.update(layers)

    for index, block in enumerate(_blocks(text, "segment"), 1):
        start, end = _point(block, "start"), _point(block, "end")
        net, net_name = _net(model, block)
        layer = _atom(block, "layer")
        model.segments.append({"id": f"seg-{index}", "x1": start[0], "y1": start[1], "x2": end[0], "y2": end[1], "width_mm": _number(block, "width"), "layer": layer, "net": net, "net_name": net_name})
        if layer:
            model.layers.add(layer)

    for index, block in enumerate(_blocks(text, "zone"), 1):
        net, net_name = _net(model, block)
        points = [(float(x), float(y)) for x, y in re.findall(r'\(xy\s+(-?[\d.]+)\s+(-?[\d.]+)\)', block)]
        model.zones.append({"id": f"zone-{index}", "net": net, "net_name": net_name, "layer": _atom(block, "layer"), "points": points})

    outline_points: list[tuple[float, float]] = []
    for block in _blocks(text, "gr_line"):
        if _atom(block, "layer") != "Edge.Cuts":
            continue
        start, end = _point(block, "start"), _point(block, "end")
        model.board_outline.append({"type": "line", "start": start, "end": end})
        outline_points.extend((start, end))
    # Rectangular Edge.Cuts are common in generated KiCad boards. Expand them
    # to their physical line segments; DFM never falls back to bbox distance.
    for block in _blocks(text, "gr_rect"):
        if _atom(block, "layer") != "Edge.Cuts":
            continue
        start, end = _point(block, "start"), _point(block, "end")
        corners = [(start[0],start[1]),(end[0],start[1]),end,(start[0],end[1])]
        for first, second in zip(corners, corners[1:]+corners[:1]):
            model.board_outline.append({"type": "line", "start": first, "end": second})
        outline_points.extend(corners)
    if outline_points:
        xs, ys = zip(*outline_points)
        model.bounds = {"min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys), "width_mm": max(xs) - min(xs), "height_mm": max(ys) - min(ys)}
    if model.segments:
        model.min_trace_mm = min(segment["width_mm"] for segment in model.segments)
    drilled = [hole["drill_mm"] for hole in model.through_holes + model.vias if hole["drill_mm"] > 0]
    if drilled:
        model.min_drill_mm = min(drilled)
    return model


def parse_kicad_pcb(name: str | Path, content: str | bytes | None = None) -> PCBModel:
    """Parse an uploaded KiCad board or a board available on disk."""
    if content is None:
        path = Path(name)
        content = path.read_text(encoding="utf-8", errors="replace")
        name = str(path)
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    return _parse_kicad_text(str(name), content)


parse_kicad_board = parse_kicad_pcb
