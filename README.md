# ForgeAgent

**Agentic PCB manufacturing review engine** â€” Gerber, Excellon, KiCad PCB and BOM inputs with deterministic geometry checks, MPN completeness checks, sourced manufacturer capability matching, and an inspectable agent trace.



https://github.com/user-attachments/assets/8f0b3421-51b5-40ef-82c3-3a1e90176aed



## What this demonstrates

`real PCB files â†’ real parsing â†’ real geometry â†’ deterministic DFM results â†’ real BOM reasoning â†’ manufacturer capability matching â†’ agent trace`

### Pipeline

1. Ingest Gerber copper, Excellon drill and BOM CSV.
2. Parse manufacturing geometry into structured evidence.
3. Run deterministic DFM checks: minimum feature, clearance, drill size.
4. Inspect BOM rows for missing MPNs; no live component sourcing data is claimed.
5. Match the board against sourced manufacturer capability profiles.
6. Emit an agent trace showing every stage and its evidence.
7. Produce a structured manufacturing-review result.

## Run

### Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
# source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000/docs`

### Analyze the real fixture

Windows PowerShell:

```powershell
curl.exe -X POST http://localhost:8000/analyze `
  -F "files=@examples/real_pcb/F_Cu.gbr" `
  -F "files=@examples/real_pcb/PTH.drl" `
  -F "files=@examples/real_pcb/bom.csv"
```

The results include deterministic geometry findings and source-backed capability outcomes. Capability checks may be conditional or unknown when process inputs such as copper weight are absent.

## Broader parser coverage

The fixture parser intentionally stays small so its behavior is transparent. For broader Gerber X2/X3 and Excellon coverage, `backend/app/parsers.py` could be adapted to a maintained Gerber/Excellon parser such as **Gerbonara** or **PyGerber**. Parser behavior should be checked against project fixtures before replacing the current deterministic path.

## Why the LLM is not the DFM calculator

Manufacturing violations should be evidence-backed. The rule engine measures geometry and compares it to a fixed generic DFM policy. Manufacturer capability checks are an independent layer with documented provenance. An eventual LLM planner can explain findings and compose a manufacturing plan, but it should not invent measured values or manufacturer data.

## KiCad-native spatial DFM

The project now accepts a `.kicad_pcb` directly. The KiCad parser extracts:

- board outline and dimensions
- signal layers
- named nets
- tracks/segments and widths
- vias and drill sizes
- footprints and references
- pads, pad sizes/shapes and transformed board coordinates
- through-hole drills

The spatial DFM engine then evaluates the actual board geometry for:

- minimum track width
- track-to-track copper clearance on the same layer
- pad-to-pad clearance
- minimum drill diameter
- hole-to-board-edge distance
- board manufacturing envelope

The clearance engine uses segment-to-segment distance rather than endpoint proximity, and ignores same-net copper when both objects have an explicit non-zero net. Unassigned copper (net 0) is conservatively checked against other unassigned copper.

### KiCad-only API example

```powershell
curl.exe -X POST http://localhost:8000/analyze `
  -F "files=@examples/real_pcb/ForgeBoard.kicad_pcb" `
  -F "files=@examples/real_pcb/bom.csv"
```

The trace now includes `kicad-parser`, `spatial-geometry-engine`, `bom-agent`, `capability-agent`, `evidence-agent`, and `report-agent` stages.

### Important limitation

This is a transparent prototype parser, not a replacement for the full KiCad parser/CAM stack. It intentionally focuses on the subset of the KiCad board S-expression required for this DFM demonstration. For production coverage, the parser should be replaced or cross-validated against KiCad's own parser / a maintained third-party parser, while keeping the same normalized geometry interface.

## v0.3 spatial board viewer

The KiCad path now returns a frontend-safe `board_scene` containing board bounds, tracks, pads, vias, footprints and nets. The dashboard renders that scene as an SVG board view and links DFM findings back to geometry IDs. Clicking a finding selects it; violating tracks/pads/vias are highlighted directly on the board.

Spatial rules are net-aware: copper clearance checks compare different nets on the same copper layer and skip segments belonging to the same net. Manufacturer matching also considers the tightest observed cross-net clearance.

## v0.4 â€” manufacturing decision loop

The native KiCad path builds a structured PCB model containing nets, tracks, pads, vias, footprints and copper zones. The DFM engine performs net-aware spatial checks; manufacturer capability evidence and any quote integration remain separate. Every deterministic finding carries geometry IDs that the frontend can highlight.

Pipeline:

`KiCad -> PCB model -> spatial DFM + DRC validation -> BOM completeness -> public capability evidence -> condition-aware process assessment -> simulated quote scenario -> agent trace`

