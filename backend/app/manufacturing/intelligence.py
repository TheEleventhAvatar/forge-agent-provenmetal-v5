"""Generic, provenance-backed manufacturer capability evaluation."""
from __future__ import annotations
from copy import deepcopy
from .manufacturers import load_manufacturer_profiles

VERIFIED_AT = "2026-09-23"
PRICE_DATA_SOURCE = "NOT_CONNECTED"

def knowledge_base():
    old = load_manufacturer_profiles()
    result = []
    processes = {"jlcpcb": [("standard_pcb", "Standard PCB", "fabrication"), ("economic_pcba", "Economic PCBA", "assembly"), ("standard_pcba", "Standard PCBA", "assembly")],
                 "pcbway": [("standard_pcb", "Standard PCB", "fabrication"), ("advanced_pcb", "Advanced PCB", "fabrication")]}
    assembly_names = {"min_package", "min_ic_pin_spacing", "min_bga_spacing"}
    for mid, profile in old.items():
        grouped=[]
        for pid,pname,ptype in processes[mid]:
            claims=[]
            for c in profile["capabilities"]:
                assembly = c["name"] in assembly_names or c["source"]["url"] == "https://jlcpcb.com/capabilities/pcb-assembly-capabilities"
                if (ptype == "assembly") != assembly: continue
                if mid == "jlcpcb" and pid == "economic_pcba" and c["conditions"].get("service") == "standard PCBA": continue
                if mid == "jlcpcb" and pid == "standard_pcba" and assembly and c["conditions"].get("service") != "standard PCBA": continue
                if mid == "pcbway" and pid == "standard_pcb" and c["conditions"].get("process") == "advanced PCB": continue
                if mid == "pcbway" and pid == "advanced_pcb" and c["conditions"].get("process") != "advanced PCB": continue
                conditions=deepcopy(c["conditions"])
                conditions.pop("service", None); conditions.pop("process", None); conditions.pop("dimension", None); conditions.pop("measurement", None)
                cap_type="CONDITIONAL_CAPABILITY" if conditions else "HARD_CAPABILITY"
                if "recommended" in c["source"]["evidence"].lower(): cap_type="RECOMMENDED"
                if c["name"]=="min_package": cap_type="TYPICAL"
                claims.append({"manufacturer_id":mid,"manufacturer":profile["name"],"process_id":pid,"process":pname,"domain":ptype,
                    "parameter":c["name"],"value":c["value"],"unit":c["unit"],"operator":"in" if isinstance(c["value"],list) else "lte" if c["name"].startswith("max_") else "gte",
                    "conditions":conditions,"capability_type":cap_type,"source":{"url":c["source"]["url"],"title":c["source"]["page_title"],"evidence_note":c["source"]["evidence"],"retrieval_date":c["source"]["retrieved_at"]},"last_verified_at":VERIFIED_AT,"source_status":"VERIFIED"})
            universe=("layer_count","board_thickness","min_board_dimensions","max_board_dimensions","material","outer_copper_weight","inner_copper_weight","min_laser_drill","via_types","blind_vias","buried_vias","microvias","via_in_pad","aspect_ratio","impedance_control","assembly_quantity_range") if ptype=="fabrication" else ("pcb_size_limits","panel_size_limits","layer_limits","supported_thickness","assembly_quantity_range","assembly_process_limitations")
            known={c["parameter"] for c in claims}
            unknown=[{"parameter":parameter,"value":None,"unit":None,"conditions":{},"capability_type":"UNSPECIFIED","source":None,"last_verified_at":VERIFIED_AT,"source_status":"UNAVAILABLE","reason":"No verified public capability value is recorded for this process."} for parameter in universe if parameter not in known]
            unresolved=[]
            if mid == "jlcpcb" and pid == "standard_pcb":
                unresolved.append({"parameter":"min_component_hole_spacing","source":{"url":"https://jlcpcb.com/capabilities/Capab","title":"PCB Manufacturing & Assembly Capabilities - JLCPCB","evidence_note":"The page labels 0.45 mm as ‘Pad Hole-to-Hole Spacing’; it does not specify whether that means center-to-center or edge-to-edge, so the metric cannot be safely compared with the extracted center-to-center measurement.","retrieval_date":VERIFIED_AT}})
            grouped.append({"process_id":pid,"name":pname,"domain":ptype,"capabilities":claims,"unknown_capabilities":unknown,"unresolved_evidence":unresolved})
        result.append({"manufacturer_id":mid,"name":profile["name"],"processes":grouped})
    return result

