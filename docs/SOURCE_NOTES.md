# Manufacturing-format references

KiCad's current documentation describes Gerber as its primary PCB manufacturing plot format and exposes Excellon drill generation alongside Gerbers. The project intentionally keeps the demo input in these manufacturing formats rather than inventing a proprietary JSON representation.

Reference: https://docs.kicad.org/10.0/en/pcbnew/pcbnew.pdf

The parser architecture is intentionally replaceable. For production-grade Gerber/X2/X3 coverage, use a maintained parser such as Gerbonara or PyGerber rather than extending the small fixture parser indefinitely.
