"""Deterministic, net-aware KiCad manufacturing checks.

These rules deliberately report only measurable, cross-net copper constraints.
Unresolved source geometry is represented as a warning, never as a short.
"""
from __future__ import annotations

import math
from .models import Finding
from .rules import GENERIC_DFM_POLICY

EPS = 1e-9


def electrically_same_net(a, b):
    """True only where KiCad supplied an electrical net identity for both."""
    return a.get("net") is not None and b.get("net") is not None and a.get("net") == b.get("net")


def _copper_layers(item):
    return set(item.get("layers") or ([item["layer"]] if item.get("layer") else []))


def _layers_intersect(a, b):
    left, right = _copper_layers(a), _copper_layers(b)
    # A through via spanning F.Cu to B.Cu is represented as *.Cu by the parser.
    return bool(left and right and ("*.Cu" in left or "*.Cu" in right or left & right))


def _has_copper(pad):
    return pad.get("type") not in {"np_thru_hole", "npth"}


def _point_to_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if abs(dx) < EPS and abs(dy) < EPS:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px-ax)*dx + (py-ay)*dy) / (dx*dx + dy*dy)))
    return math.hypot(px - (ax + t*dx), py - (ay + t*dy))


def _segment_distance(a, b):
    def orient(p, q, r): return (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])
    p, q = (a["x1"], a["y1"]), (a["x2"], a["y2"])
    r, s = (b["x1"], b["y1"]), (b["x2"], b["y2"])
    if (orient(p,q,r)*orient(p,q,s) < -EPS and orient(r,s,p)*orient(r,s,q) < -EPS):
        return 0.0
    return min(_point_to_segment(*p,*r,*s), _point_to_segment(*q,*r,*s), _point_to_segment(*r,*p,*q), _point_to_segment(*s,*p,*q))


def _circle_gap(a, b):
    return max(0.0, math.hypot(a["x"]-b["x"], a["y"]-b["y"]) - a["size_mm"]/2 - b["size_mm"]/2)


def _pad_radius(pad):
    # Circular envelope is conservative only for via/pad; pad/pad below uses
    # actual axis-aligned rectangular copper envelopes.
    return max(pad.get("size_x_mm", 0), pad.get("size_y_mm", 0)) / 2


def _pad_polygon(pad, sides=128):
    """Conservative, shape-aware polygon for a rotated KiCad pad.

    Curved boundaries use circumscribed samples (with a tiny radial expansion),
    so tessellation cannot turn a real clearance failure into a pass.
    """
    shape = pad.get("shape", "rect")
    w = pad.get("size_x_local_mm", pad.get("size_x_mm", 0))
    h = pad.get("size_y_local_mm", pad.get("size_y_mm", 0))
    angle = math.radians(pad.get("rotation_deg", 0))
    def transform(points):
        c, s = math.cos(angle), math.sin(angle)
        # KiCad's positive board angles rotate clockwise because board Y
        # increases downward; pad rotation is already in the board frame.
        return [(pad["x"] + x*c+y*s, pad["y"] - x*s+y*c) for x,y in points]
    if shape == "circle":
        radius = max(w,h)/2
        return transform([((radius / math.cos(math.pi/sides))*math.cos(2*math.pi*i/sides), (radius / math.cos(math.pi/sides))*math.sin(2*math.pi*i/sides)) for i in range(sides)])
    if shape == "rect":
        return transform([(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)])
    if shape in {"oval", "roundrect"}:
        # Capsules are the standard oval. Roundrect uses KiCad's default
        # radius when no explicit ratio was retained by the board parser.
        r = min(w,h)/2 if shape == "oval" else min(w,h)*max(0.0,min(0.5,pad.get("roundrect_rratio",0.25)))
        cx, cy = max(0,w/2-r), max(0,h/2-r)
        points=[]
        for ox,oy,start in ((cx,cy,0),(-cx,cy,90),(-cx,-cy,180),(cx,-cy,270)):
            for j in range(17):
                theta=math.radians(start+j*90/16)
                points.append((ox+(r/math.cos(math.pi/64))*math.cos(theta),oy+(r/math.cos(math.pi/64))*math.sin(theta)))
        return transform(points)
    # Custom geometry is retained by the parser. Until all primitive types
    # have dedicated offsets, use its conservative declared pad envelope.
    return transform([(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)])


def _segments(poly):
    return list(zip(poly, poly[1:] + poly[:1]))