Manufacturer process assessment uses the officially sourced, conditioned JLCPCB and PCBWay capability entries described below. No prices, inventory, availability, or lead times are inferred.

## Validation Architecture

1. **ForgeAgent deterministic DFM** measures board geometry and applies the existing fixed generic DFM policy. Those thresholds remain independent from manufacturer capability values.
2. **KiCad DRC independent validation** runs `kicad-cli pcb drc <board>` when the configured KiCad CLI is installed. Its text report is returned as an analysis artifact. A `.rpt` can also be uploaded directly.
3. **Cross-validation/evidence mapping** deterministically compares violation type, footprint/pad references, net, layer, and coordinates within tolerance. It reports `CORROBORATED`, `NOT_CORROBORATED`, `CONFLICTING_GEOMETRY`, `KICAD_ONLY`, `FORGEAGENT_ONLY`, `UNMAPPED`, or `VALIDATION_UNAVAILABLE`. KiCad's absence of a finding does not disprove a ForgeAgent manufacturing-specific finding.
4. **Manufacturer capability matching** compares available geometric measurements to published profile values and their conditions. Results are `PASS`, `FAIL`, `CONDITIONAL`, or `UNKNOWN`; unknown inputs never become a pass.
5. **Provenance** accompanies each capability value with its official source URL, title, retrieval date, and concise source wording. The UI exposes that evidence.

KiCad reports unconnected items separately from ordinary DRC violations. On the NEAToBOARD fixture, KiCad reports 523 violation records and 20 unconnected-item records, for 543 diagnostic records total. Only the 523 violation records participate in ForgeAgent object-level DRC cross-validation. ForgeAgent reports 0 geometry violations on this fixture. These tools have different rule coverage; the additional KiCad diagnostics are not contradictions.

## Manufacturer Capability Sources

