from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_CLI = Path(r"C:\Users\avita\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe")


def parse_drc_report(text: str) -> dict:
    """Parse KiCad's human-readable .rpt report into stable normalized records."""
    total = re.search(r"Found\s+(\d+)\s+DRC violations", text, re.I)
    unconnected_total = re.search(r"Found\s+(\d+)\s+unconnected pads", text, re.I)
    records = []
    chunks = re.split(r"(?=^\[[^\]]+\]:)", text, flags=re.M)
    for chunk in chunks:
        head = re.search(r"^\[([^\]]+)\]:\s*(.*)", chunk, re.M)
        if not head:
            continue
        rule = re.search(r"^\s*Rule:\s*(.*)$", chunk, re.M)
        severity_line = re.search(r"^\s*(?:Rule:\s*)?(.*?);\s*(error|warning|info)\b", chunk, re.M | re.I)
        required_actual = re.search(r"(?:clearance|width|diameter|distance)\s+([\d.]+)\s*mm;\s*actual\s+([\d.]+)\s*mm", chunk, re.I)
        coords = [(float(x), float(y)) for x, y in re.findall(r"@\(([-\d.]+)\s*mm,\s*([-\d.]+)\s*mm\)", chunk)]
        refs = []
        for match in re.finditer(r"\bPad\s+([\w.-]+)(?:\s+\[[^]]*\])?.*?\bof\s+([A-Za-z][\w.-]*)", chunk, re.I):
            refs.append({"reference": match.group(2), "pad": match.group(1)})
        for match in re.finditer(r"\b(?:NPTH|PTH)\s+pad of\s+([A-Za-z][\w.-]*)|\bFootprint\s+([A-Za-z][\w.-]*)", chunk, re.I):
            record={"reference": match.group(1) or match.group(2), "pad": None}
            if record not in refs: refs.append(record)
        for match in re.finditer(r"\b(?:track|via)\s+((?:seg|via)-\d+)\b", chunk, re.I):
            record={"reference": match.group(1), "pad": None}
            if record not in refs: refs.append(record)
        net_names = [n for n in re.findall(r"\[([^\]]+)\]", chunk) if n.lower() != head.group(1).lower()]
        layer = re.search(r"\bon\s+([FB]\.Cu|In\d+\.Cu)\b", chunk)
        records.append({
            "id": f"KDRC-{len(records)+1:04d}", "violation_type": head.group(1),
            "severity": (severity_line.group(2).lower() if severity_line else None),
            "rule_name": rule.group(1).split(";")[0].strip() if rule else (severity_line.group(1).strip() if severity_line else None),
            "required_value_mm": float(required_actual.group(1)) if required_actual else None,
            "actual_value_mm": float(required_actual.group(2)) if required_actual else None,
            "object_type": re.search(r"\b(NPTH pad|PTH pad|pad|track|via|zone|hole)\b", chunk, re.I).group(1).lower() if re.search(r"\b(NPTH pad|PTH pad|pad|track|via|zone|hole)\b", chunk, re.I) else None,
            "objects": refs, "footprint_references": [x["reference"] for x in refs],
            "pad_numbers": [x["pad"] for x in refs if x["pad"]], "net_names": net_names,
            "layer": layer.group(1) if layer else None, "coordinates": coords,
            "message": head.group(2).strip(), "raw": chunk.strip()
        })
    violations = [r for r in records if r["violation_type"].lower() != "unconnected_items"]
    unconnected = [r for r in records if r["violation_type"].lower() == "unconnected_items"]
    violation_count = int(total.group(1)) if total else len(violations)
    unconnected_count = int(unconnected_total.group(1)) if unconnected_total else len(unconnected)
    return {"violation_count": violation_count, "unconnected_item_count": unconnected_count,
            "total_diagnostics": len(records), "parsed_violation_count": len(violations),
            "parsed_unconnected_item_count": len(unconnected),
            "violation_count_discrepancy": violation_count != len(violations),
            "unconnected_count_discrepancy": unconnected_count != len(unconnected),
            # Backward-compatible names now have strict DRC-violation semantics.
            "total_violations": violation_count, "parsed_record_count": len(records),
            "count_discrepancy": violation_count != len(violations),
            "violations": violations, "unconnected_items": unconnected,
            "diagnostics": records, "report_text": text}


def run_kicad_drc(board_name: str, board_text: str, cli: str | Path | None = None) -> dict:
    """Run the KiCad CLI when installed; the report is returned as an artifact."""
    executable = Path(cli) if cli else DEFAULT_CLI
    executable = executable if executable.is_file() else (Path(shutil.which("kicad-cli")) if shutil.which("kicad-cli") else None)
    if not executable:
        return {"available": False, "reason": "KiCad CLI is not installed at the configured path.", "artifact": None, "parsed": None}
    with tempfile.TemporaryDirectory(prefix="forge-kicad-") as work:
        board = Path(work) / Path(board_name).name
        report = Path(work) / "kicad-drc.rpt"
        board.write_text(board_text, encoding="utf-8")
        try:
            result = subprocess.run([str(executable), "pcb", "drc", "--output", str(report), str(board)], capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"available": False, "reason": str(exc), "artifact": None, "parsed": None}
        if not report.exists():
            return {"available": False, "reason": result.stderr[-2000:] or "KiCad CLI did not produce a report.", "artifact": None, "parsed": None}
        report_text = report.read_text(encoding="utf-8", errors="replace")
        return {"available": True, "exit_code": result.returncode, "artifact": {"name": report.name, "media_type": "text/plain", "content": report_text}, "parsed": parse_drc_report(report_text)}
