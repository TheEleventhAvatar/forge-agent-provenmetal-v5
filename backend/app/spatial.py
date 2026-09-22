def board_scene(pcb):
 return {'bounds':pcb.bounds,'outline':pcb.board_outline,
 'segments':[{k:s[k] for k in ('id','x1','y1','x2','y2','width_mm','layer','net','net_name')} for s in pcb.segments],
 'pads':[{k:p[k] for k in ('id','reference','number','x','y','size_x_mm','size_y_mm','drill_mm','layer')}|{'net':p.get('net',0),'net_name':p.get('net_name','')} for p in pcb.pads],
 'vias':[{k:v[k] for k in ('id','x','y','size_mm','drill_mm','layers','net','net_name')} for v in pcb.vias],
 'zones':[{k:z[k] for k in ('id','layer','net','net_name','points')} for z in pcb.zones],
 'footprints':[{k:f[k] for k in ('reference','value','x','y','rotation_deg','layer')} for f in pcb.footprints],
 'nets':[{'id':i,'name':n} for i,n in sorted(pcb.nets.items())]}
