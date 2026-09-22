import csv, io, re, math
from dataclasses import dataclass, field
from typing import Any

@dataclass
class PCBGeometry:
    file: str
    units: str = "mm"
    apertures: dict[str, float] = field(default_factory=dict)
    flashes: list[dict[str, Any]] = field(default_factory=list)
    tracks: list[dict[str, Any]] = field(default_factory=list)
    segments: list[dict[str, Any]] = field(default_factory=list)
    bounds: dict[str, float] | None = None
    min_feature_mm: float | None = None

@dataclass
class DrillData:
    file: str
    units: str = "mm"
    tools: dict[str, float] = field(default_factory=dict)
    holes: list[dict[str, Any]] = field(default_factory=list)
    min_drill_mm: float | None = None

GERBER_ADD = re.compile(r"%ADD(\d+)([A-Z]),?([0-9.]+)(?:X([0-9.]+))?\*%")
DRILL_TOOL = re.compile(r"T(\d+)C([0-9.]+)")

def _mm(v: float, units: str) -> float:
    return v * 25.4 if units == "inch" else v

def _gerber_coord(token: str, units: str, decimals: int = 3) -> float:
    # Demo fixtures use explicit 3-decimal integer coordinates. Real X2 files
    # should be parsed using their FS format; this parser also accepts decimals.
    if "." in token:
        return _mm(float(token), units)
    sign = -1 if token.startswith("-") else 1
    raw = token.lstrip("-")
    return _mm(sign * (int(raw) / (10 ** decimals)), units)

def parse_gerber(name: str, text: str) -> PCBGeometry:
    units = "inch" if "%MOIN" in text.upper() else "mm"
    g = PCBGeometry(file=name, units=units)
    for m in GERBER_ADD.finditer(text):
        code, shape, a, b = m.groups()
        dims = [_mm(float(a), units)]
        if b: dims.append(_mm(float(b), units))
        g.apertures[code] = min(dims)
    current = None
    last = None
    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("%"): continue
        dm = re.search(r"D(\d+)\*", line)
        if dm and not re.search(r"X.*D0?[123]", line):
            current = dm.group(1); continue
        m = re.search(r"X(-?[0-9.]+)Y(-?[0-9.]+)(?:D0?([123]))?\*", line)
        if not m: continue
        x = _gerber_coord(m.group(1), units); y = _gerber_coord(m.group(2), units)
        op = m.group(3) or "1"
        min_x, max_x = min(min_x,x), max(max_x,x); min_y, max_y = min(min_y,y), max(max_y,y)
        if current not in g.apertures:
            last = (x,y); continue
        dia = g.apertures[current]
        if op == "3":
            g.flashes.append({"x":x,"y":y,"aperture_mm":dia,"shape":"flash"})
        elif op == "1" and last is not None:
            seg={"x1":last[0],"y1":last[1],"x2":x,"y2":y,"width_mm":dia}
            g.tracks.append(seg); g.segments.append(seg)
        last=(x,y)
    if g.apertures: g.min_feature_mm=min(g.apertures.values())
    if min_x != math.inf: g.bounds={"min_x":min_x,"min_y":min_y,"max_x":max_x,"max_y":max_y}
    return g

def parse_excellon(name: str, text: str) -> DrillData:
    units = "inch" if re.search(r"M72|INCH", text, re.I) else "mm"
    d=DrillData(file=name,units=units)
    for m in DRILL_TOOL.finditer(text): d.tools[m.group(1)] = _mm(float(m.group(2)), units)
    current=None
    for line in text.splitlines():
        line=line.strip()
        tm=re.match(r"T(\d+)",line)
        if tm and tm.group(1) in d.tools: current=tm.group(1); continue
        m=re.search(r"X(-?[0-9.]+)Y(-?[0-9.]+)",line)
        if m and current:
            d.holes.append({"x":_mm(float(m.group(1)),units),"y":_mm(float(m.group(2)),units),"tool":current,"diameter_mm":d.tools[current]})
    if d.tools: d.min_drill_mm=min(d.tools.values())
    return d

def parse_bom(name: str, content: bytes) -> list[dict[str, Any]]:
    text=content.decode("utf-8-sig",errors="replace") if isinstance(content,(bytes,bytearray)) else content
    dialect=csv.Sniffer().sniff(text[:4096]) if text.strip() else csv.excel
    rows=list(csv.DictReader(io.StringIO(text),dialect=dialect))
    return [{str(k).strip().lower().replace(" ","_"): (str(v).strip() if v is not None else "") for k,v in row.items()} for row in rows]
