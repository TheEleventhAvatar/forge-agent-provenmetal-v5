import unittest
from pathlib import Path

from app.kicad import PCBModel, parse_kicad_pcb
from app.kicad_rules import run_kicad_dfm, _pad_polygon, _track_pad_gap, _via_pad_gap
from app.rules import inspect_bom


def model(**values):
    board = PCBModel("fixture.kicad_pcb")
    for key, value in values.items():
        setattr(board, key, value)
    return board


def via(id, net, x=0, y=0, layers=None):
    return {"id": id, "net": net, "net_name": str(net), "x": x, "y": y, "size_mm": 1.0, "drill_mm": .4, "layers": layers or ["F.Cu", "B.Cu", "*.Cu"]}


def pad(id, net, x=0, y=0, layers=None):
    return {"id": id, "reference": id, "number": "1", "type": "thru_hole", "net": net, "net_name": str(net), "x": x, "y": y, "size_x_mm": 1.0, "size_y_mm": 1.0, "size_x_local_mm": 1.0, "size_y_local_mm": 1.0, "shape":"circle", "rotation_deg":0, "drill_mm": .4, "layers": layers or ["F.Cu"]}


class NetAwareDfmTests(unittest.TestCase):
    def rules(self, board): return {finding.rule_id: finding for finding in run_kicad_dfm(board)}

    def test_neatoboard_has_no_geometry_violations_or_rotated_pad_false_positives(self):
        board_path=Path(__file__).parents[2]/"examples"/"real_pcb"/"NEAToBOARD_ESP32.kicad_pcb"
        board=parse_kicad_pcb(board_path,board_path.read_text(encoding="utf-8",errors="replace"))
        findings=run_kicad_dfm(board)
        self.assertEqual(sum(f.category=="fabrication" and f.status=="VIOLATION" for f in findings),0)
        by_pad={p["id"]:p for p in board.pads}
        by_seg={s["id"]:s for s in board.segments}
        by_via={v["id"]:v for v in board.vias}
        self.assertGreater(_pad_polygon(by_pad["U4.1"])[0][0],0)
        self.assertIn("seg-48",by_seg)
        self.assertIn("via-162",by_via)
        self.assertIn("via-64",by_via)
        suspect={"U4.2","U4.1","seg-48","U2.8","via-162","U2.9","via-64"}
        self.assertFalse(any(suspect.intersection(f.evidence.get("geometry_ids",[])) for f in findings))

    def test_same_net_via_pad_is_not_a_clearance_violation(self):
        self.assertNotIn("VIA_PAD_CLEARANCE", self.rules(model(vias=[via("v1", 1)], pads=[pad("P1", 1)])))

    def test_different_net_via_pad_with_overlap_is_a_violation(self):
        self.assertIn("VIA_PAD_CLEARANCE", self.rules(model(vias=[via("v1", 1)], pads=[pad("P1", 2)])))

    def test_same_net_vias_are_not_a_clearance_violation(self):
        self.assertNotIn("VIA_CLEARANCE", self.rules(model(vias=[via("v1", 1), via("v2", 1)])))

    def test_different_net_vias_require_insufficient_edge_gap(self):
        self.assertIn("VIA_CLEARANCE", self.rules(model(vias=[via("v1", 1), via("v2", 2, x=.9)])))
        self.assertNotIn("VIA_CLEARANCE", self.rules(model(vias=[via("v1", 1), via("v2", 2, x=2)])))

    def test_same_net_pads_are_not_a_clearance_violation(self):
        self.assertNotIn("PAD_CLEARANCE", self.rules(model(pads=[pad("P1", 1), pad("P2", 1)])))

    def test_different_net_pads_use_edge_to_edge_gap(self):
        finding = self.rules(model(pads=[pad("P1", 1), pad("P2", 2, x=1.1)]))["PAD_CLEARANCE"]
        self.assertAlmostEqual(finding.evidence["actual_mm"], .1, places=3)

    def test_track_clearance_is_net_aware(self):
        track = {"id":"s1","net":1,"net_name":"GND","x1":0,"y1":0,"x2":2,"y2":0,"width_mm":.2,"layer":"F.Cu"}
        self.assertNotIn("TRACK_PAD_CLEARANCE", self.rules(model(segments=[track], pads=[pad("P1", 1, x=1,y=0)])))
        self.assertIn("TRACK_PAD_CLEARANCE", self.rules(model(segments=[track], pads=[pad("P1", 2, x=1,y=0)])))

    def test_hole_edge_uses_edge_cuts_and_is_a_warning(self):
        hole = pad("J1.1", 1, x=5, y=.6)
        board = model(through_holes=[hole], board_outline=[
            {"type":"line", "start":(0,0), "end":(10,0)},
            {"type":"line", "start":(10,0), "end":(10,10)},
            {"type":"line", "start":(10,10), "end":(0,10)},
            {"type":"line", "start":(0,10), "end":(0,0)},
        ])
        finding = self.rules(board)["HOLE_TO_EDGE"]
        self.assertEqual(finding.status, "WARNING")
        self.assertAlmostEqual(finding.evidence["actual_mm"], .1)

    def test_unresolved_zone_is_warning_not_violation(self):
        finding = self.rules(model(zones=[{"id":"z1", "layer":"F.Cu", "points":[]}]))["ZONE_GEOMETRY"]
        self.assertEqual(finding.status, "WARNING")

    def test_missing_mpn_is_procurement_warning(self):
        finding = inspect_bom([{"reference":"R1"}])[0]
        self.assertEqual((finding.category, finding.status), ("procurement", "WARNING"))

    def test_pad_coordinates_follow_footprint_rotation(self):
        text = '(kicad_pcb (footprint "x" (layer "F.Cu") (at 10 20 90) (fp_text reference "R1") (pad "1" smd rect (at 1 0) (size 2 1) (layers "F.Cu") (net 1 "GND"))))'
        pad = parse_kicad_pcb("rotation.kicad_pcb", text).pads[0]
        self.assertAlmostEqual(pad["x"], 10)
        self.assertAlmostEqual(pad["y"], 19)
        self.assertAlmostEqual(pad["size_x_mm"], 2)
        self.assertAlmostEqual(pad["size_y_mm"], 1)
        self.assertEqual(pad["rotation_deg"], 0)

    def test_rotated_rectangles_use_copper_shapes_not_envelopes(self):
        a=pad("A",1); a.update(shape="rect",size_x_local_mm=2,size_y_local_mm=.2,rotation_deg=30,size_x_mm=1.8,size_y_mm=1.8)
        b=pad("B",2,x=0,y=1.7); b.update(shape="rect",size_x_local_mm=2,size_y_local_mm=.2,rotation_deg=-30,size_x_mm=1.8,size_y_mm=1.8)
        # Their axis-aligned envelopes intersect; the actual rotated bars are separated.
        self.assertNotIn("PAD_CLEARANCE",self.rules(model(pads=[a,b])))

    def test_genuinely_overlapping_rectangular_pads_violate(self):
        a=pad("A",1); b=pad("B",2,x=.2)
        a.update(shape="rect",size_x_local_mm=1,size_y_local_mm=.5); b.update(shape="rect",size_x_local_mm=1,size_y_local_mm=.5)
        self.assertIn("PAD_CLEARANCE",self.rules(model(pads=[a,b])))

    def test_round_and_rectangular_copper_distance(self):
        via_obj=via("v",1,x=0,y=0); via_obj.update(size_mm=.4)
        p=pad("SMD",2,x=.55); p.update(shape="rect",size_x_local_mm=.4,size_y_local_mm=.4)
        self.assertIn("VIA_PAD_CLEARANCE",self.rules(model(vias=[via_obj],pads=[p])))

    def test_via_clearance_uses_through_hole_pad_copper_not_drill(self):
        via_obj=via("v",1,x=0,y=0); via_obj.update(size_mm=.4)
        p=pad("TH",2,x=.8); p.update(shape="circle",size_x_local_mm=1.2,size_y_local_mm=1.2,drill_mm=1.0,layers=["*.Cu"])
        self.assertIn("VIA_PAD_CLEARANCE",self.rules(model(vias=[via_obj],pads=[p])))

    def test_same_and_different_net_track_pad(self):
        track={"id":"t","net":1,"net_name":"1","x1":-1,"y1":0,"x2":0,"y2":0,"width_mm":.2,"layer":"F.Cu"}
        p=pad("P",1,x=0,y=0,layers=["F.Cu"]); p.update(type="smd",shape="rect",size_x_local_mm=.5,size_y_local_mm=.5)
        self.assertNotIn("TRACK_PAD_CLEARANCE",self.rules(model(segments=[track],pads=[p])))
        p["net"]=2
        self.assertIn("TRACK_PAD_CLEARANCE",self.rules(model(segments=[track],pads=[p])))

    def test_same_and_different_net_via_pad(self):
        v=via("v",1); p=pad("P",1,x=.3,layers=["F.Cu"]); p.update(shape="rect",size_x_local_mm=.6,size_y_local_mm=.6)
        self.assertNotIn("VIA_PAD_CLEARANCE",self.rules(model(vias=[v],pads=[p])))
        p["net"]=2
        self.assertIn("VIA_PAD_CLEARANCE",self.rules(model(vias=[v],pads=[p])))

    def test_parser_preserves_pad_shape_and_orientation(self):
        text='(kicad_pcb (footprint "x" (layer "F.Cu") (at 10 20 90) (fp_text reference "R1") (pad "1" smd roundrect (at 1 0 15) (size 2 1) (roundrect_rratio 0.2) (layers "F.Cu") (net 1 "GND")))'
        parsed=parse_kicad_pcb("shape.kicad_pcb",text).pads[0]
        self.assertEqual(parsed["shape"],"roundrect")
        self.assertEqual(parsed["rotation_deg"],15)
        self.assertEqual(parsed["roundrect_rratio"],.2)

    def test_kicad_pad_position_and_absolute_board_angle_cases(self):
        cases = [
            (0, "0", (11, 20), 0),
            (90, "0", (10, 19), 0),
            (0, "90", (11, 20), 90),
            (90, "90", (10, 19), 90),
            (180, "0", (9, 20), 0),
            (270, "0", (10, 21), 0),
        ]
        for fp_angle, pad_angle, center, orientation in cases:
            with self.subTest(fp_angle=fp_angle, pad_angle=pad_angle):
                text = (f'(kicad_pcb (footprint "x" (layer "F.Cu") (at 10 20 {fp_angle}) '
                        f'(fp_text reference "R1") (pad "1" smd rect (at 1 0 {pad_angle}) '
                        '(size 2 1) (layers "F.Cu") (net 1 "N1"))))')
                parsed = parse_kicad_pcb("rotation.kicad_pcb", text).pads[0]
                self.assertAlmostEqual(parsed["x"], center[0])
                self.assertAlmostEqual(parsed["y"], center[1])
                self.assertEqual(parsed["rotation_deg"], orientation)

    def test_rect_pad_long_axis_follows_absolute_board_angle(self):
        text = '(kicad_pcb (footprint "x" (layer "F.Cu") (at 10 20 90) (fp_text reference "R1") (pad "1" smd rect (at 0 0 90) (size 2 0.9) (layers "F.Cu") (net 1 "N1"))))'
        parsed = parse_kicad_pcb("rotation.kicad_pcb", text).pads[0]
        xs = [p[0] for p in _pad_polygon(parsed)]
        ys = [p[1] for p in _pad_polygon(parsed)]
        self.assertAlmostEqual(max(xs)-min(xs), .9, places=6)
        self.assertAlmostEqual(max(ys)-min(ys), 2, places=6)

    def test_non_cardinal_pad_angle_uses_kicad_clockwise_board_transform(self):
        text = '(kicad_pcb (footprint "x" (layer "F.Cu") (at 10 20 0) (fp_text reference "R1") (pad "1" smd rect (at 0 0 30) (size 2 1) (layers "F.Cu") (net 1 "N1"))))'
        parsed = parse_kicad_pcb("rotation.kicad_pcb", text).pads[0]
        first_corner = _pad_polygon(parsed)[0]
        self.assertAlmostEqual(first_corner[0], 8.8839745962, places=6)
        self.assertAlmostEqual(first_corner[1], 20.0669872981, places=6)

    def test_roundrect_dimensions_and_corner_radius_survive_rotation(self):
        text = '(kicad_pcb (footprint "x" (layer "F.Cu") (at 10 20 90) (fp_text reference "R1") (pad "1" smd roundrect (at 0 0 90) (size 1.95 0.6) (roundrect_rratio 0.25) (layers "F.Cu") (net 1 "N1"))))'
        parsed = parse_kicad_pcb("rotation.kicad_pcb", text).pads[0]
        polygon = _pad_polygon(parsed)
        self.assertAlmostEqual(max(p[0] for p in polygon)-min(p[0] for p in polygon), .6, delta=.001)
        self.assertAlmostEqual(max(p[1] for p in polygon)-min(p[1] for p in polygon), 1.95, delta=.001)
        self.assertEqual(parsed["roundrect_rratio"], .25)

    def test_rotated_pad_track_and_via_clearances(self):
        text = '(kicad_pcb (footprint "x" (layer "F.Cu") (at 10 20 90) (fp_text reference "R1") (pad "1" smd roundrect (at 0 0 90) (size 1.95 0.6) (roundrect_rratio 0.25) (layers "F.Cu") (net 2 "N2"))))'
        p = parse_kicad_pcb("rotation.kicad_pcb", text).pads[0]
        track = {"x1":11,"y1":20,"x2":12,"y2":20,"width_mm":.2}
        self.assertAlmostEqual(_track_pad_gap(track,p), .6, delta=.002)
        self.assertAlmostEqual(_via_pad_gap({"x":11,"y":20,"size_mm":.4},p), .5, delta=.002)
