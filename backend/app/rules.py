from .models import Finding, ManufacturerMatch

PROCESSES = {
    "US-PROTO-1": {"name":"US Prototype Fab", "min_trace":0.15, "min_clearance":0.15, "min_drill":0.20, "max_layers":6, "max_board":(300,400), "min_hole_edge":0.25},
    "FINE-PITCH-1": {"name":"Fine Pitch Fabricator", "min_trace":0.10, "min_clearance":0.10, "min_drill":0.15, "max_layers":8, "max_board":(400,500), "min_hole_edge":0.20},
    "ASSEMBLY-1": {"name":"US Prototype Fab + Assembly", "min_trace":0.15, "min_clearance":0.15, "min_drill":0.20, "max_layers":6, "max_board":(300,400), "min_package":"0402", "min_hole_edge":0.25},
}

PARTS={
 "ESP8266EX":{"status":"not_recommended","risk":"high","reason":"legacy module family in demo lifecycle catalog","alternatives":["ESP32-C3-MINI-1","ESP32-S3-MINI-1"]},
 "LM1117MPX-3.3":{"status":"active","risk":"low","alternatives":[]},
 "STM32G031K8T6":{"status":"active","risk":"low","alternatives":["STM32G031K8U6"]},
 "USB-C-16P":{"status":"active","risk":"low","alternatives":[]},
}

def run_dfm(geo,drill,board=None):
    caps=PROCESSES["US-PROTO-1"]; findings=[]
    if geo.min_feature_mm is not None and geo.min_feature_mm < caps["min_trace"]:
        findings.append(Finding(id="DFM-001",rule_id="MIN_TRACE_WIDTH",severity="high",title="Copper feature below process capability",description=f"Smallest parsed copper aperture is {geo.min_feature_mm:.3f} mm; selected process requires ≥ {caps['min_trace']:.3f} mm.",evidence={"measured_mm":geo.min_feature_mm,"limit_mm":caps["min_trace"],"apertures":geo.apertures},affected_artifact=geo.file,remediation="Increase the affected trace/pad feature or route the order to a finer-pitch fabrication process."))
    if drill and drill.min_drill_mm and drill.min_drill_mm < caps["min_drill"]:
        findings.append(Finding(id="DFM-003",rule_id="MIN_DRILL",severity="high",title="Drill diameter below capability",description=f"Smallest drill is {drill.min_drill_mm:.3f} mm; selected process requires ≥ {caps['min_drill']:.3f} mm.",evidence={"measured_mm":drill.min_drill_mm,"limit_mm":caps["min_drill"],"tools":drill.tools},affected_artifact=drill.file,remediation="Increase the finished hole diameter or route to a process supporting smaller drills."))
    if board and board.get("width_mm") and board.get("height_mm") and (board["width_mm"]>caps["max_board"][0] or board["height_mm"]>caps["max_board"][1]):
        findings.append(Finding(id="DFM-004",rule_id="BOARD_SIZE",severity="medium",title="Board exceeds process envelope",description="Board dimensions exceed the selected process envelope.",evidence={"board":board,"limit_mm":caps["max_board"]},affected_artifact="Edge.Cuts",remediation="Panelize/split the design or select a manufacturer with a larger working area."))
    return findings

def inspect_bom(rows):
    findings=[]
    if not rows: return [Finding(id="BOM-000",rule_id="BOM_EMPTY",severity="high",title="BOM is empty",description="No component rows were parsed.",remediation="Provide a manufacturing BOM with MPN and quantity.",source_tool="bom-agent",category="procurement")]
    for i,row in enumerate(rows,1):
        pn=next((row.get(k) for k in ("mpn","manufacturer_part_number","part_number","pn") if row.get(k)),"")
        if not pn:
            findings.append(Finding(id=f"BOM-{i:03d}",rule_id="BOM_MISSING_MPN",severity="medium",title="Missing manufacturer part number",description=f"BOM row {i} has no MPN.",evidence={"row":i,"columns":list(row),"status":"WARNING"},affected_artifact="BOM",remediation="Add an exact manufacturer part number before procurement.",source_tool="bom-agent",status="WARNING",category="procurement")); continue
        info=PARTS.get(pn.upper(),{"status":"unknown","risk":"unknown","alternatives":[]})
        if info["status"]=="not_recommended":
            findings.append(Finding(id=f"BOM-{i:03d}",rule_id="PART_LIFECYCLE",severity="high",title="Component sourcing/lifecycle risk",description=f"{pn} is flagged by the demo component intelligence catalog.",evidence={"mpn":pn,**info},affected_artifact="BOM",remediation=f"Qualify an approved alternative: {', '.join(info['alternatives']) or 'manufacturer-approved replacement'}.",source_tool="bom-agent",category="component_risk"))
    return findings

def match_manufacturers(geo,drill):
    out=[]
    for pid,p in PROCESSES.items():
        blockers=[]
        if geo.min_feature_mm is not None and geo.min_feature_mm < p["min_trace"]: blockers.append(f"min trace {geo.min_feature_mm:.3f} < {p['min_trace']:.3f} mm")
        if drill and drill.min_drill_mm and drill.min_drill_mm < p["min_drill"]: blockers.append(f"min drill {drill.min_drill_mm:.3f} < {p['min_drill']:.3f} mm")
        compatible=not blockers
        out.append(ManufacturerMatch(manufacturer=p["name"],compatible=compatible,score=max(0,100-35*len(blockers)),blockers=blockers,satisfied=[] if blockers else ["trace capability","drill capability"]))
    return out