def extract_requirements(pcb=None, geo=None, drill_model=None):
    req={"board_width_mm":None,"board_height_mm":None,"layer_count":None,"min_trace_width_mm":None,"min_spacing_mm":None,"min_drill_mm":None,"min_via_hole_mm":None,"min_via_diameter_mm":None,"min_via_hole_spacing_mm":None,"min_component_hole_spacing_mm":None,"min_via_annular_ring_mm":None,"min_pth_annular_ring_mm":None,"material":None,"copper_weight_oz":None,"inner_copper_weight_oz":None,"board_thickness_mm":None,"solder_mask_color":None,"min_package":None,"min_ic_pin_spacing_mm":None,"min_bga_spacing_mm":None,"via_types":[]}
    if pcb:
        if pcb.bounds:
            req["board_width_mm"]=round(pcb.bounds["width_mm"],4) if pcb.bounds.get("width_mm") is not None else None
            req["board_height_mm"]=round(pcb.bounds["height_mm"],4) if pcb.bounds.get("height_mm") is not None else None
        declared=getattr(pcb,"copper_layers",[]) or sorted(x for x in pcb.layers if x in {"F.Cu","B.Cu"} or __import__("re").fullmatch(r"In\d+\.Cu",x))
        req["layer_count"]=len(declared) if declared else None
        req["material"]=getattr(pcb,"material",None)
        req["board_thickness_mm"]=getattr(pcb,"board_thickness_mm",None)
        copper=getattr(pcb,"copper_thickness_by_layer_mm",{})
        outer=[copper[x] for x in ("F.Cu","B.Cu") if x in copper]
        if outer: req["copper_weight_oz"]=round(sum(outer)/len(outer)/0.0348,1)
        inner=[value for name,value in copper.items() if name.startswith("In") and name.endswith(".Cu")]
        if inner: req["inner_copper_weight_oz"]=round(sum(inner)/len(inner)/0.0348,1)
        req["solder_mask_color"]=getattr(pcb,"solder_mask_color",None)
        tracks=[x.get("width_mm") for x in pcb.segments if x.get("width_mm") is not None]
        holes=[x.get("drill_mm") for x in pcb.through_holes if x.get("drill_mm",0)>0]
        vias=[x for x in pcb.vias if x.get("drill_mm",0)>0]
        req["min_trace_width_mm"]=min(tracks) if tracks else None
        try:
            from .capability_matcher import _measurements
            _,req["min_spacing_mm"],_= _measurements(pcb)
            if req["min_spacing_mm"] is not None: req["min_spacing_mm"]=round(req["min_spacing_mm"],4)
        except Exception:
            req["min_spacing_mm"]=None
        req["min_drill_mm"]=min(holes) if holes else None
        req["min_via_hole_mm"]=min((v["drill_mm"] for v in vias),default=None)
        req["min_via_diameter_mm"]=min((v["size_mm"] for v in vias),default=None)
        req["min_via_annular_ring_mm"]=min(((v["size_mm"]-v["drill_mm"])/2 for v in vias if v.get("size_mm",0)>v.get("drill_mm",0)),default=None)
        pth=[p for p in pcb.through_holes if p.get("type")=="thru_hole" and p.get("drill_mm",0)>0]
        req["min_pth_annular_ring_mm"]=min(((min(p.get("size_x_local_mm",p.get("size_x_mm",0)),p.get("size_y_local_mm",p.get("size_y_mm",0)))-p["drill_mm"])/2 for p in pth if min(p.get("size_x_local_mm",p.get("size_x_mm",0)),p.get("size_y_local_mm",p.get("size_y_mm",0)))>p["drill_mm"]),default=None)
        req["via_types"]=sorted({"through" if "F.Cu" in v.get("layers",[]) and "B.Cu" in v.get("layers",[]) else "blind_or_buried" for v in vias})
        drills=pcb.through_holes+[v for v in vias]
        if drills and all(("F.Cu" in x.get("layers",[]) and "B.Cu" in x.get("layers",[])) for x in vias) and all(x.get("type") in {"thru_hole","np_thru_hole"} for x in pcb.through_holes): req["drill_type"]="CNC"
        distance=_minimum_center_spacing(vias); req["min_via_hole_spacing_mm"]=round(distance,4) if distance is not None else None
        distance=_minimum_center_spacing(pcb.through_holes); req["min_component_hole_spacing_mm"]=round(distance,4) if distance is not None else None
        footprints={f["reference"]:f for f in pcb.footprints}
        passive_codes=[]; ic_pitch=[]; bga_pitch=[]
        package_order=["01005","0201","0402","0603","0805","1206","1210","1812","2010","2512"]
        pads_by_ref={}
        for pad in pcb.pads: pads_by_ref.setdefault(pad.get("reference"),[]).append(pad)
        import re, math
        for ref,fp in footprints.items():
            lib=fp.get("library_id") or ""
            found=re.search(r"(?:^|[_-])(01005|0201|0402|0603|0805|1206|1210|1812|2010|2512)(?:[_-]|$)",lib)
            if found: passive_codes.append(found.group(1))
            group=[x for x in pads_by_ref.get(ref,[]) if x.get("type") in {"smd","thru_hole"}]
            if len(group)<3: continue
            spacing=_minimum_center_spacing(group,include_all=True)
            if spacing is not None and re.search(r"(?:QFP|QFN|SOIC|TSSOP|SOP|DIP|LGA|DFN|SOT)",lib,re.I): ic_pitch.append(spacing)
            if spacing is not None and re.search(r"BGA",lib,re.I): bga_pitch.append(spacing)
        if passive_codes: req["min_package"]=min(passive_codes,key=package_order.index)
        req["min_ic_pin_spacing_mm"]=round(min(ic_pitch),4) if ic_pitch else None
        req["min_bga_spacing_mm"]=round(min(bga_pitch),4) if bga_pitch else None
    else:
        tracks=[x.get("width_mm") for x in geo.tracks if x.get("width_mm") is not None] if geo else []
        req["min_trace_width_mm"]=min(tracks) if tracks else None
        req["min_drill_mm"]=drill_model.min_drill_mm if drill_model else None
    return req

