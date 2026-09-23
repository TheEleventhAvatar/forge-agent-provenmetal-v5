from __future__ import annotations

import math
from ..models import ManufacturerMatch


def _measurements(pcb):
    widths = [s["width_mm"] for s in pcb.segments if s.get("width_mm") is not None]
    drills = [h["drill_mm"] for h in pcb.through_holes if h.get("drill_mm", 0) > 0]
    gaps = []
    # Match the geometric scope conservatively: same copper layer, distinct known nets.
    from ..kicad_rules import (_segment_distance, _pad_gap, _track_pad_gap,
        _via_pad_gap, _track_round_gap, _circle_gap, _bbox_gap,
        _layers_intersect, _has_copper, electrically_same_net)
    def track_near_item(track,item,limit=.5):
        left=min(track["x1"],track["x2"])-track["width_mm"]/2
        right=max(track["x1"],track["x2"])+track["width_mm"]/2
        top=min(track["y1"],track["y2"])-track["width_mm"]/2
        bottom=max(track["y1"],track["y2"])+track["width_mm"]/2
        hx=item.get("size_x_mm",item.get("size_mm",0))/2
        hy=item.get("size_y_mm",item.get("size_mm",0))/2
        dx=max(0,left-(item["x"]+hx),(item["x"]-hx)-right)
        dy=max(0,top-(item["y"]+hy),(item["y"]-hy)-bottom)
        return math.hypot(dx,dy)<limit
    for i, a in enumerate(pcb.segments):
        for b in pcb.segments[:i]:
            if a.get("layer") != b.get("layer") or electrically_same_net(a,b): continue
            gap=max(0.0,_segment_distance(a,b)-(a["width_mm"]+b["width_mm"])/2)
            gaps.append(gap)
    for i,a in enumerate(pcb.pads):
        for b in pcb.pads[:i]:
            if _has_copper(a) and _has_copper(b) and not electrically_same_net(a,b) and _layers_intersect(a,b) and _bbox_gap(a,b)<.5:
                gaps.append(_pad_gap(a,b))
    for track in pcb.segments:
        for pad in pcb.pads:
            if _has_copper(pad) and not electrically_same_net(track,pad) and _layers_intersect({"layers":[track["layer"]]},pad) and track_near_item(track,pad):
                gaps.append(_track_pad_gap(track,pad))
        for via in pcb.vias:
            if not electrically_same_net(track,via) and _layers_intersect({"layers":[track["layer"]]},via) and track_near_item(track,via):
                gaps.append(_track_round_gap(track,via,via["size_mm"]/2))
    for i,a in enumerate(pcb.vias):
        for b in pcb.vias[:i]:
            if not electrically_same_net(a,b) and _layers_intersect(a,b): gaps.append(_circle_gap(a,b))
        for pad in pcb.pads:
            if _has_copper(pad) and not electrically_same_net(a,pad) and _layers_intersect(a,pad) and _bbox_gap(a,pad)<.5:
                gaps.append(_via_pad_gap(a,pad))
    return min(widths) if widths else None, min(gaps) if gaps else None, min(drills) if drills else None


def _evaluate(measured, claim, known_conditions):
    """Legacy helper retained for callers; route matching uses intelligence.evaluate."""
    if measured is None or claim.get("value") is None:
        return "UNKNOWN", "No measurable value or published capability is available."
    for key, expected in claim.get("conditions", {}).items():
        if key not in known_conditions:
            return "CONDITIONAL", f"Published value requires {key}={expected}; board condition is unknown."
        actual=known_conditions[key]
        exp=str(expected).lower()
        applies=(actual>=2 if exp=="2 or more" else actual>2 if exp=="multilayer" else actual in (1,2) if exp=="1-2" else actual==expected if isinstance(expected,(int,float)) else str(actual).lower()==exp)
        if not applies:
            return "CONDITIONAL", f"Published value requires {key}={expected}; detected {actual}."
    ok=measured>=claim["value"]
    return ("PASS" if ok else "FAIL", f"Measured {measured} {'meets' if ok else 'does not meet'} published minimum {claim['value']}.")


def match_capabilities(pcb=None, geo=None, drill_model=None):
    """Compatibility adapter; all decisions come from the generic evaluator."""
    from .intelligence import evaluate
    _,routes=evaluate(pcb,geo,drill_model)
    result=[]
    for name in dict.fromkeys(r["manufacturer"] for r in routes):
        candidates=[r for r in routes if r["manufacturer"]==name and r["domain"]=="fabrication"]
        route=next((r for r in candidates if r["status"]=="PASS"),candidates[0] if candidates else None)
        if route:
            result.append(ManufacturerMatch(manufacturer=name,compatible=route["status"]=="PASS",status=route["status"],score=0,
                blockers=[x["reason"] for x in route["matrix"] if x["status"]=="FAIL"],satisfied=[x["parameter"] for x in route["matrix"] if x["status"]=="PASS"],
                reasons=route["unknowns"],evidence=route["matrix"],unknowns=route["unknowns"],sources=list(dict.fromkeys(x["source"]["url"] for x in route["matrix"] if x.get("source"))),capabilities=[]))
    return result
