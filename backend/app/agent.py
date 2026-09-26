from .parsers import parse_gerber,parse_excellon,parse_bom
from .rules import run_dfm,inspect_bom
from .kicad import parse_kicad_pcb
from .kicad_rules import run_kicad_dfm
from .manufacturing.capability_matcher import match_capabilities
from .manufacturing.intelligence import evaluate as evaluate_manufacturing, requirement_quality
from .validation.kicad_drc import run_kicad_drc, parse_drc_report
from .validation.cross_validator import cross_validate
from .models import AgentStep
from .spatial import board_scene

class ForgeAgent:
 def __init__(self):self.trace=[]
 def step(self,agent,action,details=None):self.trace.append(AgentStep(step=len(self.trace)+1,agent=agent,action=action,details=details or {}))
 def analyze(self,files):
  self.step('orchestrator','ingest_project',{'files':list(files)})
  k=next((n for n in files if n.lower().endswith('.kicad_pcb')),None);g=next((n for n in files if n.lower().endswith(('.gbr','.gtl','.gbl'))),None);d=next((n for n in files if n.lower().endswith(('.drl','.xln'))),None);b=next((n for n in files if n.lower().endswith('.csv')),None);rpt=next((n for n in files if n.lower().endswith('.rpt')),None)
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
  validation={"status":"VALIDATION_UNAVAILABLE","reason":"KiCad DRC applies only to KiCad PCB inputs.","artifact":None,"cross_validation":None}
  if k:
   self.step('kicad-drc','load_or_run_independent_kicad_drc',{'artifact':k,'source':'uploaded_report' if rpt else 'kicad_cli'})
   if rpt:
    parsed=parse_drc_report(files[rpt]); drc={"available":True,"artifact":{"name":rpt,"media_type":"text/plain","content":files[rpt]},"parsed":parsed,"source":"uploaded_report"}
   else:
    drc=run_kicad_drc(k,files[k]); parsed=drc.get('parsed'); drc['source']='kicad_cli'
   validation={"status":"available" if parsed else "VALIDATION_UNAVAILABLE","source":drc.get('source'),"artifact":drc.get('artifact'),"kicad_summary":{"violation_count":parsed.get('violation_count',parsed.get('total_violations')),"unconnected_item_count":parsed.get('unconnected_item_count',0),"total_diagnostics":parsed.get('total_diagnostics',len(parsed.get('violations',[]))),"parsed_violations":len(parsed.get('violations',[])),"parsed_unconnected_items":len(parsed.get('unconnected_items',[])),"total_violations":parsed.get('violation_count',parsed.get('total_violations')),"count_discrepancy":parsed.get("violation_count_discrepancy",parsed.get("count_discrepancy",False)),"count_note":"Report headline count differs from parsed DRC violation records." if parsed.get("violation_count_discrepancy",parsed.get("count_discrepancy")) else None} if parsed else None,"reason":drc.get('reason')}
   validation["cross_validation"]=cross_validate(findings,parsed,pcb) if parsed else {"summary":{"status":"VALIDATION_UNAVAILABLE","corroborated":0,"forgeagent_only":len(findings),"kicad_only":0,"unconnected_items":0,"unmapped":0}}
   self.step('cross-validator','map_drc_to_forgeagent_evidence',validation["cross_validation"]["summary"] if parsed else {'status':'VALIDATION_UNAVAILABLE'})
  self.step('bom-agent','inspect_component_risk',{'rows':len(rows)});bom_findings=inspect_bom(rows);findings+=bom_findings
  self.step('capability-agent','extract_requirements_and_evaluate_manufacturer_processes')
  requirements,routes=evaluate_manufacturing(pcb,geo,drill)
  requirement_states=requirement_quality(requirements,pcb)
  # Legacy manufacturer summary remains available for existing consumers; detailed
  # process decisions are exposed independently in manufacturing_routes.
  from .models import ManufacturerMatch
  matches=[]
  for name in dict.fromkeys(r['manufacturer'] for r in routes):
   rs=[r for r in routes if r['manufacturer']==name and r['domain']=='fabrication']
   best=next((r for r in rs if r['status']=='PASS'),rs[0] if rs else None)
   if best: matches.append(ManufacturerMatch(manufacturer=name,compatible=best['status']=='PASS',status=best['status'],score=0,blockers=[x['reason'] for x in best['matrix'] if x['status']=='FAIL'],satisfied=[x['parameter'] for x in best['matrix'] if x['status']=='PASS'],reasons=best['unknowns'],evidence=best['matrix'],unknowns=best['unknowns'],sources=list(dict.fromkeys(x['source']['url'] for x in best['matrix'] if x.get('source'))),capabilities=[]))
  plan=self._resolution_plan(findings,matches,rows)
  self.step('resolution-agent','resolve_manufacturing_options',{'options':len(plan['options'])})
  quote=self._quote(plan,matches,rows)
  self.step('quote-agent','generate_quote_scenarios',{'scenarios':len(quote)})
  self.step('evidence-agent','aggregate_findings',{'findings':len(findings)})
  self.step('report-agent','generate_manufacturing_plan',{'actions':len(plan['actions'])})
  metrics={'tracks':len(pcb.segments) if pcb else len(geo.tracks) if geo else 0,'pads':len(pcb.pads) if pcb else 0,'footprints':len(pcb.footprints) if pcb else 0,'nets':len(pcb.nets) if pcb else 0,'vias':len(pcb.vias) if pcb else 0,'zones':len(pcb.zones) if pcb else 0,'holes':len(pcb.through_holes) if pcb else len(drill.holes) if drill else 0,'bom_rows':len(rows),'min_feature_mm':pcb.min_trace_mm if pcb else geo.min_feature_mm if geo else None,'min_drill_mm':pcb.min_drill_mm if pcb else drill.min_drill_mm if drill else None,'board':pcb.bounds if pcb else None,'board_scene':board_scene(pcb) if pcb else None}
  metrics['manufacturing_requirements']=requirements
  metrics['requirement_quality']=requirement_states
  metrics['manufacturing_routes']=routes
  return findings,matches,self.trace,metrics,plan,quote,validation
 def _resolution_plan(self,findings,matches,rows):
  actions=[];opts=[]
  for f in findings:
   if f.rule_id in {'MIN_TRACE_WIDTH','MIN_COPPER_CLEARANCE','PAD_CLEARANCE','VIA_CLEARANCE','VIA_PAD_CLEARANCE','TRACK_PAD_CLEARANCE','TRACK_VIA_CLEARANCE','MIN_DRILL'}:
    actions.append({'finding_id':f.id,'action':'modify_pcb','title':f'Remediate {f.title}','details':f.remediation,'geometry_ids':f.evidence.get('geometry_ids',[])})
  compatible=[m for m in matches if m.compatible]
  if compatible:opts.append({'type':'route','title':f'Compare published capabilities for {compatible[0].manufacturer}','manufacturer':compatible[0].manufacturer,'reason':'Measured dimensions meet the published capability profile for checked conditions.'})
  for f in findings:
   if f.rule_id=='PART_LIFECYCLE':opts.append({'type':'substitute','title':'Qualify BOM alternative','details':f.remediation,'mpn':f.evidence.get('mpn')})
  fabrication_blockers=[f for f in findings if f.category in {'fabrication','assembly'} and f.status=='VIOLATION' and f.severity in {'critical','high'}]
  return {'status':'requires_changes' if fabrication_blockers else 'review','actions':actions,'options':opts}
 def _quote(self,plan,matches,rows):
  scenarios=[]
  for m in matches:
   scenarios.append({'manufacturer':m.manufacturer,'status':'capability_review_required','estimate_type':'SIMULATED — not a live manufacturer quote.','actual_quote':False,'estimated_fabrication_usd':None,'estimated_lead_days':None,'blocking_reasons':m.blockers,'capability_status':m.status,'price_data_source':'NOT_CONNECTED'})
  return scenarios
