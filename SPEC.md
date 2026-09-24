# ForgeAgent --- Technical Specification

## 1. Purpose

ForgeAgent is an agentic PCB manufacturing review system.

It takes a PCB design and BOM, converts the design into a normalized
engineering representation, runs deterministic manufacturing checks,
extracts manufacturing requirements, compares those requirements against
documented manufacturer capabilities, and produces an evidence-backed
manufacturing feasibility assessment.

**Core principle:** deterministic engineering logic produces the facts;
the agent/LLM reasons over those facts.

The LLM is not the source of truth for PCB geometry, measured
dimensions, DFM violations, or manufacturer capability values.

## 2. End-to-End Procedure

``` text
PCB + BOM
   ↓
1. Ingestion
   ↓
2. KiCad parsing
   ↓
3. Normalized PCB model
   ↓
4. Deterministic DFM analysis ──→ DFM findings
   ↓
5. BOM/component analysis ──────→ BOM findings
   ↓
6. KiCad DRC cross-validation
   ↓
7. Manufacturing requirement extraction
   ↓
8. Manufacturer capability knowledge base
   ↓
9. Requirement ↔ capability evaluation
   ↓
10. Evidence-backed manufacturing feasibility assessment
   ↓
11. Agent/LLM reasoning + manufacturing workflow
```

## 3. Inputs

### PCB

Primary input is a KiCad `.kicad_pcb` board.

The parser extracts, where available:

-   board outline
-   copper layers
-   tracks
-   vias
-   pads
-   footprints
-   nets
-   holes
-   zones
-   pad shapes and dimensions
-   pad and footprint rotation
-   drill dimensions
-   layer information
-   declared manufacturing metadata

### BOM

The BOM is used for component-level analysis.

Relevant fields include:

-   reference designator
-   value
-   footprint
-   manufacturer part number
-   manufacturer
-   lifecycle information where available

Missing component information is reported rather than silently invented.

## 4. PCB Normalization

The KiCad board is converted into a normalized internal model
containing:

-   **Geometry:** tracks, pads, vias, holes, board outline
-   **Connectivity:** nets and feature-to-net relationships
-   **Components:** footprints, references, pads and package metadata
    where identifiable
-   **Manufacturing metadata:** layer count, dimensions, thickness,
    material and declared copper information

This normalized model is the common input to downstream analysis.

## 5. Deterministic DFM Engine

DFM checks are deterministic. The system measures the actual PCB
geometry and applies explicit rules rather than asking an LLM whether a
feature is manufacturable.

Supported checks include:

-   minimum trace width
-   minimum copper clearance
-   pad-to-pad clearance
-   track-to-pad clearance
-   via-to-pad clearance
-   minimum drill size
-   other supported manufacturing constraints

Each finding contains structured evidence such as:

-   rule ID
-   feature A / feature B
-   measured value
-   required threshold
-   involved nets
-   involved layers
-   severity
-   finding type
-   reason

### Geometry handling

The engine applies KiCad board-coordinate transformations correctly,
including footprint and pad rotation.

Supported copper representations include:

-   rectangular pads
-   rounded/roundrect pads
-   circular/oval geometry
-   rotated pad geometry
-   conservative envelope fallback for unsupported/custom primitives

Bounding boxes can be used for broad-phase filtering, while supported
final checks use transformed copper shapes.

### Net awareness

The engine distinguishes:

-   same-net geometry
-   different-net geometry
-   unconnected/NC geometry

This prevents physical proximity from automatically becoming an
electrical violation.

## 6. Finding Classification

### VIOLATION

A deterministic rule measured a value that fails a defined requirement.

### WARNING

A risk or incomplete input was detected, but the evidence does not
establish a hard DFM violation.

### INFO

Contextual information that is not a failure.

BOM completeness warnings remain separate from confirmed PCB geometry
violations.

## 7. BOM / Component Analysis

BOM analysis is separate from geometric DFM.

Examples:

-   missing MPN
-   missing manufacturer information
-   lifecycle risk where supported
-   incomplete component metadata

The system does not fabricate missing part information.

## 8. KiCad DRC Cross-Validation

