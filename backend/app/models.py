from pydantic import BaseModel, Field
from typing import Any, Literal

class Finding(BaseModel):
    id: str
    rule_id: str
    severity: Literal["low","medium","high","critical"]
    title: str
    description: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    affected_artifact: str | None = None
    remediation: str
    source_tool: str = "deterministic-rule"
    # Additive fields: existing clients can continue using severity/evidence.
    status: Literal["VIOLATION", "WARNING", "INFO"] = "VIOLATION"
    category: Literal["fabrication", "assembly", "procurement", "component_risk"] = "fabrication"

class AgentStep(BaseModel):
    step: int
    agent: str
    action: str
    status: str = "completed"
    details: dict[str, Any] = Field(default_factory=dict)

class ManufacturerMatch(BaseModel):
    manufacturer: str
    compatible: bool
    score: float
    blockers: list[str]
    satisfied: list[str]

class ManufacturingPlan(BaseModel):
    status: str
    actions: list[dict[str, Any]] = Field(default_factory=list)
    options: list[dict[str, Any]] = Field(default_factory=list)

class AnalysisResult(BaseModel):
    project: dict[str, Any]
    findings: list[Finding]
    manufacturers: list[ManufacturerMatch]
    trace: list[AgentStep]
    metrics: dict[str, Any]
