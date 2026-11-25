# Test Report

- UTC: 2026-11-25 06:53:12
- Result: **PASS**
- Tests: 46 (per environment)
- Passed: 46
- Failures: 0
- Errors: 0
- Skipped: 0

## Dual-track verification

- Local XLSX geometry tests: **13/13 PASS**, using generated XLSX/ZIP/XML fixtures (no personal workbook required).
- GitHub Actions Ubuntu / Python 3.12: **46/46 PASS** (3.708 s).
- GitHub Actions Windows / Python 3.14: **46/46 PASS** (3.895 s).
- GitHub Actions run: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45563855415

## Scope

Python module startup, Bokeh/Three.js existing integration, unique-XLSX
selection and temporary-file exclusions, A1-origin image/shape coordinates,
single/two-cell and absolute anchors, row heights and column widths,
EMU offsets, image/shape size, theme fill/line/text colors, rotation,
console output, missing/multiple XLSX errors, static resources, and HTTP serving.

## Limitations

96-DPI pixels assume standard Excel column font metrics. Original bounds are
also preserved as integer EMUs. Four corners describe an object's drawing
rectangle, not every control point of a freeform curve or polygon.
Actual luoD.xlsx was not supplied to CI; its rendered geometry requires local verification.