ForgeAgent can invoke KiCad's DRC tooling and compare its supported DFM
results against the DRC report.

Counts remain separate:

-   **DRC violations** = KiCad violation records
-   **Unconnected items** = KiCad connectivity diagnostics
-   **Total diagnostics** = both categories combined

Unconnected items are not automatically treated as ordinary DRC
violations.

The purpose is cross-validation, not claiming to reproduce every KiCad
DRC rule.

## 9. Manufacturing Requirement Extraction

The analyzed PCB is converted into a normalized
manufacturing-requirements object.

Every requirement has provenance.

### MEASURED

Directly measured/read from the board.

Examples: minimum trace width, minimum drill.

### DERIVED

Calculated from measured geometry.

Examples: board dimensions, net-aware spacing, via spacing, annular
ring.

### METADATA_DERIVED

Inferred from explicit design metadata or identifiers.

Example: recognizing a `0201` package from a KiCad footprint identifier.

### GEOMETRY_DERIVED

Calculated from geometric relationships.

Example: IC pin spacing calculated from pad centers.

### UNKNOWN

The board does not contain enough evidence to establish the value.

Example: inner copper weight when it is not declared.

### NOT_APPLICABLE

The requirement does not apply.

Example: BGA pitch when there is no BGA footprint.

The provenance label prevents inferred values from being presented as
direct measurements.

## 10. Manufacturer Capability Knowledge Base

Manufacturer capabilities are stored as structured records rather than
free-form text.

A capability record can contain:

-   manufacturer
-   process
-   capability type
-   value
-   operator
-   units
-   conditions
-   source
-   source type
-   verification date
-   evidence status

Examples include:

-   minimum trace width
-   minimum spacing
-   minimum drill
-   via dimensions
-   annular ring
-   board dimensions
-   layer count
-   PCB thickness
-   assembly package size
-   IC pin spacing
-   BGA spacing

The current knowledge base uses documented public manufacturer sources.

## 11. Capability Evaluation

For each applicable requirement:

``` text
PCB requirement
+ requirement provenance
+ manufacturer capability
+ capability type
+ conditions
        ↓
evaluation
```

Possible results:

-   **PASS:** documented capability supports the requirement under
    applicable conditions.
-   **FAIL:** documented capability conflicts with the requirement.
-   **CONDITIONAL:** published conditions or conflicting evidence
    prevent an unconditional result.
-   **UNKNOWN:** insufficient published evidence to establish
    compatibility.
-   **NOT_APPLICABLE:** the capability does not apply.

`UNKNOWN` is not converted into `FAIL`.

A known hard failure can block a process; missing evidence remains an
evidence limitation.

## 12. Process Separation

Manufacturing assessment is separated into:

-   fabrication
-   assembly
-   procurement
-   overall manufacturing assessment

A fabrication capability failure does not automatically become an
assembly failure, and incomplete BOM information does not automatically
become a fabrication failure.

## 13. Evidence-Backed Manufacturer Assessment

For every manufacturer/process, the UI exposes:

-   requirement
-   requirement provenance
-   published capability
-   capability type
-   conditions
-   comparison
-   result
-   reason
-   source
-   manufacturer
-   verification date

The system does **not** claim:

-   guaranteed manufacturer acceptance
-   live supplier inventory
-   live pricing
-   guaranteed lead time
-   guaranteed procurement

Those require live integrations or manufacturer confirmation.

## 14. Quotes

Current quote scenarios are explicitly:

**SIMULATED**

Pricing is:

**NOT_CONNECTED**

Therefore the quote layer is a workflow/demo layer, not a claim of live
manufacturer pricing.

## 15. Agent / LLM Layer

The responsibility split is deliberate.

### Deterministic layer

-   parse PCB
-   measure geometry
-   apply DFM rules
-   extract requirements
-   evaluate documented capabilities
-   produce structured evidence

### Agent / LLM layer

-   interpret structured evidence
-   prioritize issues
-   explain findings
-   coordinate tool calls
-   reason over available evidence
-   generate a manufacturing workflow
-   produce human-readable summaries

