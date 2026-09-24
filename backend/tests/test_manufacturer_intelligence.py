import unittest
from app.manufacturing.intelligence import knowledge_base, extract_requirements, evaluate, PRICE_DATA_SOURCE
from app.manufacturing.evaluator import aggregate_route_status
from app.kicad import PCBModel

class ManufacturerIntelligenceTests(unittest.TestCase):
    def test_process_model_and_provenance(self):
        kb=knowledge_base()
        self.assertEqual({p['process_id'] for m in kb for p in m['processes']},{'standard_pcb','advanced_pcb','economic_pcba','standard_pcba'})
        for m in kb:
            for p in m['processes']:
                for c in p['capabilities']:
                    self.assertTrue(c['source']['url'].startswith('https://'))
                    self.assertTrue(c['source']['evidence_note'])
                    self.assertTrue(c['last_verified_at'])
                    self.assertIn(c['capability_type'],{'HARD_CAPABILITY','CONDITIONAL_CAPABILITY','RECOMMENDED','TYPICAL'})
                for c in p['unknown_capabilities']:
                    self.assertEqual(c['capability_type'],'UNSPECIFIED')
                    self.assertIsNone(c['source'])
    def test_unknown_inputs_remain_unknown_and_prices_disconnected(self):
        req=extract_requirements(PCBModel(file='x'))
        self.assertIsNone(req['copper_weight_oz'])
        self.assertIsNone(req['board_thickness_mm'])
        self.assertEqual(PRICE_DATA_SOURCE,'NOT_CONNECTED')
    def test_layer_measurement_and_route_coverage(self):
        pcb=PCBModel(file='x',layers={'F.Cu','B.Cu'},bounds={'width_mm':40,'height_mm':30},segments=[{'width_mm':.12}],through_holes=[{'drill_mm':.2}],vias=[{'drill_mm':.2,'size_mm':.4}])
        req,routes=evaluate(pcb)
        self.assertEqual(req['layer_count'],2)
        self.assertEqual(req['min_trace_width_mm'],.12)
        self.assertEqual(req['min_drill_mm'],.2)
        self.assertTrue(all('capability_coverage' in r and 'matrix' in r for r in routes))
        self.assertTrue(any(r['domain']=='assembly' and r['status'] in {'UNKNOWN','CONDITIONAL'} for r in routes))
        self.assertTrue(any(x['status']=='UNKNOWN' for r in routes for x in r['matrix']))
    def test_processes_are_evaluated_separately(self):
        pcb=PCBModel(file='x',layers={'F.Cu','B.Cu'},bounds={'width_mm':40,'height_mm':30},segments=[{'width_mm':.08}])
        _,routes=evaluate(pcb)
        jlc={r['process_id']:r for r in routes if r['manufacturer_id']=='jlcpcb' and r['domain']=='fabrication'}
        self.assertEqual(set(jlc),{'standard_pcb'})
        self.assertTrue(any(r['status']=='FAIL' for r in routes if r['manufacturer_id']=='pcbway'))

    def test_fabrication_claims_do_not_leak_into_assembly_processes(self):
        kb={m['manufacturer_id']:m for m in knowledge_base()}
        jlc={p['process_id']:p for p in kb['jlcpcb']['processes']}
        fabrication={c['parameter'] for c in jlc['standard_pcb']['capabilities']}
        assembly={c['parameter'] for p in (jlc['economic_pcba'],jlc['standard_pcba']) for c in p['capabilities']}
        self.assertIn('min_trace_width',fabrication)
        self.assertNotIn('min_trace_width',assembly)
        self.assertIn('min_package',assembly)
        self.assertNotIn('min_package',fabrication)
        self.assertEqual({p['domain'] for p in kb['pcbway']['processes']},{'fabrication'})

    def test_unknown_does_not_become_fail_in_route_aggregation(self):
        self.assertEqual(aggregate_route_status('PASS','UNKNOWN','UNKNOWN'),'CONDITIONAL')
        self.assertEqual(aggregate_route_status('PASS','PASS','UNKNOWN'),'CONDITIONAL')
        self.assertEqual(aggregate_route_status('FAIL','UNKNOWN','UNKNOWN'),'BLOCKED')

    def test_unsourced_or_absent_feature_does_not_reduce_coverage(self):
        pcb=PCBModel(file='x',layers={'F.Cu','B.Cu'},copper_layers=['F.Cu','B.Cu'],bounds={'width_mm':10,'height_mm':10},segments=[])
        _,routes=evaluate(pcb)
        route=next(r for r in routes if r['manufacturer_id']=='jlcpcb' and r['process_id']=='standard_pcb')
        self.assertGreater(route['status_counts']['NOT_APPLICABLE'],0)
        self.assertNotIn('min_drill',[x['parameter'] for x in route['requirement_results']])
        self.assertLessEqual(route['capability_coverage'],100)

    def test_every_sourced_knowledge_claim_has_complete_provenance(self):
        for m in knowledge_base():
            for process in m['processes']:
                for c in process['capabilities']:
                    self.assertEqual(c['manufacturer'],m['name'])
                    self.assertEqual(c['process'],process['name'])
                    self.assertTrue(c['parameter'] and c['unit'] and c['operator'])
                    self.assertIn('conditions',c)
                    self.assertIn(c['capability_type'],{'HARD_CAPABILITY','CONDITIONAL_CAPABILITY','RECOMMENDED','TYPICAL'})
                    self.assertTrue(c['source']['url'].startswith('https://'))
                    self.assertTrue(c['source']['title'] and c['source']['evidence_note'] and c['source']['retrieval_date'])
                    self.assertTrue(c['last_verified_at'])
                for c in process['unknown_capabilities']:
                    self.assertIsNone(c['source'])
                    self.assertEqual(c['capability_type'],'UNSPECIFIED')

    def test_jlc_pad_hole_spacing_semantics_remain_unknown_with_source_reason(self):
        from pathlib import Path
        from app.kicad import parse_kicad_pcb
        board=parse_kicad_pcb(Path('..')/'examples'/'real_pcb'/'NEAToBOARD_ESP32.kicad_pcb')
        _,routes=evaluate(board)
        route=next(x for x in routes if x['manufacturer']=='JLCPCB' and x['process']=='Standard PCB')
        row=next(x for x in route['requirement_results'] if x['parameter']=='min_component_hole_spacing')
        self.assertEqual(row['status'],'UNKNOWN')
        self.assertEqual(row['reason_code'],'SOURCE_SEMANTICS_UNRESOLVED')
        self.assertIn('Hole-to-Hole Spacing',row['reason'])
        self.assertTrue(row['source']['url'].startswith('https://jlcpcb.com/'))

    def test_evidence_chain_pass_fail_unknown_conditional_and_quality(self):
        from app.manufacturing.intelligence import requirement_quality
        pcb=PCBModel(file='x',layers={'F.Cu','B.Cu'},copper_layers=['F.Cu','B.Cu'],bounds={'width_mm':40,'height_mm':30},segments=[{'width_mm':.25}],vias=[{'x':1,'y':1,'drill_mm':.3,'size_mm':.6,'layers':['F.Cu','B.Cu']}])
        pcb.board_thickness_mm=1.6; pcb.material='FR-4'; pcb.copper_thickness_by_layer_mm={'F.Cu':.0348,'B.Cu':.0348}
        req,routes=evaluate(pcb)
        jlc=next(x for x in routes if x['manufacturer_id']=='jlcpcb' and x['process_id']=='standard_pcb')
        trace=next(x for x in jlc['matrix'] if x['parameter']=='min_trace_width' and x['result']=='PASS')
        self.assertEqual(trace['result'],'PASS')
        self.assertEqual(trace['requirement_quality']['status'],'MEASURED')
        self.assertEqual(trace['source']['manufacturer'],'JLCPCB')
        self.assertTrue(trace['source']['url'].startswith('https://'))
        self.assertIn('expression',trace['comparison'])
        pcb.segments=[{'width_mm':.01}]
        _,routes=evaluate(pcb)
        jlc=next(x for x in routes if x['manufacturer_id']=='jlcpcb' and x['process_id']=='standard_pcb')
        self.assertEqual(next(x for x in jlc['matrix'] if x['parameter']=='min_trace_width' and x['result']=='FAIL')['result'],'FAIL')
        assembly=PCBModel(file='x',layers={'F.Cu','B.Cu'},bounds={'width_mm':40,'height_mm':30},footprints=[{'reference':'R1','library_id':'Resistor_SMD:R_0201_0603Metric'}])
        _,routes=evaluate(assembly)
        economic=next(x for x in routes if x['manufacturer_id']=='jlcpcb' and x['process_id']=='economic_pcba')
        conditional=next(x for x in economic['matrix'] if x['parameter']=='min_package')
        self.assertEqual(conditional['result'],'CONDITIONAL')
        self.assertIn('process scope',conditional['reason'])
        pcb=PCBModel(file='x',layers={'F.Cu','B.Cu'},bounds={'width_mm':40,'height_mm':30},segments=[{'width_mm':.25}],vias=[{'x':1,'y':1,'drill_mm':.3,'size_mm':.6,'layers':['F.Cu','B.Cu']}])
        _,routes=evaluate(pcb)
        pcbway=next(x for x in routes if x['manufacturer_id']=='pcbway' and x['process_id']=='standard_pcb')
        unknown=next(x for x in pcbway['matrix'] if x['parameter']=='min_via_diameter')
        self.assertEqual(unknown['result'],'UNKNOWN')
        self.assertEqual(unknown['reason_code'],'NO_MANUFACTURER_DOCUMENTATION')
        self.assertIsNone(unknown['source'])
        quality=requirement_quality({'min_package':'0201','min_ic_pin_spacing_mm':.9,'min_bga_spacing_mm':None},PCBModel(file='x',footprints=[]))
        self.assertEqual(quality['min_package']['status'],'METADATA_DERIVED')
        self.assertEqual(quality['min_ic_pin_spacing_mm']['status'],'GEOMETRY_DERIVED')
        self.assertEqual(quality['min_bga_spacing_mm']['status'],'NOT_APPLICABLE')

if __name__=='__main__': unittest.main()
