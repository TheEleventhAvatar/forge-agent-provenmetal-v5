"""Officially sourced public capability claims; absent values stay unknown."""
from copy import deepcopy

RETRIEVED_AT = "2026-09-23"
JLC_PCB = "https://jlcpcb.com/capabilities/Capab"
JLC_ASSEMBLY = "https://jlcpcb.com/capabilities/pcb-assembly-capabilities"
PCBWAY = "https://www.pcbway.com/capabilities.html"


def claim(name, value, unit, url, title, evidence, conditions=None):
    return {"name": name, "value": value, "unit": unit, "conditions": conditions or {},
            "source": {"manufacturer": "JLCPCB" if "jlcpcb" in url else "PCBWay", "url": url,
                       "page_title": title, "retrieved_at": RETRIEVED_AT, "evidence": evidence}}


PROFILES = {
 "jlcpcb": {"manufacturer_id":"jlcpcb", "name":"JLCPCB", "source_retrieved_at":RETRIEVED_AT, "sources":[JLC_PCB,JLC_ASSEMBLY],
   "capabilities":[
    claim("max_layers",32,"layers",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","Layer count: 1-32 copper layers"),
    claim("min_trace_width",.10,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","1- and 2-layer: 0.10 mm; multilayer: 0.09 mm (1 oz)",{"copper_weight_oz":1,"layers":"1-2"}),
    claim("min_trace_width",.09,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","1- and 2-layer: 0.10 mm; multilayer: 0.09 mm (1 oz)",{"copper_weight_oz":1,"layers":"multilayer"}),
    claim("min_spacing",.10,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","1- and 2-layer: 0.10 mm; multilayer: 0.09 mm (1 oz)",{"copper_weight_oz":1,"layers":"1-2"}),
    claim("min_spacing",.09,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","1- and 2-layer: 0.10 mm; multilayer: 0.09 mm (1 oz)",{"copper_weight_oz":1,"layers":"multilayer"}),
    claim("min_drill",.15,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","Minimum drill diameter for 2-or-more-layer PCBs is 0.15 mm",{"layers":"2 or more","board_type":"rigid FR-4"}),
    claim("min_via_hole",.15,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","2-layer and multilayer via hole size: 0.15 mm",{"layers":"2 or more"}),
    claim("min_via_diameter",.25,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","2-layer and multilayer via diameter: 0.25 mm",{"layers":"2 or more"}),
    claim("min_pad_to_track_clearance",.10,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","Pad to track clearance: minimum 0.1 mm"),
    claim("min_smd_pad_clearance",.15,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","SMD pad-to-pad clearance for different nets: 0.15 mm"),
    claim("min_pth_annular_ring",.18,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","2-layer 1 oz PTH annular ring absolute minimum: 0.18 mm",{"layers":2,"copper_weight_oz":1}),
    claim("min_pth_annular_ring",.15,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","Multilayer 1 oz PTH annular ring absolute minimum: 0.15 mm",{"layers":"multilayer","copper_weight_oz":1}),
    claim("min_pth_annular_ring",.254,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","PTH annular ring minimum for 2 oz copper: 0.254 mm",{"layers":"2 or more","copper_weight_oz":2}),
    claim("min_via_annular_ring",.18,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","2-layer 1 oz PTH annular ring absolute minimum: 0.18 mm",{"layers":2,"copper_weight_oz":1}),
    claim("min_via_annular_ring",.15,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","Multilayer 1 oz PTH annular ring absolute minimum: 0.15 mm",{"layers":"multilayer","copper_weight_oz":1}),
    claim("min_via_annular_ring",.254,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","PTH annular ring minimum for 2 oz copper: 0.254 mm",{"layers":"2 or more","copper_weight_oz":2}),
    claim("max_board_width",670,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","FR-4 2-layer maximum dimension: 670 × 600 mm",{"layers":2,"dimension":"width","thickness_mm_min":.8}),
    claim("max_board_height",600,"mm",JLC_PCB,"PCB Manufacturing & Assembly Capabilities - JLCPCB","FR-4 2-layer maximum dimension: 670 × 600 mm",{"layers":2,"dimension":"height","thickness_mm_min":.8}),
    claim("max_layers",32,"layers",JLC_ASSEMBLY,"PCB Manufacturing & Assembly Capabilities - JLCPCB","Standard PCBA PCB layer: 1-32 layers",{"service":"standard PCBA"}),
    claim("min_package","0201","package",JLC_ASSEMBLY,"PCB Manufacturing & Assembly Capabilities - JLCPCB","The PCBA technical table lists 0201 for Standard PCBA; the same official page FAQ separately states that 01005 components are supported, without clarifying process-specific scope.",{"service":"standard PCBA"}),
    claim("min_ic_pin_spacing",.35,"mm",JLC_ASSEMBLY,"PCB Manufacturing & Assembly Capabilities - JLCPCB","Standard PCBA minimum IC pin spacing: 0.35 mm",{"service":"standard PCBA"}),
    claim("min_bga_spacing",.30,"mm",JLC_ASSEMBLY,"PCB Manufacturing & Assembly Capabilities - JLCPCB","Standard PCBA minimum BGA spacing 0.3 mm center-to-center",{"service":"standard PCBA","measurement":"center-to-center"}),
   ]},
 "pcbway": {"manufacturer_id":"pcbway", "name":"PCBWay", "source_retrieved_at":RETRIEVED_AT, "sources":[PCBWAY,"https://www.pcbway.com/advanced-pcb-capabilities.html"],
   "capabilities":[
    claim("max_layers",14,"layers",PCBWAY,"PCB Capabilities - PCBWay","Standard PCB number of layers: 1-14",{"process":"standard PCB"}),
    claim("max_board_width",600,"mm",PCBWAY,"PCB Capabilities - PCBWay","Single/double-sided maximum 600 × 1200 mm",{"process":"standard PCB","layers":"1-2","dimension":"width"}),
    claim("max_board_height",1200,"mm",PCBWAY,"PCB Capabilities - PCBWay","Single/double-sided maximum 600 × 1200 mm",{"process":"standard PCB","layers":"1-2","dimension":"height"}),
    claim("max_board_width",560,"mm",PCBWAY,"PCB Capabilities - PCBWay","Multilayer maximum 560 × 1150 mm",{"process":"standard PCB","layers":"multilayer","dimension":"width"}),
    claim("max_board_height",1150,"mm",PCBWAY,"PCB Capabilities - PCBWay","Multilayer maximum 560 × 1150 mm",{"process":"standard PCB","layers":"multilayer","dimension":"height"}),
    claim("min_board_width",3,"mm",PCBWAY,"PCB Capabilities - PCBWay","Standard PCB minimum size is 3 × 3 mm",{"process":"standard PCB","dimension":"width"}),
    claim("min_board_height",3,"mm",PCBWAY,"PCB Capabilities - PCBWay","Standard PCB minimum size is 3 × 3 mm",{"process":"standard PCB","dimension":"height"}),
    claim("min_trace_width",.10,"mm",PCBWAY,"PCB Capabilities - PCBWay","Minimum manufacturable trace 4 mil (0.1 mm)",{"process":"standard PCB"}),
    claim("min_spacing",.10,"mm",PCBWAY,"PCB Capabilities - PCBWay","Minimum manufacturable spacing 4 mil (0.1 mm)",{"process":"standard PCB"}),
    claim("min_drill",.15,"mm",PCBWAY,"PCB Capabilities - PCBWay","Minimum CNC drill 0.15 mm",{"process":"standard PCB"}),
    claim("min_via_hole",.15,"mm",PCBWAY,"PCB Capabilities - PCBWay","Minimum CNC drill 0.15 mm applies to mechanically drilled holes",{"process":"standard PCB","drill":"CNC"}),
    claim("min_annular_ring",.15,"mm",PCBWAY,"PCB Capabilities - PCBWay","Minimum annular ring width 0.15 mm for pads with vias in middle",{"feature":"via-in-pad"}),
    claim("min_via_hole",.15,"mm","https://www.pcbway.com/advanced-pcb-capabilities.html","Advanced High-quality PCB Capabilities - PCBWay","Advanced PCB minimum hole size: 0.15 mm CNC",{"process":"advanced PCB","drill":"CNC"}),
    claim("max_layers",64,"layers","https://www.pcbway.com/advanced-pcb-capabilities.html","Advanced High-quality PCB Capabilities - PCBWay","Maximum layer count: 64 layers",{"process":"advanced PCB"}),
   ]},
}

# Additional explicit values from the same official capability tables.
_jtitle = "PCB Manufacturing & Assembly Capabilities - JLCPCB"
_ptitle = "Advanced High-quality PCB Capabilities - PCBWay"
PROFILES["jlcpcb"]["capabilities"] += [
 claim("max_layers",[2,4,6],"layers",JLC_ASSEMBLY,"PCB Assembly Capabilities - JLCPCB","Economic PCBA supports 2-, 4- and 6-layer boards",{"service":"economic PCBA"}),
 claim("max_board_width",470,"mm",JLC_ASSEMBLY,"PCB Assembly Capabilities - JLCPCB","Economic PCBA single-board maximum dimension 470 x 500 mm",{"service":"economic PCBA","dimension":"width"}),
 claim("max_board_height",500,"mm",JLC_ASSEMBLY,"PCB Assembly Capabilities - JLCPCB","Economic PCBA single-board maximum dimension 470 x 500 mm",{"service":"economic PCBA","dimension":"height"}),
 claim("min_board_width",10,"mm",JLC_ASSEMBLY,"PCB Assembly Capabilities - JLCPCB","Economic PCBA single-board minimum dimension 10 x 10 mm",{"service":"economic PCBA","dimension":"width"}),
 claim("min_board_height",10,"mm",JLC_ASSEMBLY,"PCB Assembly Capabilities - JLCPCB","Economic PCBA single-board minimum dimension 10 x 10 mm",{"service":"economic PCBA","dimension":"height"}),
 claim("max_board_width",460,"mm",JLC_ASSEMBLY,"PCB Assembly Capabilities - JLCPCB","Standard PCBA single-board maximum dimension 460 x 500 mm",{"service":"standard PCBA","dimension":"width"}),
 claim("max_board_height",500,"mm",JLC_ASSEMBLY,"PCB Assembly Capabilities - JLCPCB","Standard PCBA single-board maximum dimension 460 x 500 mm",{"service":"standard PCBA","dimension":"height"}),
 claim("min_board_width",70,"mm",JLC_ASSEMBLY,"PCB Assembly Capabilities - JLCPCB","Standard PCBA single-board minimum dimension 70 x 70 mm",{"service":"standard PCBA","dimension":"width"}),
 claim("min_board_height",70,"mm",JLC_ASSEMBLY,"PCB Assembly Capabilities - JLCPCB","Standard PCBA single-board minimum dimension 70 x 70 mm",{"service":"standard PCBA","dimension":"height"}),
 claim("min_package","0402","package",JLC_ASSEMBLY,"PCB Assembly Capabilities - JLCPCB","The PCBA technical table lists 0402 for Economic PCBA; the same official page FAQ separately states that 01005 components are supported, without clarifying process-specific scope.",{"service":"economic PCBA"}),
 claim("min_ic_pin_spacing",.4,"mm",JLC_ASSEMBLY,"PCB Assembly Capabilities - JLCPCB","Economic PCBA minimum IC pin spacing 0.4 mm",{"service":"economic PCBA"}),
 claim("min_bga_spacing",.5,"mm",JLC_ASSEMBLY,"PCB Assembly Capabilities - JLCPCB","Economic PCBA minimum BGA spacing 0.5 mm center-to-center",{"service":"economic PCBA","measurement":"center-to-center"}),
 claim("min_board_width",3,"mm",JLC_PCB,_jtitle,"Minimum PCB dimensions are 3 x 3 mm",{"board_type":"FR-4/Rogers/PTFE","thickness_mm_min":0.6}),
 claim("min_board_height",3,"mm",JLC_PCB,_jtitle,"Minimum PCB dimensions are 3 x 3 mm",{"board_type":"FR-4/Rogers/PTFE","thickness_mm_min":0.6}),
 claim("max_board_width",663,"mm",JLC_PCB,_jtitle,"FR-4 4-layer maximum dimension is 663 x 593 mm for thickness >=0.8 mm",{"layers":4,"thickness_mm_min":0.8,"dimension":"width"}),
 claim("max_board_height",593,"mm",JLC_PCB,_jtitle,"FR-4 4-layer maximum dimension is 663 x 593 mm for thickness >=0.8 mm",{"layers":4,"thickness_mm_min":0.8,"dimension":"height"}),
 claim("max_board_width",656,"mm",JLC_PCB,_jtitle,"FR-4 6-layer and above maximum dimension is 656 x 586 mm for thickness >=0.8 mm",{"layers":"6 or more","thickness_mm_min":0.8,"dimension":"width"}),
 claim("max_board_height",586,"mm",JLC_PCB,_jtitle,"FR-4 6-layer and above maximum dimension is 656 x 586 mm for thickness >=0.8 mm",{"layers":"6 or more","thickness_mm_min":0.8,"dimension":"height"}),
 claim("min_trace_width",.16,"mm",JLC_PCB,_jtitle,"2 oz copper trace/space minimum is 0.16/0.16 mm",{"copper_weight_oz":2,"layers":"1-2"}),
 claim("min_spacing",.16,"mm",JLC_PCB,_jtitle,"2 oz copper trace/space minimum is 0.16/0.16 mm",{"copper_weight_oz":2,"layers":"1-2"}),
 claim("trace_width_tolerance",20,"percent",JLC_PCB,_jtitle,"Track width tolerance is +/-20 percent"),
 claim("min_via_hole_spacing",.2,"mm",JLC_PCB,_jtitle,"Minimum via hole-to-hole spacing is 0.2 mm"),
 claim("via_hole_to_track_clearance",.2,"mm",JLC_PCB,_jtitle,"Via hole-to-track clearance is 0.2 mm"),
 claim("pth_to_track_clearance",.28,"mm",JLC_PCB,_jtitle,"PTH-to-track minimum is 0.28 mm"),
 claim("npth_to_track_clearance",.2,"mm",JLC_PCB,_jtitle,"NPTH-to-track clearance is 0.2 mm"),
 claim("min_solder_mask_bridge",.1,"mm",JLC_PCB,_jtitle,"Solder mask bridge minimum 0.10 mm for specified 1 oz colors",{"copper_weight_oz":1,"mask_color":"green/red/yellow/blue/purple"}),
 claim("min_plated_slot_width",.5,"mm",JLC_PCB,_jtitle,"Minimum plated slot width is 0.5 mm for 1-2 layers",{"layers":"1-2"}),
]
PROFILES["pcbway"]["capabilities"] += [
 claim("min_drill",.15,"mm","https://www.pcbway.com/advanced-pcb-capabilities.html",_ptitle,"Advanced minimum hole size is 0.15 mm for CNC; 0.1 mm for laser blind/buried vias",{"drill":"CNC","process":"advanced PCB"}),
 claim("max_board_width",609,"mm","https://www.pcbway.com/advanced-pcb-capabilities.html",_ptitle,"Maximum advanced PCB size is 609 x 889 mm",{"dimension":"width","process":"advanced PCB"}),
 claim("max_board_height",889,"mm","https://www.pcbway.com/advanced-pcb-capabilities.html",_ptitle,"Maximum advanced PCB size is 609 x 889 mm",{"dimension":"height","process":"advanced PCB"}),
 claim("min_trace_width",.0508,"mm","https://www.pcbway.com/advanced-pcb-capabilities.html",_ptitle,"Advanced inner trace width 2 mil with H/H oz base copper, partial traces/spaces only",{"layer_position":"inner","base_copper":"H/H oz","partial_features_only":True,"process":"advanced PCB"}),
 claim("min_spacing",.0508,"mm","https://www.pcbway.com/advanced-pcb-capabilities.html",_ptitle,"Advanced inner spacing 2 mil with H/H oz base copper, partial traces/spaces only",{"layer_position":"inner","base_copper":"H/H oz","partial_features_only":True,"process":"advanced PCB"}),
 claim("min_trace_width",.0508,"mm","https://www.pcbway.com/advanced-pcb-capabilities.html",_ptitle,"Advanced outer trace width 2 mil with 1/3 oz base copper, partial traces/spaces only",{"layer_position":"outer","base_copper":"1/3 oz","partial_features_only":True,"process":"advanced PCB"}),
 claim("min_spacing",.0508,"mm","https://www.pcbway.com/advanced-pcb-capabilities.html",_ptitle,"Advanced outer spacing 2 mil with 1/3 oz base copper, partial traces/spaces only",{"layer_position":"outer","base_copper":"1/3 oz","partial_features_only":True,"process":"advanced PCB"}),
 claim("min_via_annular_ring",.0762,"mm","https://www.pcbway.com/advanced-pcb-capabilities.html",_ptitle,"Advanced via annular ring minimum 3 mil",{"process":"advanced PCB"}),
 claim("min_component_hole_annular_ring",.127,"mm","https://www.pcbway.com/advanced-pcb-capabilities.html",_ptitle,"Advanced component-hole annular ring minimum 5 mil",{"process":"advanced PCB"}),
    claim("min_component_hole_spacing",.4064,"mm","https://www.pcbway.com/advanced-pcb-capabilities.html",_ptitle,"Advanced capability table: component hole-to-hole spacing at least 16 mil",{"process":"advanced PCB"}),
 claim("min_via_hole_spacing",.2794,"mm",PCBWAY,_ptitle,"Advanced capability table: spacing for vias up to 0.45 mm is at least 11 mil",{"process":"advanced PCB","via_diameter_max_mm":0.45}),
 claim("min_bga_pitch",.4,"mm","https://www.pcbway.com/advanced-pcb-capabilities.html",_ptitle,"Advanced PCB BGA pitch minimum 0.4 mm",{"process":"advanced PCB"}),
 claim("max_aspect_ratio",20,"ratio","https://www.pcbway.com/advanced-pcb-capabilities.html",_ptitle,"Maximum aspect ratio 20:1",{"process":"advanced PCB"}),
 claim("min_solder_mask_bridge",.0762,"mm","https://www.pcbway.com/advanced-pcb-capabilities.html",_ptitle,"Minimum solder mask bridge 3 mil",{"process":"advanced PCB"}),
]


def load_manufacturer_profiles():
    """Return isolated profile data, preserving each condition and provenance."""
    return deepcopy(PROFILES)