**Rule:** the model may reason over evidence, but should not invent the
evidence.

For example, the LLM should not independently decide that a 0.12 mm
trace is manufacturable. The deterministic system measures the trace,
and the capability evaluator determines the relevant documented
manufacturer constraint.

## 16. Agent Trace

A representative workflow trace is:

1.  `ingest_project`
2.  `parse_board_geometry`
3.  `build_pcb_model`
4.  `parse_bom`
5.  `run_spatial_geometry_rules`
6.  `inspect_component_risk`
7.  `match_manufacturer_processes`
8.  `resolve_manufacturing_options`
9.  `generate_quote_scenarios`
10. `aggregate_findings`
11. `generate_manufacturing_plan`

The trace makes the workflow inspectable instead of presenting the
result as an opaque model response.

## 17. Risk Score

The dashboard may expose an overall risk score derived from system
findings.

It is a product-level summary, not an engineering measurement.

The underlying evidence remains authoritative:

-   confirmed DFM violations
-   BOM warnings
-   manufacturer failures
-   unresolved evidence
-   process conditions

## 18. Current Demonstration Board

The demonstration uses an open-source ESP32-WROOM-32 KiCad board from
NEAToBOARD.

Current normalized characteristics include:

-   100 × 60 mm board
-   2 copper layers
-   1.6 mm thickness
-   FR-4
-   0.25 mm minimum measured trace width
-   0.30 mm minimum measured drill

Current ForgeAgent result:

-   **0 confirmed DFM geometry violations**
-   **19 BOM missing-MPN warnings**

KiCad's independent DRC output currently contains:

-   **523 DRC violations**
-   **20 unconnected items**
-   **543 diagnostics total**

The 20 unconnected items are kept separate from the 523 DRC violations.

## 19. Current Manufacturer Knowledge Base

The current supported processes are:

### JLCPCB

-   Standard PCB
-   Economic PCBA
-   Standard PCBA

### PCBWay

-   Standard PCB
-   Advanced PCB

Capability records include public source evidence, conditions and
verification dates.

The knowledge base is not live supplier inventory.

## 20. Known Limitations

### Package recognition

Package recognition is deliberately conservative.

For example:

-   `0201` recognition can be `METADATA_DERIVED` from a KiCad footprint
    identifier.
-   IC pin spacing can be `GEOMETRY_DERIVED` from pad centers.
-   BGA requirements can be `NOT_APPLICABLE` when no BGA footprint
    exists.

This is not a universal package-recognition system.

### Manufacturer evidence

Documented capability does not prove current:

-   production availability
-   acceptance of a particular board
-   procurement inventory
-   pricing
-   lead time

### Unknown capabilities

If a manufacturer does not publish enough information, ForgeAgent
reports `UNKNOWN` rather than inventing a value.

### Conditional evidence

Conflicting or process-specific public documentation can result in
`CONDITIONAL`.

### KiCad coverage

ForgeAgent does not attempt to reproduce every KiCad DRC rule. Its DFM
engine covers supported manufacturing rules and uses KiCad DRC as an
independent validation source.

## 21. Design Principles

1.  Evidence before language.
2.  Deterministic engineering checks before LLM reasoning.
3.  Never manufacture missing capability data.
4.  Preserve provenance for every requirement.
5.  Separate geometry violations from BOM warnings.
6.  Separate fabrication, assembly and procurement assessments.
7.  Treat unknown evidence as unknown.
8.  Expose conditions instead of hiding them.
9.  Use external DRC as validation, not as a black-box replacement.
10. Make the reasoning trace inspectable.

## 22. Future Architecture

``` text
PCB
 │
 ├── deterministic DFM
 ├── BOM intelligence
 ├── manufacturer capability intelligence
 ├── procurement intelligence
 │
 ▼
Evidence Graph
 │
 ▼
Agentic Manufacturing Planner
 │
 ├── DFM remediation
 ├── manufacturer/process selection
 ├── procurement
 ├── quoting
 └── production workflow
```

The architectural constraint remains:

**Agentic reasoning operates over structured, traceable engineering
evidence rather than replacing deterministic engineering computation.**
