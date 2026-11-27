# Test Report

- UTC (CI report upload): 2026-11-27 10:13:29
- Overall result: **PASS**
- Verified functional commit: `edab41a2054c126cb54ba381f9ca05c63d52f449`
- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45980124286

## GitHub Actions + test_report.md dual-track certification

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JavaScript syntax | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Ubuntu / Python 3.12 | 110/110 (3.259s) | 48/48 | 1/1 | PASS | **PASS** |
| Windows / Python 3.14 | 110/110 (5.623s) | 48/48 | 1/1 | PASS | **PASS** |

- Failures: 0; errors: 0.
- Both workflow jobs succeeded, independently generated and uploaded `test_report.md: PASS`.
- Ubuntu report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45980124286/artifacts/15188388842
- Windows report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45980124286/artifacts/15188393877

## Changes and regression coverage

- SVG width defaults to original markup. Menu offers only 2, 2.5, 3, 3.5, 4; no original-width or 5 item. Original size remains the initial state after closing/reloading.
- Blank or absent alternative-text rectangles use the same closed-loop outline generator as ellipses, with four rectangle corners versus 72 circle vertices. Uses existing DrawingML outline color/width policy and contrasting halo. A nested border group orders these outlines after rectangle fills, before ellipse geometry, without changing the rectangle plane. Nonempty invalid/zero height directives retain prior rendering. Cuboid and ellipse geometry/opacity, textboxes and picking remain unchanged.
- Node regression checks missing, blank, whitespace and encoded-empty alt text, and preserves nonempty alt text handling; checks shared outline coordinates, all five permitted widths and invalid choices.
- Real Chrome/WebGL test checks actual rendered outline pixels for all ten synthetic CAD objects in top and tilted views (20 checks per platform), including a rotated flat rectangle with missing alt text and a different XLSX-derived width, the distinct blank-alt border group and preserved circle/cuboid paths. Checks marker dimensions and center positions at all five selectable widths and original defaults, with auxiliary points unchanged.
- Existing geometry, paired SVG read-only cache, seven colors, four line types, HTTP, security and shape regression tests passed.
- Actual private XLSX/SVG resources remain absent; real workbook appearance still requires local visual verification. The automated browser fixture verifies the implementation, not the user's exact workbook.

This checked-in report summarizes observed CI logs and artifact metadata. The report-only commit does not alter functional code.
