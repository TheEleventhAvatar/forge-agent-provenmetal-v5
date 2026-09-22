# ForgeAgent

**Agentic PCB manufacturing review engine** — real Gerber + Excellon + BOM inputs, deterministic geometry checks, component intelligence, manufacturer capability matching, and an inspectable agent trace.

## What this demonstrates

`real PCB files → real parsing → real geometry → real DFM violations → real BOM reasoning → manufacturer capability matching → agent trace`

### Pipeline

1. Ingest Gerber copper, Excellon drill and BOM CSV.
2. Parse manufacturing geometry into structured evidence.
3. Run deterministic DFM checks: minimum feature, clearance, drill size.
4. Inspect BOM rows for missing MPNs and component lifecycle/sourcing risk.
5. Match the board against manufacturer process capabilities.
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

You should see findings for:

- minimum copper feature
- copper-to-copper clearance
- minimum drill
- ESP8266EX component risk

and manufacturer matches where the fine-pitch process can accept the geometry while the standard prototype process cannot.

## Production parser upgrade

The fixture parser intentionally stays small so its behavior is transparent. For broader Gerber X2/X3 and Excellon coverage, replace `backend/app/parsers.py` with an adapter around **Gerbonara** or **PyGerber**. Gerbonara explicitly supports Gerber and Excellon and is available for Python 3.12+; PyGerber provides a modern Gerber parser/rendering API.

## Why the LLM is not the DFM calculator

Manufacturing violations should be evidence-backed. The rule engine measures geometry and compares it to a manufacturer process profile. An eventual LLM planner can select tools, explain findings, propose alternatives, and compose a manufacturing plan — but it should not invent the measured values.

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

## v0.4 — manufacturing decision loop

The native KiCad path now builds a structured PCB model containing nets, tracks, pads, vias, footprints and copper zones. The DFM engine performs net-aware spatial checks, then the agent produces manufacturer routing options and quote scenarios. Every deterministic finding carries geometry IDs that the frontend can highlight.

Pipeline:

`KiCad -> PCB model -> spatial DFM -> BOM risk -> manufacturer capability -> resolution options -> quote scenarios -> agent trace`

The manufacturer profiles and component intelligence are intentionally labeled demo data; replace them with authoritative manufacturer/distributor data before making commercial claims.