def _poly_gap(a, b):
    pa, pb = a if isinstance(a, list) else _pad_polygon(a), b if isinstance(b, list) else _pad_polygon(b)
    def inside(point, poly):
        x,y=point; hit=False
        for (x1,y1),(x2,y2) in _segments(poly):
            if (y1>y)!=(y2>y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1: hit=not hit
        return hit
    if inside(pa[0],pb) or inside(pb[0],pa): return 0.0
    edges_a,edges_b=_segments(pa),_segments(pb)
    return min(_segment_distance({"x1":p[0],"y1":p[1],"x2":q[0],"y2":q[1]}, {"x1":r[0],"y1":r[1],"x2":s[0],"y2":s[1]}) for p,q in edges_a for r,s in edges_b)


def _via_pad_gap(via, pad):
    radius=via["size_mm"]/2
    circle=[(via["x"]+(radius/math.cos(math.pi/128))*math.cos(2*math.pi*i/128),via["y"]+(radius/math.cos(math.pi/128))*math.sin(2*math.pi*i/128)) for i in range(128)]
    return _poly_gap(circle,pad)


def _track_round_gap(track, item, item_radius):
    return max(0.0, _point_to_segment(item["x"], item["y"], track["x1"], track["y1"], track["x2"], track["y2"])
               - track["width_mm"]/2 - item_radius)


def _track_pad_gap(track, pad):
    line=[(track["x1"],track["y1"]),(track["x2"],track["y2"])]
    # Distance segment-to-polygon via the existing segment distance helper.
    poly=_pad_polygon(pad)
    if any(_point_in_polygon(point,poly) for point in line): return 0.0
    center_gap=min(_segment_distance(track,{"x1":a[0],"y1":a[1],"x2":b[0],"y2":b[1]}) for a,b in _segments(poly))
    return max(0.0,center_gap-track["width_mm"]/2)


def _point_in_polygon(point, poly):
    x,y=point; hit=False
    for (x1,y1),(x2,y2) in _segments(poly):
        if (y1>y)!=(y2>y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1: hit=not hit
    return hit


def _pad_gap(a, b):
    """Shape-aware edge gap of KiCad pad copper."""
    return _poly_gap(a,b)


def _bbox_gap(a, b):
    dx=max(0.0,abs(a["x"]-b["x"])-(a.get("size_x_mm",a.get("size_mm",0))+b.get("size_x_mm",b.get("size_mm",0)))/2)
    dy=max(0.0,abs(a["y"]-b["y"])-(a.get("size_y_mm",a.get("size_mm",0))+b.get("size_y_mm",b.get("size_mm",0)))/2)
    return math.hypot(dx,dy)


def _edge_clearance(pcb, hole):
    """Copper/hole envelope to actual Edge.Cuts line geometry."""
    distances = []
    radius = max(hole.get("size_x_mm", 0), hole.get("size_y_mm", 0), hole.get("drill_mm", 0)) / 2
    for edge in pcb.board_outline:
        if edge.get("type") == "line":
            distances.append(_point_to_segment(hole["x"], hole["y"], *edge["start"], *edge["end"]) - radius)
    return min(distances) if distances else None


def _add(findings, pcb, rule, severity, title, description, evidence, remediation, *, status="VIOLATION", category="fabrication"):
    evidence = {"status": status, "category": category, "source": "deterministic_geometry", **evidence}
    findings.append(Finding(id=f"KDFM-{len(findings)+1:03d}", rule_id=rule, severity=severity,
        title=title, description=description, evidence=evidence, affected_artifact=pcb.file,
        remediation=remediation, source_tool="spatial-dfm-engine", status=status, category=category))


def run_kicad_dfm(pcb):
    process, findings = GENERIC_DFM_POLICY, []
    required = process["min_clearance"]

    if pcb.min_trace_mm is not None and pcb.min_trace_mm < process["min_trace"]:
        segment = min(pcb.segments, key=lambda item: item["width_mm"])
        _add(findings, pcb, "MIN_TRACE_WIDTH", "high", "Track width below ForgeAgent DFM threshold",
             f'{segment["width_mm"]:.3f} mm is below the fixed ForgeAgent DFM threshold of {process["min_trace"]:.3f} mm.',
             {"actual_mm":segment["width_mm"], "required_mm":process["min_trace"], "geometry_ids":[segment["id"]], "nets":[segment["net_name"]], "layers":[segment["layer"]]},
             "Increase trace width or route to a finer-line process.")

    # Each pair is visited once. Cross-net and layer relevance are prerequisites,
    # so intentional same-net joints cannot become copper-clearance findings.
    closest_segments = None
    for index, a in enumerate(pcb.segments):
        for b in pcb.segments[:index]:
            if electrically_same_net(a,b) or a.get("layer") != b.get("layer"):
                continue
            gap = max(0.0, _segment_distance(a,b) - (a["width_mm"]+b["width_mm"])/2)
            if closest_segments is None or gap < closest_segments[0]: closest_segments = (gap,a,b)
    if closest_segments and closest_segments[0] < required:
        gap,a,b = closest_segments
        _add(findings, pcb, "MIN_COPPER_CLEARANCE", "critical", "Cross-net copper clearance violation",
             f'{a["net_name"] or a["net"]} to {b["net_name"] or b["net"]} is {gap:.3f} mm; the fixed ForgeAgent DFM threshold is {required:.3f} mm.',
             {"actual_mm":round(gap,4), "required_mm":required, "geometry_ids":[a["id"],b["id"]], "nets":[a["net_name"],b["net_name"]], "layers":[a["layer"]]},
             "Increase spacing or select a finer-clearance process.")

    closest_pads = None
    for index, a in enumerate(pcb.pads):
        for b in pcb.pads[:index]:
            if not _has_copper(a) or not _has_copper(b) or electrically_same_net(a,b) or not _layers_intersect(a,b) or _bbox_gap(a,b) >= required:
                continue
            gap = _pad_gap(a,b)
            if closest_pads is None or gap < closest_pads[0]: closest_pads = (gap,a,b)
    if closest_pads and closest_pads[0] < required:
        gap,a,b = closest_pads
        _add(findings, pcb, "PAD_CLEARANCE", "critical", "Pad-to-pad clearance violation",
             f'{a["id"]} to {b["id"]} has {gap:.3f} mm copper gap.',
             {"actual_mm":round(gap,4), "required_mm":required, "geometry_ids":[a["id"],b["id"]], "nets":[a["net_name"],b["net_name"]], "layers":sorted(_copper_layers(a)&_copper_layers(b))},
             "Move pads, reduce pad copper, or select a finer assembly process.")

    # Track-to-pad/via checks use the same electrical and layer gates.  They
    # cover crossing copper without interpreting a same-net routed connection
    # as a short.
    for rule, items, radius, title in (
        ("TRACK_PAD_CLEARANCE", pcb.pads, None, "Track-to-pad clearance below ForgeAgent DFM threshold"),
        ("TRACK_VIA_CLEARANCE", pcb.vias, lambda item: item["size_mm"]/2, "Track-to-via clearance below ForgeAgent DFM threshold"),
    ):
        nearest = None
        for track in pcb.segments:
            for item in items:
                if (not _has_copper(item) if rule == "TRACK_PAD_CLEARANCE" else False) or electrically_same_net(track,item) or not _layers_intersect({"layers":[track["layer"]]}, item):
                    continue
                # Cheap bounding-box rejection keeps real boards tractable;
                # exact segment geometry is only evaluated near the pad/via.
                min_x,max_x = sorted((track["x1"],track["x2"])); min_y,max_y = sorted((track["y1"],track["y2"]))
                extent_x = item.get("size_x_mm",item.get("size_mm",0))/2 + track["width_mm"]/2 + required
                extent_y = item.get("size_y_mm",item.get("size_mm",0))/2 + track["width_mm"]/2 + required
                if item["x"] < min_x-extent_x or item["x"] > max_x+extent_x or item["y"] < min_y-extent_y or item["y"] > max_y+extent_y:
                    continue
                gap = _track_pad_gap(track, item) if rule == "TRACK_PAD_CLEARANCE" else _track_round_gap(track, item, radius(item))
                if nearest is None or gap < nearest[0]: nearest = (gap,track,item)
        if nearest and nearest[0] < required:
            gap,track,item = nearest
            _add(findings, pcb, rule, "high", title,
                 f'{track["id"]} to {item["id"]} is {gap:.3f} mm; the fixed ForgeAgent DFM threshold is {required:.3f} mm.',
                 {"actual_mm":round(gap,4),"required_mm":required,"geometry_ids":[track["id"],item["id"]],"nets":[track["net_name"],item["net_name"]],"layers":[track["layer"]]},
                 "Increase copper spacing or change the routing.")

    via_pad = []
    for via in pcb.vias:
        candidates = [( _via_pad_gap(via,pad), pad) for pad in pcb.pads
                      if _has_copper(pad) and not electrically_same_net(via,pad) and _layers_intersect(via,pad)
                      and _bbox_gap(via,pad) < required]
        if candidates:
            gap,pad = min(candidates, key=lambda item:item[0])
            if gap < required: via_pad.append((via["id"],gap,via,pad))
    for _,gap,via,pad in sorted(via_pad)[:10]:
        _add(findings, pcb, "VIA_PAD_CLEARANCE", "high", "Via-to-pad clearance below ForgeAgent DFM threshold",
             f'{via["id"]} to {pad["id"]} is {gap:.3f} mm; the fixed ForgeAgent DFM threshold is {required:.3f} mm.',
             {"actual_mm":round(gap,4), "required_mm":required, "geometry_ids":[via["id"],pad["id"]], "nets":[via["net_name"],pad["net_name"]], "layers":sorted(_copper_layers(via)&_copper_layers(pad))},
             "Move the via, move the pad, or change the routing.")
    if len(via_pad) > 10:
        _add(findings, pcb, "VIA_PAD_CLEARANCE_SUMMARY", "medium", "Additional via-to-pad violations suppressed",
             f"{len(via_pad)-10} additional, unique cross-net pairs were suppressed.", {"total_violations":len(via_pad),"reported":10},
             "Inspect the deterministic geometry evidence before manufacturing.", status="WARNING")

    via_pairs = []
    for index, a in enumerate(pcb.vias):
        for b in pcb.vias[:index]:
            if electrically_same_net(a,b) or not _layers_intersect(a,b): continue
            gap = _circle_gap(a,b)
            if gap < required: via_pairs.append((tuple(sorted((a["id"],b["id"]))),gap,a,b))
    for _,gap,a,b in sorted(via_pairs)[:10]:
        _add(findings, pcb, "VIA_CLEARANCE", "high", "Via-to-via clearance below ForgeAgent DFM threshold",
             f'{a["id"]} to {b["id"]} is {gap:.3f} mm; the fixed ForgeAgent DFM threshold is {required:.3f} mm.',
             {"actual_mm":round(gap,4), "required_mm":required, "geometry_ids":[a["id"],b["id"]], "nets":[a["net_name"],b["net_name"]], "layers":sorted(_copper_layers(a)&_copper_layers(b))},
             "Increase via spacing or move one via to another routing channel.")

    drilled = [hole for hole in pcb.through_holes if hole.get("drill_mm",0) > 0]
    if pcb.min_drill_mm is not None and pcb.min_drill_mm < process["min_drill"] and drilled:
        hole = min(drilled, key=lambda item:item["drill_mm"])
        _add(findings, pcb, "MIN_DRILL", "high", "Drill diameter below ForgeAgent DFM threshold",
             f'{hole["drill_mm"]:.3f} mm is below the fixed ForgeAgent DFM threshold of {process["min_drill"]:.3f} mm.', {"actual_mm":hole["drill_mm"],"required_mm":process["min_drill"],"geometry_ids":[hole["id"]]},
             "Increase drill diameter or select a micro-drill capable process.")

    if pcb.bounds and (pcb.bounds["width_mm"] > process["max_board"][0] or pcb.bounds["height_mm"] > process["max_board"][1]):
        _add(findings, pcb, "BOARD_SIZE", "medium", "Board exceeds ForgeAgent DFM size threshold", "Board dimensions exceed the fixed ForgeAgent DFM envelope.",
             {"board":pcb.bounds,"limit_mm":process["max_board"]}, "Split/panelize or select a larger-format manufacturer.", status="WARNING")

    # A hole is checked once by its stable parser identity, against Edge.Cuts only.
    seen_holes = set()
    for hole in drilled:
        if hole["id"] in seen_holes: continue
        seen_holes.add(hole["id"])
        edge = _edge_clearance(pcb, hole)
        if edge is not None and edge < process.get("min_hole_edge", .25):
            _add(findings, pcb, "HOLE_TO_EDGE", "medium", "Hole too close to board edge",
                 f'{hole["id"]} leaves {max(0,edge):.3f} mm to actual Edge.Cuts.', {"actual_mm":round(edge,4),"required_mm":process["min_hole_edge"],"geometry_ids":[hole["id"]],"hole_type":hole.get("type")},
                 "Move the hole inward or use a process with a smaller hole-edge requirement.", status="WARNING")

    unresolved = [zone for zone in pcb.zones if len(zone.get("points",[])) < 3]
    if unresolved:
        _add(findings, pcb, "ZONE_GEOMETRY", "medium", "Copper zone geometry unresolved",
             f"{len(unresolved)} zone polygon(s) could not be reconstructed; fill clearance was not verified.",
             {"geometry_ids":[zone["id"] for zone in unresolved],"layers":[zone["layer"] for zone in unresolved]},
             "Open and re-save valid zone geometry before fabrication review.", status="WARNING")
    return findings
