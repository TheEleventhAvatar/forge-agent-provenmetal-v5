import React,{useMemo,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Upload,Factory,FileCode2,ChevronDown,Crosshair,Layers3,MousePointer2} from 'lucide-react';
import './style.css';
const API='http://localhost:8000';

function BoardViewer({scene,findings,onSelect}){
 const [hover,setHover]=useState(null);
 const [layer,setLayer]=useState('F.Cu');
 if(!scene?.bounds) return null;
 const b=scene.bounds, pad=3, W=820, H=500;
 const sx=(W-2*pad)/b.width_mm, sy=(H-2*pad)/b.height_mm, scale=Math.min(sx,sy);
 const ox=(W-b.width_mm*scale)/2, oy=(H-b.height_mm*scale)/2;
 const X=x=>ox+(x-b.min_x)*scale, Y=y=>H-(oy+(y-b.min_y)*scale);
 const criticalIds=new Set(findings.flatMap(f=>f.evidence?.geometry_ids||[]));
 const selected=new Map(findings.map(f=>[(f.evidence?.geometry_ids||[]).join(','),f]));
 const geomColor=id=>criticalIds.has(id)?'#ff4d4d':'#38d9a9';
 return <div className="boardCard">
   <div className="boardHead"><div><b>Spatial board view</b><span>KiCad geometry · mm</span></div><div className="boardTools"><Layers3 size={15}/><button className={layer==='F.Cu'?'active':''} onClick={()=>setLayer('F.Cu')}>F.Cu</button><button className={layer==='B.Cu'?'active':''} onClick={()=>setLayer('B.Cu')}>B.Cu</button></div></div>
   <div className="boardWrap">
    <svg viewBox={`0 0 ${W} ${H}`} className="boardSvg">
      <rect x={ox} y={H-oy-b.height_mm*scale} width={b.width_mm*scale} height={b.height_mm*scale} rx="2" className="boardBg"/>
      {scene.segments.filter(s=>s.layer===layer).map(s=><line key={s.id} x1={X(s.x1)} y1={Y(s.y1)} x2={X(s.x2)} y2={Y(s.y2)} stroke={geomColor(s.id)} strokeWidth={Math.max(1.5,s.width_mm*scale)} strokeLinecap="round" onMouseEnter={()=>setHover(s.id)} onMouseLeave={()=>setHover(null)} onClick={()=>onSelect(selected.get([s.id].join(',')))} className="geom"/>) }
      {scene.vias.map(v=><g key={v.id}><circle cx={X(v.x)} cy={Y(v.y)} r={Math.max(3,v.size_mm*scale/2)} className={criticalIds.has(v.id)?'via bad':'via'}/><circle cx={X(v.x)} cy={Y(v.y)} r={Math.max(1,v.drill_mm*scale/2)} className="drill"/></g>)}
      {scene.pads.map(p=><g key={p.id} onMouseEnter={()=>setHover(p.id)} onMouseLeave={()=>setHover(null)} onClick={()=>onSelect(selected.get([p.id].join(',')))} className="geom"><circle cx={X(p.x)} cy={Y(p.y)} r={Math.max(2,p.size_x_mm*scale/2)} className={criticalIds.has(p.id)?'pad bad':'pad'}/><circle cx={X(p.x)} cy={Y(p.y)} r={p.drill_mm?Math.max(1,p.drill_mm*scale/2):0} className="drill"/></g>)}
      {findings.map(f=>{const c=f.evidence?.coordinates?.[0]; if(!c)return null; return <circle key={f.id} cx={X((c[0]+c[2])/2)} cy={Y((c[1]+c[3])/2)} r="7" className="violationPulse"/>})}
    </svg>
    {hover&&<div className="hoverTag"><MousePointer2 size={13}/> {hover}</div>}
   </div>
   <div className="boardLegend"><span><i className="legendCopper"/> copper</span><span><i className="legendBad"/> violation</span><span><i className="legendVia"/> via/pad drill</span><span>{scene.nets.length} nets · {scene.segments.length} tracks · {scene.pads.length} pads</span></div>
 </div>
}

