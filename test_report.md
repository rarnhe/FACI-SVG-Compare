# Test Report

- UTC (CI report upload): 2026-11-27 09:32:54
- Overall result: **PASS**
- Verified functional commit: `19bb5a46c3ffe4d1f3f82d25057029f26f1f4b8a`
- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45974530175

## GitHub Actions + test_report.md dual-track certification

| Platform | Python unittest | Node geometry/UI | JavaScript syntax | Result |
| --- | ---: | ---: | ---: | --- |
| Ubuntu / Python 3.12 | 110/110 (3.475s) | 45/45 | PASS | **PASS** |
| Windows / Python 3.14 | 110/110 (4.546s) | 45/45 | PASS | **PASS** |

- Failures: 0; errors: 0.
- Both workflow jobs succeeded and independently generated and uploaded `test_report.md: PASS`.
- Ubuntu report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45974530175/artifacts/15187165033
- Windows report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45974530175/artifacts/15186282456

## Changes and regression coverage

- Seven named colors (red, orange, yellow, green, blue, purple, gray), auto-cycle and menu; removed dotted line and widths below 3; original plus 3/4/5/6/7 widths.
- Octave-specific paint pass covers separate stroked lines and filled point symbols, including common CSS, circle/ellipse/polygon, closed paths and local use references; preserves unpainted channels and protects labels and clipping definitions. PSD continues its curve-targeted strategy.
- Added DrawingML line width parsing (direct and theme line references) with manifest metadata; screen-space LineSegments2/LineMaterial contours for cuboids, flat rectangles and reconstructed circles. Prefer XLSX outline color; use darker fill-derived contrast fallback for equipment/sensors without usable outline; clamp width to 2–5 screen pixels. Textbox no-outline setting remains respected.
- Existing XLSX backgrounds, camera linkage, geometry and elevation, 93%/100% cuboid opacity, picking, original SVG cache and read-only backend regression tests passed.
- New Node tests cover octave line/point recoloring and outline specification; Python test covers direct and inherited DrawingML line widths.
- Actual workbook/SVGs are not committed. Browser WebGL appearance, unusual SVG marker/paint structures and visual effects of thicker contours still require local verification.

This checked-in report summarizes observed workflow logs and uploaded artifact metadata; the report-only commit does not change functional code.
