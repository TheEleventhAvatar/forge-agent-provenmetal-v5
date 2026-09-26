from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os

from .agent import ForgeAgent
from .manufacturing.intelligence import knowledge_base, PRICE_DATA_SOURCE


app = FastAPI(
    title="ForgeAgent",
    version="0.3.0",
    description="Evidence-backed agentic PCB DFM and manufacturing review",
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

frontend_origin = os.getenv("FRONTEND_ORIGIN", "").strip().rstrip("/")

allowed_origins = [
    "http://localhost:5173",
    "http://localhost:4173",
    "https://forge-agent-provenmetal-v5.vercel.app",
]

if frontend_origin and frontend_origin not in allowed_origins:
    allowed_origins.append(frontend_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "forge-agent",
    }


# ---------------------------------------------------------------------------
# Manufacturers
# ---------------------------------------------------------------------------

@app.get("/manufacturers")
def manufacturers():
    return {
        "manufacturers": knowledge_base(),
        "price_data_source": PRICE_DATA_SOURCE,
    }


# ---------------------------------------------------------------------------
# PCB Analysis
# ---------------------------------------------------------------------------

@app.post("/analyze")
async def analyze(files: list[UploadFile] = File(...)):
    payload = {}

    allowed_extensions = (
        ".gbr",
        ".gtl",
        ".gbl",
        ".drl",
        ".xln",
        ".csv",
        ".kicad_pcb",
        ".rpt",
    )

    for file in files:
        if not file.filename:
            continue

        filename = file.filename
        lower_filename = filename.lower()

        if not lower_filename.endswith(allowed_extensions):
            continue

        content = await file.read()

        payload[filename] = content.decode(
            "utf-8",
            errors="replace",
        )

    if not payload:
        raise HTTPException(
            status_code=400,
            detail="Upload Gerber, Excellon drill and/or BOM CSV files",
        )

    # -----------------------------------------------------------------------
    # Run ForgeAgent
    # -----------------------------------------------------------------------

    agent = ForgeAgent()

    (
        findings,
        matches,
        trace,
        metrics,
        plan,
        quote,
        validation,
    ) = agent.analyze(payload)

    # -----------------------------------------------------------------------
    # Calculate risk
    # -----------------------------------------------------------------------

    weights = {
        "critical": 40,
        "high": 20,
        "medium": 4,
        "low": 1,
    }

    fabrication = sum(
        weights.get(f.severity, 0)
        for f in findings
        if (
            f.status == "VIOLATION"
            and f.category in {"fabrication", "assembly"}
        )
    )

    procurement = sum(
        weights.get(f.severity, 0)
        for f in findings
        if f.category in {"procurement", "component_risk"}
    )

    warning_risk = sum(
        2
        for f in findings
        if (
            f.status == "WARNING"
            and f.category in {"fabrication", "assembly"}
        )
    )

    risk = min(
        100,
        fabrication
        + warning_risk
        + min(10, procurement // 4),
    )

    confirmed = sum(
        1
        for f in findings
        if (
            f.status == "VIOLATION"
            and f.category in {"fabrication", "assembly"}
            and f.severity in {"critical", "high"}
        )
    )

    warnings = sum(
        1
        for f in findings
        if (
            f.status == "WARNING"
            or f.severity == "medium"
        )
    )

    # -----------------------------------------------------------------------
    # Merge calculated metrics with agent metrics
    # -----------------------------------------------------------------------

    metrics = {
        **metrics,
        "risk_score": risk,
        "confirmed_violations": confirmed,
        "warnings": warnings,
        "fabrication_risk": min(
            100,
            fabrication + warning_risk,
        ),
        "procurement_risk": min(
            100,
            procurement,
        ),
    }

    # -----------------------------------------------------------------------
    # Response
    # -----------------------------------------------------------------------

    manufacturing_requirements = metrics.pop(
        "manufacturing_requirements",
        {},
    )

    requirement_quality = metrics.pop(
        "requirement_quality",
        {},
    )

    manufacturing_routes = metrics.pop(
        "manufacturing_routes",
        [],
    )

    return {
        "project": {
            "name": "uploaded-pcb",
            "artifacts": list(payload.keys()),
        },
        "findings": [
            finding.model_dump()
            for finding in findings
        ],
        "manufacturers": [
            manufacturer.model_dump()
            for manufacturer in matches
        ],
        "manufacturing_requirements": manufacturing_requirements,
        "requirement_quality": requirement_quality,
        "manufacturing_routes": manufacturing_routes,
        "price_data_source": PRICE_DATA_SOURCE,
        "trace": [
            item.model_dump()
            for item in trace
        ],
        "metrics": metrics,
        "manufacturing_plan": plan,
        "quote_scenarios": quote,
        "validation": validation,
    }