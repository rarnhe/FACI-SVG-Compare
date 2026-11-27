# Test Report

- UTC (CI report upload): 2026-11-27 11:25:17
- Overall result: **PASS**
- Base main: `6f5cf1889db680bc5f797f8d1089ba3e14330bae`
- Verified commit: `6ff454a56ce10af2cd056ea875b5bd186e097934`
- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45990204355

## P0 dual-track certification

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 115/115 (4.322s) | 48/48 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 115/115 (4.618s) | 48/48 | 2/2 | PASS | PASS |

Both jobs succeeded, independently generated and uploaded test_report.md. Zero failures/errors in the final run.

- Ubuntu report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45990204355/artifacts/15193880007
- Windows report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45990204355/artifacts/15192448625

## Implementation and coverage

- XLSX drawing anchor bounds alone determine displayed geometry; decoded raster dimensions no longer determine X/Y scale. Preserve common displayed image width, synchronized cameras, and one uniform scale per sheet.
- The two browser PNGs intentionally have different native and anchor aspect ratios. Verify actual texture dimensions, background geometry/center, rectangle and textbox dimensions, original rotated corners, square screen projection, textbox texture plane, cuboid height, ellipse radius and inside/partial/outside elevation, and linked camera zoom.
- Retain prior WebGL outline/color and octave marker tests, all existing Python and Node regressions, geometry classification, SVG catalog, and UI behavior.
- Initial run 45990060501 caught fractional CSS viewport versus integer WebGL viewport rounding in the new test (about 0.045% aspect difference in one assertion). Test-only follow-up separates exact logical viewport projection from CSS pixel rounding, with a bound derived from measured viewport dimensions and at most one pixel of difference. Core geometry assertions retain their original strict tolerance; final rerun passed.
- P1 (XLSX column-width and anchor extraction) is intentionally out of scope. Per-sheet normalization is not an absolute physical scale shared across both sheets. If the original workbook displays a stretched picture, that displayed aspect is intentionally preserved.
- User's private workbook was unavailable; real-workbook visual verification remains necessary.

This checked-in summary reflects verified CI logs and uploaded artifact metadata. Report-only commit does not change production or test code.
