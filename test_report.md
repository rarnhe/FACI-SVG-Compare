# Test Report

- UTC: 2026-11-25 15:34:36
- Result: **PASS**
- Python tests: **74 per environment**
- Node geometry tests: **12 per environment**
- Failures: 0
- Errors: 0
- Skipped: 0

## Dual-track verification

| Environment | Python unittest | Node geometry tests | Result |
| --- | --- | --- | --- |
| Ubuntu / Python 3.12 | 74/74 | 12/12 | PASS |
| Windows / Python 3.14 | 74/74 | 12/12 | PASS |

- Successful run: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45646581421
- Both platforms check JavaScript module syntax, run `node --test tests/test_cad_geometry.mjs`, and run `python tests/run_tests.py`.
- The CI writes and uploads test_report.md even for failures. The report here summarizes both tracks and the final verified code revision.

## Spatial geometry invariants

- Exactly 2 sheets and 1 picture per sheet, with independent picture-origin CAD coordinates.
- Preserve individually rotated Excel rectangles.
- Rectangle-to-rectangle SAT: positive-area overlap **fails startup**, edge contact allowed; error identifies Sheet and both shape names.
- Reconstructed circle uses the diagonal of the Excel ellipse bounding box as **diameter**.
- Full-circle containment in one rotated rectangle: ellipse height = rectangle roof Z.
- Exactly one partial circle/rectangle intersection (including edge tangency): ellipse height = half rectangle roof Z.
- Circle completely outside all rectangles: ellipse height = 0.
- Circle meeting **two or more** rectangles: **startup fails**, with Sheet and shape names.
- Invalid height suffix: rectangle Z=0; valid `_x<ratio>` uses width and `_y<ratio>` uses height.
- Cross-Sheet shapes are validated independently.
- Python XLSX startup integration verifies that invalid geometry never opens the Bokeh server/browser.
- Remaining Bokeh/HTTP frontend and SVG responsiveness regressions remain covered.

## Limitations

Actual local XLSX/SVG assets are unavailable in CI. WebGL rendering quality,
front-to-back appearance, and calibration against real drawings still require
local Windows browser visual verification.
