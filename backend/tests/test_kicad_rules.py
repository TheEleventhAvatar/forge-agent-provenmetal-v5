import unittest

from app.kicad import PCBModel, parse_kicad_pcb
from app.kicad_rules import run_kicad_dfm
from app.rules import inspect_bom


def model(**values):
    board = PCBModel("fixture.kicad_pcb")
    for key, value in values.items():
        setattr(board, key, value)
    return board


def via(id, net, x=0, y=0, layers=None):
    return {"id": id, "net": net, "net_name": str(net), "x": x, "y": y, "size_mm": 1.0, "drill_mm": .4, "layers": layers or ["F.Cu", "B.Cu", "*.Cu"]}


def pad(id, net, x=0, y=0, layers=None):
    return {"id": id, "reference": id, "number": "1", "type": "thru_hole", "net": net, "net_name": str(net), "x": x, "y": y, "size_x_mm": 1.0, "size_y_mm": 1.0, "drill_mm": .4, "layers": layers or ["F.Cu"]}


class NetAwareDfmTests(unittest.TestCase):
    def rules(self, board): return {finding.rule_id: finding for finding in run_kicad_dfm(board)}

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
        self.assertAlmostEqual(finding.evidence["actual_mm"], .1)

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
        self.assertAlmostEqual(pad["size_x_mm"], 1)
        self.assertAlmostEqual(pad["size_y_mm"], 2)
