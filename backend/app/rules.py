from .models import Finding

GENERIC_DFM_POLICY = {"min_trace":0.15, "min_clearance":0.15, "min_drill":0.20,
                      "max_board":(300,400), "min_hole_edge":0.25}

def run_dfm(geo,drill,board=None):
    caps=GENERIC_DFM_POLICY; findings=[]
    if geo.min_feature_mm is not None and geo.min_feature_mm < caps["min_trace"]:
        findings.append(Finding(id="DFM-001",rule_id="MIN_TRACE_WIDTH",severity="high",title="Copper feature below ForgeAgent DFM threshold",description=f"Smallest parsed copper aperture is {geo.min_feature_mm:.3f} mm; the fixed ForgeAgent DFM threshold is {caps['min_trace']:.3f} mm.",evidence={"measured_mm":geo.min_feature_mm,"limit_mm":caps["min_trace"],"apertures":geo.apertures},affected_artifact=geo.file,remediation="Increase the affected trace/pad feature or review the published capabilities of a finer-line process."))
    if drill and drill.min_drill_mm and drill.min_drill_mm < caps["min_drill"]:
        findings.append(Finding(id="DFM-003",rule_id="MIN_DRILL",severity="high",title="Drill diameter below ForgeAgent DFM threshold",description=f"Smallest drill is {drill.min_drill_mm:.3f} mm; the fixed ForgeAgent DFM threshold is {caps['min_drill']:.3f} mm.",evidence={"measured_mm":drill.min_drill_mm,"limit_mm":caps["min_drill"],"tools":drill.tools},affected_artifact=drill.file,remediation="Increase the finished hole diameter or review published drill capabilities."))
    if board and board.get("width_mm") and board.get("height_mm") and (board["width_mm"]>caps["max_board"][0] or board["height_mm"]>caps["max_board"][1]):
        findings.append(Finding(id="DFM-004",rule_id="BOARD_SIZE",severity="medium",title="Board exceeds ForgeAgent DFM size threshold",description="Board dimensions exceed the fixed ForgeAgent DFM envelope.",evidence={"board":board,"limit_mm":caps["max_board"]},affected_artifact="Edge.Cuts",remediation="Panelize/split the design or review sourced manufacturer board-size capabilities."))
    return findings

def inspect_bom(rows):
    findings=[]
    if not rows: return [Finding(id="BOM-000",rule_id="BOM_EMPTY",severity="high",title="BOM is empty",description="No component rows were parsed.",remediation="Provide a manufacturing BOM with MPN and quantity.",source_tool="bom-agent",category="procurement")]
    for i,row in enumerate(rows,1):
        pn=next((row.get(k) for k in ("mpn","manufacturer_part_number","part_number","pn") if row.get(k)),"")
        if not pn:
            findings.append(Finding(id=f"BOM-{i:03d}",rule_id="BOM_MISSING_MPN",severity="medium",title="Missing manufacturer part number",description=f"BOM row {i} has no MPN.",evidence={"row":i,"columns":list(row),"status":"WARNING"},affected_artifact="BOM",remediation="Add an exact manufacturer part number before procurement.",source_tool="bom-agent",status="WARNING",category="procurement")); continue
        # No live component lifecycle or sourcing dataset is configured. Avoid
        # inventing stock, lifecycle, or substitute claims for an MPN.
    return findings
