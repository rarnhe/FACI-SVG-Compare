# Test Report

- UTC: 2026-11-25 10:55:18
- Result: **PASS**
- Tests: **61 per environment**
- Passed: 61
- Failures: 0
- Errors: 0
- Skipped: 0

## Dual-track GitHub Actions

| Environment | Result | Tests | Duration |
| --- | --- | --- | --- |
| Ubuntu / Python 3.12 | PASS | 61/61 | 3.829s |
| Windows / Python 3.14 | PASS | 61/61 | 5.416s |

- Successful workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45599415405
- Both platforms run `python tests/run_tests.py` and independently validate the CAD JavaScript module syntax.
- The runner regenerates `test_report.md` even if tests fail and the CI uploads its report artifact.

## Regression coverage

- Exactly one workbook, exactly two sheets, exactly one image per sheet
- Start-up errors before browser/server launch when constraints are violated
- Excel DrawingML shape detection: textbox, ellipse, rectangle
- Image origin (per sheet) normalization for Fab/Subfab
- Original A1-relative source coordinates retained in Python
- CAD UI splitters, mouse controls, reset without changing zoom, top-left aspect-correct text
- Shape-specific 3D drawing and click targeting: gray textbox plane, diagonal-diameter circle, extruded rectangular box
- Right-side SVG name `1-3-Octave_base.svg`, per-pane height filling with aspect-ratio-preserving width and horizontal scrolling
- Existing Bokeh server, resource security, and HTTP startup

## Verification boundaries

The actual `luoD.xlsx`, `PSD_base.svg`, and `1-3-Octave_base.svg`
are only available on the user's local machine. CI tests synthetic XLSX
fixtures, Python / HTTP behavior, and JavaScript syntax/contract checks.
The real Excel drawing placement, in-browser Three.js 3D interaction,
and final SVG appearance still require manual visual verification.
