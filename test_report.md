# Test Report

- UTC (final CI report upload): 2026-11-27 11:49:10
- Overall result: **PASS**
- Verified commit: `b7b6eceaeeacdd1c50fb2bed076a63e9d9e67b1e`
- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45993444128

## Dual-track certification

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 124/124 (3.302s) | 48/48 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 124/124 (4.072s) | 48/48 | 2/2 | PASS | PASS |

Both jobs succeeded on the first run. Each generated and uploaded its own test_report.md. Zero failures/errors.

- Ubuntu report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45993444128/artifacts/15194233560
- Windows report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45993444128/artifacts/15194957193

## Strict DrawingML geometry

- Remove SheetMetrics, stored column width conversion, marker-to-coordinate calculations and cell-derived fallback. Worksheet relationships still locate drawings; worksheet XML bodies are not read. A ZIP read guard tests this explicitly.
- oneCellAnchor/twoCellAnchor use complete top-level xfrm/off and xfrm/ext, absoluteAnchor uses direct pos/ext. Positive integer EMU extents required; rotation retained. Negative positions allowed. A genuine all-zero origin is valid, but all-zero transform offset with a nonzero from marker is treated as ambiguous and rejected (not converted to a coordinate).
- Missing/invalid geometry fails before browser or server startup, identifying sheet, object, anchor type, drawing part and missing/invalid field. No guessed fallback. geometry_source is xfrm or absoluteAnchor.
- Regression verifies one-cell and two-cell transforms, direct absolute anchor precedence, malformed geometry, zero-offset ambiguity, hidden rows/columns, unchanged geometry with altered sheet metrics, image-relative rotated corners, and actual generated XLSX-to-HTTP-to-WebGL rendering with deliberately inconsistent marker/worksheet layouts.
- P0 uniform XY scaling, common displayed image width, image extraction, geometry validation, SVG lookup logic, colors, outlines, and other frontend interactions remain unchanged.
- Strict mode reproduces saved top-level geometry, not Excel's future layout or stale transform synchronization. Some XLSX generators omit transforms or use placeholder offsets; such files are rejected, including ambiguous genuine zero coordinates with hidden nonzero-index cells. Group children are not expanded. Private workbook not available for direct visual confirmation.

This checked-in summary is based on verified job logs and uploaded artifact metadata. The report-only commit does not alter production or test code.
