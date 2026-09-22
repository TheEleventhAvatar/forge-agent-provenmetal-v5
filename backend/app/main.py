from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .agent import ForgeAgent

app=FastAPI(title="ForgeAgent",version="0.3.0",description="Evidence-backed agentic PCB DFM and manufacturing review")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

@app.get("/health")
def health(): return {"status":"ok","service":"forge-agent"}

@app.post("/analyze")
async def analyze(files:list[UploadFile]=File(...)):
    payload={}
    for f in files:
        if not f.filename: continue
        if not f.filename.lower().endswith((".gbr",".gtl",".gbl",".drl",".xln",".csv",".kicad_pcb")): continue
        payload[f.filename]=(await f.read()).decode("utf-8",errors="replace")
    if not payload: raise HTTPException(400,"Upload Gerber, Excellon drill and/or BOM CSV files")
    agent=ForgeAgent(); findings,matches,trace,metrics,plan,quote=agent.analyze(payload)
    weights={"critical":40,"high":20,"medium":4,"low":1}
    # Only deterministic confirmed fabrication/assembly violations can dominate
    # manufacturing risk. Procurement readiness remains visible but is capped.
    fabrication=sum(weights.get(f.severity,0) for f in findings if f.status=="VIOLATION" and f.category in {"fabrication","assembly"})
    procurement=sum(weights.get(f.severity,0) for f in findings if f.category in {"procurement","component_risk"})
    warning_risk=sum(2 for f in findings if f.status=="WARNING" and f.category in {"fabrication","assembly"})
    risk=min(100,fabrication+warning_risk+min(10,procurement//4))
    confirmed=sum(1 for f in findings if f.status=="VIOLATION" and f.category in {"fabrication","assembly"} and f.severity in {"critical","high"})
    warnings=sum(1 for f in findings if f.status=="WARNING" or f.severity=="medium")
    metrics={**metrics,"risk_score":risk,"confirmed_violations":confirmed,"warnings":warnings,"fabrication_risk":min(100,fabrication+warning_risk),"procurement_risk":min(100,procurement)}
    return {"project":{"name":"uploaded-pcb","artifacts":list(payload)},"findings":[f.model_dump() for f in findings],"manufacturers":[m.model_dump() for m in matches],"trace":[t.model_dump() for t in trace],"metrics":metrics,"manufacturing_plan":plan,"quote_scenarios":quote}