- [JLCPCB PCB capabilities](https://jlcpcb.com/capabilities/Capab) and [JLCPCB assembly capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities). Sourced PCB fields include layer count, layer/copper-dependent trace and spacing minima, drill and via dimensions, pad-to-track spacing, SMD pad spacing, and selected assembly package/pitch values. Conditions are retained per claim. Selected annular-ring limits are sourced; unsupported board configuration details remain unknown.
- [PCBWay standard PCB capabilities](https://www.pcbway.com/capabilities.html) and [PCBWay advanced PCB capabilities](https://www.pcbway.com/advanced-pcb-capabilities.html). Sourced fields include layer count, trace/spacing minima, CNC drill size, via annular ring, and board size where the process condition is explicit. Assembly capability fields remain unknown in this profile.

Terminology: **published capability** is a sourced manufacturer statement; **ForgeAgent inference** is the deterministic comparison of that statement with parsed board measurements; **illustrative estimate** is explicitly non-live if ever added; **live quote** requires a real pricing integration. Current quote scenarios contain no price or lead-time claims and are marked as non-live. A profile match means â€œmatches the published capability profile,â€ not a guarantee of acceptance. Capabilities may vary by process, stackup, material, copper weight, board geometry, and order configuration. Final manufacturability is subject to manufacturer review.

## Manufacturer Capability Intelligence

ForgeAgent extracts measurable board requirements from the normalized PCB model, evaluates each process against individually sourced capability claims, resolves documented conditions, and reports the evidence row by row. Conditions stay attached to a claim; unsupported values and unmeasurable board requirements remain unknown. Capability coverage measures documented applicable checks, not acceptance probability.

```text
PCB
â†“
PCB Requirement Extraction
â†“
Manufacturer Capability Knowledge Base
â†“
Condition Resolution
â†“
Capability Evaluation
â†“
Evidence / Provenance
â†“
Manufacturing Feasibility Assessment
```

The configured process profiles include JLCPCB Standard PCB, Economic PCBA and Standard PCBA, plus PCBWay Standard PCB and Advanced PCB. Fabrication, assembly and component procurement receive separate statuses. The knowledge base can be inspected at `GET /manufacturers`; it records source URL/title/evidence, retrieval and verification date, capability type, conditions, and source status. Verification dates are manually recorded, not automatically refreshed. Capability claims are sourced from JLCPCB's [PCB capability](https://jlcpcb.com/capabilities/Capab), [assembly capability](https://jlcpcb.com/capabilities/pcb-assembly-capabilities), [SMD spacing](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components), [PCB dimensions](https://jlcpcb.com/help/article/pcb-dimensions), and [API access](https://jlcpcb.com/help/article/jlcpcb-online-api-available-now) pages; and PCBWay's [standard capability](https://www.pcbway.com/capabilities.html) and [advanced capability](https://www.pcbway.com/advanced-pcb-capabilities.html) pages. The SMD-spacing help page was not independently available during retrieval; no extra claims are attributed to it.

Pricing/inventory integration is `NOT_CONNECTED`. Quote scenarios remain `SIMULATED`; no actual prices, availability, lead times or supplier acceptance are asserted. Published capability, ForgeAgent's deterministic comparison, illustrative estimates and live quotes are distinct data types and claims.

## Final engineering audit (2026-09-23)

The supplied KiCad report and a fresh local CLI run both report **523 DRC violations** and **20 unconnected items**. The report has **543 diagnostic blocks total** because the 20 `[unconnected_items]` blocks are included in that diagnostic-record total but are a separate class, not ordinary violations. The parser and UI now retain all three counts separately; cross-validation only matches the 523 violation records. The CLI emitted Windows registry access warnings while still saving the fresh report and producing the stated counts.

Capability coverage is now computed over parameter-level applicable checks: documented PASS and FAIL checks count as evidence; CONDITIONAL and UNKNOWN do not; NOT_APPLICABLE is excluded. It is evidence coverage, not acceptance probability. On NEAToBOARD the five configured process results are: JLCPCB Standard PCB 92.9% (12 PASS, 1 FAIL, 1 UNKNOWN); JLCPCB Economic PCBA 85.7% (6 PASS, 1 CONDITIONAL, 1 NOT_APPLICABLE); JLCPCB Standard PCBA 100% (6 PASS, 1 FAIL, 1 NOT_APPLICABLE); PCBWay Standard PCB 64.3% (9 PASS, 5 UNKNOWN); PCBWay Advanced PCB 50% (7 PASS, 7 UNKNOWN). Fabrication, assembly, procurement and overall route statuses remain independent fields. A known FAIL in a phase makes that specific process route BLOCKED; absent or conditional evidence without a known failure yields CONDITIONAL, never FAIL.

The JLCPCB Standard PCB unknown for component-hole spacing is specifically a source-semantics issue: the official capability page gives “Pad Hole-to-Hole Spacing” as 0.45 mm but does not state whether the value is center-to-center or edge-to-edge. ForgeAgent measures center-to-center spacing, so it does not compare unlike definitions. PCBWay Advanced unknowns include undocumented minimum dimensions, via diameter and PTH annular ring; trace/space claims are documented only for special copper/layer/partial-feature conditions that do not match this 2-layer, nominal 1 oz board; the advanced via-spacing claim is limited to vias up to 0.45 mm while the measured minimum via diameter is 0.60 mm. PCBWay Standard unknowns are via diameter, via-hole spacing, via/PTH annular ring and component-hole spacing. These unknowns are not failures.

NEAToBOARD extracted requirements are shown with field-level quality in the UI. Package recognition is name-based and incomplete: the 0201 passive package field is METADATA_DERIVED from the KiCad footprint identifier, not a complete IPC/package-recognition result. IC pin spacing is GEOMETRY_DERIVED from pad centers. A missing inner copper declaration is UNKNOWN; BGA spacing is NOT_APPLICABLE only when no BGA footprint is detected. The per-board normalized requirement object is the source of displayed values and measurement basis.

The official JLCPCB assembly page presents different package thresholds in its table and FAQ (0402 for Economic, 0201 for Standard, and a separate statement supporting 01005 without explicit process scope). Those package claims are marked TYPICAL and evaluated conservatively; the Economic package outcome remains CONDITIONAL rather than asserting a hard failure. PCBWay Advanced component-hole spacing provenance points to the official advanced capability page. No capability values are sourced from third-party aggregators; the JLCPCB SMD-spacing help page is not used because it was not independently verified.


## Example: NEAToBOARD

This fixture shows the difference between KiCad design-rule validation and ForgeAgent manufacturing feasibility:

```text
Real KiCad board
↓
100 × 60 mm / 2 layers / 1.6 mm FR-4
↓
ForgeAgent geometry analysis: 0 geometry violations
↓
KiCad DRC: 523 violations / 20 unconnected items / 543 total diagnostics
↓
Normalized manufacturing requirements with measurement quality
↓
Publicly sourced manufacturer capability evidence
↓
Condition-aware process comparisons
↓
Documented Manufacturing Feasibility Assessment
```

For example, the derived via annular ring is **0.15 mm**. The JLCPCB Standard PCB profile documents a **0.18 mm minimum** for the applicable two-layer, nominal one-ounce condition, so the result is **FAIL**. The UI exposes the requirement quality, condition, comparison, source page, and verification date. The board also has 19 BOM missing-MPN warnings; these are procurement findings and do not count as geometry violations.
