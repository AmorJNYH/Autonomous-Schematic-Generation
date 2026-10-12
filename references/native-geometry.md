# Finite native geometry context

`verify_schematic.py` enables a fresh finite native SVG geometry job for a
hierarchical root. A standalone page can request the same channel with
`--native-geometry`. In-memory `Sheet.build()` and the default standalone
geometry CLI keep their existing estimate/contact behavior. The native channel
does not change names, font sizes, electrical sources or native ERC/XML/PDF.

The job copies reachable native source files, project configuration and local
library context to fresh output folders. It uses KiCad 10.0.6 full-project SVG
exports with drawing sheets excluded. A baseline and replica must agree in
all visible primitives and complete hidden SVG text companions. One added
source-specific annotation establishes the exported page/source identity; no
nearest-coordinate, filename or same-string matching supplies ownership.

Each sheet-field visibility, frame-width/fill, or unique cache pin-name
intervention changes exactly one source span in a render-only clone. All other
source bytes and non-target exported objects/pages must remain unchanged.
The job records actual commands, return codes, timing, source/tool/configuration
hashes and raw export hashes. Fontconfig warnings are retained and are not a
qualification by themselves; reproducibility and complete differences determine
the supported finite profile. Unknown source font faces, variables, filled or
curved glyphs, visible transforms and other unsupported profiles remain gaps.
The source-edit subset is UTF-8/LF; non-LF schematics remain INS rather than
normalize bytes outside a target span. Extra structural display flags, including
DNP, are unsupported; their added ink cannot be covered by a borrowed rectangle.

Supported structural graphics are axis-aligned unfilled rectangles, including
transparent rectangular sheets without sheet pins. Native/source coordinates
must agree within the native SVG serialization precision; collision uses the
actual native stroke, not that matching tolerance. A width probe that also
changes sheet-field pens is rejected. A fill-only fallback is accepted only
when it causally deletes one complete original frame outline and introduces
one rectangle of identical geometry, with all other primitives/text unchanged.
Zero deleted outlines cannot borrow a foreign matching perimeter. Duplicate
outlines and overlapping sheets remain collision candidates.

Sheetname and Sheetfile use the entire causally removed glyph union and complete
native shown literal, including the actual localized file prefix. Their checked
envelope unions native ink with the existing estimate of that complete literal;
it never shrinks text or uses a decoded-name shortcut. Architecture annotation
inside a sheet frame is legal; native edge collisions and foreign electrical
wires through sheet structure remain defects. Fields, outlines and page/title
region extents are checked separately. Sheet pins, normalized anchors and their
text/outlines remain explicit unsupported coverage in this implementation.

The limited pin-name channel binds one placed symbol, used unit/convert, unique
physical pin and original cache source span. It requires a unique active cache
instance and an exclusive raw-name-empty render difference. Reused definitions,
multiunit/convert variations, inheritance, hidden/empty names, power-symbol
behavior and formatting remain gaps. **Pin numbers are never changed**; their
geometry remains native-review coverage rather than a falsely qualified channel.
Different pin names, foreign fields/wires/bodies, and qualified actual symbol
foreground outlines protect collisions. Own rectangular background fill can
legitimately contain pin names; that does not exempt foreground strokes or other
pins. Unknown foreground shapes keep a gap. Errors take precedence over gaps.

The serialized `native-geometry/context.json` is **audit evidence only**.
`check_schematic_geometry.py --native-context` cannot authorize geometry coverage
or close gaps, even if its supplied SHA matches. The official runner consumes
only its own unchanged live fresh-job return value and rechecks input, producer,
environment, tool, configuration and raw output bindings before geometry.
Editing arrays/gaps or replaying a self-declared PASS JSON cannot authorize PASS.

The live object is a receipt of a **trusted internal controller**, not a security
boundary against Python code running in that same process. Its private mutable
seal is an integrity check for the official runner's unchanged return value,
not an authentication token: a caller that deliberately overwrites the private
seal can re-seal modified arrays. Such privileged same-process rewriting is
outside this API's qualification contract and must never be presented as a
protected input path. External serialized contexts remain audit-only and the
official CLI does not accept caller-supplied live objects.

This is a finite geometry gate, not full font/renderer coverage, electrical GO,
or human render review. An unsupported page remains INSUFFICIENT; a captured
actual collision is FAIL even when another category is unknown. Baseline bench
labels/counts must not be changed to accommodate new coverage. A missing finding
caused only by overall INS/UNMAPPED is not a G1 improvement.