function App(){
 const [files,setFiles]=useState([]),[report,setReport]=useState(null),[loading,setLoading]=useState(false),[open,setOpen]=useState(null),[error,setError]=useState(''),[selected,setSelected]=useState(null);
 const run=async()=>{setLoading(true);setError('');try{const fd=new FormData();files.forEach(f=>fd.append('files',f));const r=await fetch(API+'/analyze',{method:'POST',body:fd});const data=await r.json();if(!r.ok)throw new Error(data.detail||'Analysis failed');setReport(data)}catch(e){setError(e.message)}finally{setLoading(false)}};
 const selectFinding=f=>{setSelected(f?.id||null); if(f){const i=report.findings.findIndex(x=>x.id===f.id);setOpen(i)}};
 return <div className="page"><header><div className="brand"><Factory/> FORGEAGENT</div><div className="status"><span/> evidence-backed PCB review</div></header>
 <main><section className="hero"><div className="eyebrow">PCB MANUFACTURING INTELLIGENCE</div><h1>From KiCad geometry to manufacturability.</h1><p>Net-aware spatial analysis of tracks, pads and vias, backed by deterministic evidence and manufacturer capability matching.</p></section>
 <section className="card upload"><label><Upload size={30}/><b>Drop your manufacturing package</b><small>KiCad .kicad_pcb / Gerber / Excellon / BOM CSV</small><input type="file" multiple onChange={e=>setFiles([...e.target.files])}/></label><div className="files">{files.map(f=><span key={f.name}><FileCode2 size={14}/>{f.name}</span>)}</div><div className="actions"><button disabled={!files.length||loading} onClick={run}>{loading?'Running spatial inspection…':'Analyze manufacturing package'}</button><span>Geometry measurements happen deterministically; the agent receives evidence, not raw guesses.</span></div>{error&&<div className="error">{error}</div>}</section>
 {report&&<section className="results"><div className="summary"><Metric label="RISK SCORE" value={`${report.metrics.risk_score}/100`}/><Metric label="CONFIRMED" value={report.metrics.confirmed_violations||0}/><Metric label="WARNINGS" value={report.metrics.warnings||0}/><Metric label="GEOMETRY" value={`${report.metrics.tracks||0} tracks · ${report.metrics.pads||0} pads`}/><Metric label="NETS" value={report.metrics.nets||0}/><Metric label="BOARD" value={report.metrics.board?`${report.metrics.board.width_mm.toFixed(1)} × ${report.metrics.board.height_mm.toFixed(1)} mm`:`—`}/></div>
 <BoardViewer scene={report.metrics.board_scene} findings={report.findings} onSelect={selectFinding}/>
 <h2>Manufacturing findings</h2>{report.findings.map((f,i)=><article className={'finding '+(selected===f.id?'selected':'')} key={f.id} onClick={()=>{setOpen(open===i?null:i);setSelected(f.id)}}><div className={'severity '+f.severity}>!</div><div className="fbody"><div className="ftop"><b>{f.title}</b><ChevronDown className={open===i?'rot':''} size={17}/></div><p>{f.description}</p><small>{f.rule_id} · source: {f.source_tool} · {f.affected_artifact||'project'}</small>{open===i&&<div className="evidence"><b>Evidence</b><pre>{JSON.stringify(f.evidence,null,2)}</pre><div><b>Remediation</b><br/>{f.remediation}</div></div>}</div></article>)}
 <h2>Manufacturer capability matching</h2><div className="manufacturers">{report.manufacturers.map(m=><div className={'manufacturer '+(m.compatible?'ok':'blocked')} key={m.manufacturer}><div><Factory size={17}/><b>{m.manufacturer}</b></div><strong>{m.compatible?'READY':'BLOCKED'}</strong><div className="bar"><i style={{width:m.score+'%'}}/></div>{m.blockers.length?<small>Blockers: {m.blockers.join(' · ')}</small>:<small>{m.satisfied.join(' · ')}</small>}</div>)}</div>
 <h2>Resolution plan</h2><div className="resolution"><div className="planStatus">{report.manufacturing_plan.status.replace('_',' ').toUpperCase()}</div>{report.manufacturing_plan.actions.map(a=><div className="planRow" key={a.finding_id}><b>{a.title}</b><span>{a.details}</span></div>)}{report.manufacturing_plan.options.map((o,i)=><div className="planOption" key={i}><b>{o.title}</b><span>{o.reason||o.details||''}</span></div>)}</div>
 <h2>Quote scenarios</h2><div className="manufacturers">{report.quote_scenarios.map(q=><div className={'manufacturer '+(q.status==='ready'?'ok':'blocked')} key={q.manufacturer}><div><Factory size={17}/><b>{q.manufacturer}</b></div><strong>{q.status.toUpperCase()}</strong><div className="quote">{q.status==='ready'?`Demo estimate: $${q.estimated_fabrication_usd} · ${q.estimated_lead_days} days`:'Blocked by '+q.blocking_reasons.join(' · ')}</div></div>)}</div>
 <h2>Agent trace</h2><div className="trace">{report.trace.map(x=><div className="traceRow" key={x.step}><div className="dot">{x.step}</div><div><b>{x.agent}</b><span>{x.action}</span></div><em>completed</em></div>)}</div></section>}</main></div>
}
function Metric({label,value}){return <div className="metric"><small>{label}</small><strong>{value}</strong></div>}
createRoot(document.getElementById('root')).render(<App/>);
