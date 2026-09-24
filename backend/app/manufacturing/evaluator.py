"""Applicability-aware, evidence-first capability comparison."""
from .intelligence import knowledge_base, extract_requirements, PARAMS, _condition_state, requirement_quality

BASE = ["max_layers", "max_board_width", "max_board_height", "min_board_width", "min_board_height"]
FAB = ["min_trace_width", "min_spacing", "min_drill", "min_via_hole", "min_via_diameter", "min_via_hole_spacing", "min_component_hole_spacing", "min_via_annular_ring", "min_pth_annular_ring"]
ASM = ["min_package", "min_ic_pin_spacing", "min_bga_spacing"]

def _compare(parameter, value, cap):
    if parameter == "min_package":
        order=["01005","0201","0402","0603","0805","1206","1210","1812","2010","2512"]
        return value in order and cap["value"] in order and order.index(value)>=order.index(cap["value"])
    return value in cap["value"] if cap["operator"]=="in" else value<=cap["value"] if cap["operator"]=="lte" else value>=cap["value"]

def aggregate_route_status(fabrication, assembly, procurement):
    """Known failure blocks; unresolved independent phases keep the route conditional."""
    phases=[fabrication,assembly,procurement]
    if "FAIL" in phases: return "BLOCKED"
    if all(x in {"PASS","NOT_APPLICABLE"} for x in phases): return "PASS"
    return "CONDITIONAL" if any(x in {"UNKNOWN","CONDITIONAL"} for x in phases) else "UNKNOWN"

