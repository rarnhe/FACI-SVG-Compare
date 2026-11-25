# Test Report

- UTC: 2026-11-25 10:06:00
- Result: **PASS**
- Tests: **60 per environment**
- Passed: 60
- Failures: 0
- Errors: 0
- Skipped: 0

## Dual-track GitHub Actions

| Environment | Result | Tests | Duration |
| --- | --- | --- | --- |
| Ubuntu / Python 3.12 | PASS | 60/60 | 3.290s |
| Windows / Python 3.14 | PASS | 60/60 | 5.343s |

- Successful workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45591589948
- Both platforms run `python tests/run_tests.py` and independently validate the CAD JavaScript module syntax.
- The runner regenerates `test_report.md` even if tests fail and the CI uploads its report artifact.

## Regression coverage

- Exactly one workbook, exactly two sheets, exactly one image per sheet
- Start-up errors before browser/server launch when constraints are violated
- Excel DrawingML shape detection: textbox, ellipse, rectangle
- Image origin (per sheet) normalization for Fab/Subfab
- Original A1-relative source coordinates retained in Python
- CAD UI splitters, mouse controls, reset without changing zoom, top-left aspect-correct text
- Right-side SVG name `1-3-Octave_base.svg` and shared display width
- Existing Bokeh server, resource security, and HTTP startup

## Verification boundaries

The actual `luoD.xlsx`, `PSD_base.svg`, and `1-3-Octave_base.svg`
are only available on the user's local machine. CI tests synthetic XLSX
fixtures, Python / HTTP behavior, and JavaScript syntax/contract checks.
The real Excel drawing placement, in-browser Three.js 3D interaction,
and final SVG appearance still require manual visual verification.