def _minimum_center_spacing(items,include_all=False):
    import math
    points=[(x.get("x"),x.get("y")) for x in items if (include_all or x.get("drill_mm",0)>0) and x.get("x") is not None and x.get("y") is not None]
    distances=[math.hypot(x1-x2,y1-y2) for i,(x1,y1) in enumerate(points) for x2,y2 in points[:i]]
    return min(distances) if distances else None

PARAMS={"min_trace_width":"min_trace_width_mm","min_spacing":"min_spacing_mm","min_drill":"min_drill_mm","min_via_hole":"min_via_hole_mm","min_via_diameter":"min_via_diameter_mm","min_via_hole_spacing":"min_via_hole_spacing_mm","min_component_hole_spacing":"min_component_hole_spacing_mm","min_via_annular_ring":"min_via_annular_ring_mm","min_pth_annular_ring":"min_pth_annular_ring_mm","max_layers":"layer_count","max_board_width":"board_width_mm","max_board_height":"board_height_mm","min_board_width":"board_width_mm","min_board_height":"board_height_mm","min_ic_pin_spacing":"min_ic_pin_spacing_mm","min_bga_spacing":"min_bga_spacing_mm","min_package":"min_package"}
def _condition_state(conditions, req):
    for key, expected in conditions.items():
        if key=="layer_position" and str(expected).lower()=="inner" and req.get("layer_count",0)<=2: return "NOT_APPLICABLE","The board has no inner copper layer."
        if key=="layer_position" and str(expected).lower()=="outer": continue
        keymap={"layers":"layer_count","layer_count":"layer_count","thickness_mm_min":"board_thickness_mm","drill":"drill_type","via_diameter_max_mm":"min_via_diameter_mm","board_type":"material","base_copper":"copper_weight_oz","mask_color":"solder_mask_color"}
        rk=keymap.get(key,key)
        actual=req.get(rk)
        if actual is None: return "CONDITIONAL",f"Published value requires {key}={expected}; board condition is unknown."
        exp=str(expected).lower()
        norm=lambda x: "".join(ch.lower() for ch in str(x) if ch.isalnum())
        if key=="layer_position" and exp=="inner" and req.get("layer_count",0)<=2: return "NOT_APPLICABLE","The board has no inner copper layer."
        if key=="layer_position" and exp=="outer": continue
        if key=="base_copper" and exp=="1/3 oz":
            if req.get("copper_weight_oz") is None: return "CONDITIONAL",f"Published value requires {key}={expected}; copper weight is unknown."
            if abs(req["copper_weight_oz"]-(1/3))>0.05: return "NOT_APPLICABLE",f"Capability condition {key}={expected} does not match derived copper weight {req['copper_weight_oz']} oz."
            continue
        ok=(actual>=2 if exp=="2 or more" else actual>=6 if exp=="6 or more" else actual>2 if exp=="multilayer" else actual in (1,2) if exp=="1-2" else actual>=expected if key in {"thickness_mm_min"} else actual<=expected if key=="via_diameter_max_mm" else norm(actual) in {"fr4","rigidfr4"} if key=="board_type" and "fr4" in norm(expected) else actual==expected if isinstance(expected,(float,int)) else norm(actual)==norm(expected))
        if not ok:return "NOT_APPLICABLE",f"Capability condition {key}={expected} does not match detected {actual}."
    return "PASS",None