def evaluate_routes(pcb=None, geo=None, drill_model=None):
    req=extract_requirements(pcb,geo,drill_model)
    qualities=requirement_quality(req,pcb)
    has_board=pcb is not None or geo is not None
    vias=[v for v in getattr(pcb,"vias",[]) if v.get("drill_mm",0)>0]
    holes=[h for h in getattr(pcb,"through_holes",[]) if h.get("drill_mm",0)>0]
    pth=[h for h in holes if h.get("type")=="thru_hole"]
    has_drills=bool(holes or vias or drill_model)
    has_tracks=bool((pcb and pcb.segments) or (geo and geo.tracks))
    has_bga=bool(pcb and any("BGA" in (f.get("library_id") or "").upper() for f in pcb.footprints))
    has_multi_pad_ic=bool(req.get("min_ic_pin_spacing_mm") is not None)
    routes=[]
    for manufacturer in knowledge_base():
      for process in manufacturer["processes"]:
        is_fab=process["domain"]=="fabrication"
        applicable=list(BASE) if has_board else []
        not_applicable=[]
        if is_fab:
            (applicable if has_tracks else not_applicable).extend(["min_trace_width","min_spacing"])
            (applicable if has_drills else not_applicable).append("min_drill")
            (applicable if vias else not_applicable).extend(["min_via_hole","min_via_diameter","min_via_hole_spacing"])
            (applicable if vias else not_applicable).append("min_via_annular_ring")
            (applicable if pth else not_applicable).append("min_pth_annular_ring")
            (applicable if len(holes)>=2 else not_applicable).append("min_component_hole_spacing")
        else:
            if has_board:
                applicable.extend(["min_package","min_ic_pin_spacing"])
                # A board with footprint data but no recognized IC footprint is
                # an extractor gap, not proof that assembly pin pitch is N/A.
                if not has_multi_pad_ic: applicable.append("min_ic_pin_spacing")
            (applicable if has_bga else not_applicable).append("min_bga_spacing")
        applicable=list(dict.fromkeys(applicable))
        rows=[]; by_parameter={}
        for cap in process["capabilities"]:
            parameter=cap["parameter"]
            if parameter not in applicable and parameter not in not_applicable: continue
            value=req.get(PARAMS.get(parameter,""))
            if parameter in not_applicable:
                rows.append({"parameter":parameter,"requirement":None,"capability":cap["value"],"unit":cap["unit"],"conditions":cap["conditions"],"capability_type":cap["capability_type"],"status":"NOT_APPLICABLE","reason":"The PCB has no feature in this capability scope.","source":cap["source"]})
                continue
            if value is None: continue
            condition, reason=_condition_state(cap["conditions"],req)
            if condition=="NOT_APPLICABLE": state="NOT_APPLICABLE"
            elif condition=="CONDITIONAL": state="CONDITIONAL"
            else:
                passed=_compare(parameter,value,cap)
                state="PASS" if passed else "FAIL"
                reason=f"Requirement {value} {cap['unit']} {'meets' if passed else 'does not meet'} published capability {cap['value']} {cap['unit']}."
                if cap["capability_type"]=="RECOMMENDED" and passed:
                    state="CONDITIONAL"; reason="The value is within a published recommendation, not a hard capability statement."
                if cap["capability_type"]=="TYPICAL" and not passed:
                    state="CONDITIONAL"; reason="The PCB is below the technical table's typical package threshold, but the same official source also states support for a smaller package without clarifying process scope."
            expression=(f"package_order_index({value}) >= package_order_index({cap['value']})" if parameter=="min_package" else f"{value} {'in' if cap['operator']=='in' else '>=' if cap['operator']=='gte' else '<='} {cap['value']}")
            comparison={"operator":cap["operator"],"passed":_compare(parameter,value,cap),"expression":expression,"basis":"ordered EIA package-size list" if parameter=="min_package" else "numeric/value comparison"} if state in {"PASS","FAIL"} else None
            row={"parameter":parameter,"requirement":value,"requirement_unit":cap["unit"],"requirement_quality":qualities.get(PARAMS.get(parameter),{}),"capability":cap["value"],"unit":cap["unit"],"capability_type":cap["capability_type"],"operator":cap["operator"],"conditions":cap["conditions"],"condition_result":condition,"comparison":comparison,"status":state,"result":state,"reason":reason,"source":{**cap["source"],"manufacturer":manufacturer["name"],"verification_date":cap["last_verified_at"]}}
            rows.append(row)
            if state!="NOT_APPLICABLE": by_parameter.setdefault(parameter,[]).append(row)
        for parameter in not_applicable:
            if not any(r["parameter"]==parameter and r["status"]=="NOT_APPLICABLE" for r in rows):
                rows.append({"parameter":parameter,"requirement":None,"capability":None,"conditions":{},"status":"NOT_APPLICABLE","reason":"The PCB has no feature in this capability scope."})
        summary=[]
        documented_by_parameter={}
        for claim in process["capabilities"]: documented_by_parameter.setdefault(claim["parameter"],claim)
        for parameter in applicable:
            ambiguous=None
            options=by_parameter.get(parameter,[])
            states={x["status"] for x in options}
            if "FAIL" in states: state="FAIL"
            elif "PASS" in states: state="PASS"
            elif "CONDITIONAL" in states: state="CONDITIONAL"
            else: state="UNKNOWN"
            chosen=next((x for x in options if x["status"]==state),None)
            field=PARAMS.get(parameter); value=req.get(field)
            if chosen: reason=chosen["reason"]; reason_code="CONDITION_UNRESOLVED" if state=="CONDITIONAL" else None
            elif any(x["parameter"]==parameter and x["status"]=="NOT_APPLICABLE" for x in rows):
                reason="Sourced capabilities exist, but none applies to the detected configuration."; reason_code="NO_APPLICABLE_SOURCE_CLAIM"
            elif value is None and parameter in documented_by_parameter:
                claim=documented_by_parameter[parameter]
                reason="Manufacturer capability is documented, but the PCB input does not contain the data needed to evaluate this requirement."; reason_code="BOARD_INPUT_MISSING"
                chosen={"capability":claim["value"],"capability_type":claim["capability_type"],"conditions":claim["conditions"],"comparison":None,"source":{**claim["source"],"manufacturer":manufacturer["name"],"verification_date":claim["last_verified_at"]}}
            elif value is None:
                reason="The PCB input does not provide enough data to extract this requirement, and no sufficient manufacturer capability evidence is recorded."; reason_code="BOARD_INPUT_AND_SOURCE_UNKNOWN"
            else:
                ambiguous=next((u for u in process.get("unresolved_evidence",[]) if u["parameter"]==parameter),None)
                if ambiguous:
                    reason=ambiguous["source"]["evidence_note"]; reason_code="SOURCE_SEMANTICS_UNRESOLVED"
                else:
                    reason="No sufficient official capability evidence is recorded for this process parameter."; reason_code="NO_MANUFACTURER_DOCUMENTATION"
            cap_source=chosen.get("source") if chosen else (ambiguous["source"] if ambiguous and reason_code=="SOURCE_SEMANTICS_UNRESOLVED" else None)
            if cap_source and "manufacturer" not in cap_source:
                cap_source={**cap_source,"manufacturer":manufacturer["name"],"verification_date":cap_source.get("retrieval_date")}
            summary.append({"parameter":parameter,"requirement":value,"requirement_quality":qualities.get(PARAMS.get(parameter),{}),"capability":chosen.get("capability") if chosen else None,"capability_type":chosen.get("capability_type") if chosen else ("UNSPECIFIED" if reason_code=="NO_MANUFACTURER_DOCUMENTATION" else None),"conditions":chosen.get("conditions",{}) if chosen else {},"result":state,"status":state,"reason":reason,"reason_code":reason_code,"comparison":chosen.get("comparison") if chosen else None,"source":cap_source})
            rows.append(summary[-1])
        counts={s:sum(x["status"]==s for x in summary) for s in ("PASS","FAIL","CONDITIONAL","UNKNOWN")}
        counts["NOT_APPLICABLE"]=len(not_applicable)
        coverage=round(100*(counts["PASS"]+counts["FAIL"])/len(applicable),1) if applicable else 0.0
        status="FAIL" if counts["FAIL"] else "CONDITIONAL" if counts["CONDITIONAL"] else "UNKNOWN" if counts["UNKNOWN"] or not summary else "PASS"
        fab=status if is_fab else "UNKNOWN"; assembly=status if not is_fab else "UNKNOWN"; procurement="UNKNOWN"
        phases=[fab,assembly,procurement]
        overall=aggregate_route_status(*phases)
        routes.append({"manufacturer":manufacturer["name"],"manufacturer_id":manufacturer["manufacturer_id"],"process":process["name"],"process_id":process["process_id"],"domain":process["domain"],"status":status,"fabrication_status":fab,"assembly_status":assembly,"procurement_status":procurement,"overall_route_status":overall,"capability_coverage":coverage,"documented_checks":counts["PASS"]+counts["FAIL"],"applicable_checks":len(applicable),"status_counts":counts,"matrix":rows,"requirement_results":summary,"unknowns":[x["reason"] for x in summary if x["status"] in {"UNKNOWN","CONDITIONAL"}],"source_status":"VERIFIED"})
    return req,routes
