import unittest

from app.kicad import PCBModel
from app.models import Finding
from app.validation.kicad_drc import parse_drc_report
from app.validation.cross_validator import cross_validate
from app.manufacturing.manufacturers import load_manufacturer_profiles
from app.manufacturing.capability_matcher import _evaluate
from app.agent import ForgeAgent
from app.models import ManufacturerMatch


REPORT = '''** Found 1 DRC violations **
[clearance]: Clearance violation (board setup constraints clearance 0.1500 mm; actual 0.1200 mm)
    Rule: board setup constraints clearance; error
    @(10.0100 mm, 20.0000 mm): Pad 2 [SIG] on F.Cu of U4
    @(11.0000 mm, 20.0000 mm): Pad 1 [GND] on F.Cu of U4
'''


def finding(rule="PAD_CLEARANCE", ids=None):
    return Finding(id="F1", rule_id=rule, severity="high", title="clearance", description="test",
                   evidence={"geometry_ids": ids if ids is not None else ["U4.2", "U4.1"], "actual_mm": .12, "required_mm": .15}, remediation="")


class DrcParsingTests(unittest.TestCase):
    def test_real_neatoboard_violation_and_unconnected_totals_stay_separate(self):
        from pathlib import Path
        fixture=Path(__file__).resolve().parents[2]/'NEAToBOARD_ESP32-drc.rpt'
        parsed=parse_drc_report(fixture.read_text(encoding='utf-8',errors='replace'))
        self.assertEqual(parsed['violation_count'],523)
        self.assertEqual(parsed['unconnected_item_count'],20)
        self.assertEqual(parsed['total_diagnostics'],543)
        self.assertEqual(len(parsed['violations']),523)
        self.assertEqual(len(parsed['unconnected_items']),20)

    def test_unconnected_items_are_separate_from_drc_violations(self):
        report="""** Found 2 DRC violations **
[clearance]: Clearance violation (clearance 0.2 mm; actual 0.1 mm)
    Rule: clearance; error
[unconnected_items]: Missing connection between items
    @(1 mm, 2 mm): Track [SIG] on F.Cu
** Found 1 unconnected pads **
"""
        parsed=parse_drc_report(report)
        self.assertEqual(parsed['violation_count'],2)
        self.assertEqual(parsed['unconnected_item_count'],1)
        self.assertEqual(parsed['total_diagnostics'],2)
        self.assertEqual(len(parsed['violations']),1)
        self.assertEqual(len(parsed['unconnected_items']),1)
        cross=cross_validate([],parsed,PCBModel("x"))
        self.assertEqual(len(cross['kicad_only']),1)
        self.assertEqual(len(cross['unconnected_items']),1)
        self.assertEqual(cross['summary']['kicad_only'],1)
        self.assertEqual(cross['summary']['unconnected_items'],1)

    def test_parse_violation_type_severity_values_refs_nets_layers_coords(self):
        parsed = parse_drc_report(REPORT)
        self.assertEqual(parsed["total_violations"], 1)
        item = parsed["violations"][0]
        self.assertEqual(item["violation_type"], "clearance")
        self.assertEqual(item["severity"], "error")
        self.assertEqual(item["required_value_mm"], .15)
        self.assertEqual(item["actual_value_mm"], .12)
        self.assertIn("U4", item["footprint_references"])
        self.assertIn("SIG", item["net_names"])
        self.assertEqual(item["layer"], "F.Cu")
        self.assertEqual(item["coordinates"][0], (10.01, 20.0))

    def test_empty_report_parses_to_zero(self):
        self.assertEqual(parse_drc_report("** Found 0 DRC violations **")["total_violations"], 0)

    def test_parse_local_override_format_and_pad_object_identity(self):
        report="""[clearance]: Clearance violation ( clearance 0.2000 mm; actual 0.1000 mm)
    Local override; error
    @(10.0 mm, 20.0 mm): Pad 1 [SIG] of U4 on F.Cu
"""
        item=parse_drc_report(report)["violations"][0]
        self.assertEqual(item["severity"],"error")
        self.assertEqual(item["required_value_mm"],.2)
        self.assertEqual(item["footprint_references"],["U4"])
        self.assertEqual(item["pad_numbers"],["1"])

    def test_track_net_name_is_not_misread_as_an_object_reference(self):
        item=parse_drc_report("[unconnected_items]: Missing connection\n @(1 mm, 2 mm): Track [SDA] on F.Cu, length 1 mm\n")["unconnected_items"][0]
        self.assertEqual(item["net_names"],["SDA"])
        self.assertEqual(item["footprint_references"],[])