def evaluate(pcb=None,geo=None,drill_model=None):
    req=extract_requirements(pcb,geo,drill_model); matrix=[]; routes=[]
    for man in knowledge_base():
      for proc in man["processes"]:
        rows=[]
        for cap in proc["capabilities"]:
            field=PARAMS.get(cap["parameter"]); value=req.get(field) if field else None
            if value is None: continue
            cond,why=_condition_state(cap["conditions"],req)
            if cond=="NOT_APPLICABLE": continue
            if cond=="CONDITIONAL": status=cond; reason=why
            else:
                ok=(value in cap["value"] if cap["operator"]=="in" else value<=cap["value"] if cap["operator"]=="lte" else value>=cap["value"])
                status="PASS" if ok else "FAIL"
                reason=f"Measured {value} {cap['unit']} {'meets' if ok else 'exceeds'} published limit {cap['value']} {cap['unit']}."
                if cap["capability_type"]=="RECOMMENDED" and ok: status="CONDITIONAL"; reason="Within a published recommendation; this is not a hard capability guarantee."
            rows.append({"parameter":cap["parameter"],"requirement":value,"requirement_unit":cap["unit"],"capability":cap["value"],"unit":cap["unit"],"conditions":cap["conditions"],"capability_type":cap["capability_type"],"status":status,"reason":reason,"source":cap["source"]})
        # Applicable checks without claims are unknown and count against evidence coverage.
        domain_params=(["min_trace_width","min_spacing","min_drill","max_layers","max_board_width","max_board_height","min_board_width","min_board_height","min_via_hole","min_via_diameter"] if proc["domain"]=="fabrication" else ["max_layers","max_board_width","max_board_height","min_board_width","min_board_height","min_package","min_ic_pin_spacing","min_bga_spacing"])
        # Every applicable parameter is accounted for, even when the extractor
        # cannot measure it. This makes coverage an evidence metric, not a pass rate.
        applicable=domain_params if (pcb or geo or drill_model) else []
        checked={r["parameter"] for r in rows}; unknown=[p for p in applicable if p not in checked]
        for p in unknown: rows.append({"parameter":p,"requirement":req[PARAMS[p]],"capability":None,"unit":"mm" if p!="max_layers" else "layers","conditions":{},"status":"UNKNOWN","reason":"No applicable official capability evidence is available."})
        statuses=[r["status"] for r in rows]
        status="FAIL" if "FAIL" in statuses else "CONDITIONAL" if "CONDITIONAL" in statuses else "UNKNOWN" if "UNKNOWN" in statuses or not statuses else "PASS"
        evidenced={p for p in applicable if any(r["parameter"]==p and r["status"] in {"PASS","FAIL"} and r.get("source") is not None for r in rows)}
        coverage=round(100*len(evidenced)/len(applicable),1) if applicable else 0.0
        fab=status if proc["domain"]=="fabrication" else "UNKNOWN"
        assembly=status if proc["domain"]=="assembly" else "UNKNOWN"
        routes.append({"manufacturer":man["name"],"manufacturer_id":man["manufacturer_id"],"process":proc["name"],"process_id":proc["process_id"],"domain":proc["domain"],"status":status,"fabrication_status":fab,"assembly_status":assembly,"procurement_status":"UNKNOWN","overall_route_status":"BLOCKED" if status=="FAIL" else "PASS" if status=="PASS" else "CONDITIONAL" if status in {"CONDITIONAL","UNKNOWN"} else "UNKNOWN","capability_coverage":coverage,"documented_checks":len(evidenced),"applicable_checks":len(applicable),"matrix":rows,"unknowns":[r["reason"] for r in rows if r["status"] in {"UNKNOWN","CONDITIONAL"}],"source_status":"VERIFIED"})
    return req,routes

