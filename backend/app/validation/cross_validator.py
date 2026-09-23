from __future__ import annotations

import math

STATUSES = {"CORROBORATED", "NOT_CORROBORATED", "CONFLICTING_GEOMETRY", "KICAD_ONLY", "FORGEAGENT_ONLY", "UNMAPPED", "VALIDATION_UNAVAILABLE"}


def _rule_related(finding, violation):
    f = finding.rule_id.lower()
    k = violation.get("violation_type", "").lower()
    return ("clearance" in f and "clearance" in k) or ("drill" in f and ("hole" in k or "drill" in k)) or ("trace" in f and ("width" in k or "track" in k))


def cross_validate(findings, parsed, pcb=None, tolerance_mm=.25):
    if not parsed:
        return {"status": "VALIDATION_UNAVAILABLE", "evidence": [], "kicad_only": [], "unconnected_items": [], "summary": {"corroborated": 0, "forgeagent_only": 0, "kicad_only": 0, "unmapped": 0, "unconnected_items": 0}}
    violations = parsed.get("violations", [])
    unconnected_items = parsed.get("unconnected_items", [])
    matched = set(); evidence = []
    for finding in findings:
        geom_ids = finding.evidence.get("geometry_ids", [])
        if not geom_ids:
            evidence.append({"forgeagent_finding_id": finding.id, "kicad_match": None, "status": "UNMAPPED", "confidence": 0.0, "reason": "ForgeAgent finding has no object identifiers for deterministic mapping.", "sources": ["forgeagent_geometry"]})
            continue
        geom = _geometry(pcb, geom_ids) if pcb else []
        if not geom:
            evidence.append({"forgeagent_finding_id": finding.id, "kicad_match": None, "status": "UNMAPPED", "confidence": 0.0, "reason": "ForgeAgent object identifiers could not be resolved in the parsed PCB geometry model.", "sources": ["forgeagent_geometry"]})
            continue
        candidates = []
        for v in violations:
            score = 0
            expected_refs = {g.get("reference") for g in geom if g.get("reference")}
            expected_pads = {str(g.get("number")) for g in geom if g.get("number")}
            actual_refs = set(v.get("footprint_references", [])); actual_pads = set(v.get("pad_numbers", []))
            if expected_refs & actual_refs: score += 5
            if expected_pads & actual_pads: score += 3
            expected_nets = {str(g.get("net_name")) for g in geom if g.get("net_name")}
            if expected_nets & set(v.get("net_names", [])): score += 2
            expected_layers = {g.get("layer") for g in geom if g.get("layer")}
            if v.get("layer") in expected_layers: score += 1
            if geom and v.get("coordinates"):
                distances=[]
                for c in v["coordinates"]:
                    for g in geom:
                        if "x" in g and "y" in g: distances.append(math.hypot(c[0]-g["x"],c[1]-g["y"]))
                        elif all(k in g for k in ("x1","y1","x2","y2")):
                            dx,dy=g["x2"]-g["x1"],g["y2"]-g["y1"]
                            t=max(0,min(1,((c[0]-g["x1"])*dx+(c[1]-g["y1"])*dy)/(dx*dx+dy*dy or 1)))
                            distances.append(math.hypot(c[0]-(g["x1"]+t*dx),c[1]-(g["y1"]+t*dy)))
                if distances and min(distances) <= tolerance_mm: score += 3
            if _rule_related(finding, v): score += 2
            if score >= 2: candidates.append((score, v, score- (2 if _rule_related(finding,v) else 0)))
        candidates.sort(key=lambda row: row[0], reverse=True)
        chosen_candidate = candidates[0] if candidates else None
        chosen = chosen_candidate[1] if chosen_candidate and chosen_candidate[2] >= 2 else None
        actual = finding.evidence.get("actual_mm")
        required = finding.evidence.get("required_mm")
        conflicting = chosen and actual is not None and chosen.get("actual_value_mm") is not None and abs(actual-chosen["actual_value_mm"]) > tolerance_mm
        if chosen and conflicting: status, reason = "CONFLICTING_GEOMETRY", "KiCad reported a related object/rule, but its measured value differs beyond tolerance."
        elif chosen: status, reason = "CORROBORATED", "KiCad independently reported a related rule and matching board objects."
        elif candidates: status, reason = "NOT_CORROBORATED", "A related KiCad rule exists, but object-level evidence did not match confidently."
        else: status, reason = "FORGEAGENT_ONLY", "No matching KiCad DRC item was found; this does not invalidate the ForgeAgent manufacturing rule."
        if chosen: matched.add(chosen["id"])
        evidence.append({"forgeagent_finding_id": finding.id, "kicad_match": chosen["id"] if chosen else None, "status": status, "confidence": min(.99, .55 + (candidates[0][0]*.04 if candidates else 0)), "reason": reason, "sources": ["forgeagent_geometry"] + (["kicad_drc"] if chosen else [])})
    kicad_only = [{"kicad_match": v["id"], "status": "KICAD_ONLY", "violation": v} for v in violations if v["id"] not in matched]
    counts = {s.lower(): sum(item["status"] == s for item in evidence) for s in ("CORROBORATED", "FORGEAGENT_ONLY", "UNMAPPED")}
    counts["kicad_only"] = len(kicad_only)
    counts["unconnected_items"] = len(unconnected_items)
    return {"status": "available", "evidence": evidence, "kicad_only": kicad_only,
            "unconnected_items": unconnected_items, "summary": counts,
            "kicad_total_violations": parsed.get("violation_count", parsed.get("total_violations", len(violations)))}


def _geometry(pcb, ids):
    if not pcb: return []
    all_items = pcb.pads + pcb.vias + pcb.segments
    return [item for item in all_items if item.get("id") in ids]