class CrossValidationTests(unittest.TestCase):
    def test_footprint_pad_match_corroborates(self):
        pcb = PCBModel("test")
        pcb.pads = [
            {"id":"U4.2", "reference":"U4", "number":"2", "x":10, "y":20, "net_name":"SIG", "layer":"F.Cu"},
            {"id":"U4.1", "reference":"U4", "number":"1", "x":11, "y":20, "net_name":"GND", "layer":"F.Cu"},
        ]
        result = cross_validate([finding()], parse_drc_report(REPORT), pcb)
        self.assertEqual(result["evidence"][0]["status"], "CORROBORATED")

    def test_coordinate_tolerance_rejects_far_objects(self):
        pcb = PCBModel("test")
        pcb.segments = [{"id":"seg-1","x1":100,"y1":100,"x2":101,"y2":100}]
        result = cross_validate([finding(ids=["seg-1"])], parse_drc_report(REPORT), pcb, tolerance_mm=.05)
        self.assertEqual(result["evidence"][0]["status"], "NOT_CORROBORATED")

    def test_coordinate_within_tolerance_maps_track(self):
        pcb=PCBModel("test"); pcb.segments=[{"id":"seg-1","x1":10,"y1":20,"x2":10.2,"y2":20}]
        result=cross_validate([finding(ids=["seg-1"])],parse_drc_report(REPORT),pcb,tolerance_mm=.05)
        self.assertEqual(result["evidence"][0]["status"],"CORROBORATED")

    def test_net_name_provides_mapping_signal(self):
        pcb = PCBModel("test")
        pcb.pads = [{"id":"U4.2","reference":"U4","number":"2","x":90,"y":90,"net_name":"SIG","layer":"F.Cu"}]
        result = cross_validate([finding(ids=["U4.2"])], parse_drc_report(REPORT), pcb, tolerance_mm=.01)
        self.assertEqual(result["evidence"][0]["status"], "CORROBORATED")

    def test_forgeagent_only_is_not_a_false_finding_conclusion(self):
        report = parse_drc_report("** Found 0 DRC violations **")
        pcb=PCBModel("x"); pcb.pads=[{"id":"x","x":0,"y":0}]
        result = cross_validate([finding("MIN_DRILL", ["x"])], report, pcb)
        self.assertEqual(result["evidence"][0]["status"], "FORGEAGENT_ONLY")
        self.assertIn("does not invalidate", result["evidence"][0]["reason"])

    def test_kicad_only_items_are_preserved_separately(self):
        result = cross_validate([], parse_drc_report(REPORT), PCBModel("x"))
        self.assertEqual(result["kicad_only"][0]["status"], "KICAD_ONLY")

    def test_missing_geometry_ids_are_unmapped(self):
        result = cross_validate([finding(ids=[])], parse_drc_report(REPORT), PCBModel("x"))
        self.assertEqual(result["evidence"][0]["status"], "UNMAPPED")

    def test_missing_report_is_validation_unavailable(self):
        self.assertEqual(cross_validate([finding()], None)["status"], "VALIDATION_UNAVAILABLE")

    def test_conflicting_geometry_value_is_flagged(self):
        pcb = PCBModel("test")
        pcb.pads = [{"id":"U4.2","reference":"U4","number":"2","x":10.01,"y":20,"net_name":"SIG","layer":"F.Cu"}]
        f = finding(ids=["U4.2"]); f.evidence["actual_mm"] = .5
        result = cross_validate([f], parse_drc_report(REPORT), pcb)
        self.assertEqual(result["evidence"][0]["status"], "CONFLICTING_GEOMETRY")


class ManufacturerProfileTests(unittest.TestCase):
    def test_only_documented_real_profiles_exist(self):
        profiles = load_manufacturer_profiles()
        self.assertEqual({p["name"] for p in profiles.values()}, {"JLCPCB", "PCBWay"})

    def test_each_capability_has_official_source_provenance(self):
        for profile in load_manufacturer_profiles().values():
            for item in profile["capabilities"]:
                self.assertTrue(item["source"]["url"].startswith("https://"))
                self.assertTrue(item["source"]["evidence"])
                self.assertEqual(item["source"]["retrieved_at"], "2026-09-23")

    def test_conditional_capability_needs_matching_configuration(self):
        claim = {"value": .1, "conditions": {"copper_weight_oz": 1}}
        self.assertEqual(_evaluate(.15, claim, {})[0], "CONDITIONAL")
        self.assertEqual(_evaluate(.15, claim, {"copper_weight_oz": 2})[0], "CONDITIONAL")

    def test_pass_and_fail_are_measured_against_published_floor(self):
        claim = {"value": .1, "conditions": {}}
        self.assertEqual(_evaluate(.15, claim, {})[0], "PASS")
        self.assertEqual(_evaluate(.08, claim, {})[0], "FAIL")

    def test_insufficient_documentation_is_unknown(self):
        self.assertEqual(_evaluate(.1, {"value": None, "conditions": {}}, {})[0], "UNKNOWN")

    def test_no_fake_price_availability_or_lead_time_fields_in_profiles(self):
        for profile in load_manufacturer_profiles().values():
            rendered = repr(profile).lower()
            self.assertNotIn("price", rendered)
            self.assertNotIn("availability", rendered)
            self.assertNotIn("lead_time", rendered)

    def test_quote_scenarios_do_not_claim_prices_or_lead_times(self):
        m=ManufacturerMatch(manufacturer="JLCPCB",compatible=False,score=50,blockers=[],satisfied=[],status="CONDITIONAL")
        quote=ForgeAgent()._quote({},[m],[])[0]
        self.assertFalse(quote["actual_quote"])
        self.assertIsNone(quote["estimated_fabrication_usd"])
        self.assertIsNone(quote["estimated_lead_days"])
        self.assertIn("not a live",quote["estimate_type"])


if __name__ == "__main__":
    unittest.main()