def evaluate(pcb=None,geo=None,drill_model=None):
    # Keep this module's public API stable while the routing evaluator owns
    # applicability, per-parameter summaries, and phase aggregation.
    from .evaluator import evaluate_routes
    return evaluate_routes(pcb,geo,drill_model)

def requirement_quality(req, pcb=None):
    source={"board_width_mm":("DERIVED","Computed from Edge.Cuts bounds."),"board_height_mm":("DERIVED","Computed from Edge.Cuts bounds."),"layer_count":("MEASURED","Read from the declared KiCad copper layer stack."),"min_trace_width_mm":("MEASURED","Minimum serialized track width."),"min_spacing_mm":("DERIVED","Minimum net-aware copper geometry separation."),"min_drill_mm":("MEASURED","Minimum serialized drill diameter."),"min_via_hole_mm":("MEASURED","Minimum via drill diameter."),"min_via_diameter_mm":("MEASURED","Minimum serialized via copper diameter."),"min_via_hole_spacing_mm":("DERIVED","Minimum center-to-center distance between drilled via objects."),"min_component_hole_spacing_mm":("DERIVED","Minimum center-to-center distance between drilled footprint pads."),"min_via_annular_ring_mm":("DERIVED","Half the via copper diameter minus the via drill diameter."),"min_pth_annular_ring_mm":("DERIVED","Half the minimum drilled PTH pad width minus drill diameter."),"board_thickness_mm":("MEASURED","Read from KiCad general board thickness."),"material":("MEASURED","Read from KiCad stackup dielectric material."),"copper_weight_oz":("DERIVED","Nominal oz equivalent computed from declared outer copper thickness (mm / 0.0348)."),"solder_mask_color":("MEASURED","Read from KiCad solder-mask layer metadata."),"min_package":("METADATA_DERIVED","Smallest recognized passive EIA package token in parsed KiCad footprint library IDs; package recognition is name-based and incomplete."),"min_ic_pin_spacing_mm":("GEOMETRY_DERIVED","Minimum pad-center spacing on footprints whose library IDs match recognized IC families."),"min_bga_spacing_mm":("GEOMETRY_DERIVED","Minimum pad-center spacing on footprints explicitly named as BGA."),"via_types":("DERIVED","Inferred from each via copper-layer span.")}
    result={}
    for key,value in req.items():
        if key=="min_bga_spacing_mm" and pcb and value is None and not any("BGA" in (f.get("library_id") or "").upper() for f in pcb.footprints):
            result[key]={"status":"NOT_APPLICABLE","reason":"No BGA footprint was detected."}; continue
        kind,reason=source.get(key,("DERIVED","Deterministic value from the parsed PCB model."))
        if value is None or value==[]:
            reason="No inner copper layer weight is declared in the PCB stackup." if key=="inner_copper_weight_oz" else "The input does not contain enough data to extract this requirement."
            result[key]={"status":"UNKNOWN","reason":reason}
        else: result[key]={"status":kind,"reason":reason}
    return result
