# ForgeBoard Demo Fixture

This is a small, valid manufacturing-data fixture using the same file families produced by KiCad: Gerber copper, Excellon drill, BOM CSV, and a KiCad PCB source file. KiCad documents Gerber as its primary PCB manufacturing output and Excellon as the drill output. See `docs/SOURCE_NOTES.md`.

The fixture intentionally contains manufacturing issues so ForgeAgent has something real to detect:

- 0.10 mm copper feature vs 0.15 mm prototype-process minimum
- approximately 0.06 mm copper-to-copper clearance vs 0.15 mm minimum
- 0.15 mm drill vs 0.20 mm minimum
- ESP8266EX flagged by the demo component lifecycle catalog

The Gerber and Excellon are actual RS-274X/Excellon-style manufacturing files, not a JSON mock.
