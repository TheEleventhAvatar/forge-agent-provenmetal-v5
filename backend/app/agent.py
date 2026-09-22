from .parsers import parse_gerber,parse_excellon,parse_bom
from .rules import run_dfm,inspect_bom,match_manufacturers
from .kicad import parse_kicad_pcb
from .kicad_rules import run_kicad_dfm,match_kicad_manufacturers
from .models import AgentStep
from .spatial import board_scene

PART_CATALOG={
 'ESP8266EX':{'status':'not_recommended','stock':14,'required_default':50,'lead_weeks':16,'alternatives':['ESP32-WROOM-32E'],'reason':'lifecycle/procurement risk'},
 'STM32F103C8T6':{'status':'ok','stock':2400,'lead_weeks':2,'alternatives':[],'reason':'normal availability'},
}
class ForgeAgent:
 def __init__(self):self.trace=[]
 def step(self,agent,action,details=None):self.trace.append(AgentStep(step=len(self.trace)+1,agent=agent,action=action,details=details or {}))
 def analyze(self,files):
  self.step('orchestrator','ingest_project',{'files':list(files)})
  k=next((n for n in files if n.lower().endswith('.kicad_pcb')),None);g=next((n for n in files if n.lower().endswith(('.gbr','.gtl','.gbl'))),None);d=next((n for n in files if n.lower().endswith(('.drl','.xln'))),None);b=next((n for n in files if n.lower().endswith('.csv')),None)
  pcb=geo=drill=None
  if k:
   pcb=parse_kicad_pcb(k,files[k]);self.step('kicad-parser','parse_board_geometry',{'artifact':k,'segments':len(pcb.segments),'pads':len(pcb.pads),'footprints':len(pcb.footprints),'nets':len(pcb.nets),'vias':len(pcb.vias),'zones':len(pcb.zones)});self.step('kicad-parser','build_pcb_model',{'layers':list(pcb.layers),'bounds':pcb.bounds})
  elif g:
   geo=parse_gerber(g,files[g]);self.step('pcb-parser','parse_gerber',{'artifact':g,'tracks':len(geo.tracks),'flashes':len(geo.flashes)})
  if d:
   drill=parse_excellon(d,files[d]);self.step('pcb-parser','parse_excellon',{'artifact':d,'holes':len(drill.holes)})
  rows=parse_bom(b,files[b]) if b else [];self.step('bom-agent','parse_bom',{'artifact':b,'rows':len(rows)})
  self.step('dfm-agent','run_spatial_geometry_rules',{'mode':'KiCad native' if pcb else 'Gerber/Excellon','rules':['trace_width','cross_net_clearance','pad_clearance','via_clearance','drill','hole_edge','board_size','zone_geometry']})
  findings=run_kicad_dfm(pcb) if pcb else (run_dfm(geo,drill) if geo else [])
  self.step('bom-agent','inspect_component_risk',{'rows':len(rows)});bom_findings=inspect_bom(rows);findings+=bom_findings
  self.step('capability-agent','match_manufacturer_processes');matches=match_kicad_manufacturers(pcb) if pcb else (match_manufacturers(geo,drill) if geo else [])
  plan=self._resolution_plan(findings,matches,rows)
  self.step('resolution-agent','resolve_manufacturing_options',{'options':len(plan['options'])})
  quote=self._quote(plan,matches,rows)
  self.step('quote-agent','generate_quote_scenarios',{'scenarios':len(quote)})
  self.step('evidence-agent','aggregate_findings',{'findings':len(findings)})
  self.step('report-agent','generate_manufacturing_plan',{'actions':len(plan['actions'])})
  metrics={'tracks':len(pcb.segments) if pcb else len(geo.tracks) if geo else 0,'pads':len(pcb.pads) if pcb else 0,'footprints':len(pcb.footprints) if pcb else 0,'nets':len(pcb.nets) if pcb else 0,'vias':len(pcb.vias) if pcb else 0,'zones':len(pcb.zones) if pcb else 0,'holes':len(pcb.through_holes) if pcb else len(drill.holes) if drill else 0,'bom_rows':len(rows),'min_feature_mm':pcb.min_trace_mm if pcb else geo.min_feature_mm if geo else None,'min_drill_mm':pcb.min_drill_mm if pcb else drill.min_drill_mm if drill else None,'board':pcb.bounds if pcb else None,'board_scene':board_scene(pcb) if pcb else None}
  return findings,matches,self.trace,metrics,plan,quote
 def _resolution_plan(self,findings,matches,rows):
  actions=[];opts=[]
  for f in findings:
   if f.rule_id in {'MIN_TRACE_WIDTH','MIN_COPPER_CLEARANCE','PAD_CLEARANCE','VIA_CLEARANCE','VIA_PAD_CLEARANCE','TRACK_PAD_CLEARANCE','TRACK_VIA_CLEARANCE','MIN_DRILL'}:
    actions.append({'finding_id':f.id,'action':'modify_pcb','title':f'Remediate {f.title}','details':f.remediation,'geometry_ids':f.evidence.get('geometry_ids',[])})
  compatible=[m for m in matches if m.compatible]
  if compatible:opts.append({'type':'route','title':f'Route to {compatible[0].manufacturer}','manufacturer':compatible[0].manufacturer,'reason':'All confirmed deterministic DFM constraints fit this demo process profile.'})
  for f in findings:
   if f.rule_id=='PART_LIFECYCLE':opts.append({'type':'substitute','title':'Qualify BOM alternative','details':f.remediation,'mpn':f.evidence.get('mpn')})
  fabrication_blockers=[f for f in findings if f.category in {'fabrication','assembly'} and f.status=='VIOLATION' and f.severity in {'critical','high'}]
  return {'status':'requires_changes' if fabrication_blockers else 'review','actions':actions,'options':opts}
 def _quote(self,plan,matches,rows):
  scenarios=[]
  for m in matches:
   base=180 if 'Prototype' in m.manufacturer else 230
   complexity=20+max(0,len(rows)-10)*2
   scenarios.append({'manufacturer':m.manufacturer,'status':'ready' if m.compatible else 'blocked','estimated_fabrication_usd':base+complexity if m.compatible else None,'estimated_lead_days':7 if m.compatible else None,'is_demo':True,'blocking_reasons':m.blockers})
  return scenarios
