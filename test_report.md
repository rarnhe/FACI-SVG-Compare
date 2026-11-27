# Test Report

- UTC (final CI report upload): 2026-11-27 11:39:03
- Overall result: **PASS**
- Verified commit: `b0c0668d34fab61fc786635f3749a9a86dc18730`
- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45991941845

## Dual-track certification

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 120/120 (3.860s) | 48/48 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 120/120 (4.850s) | 48/48 | 2/2 | PASS | PASS |

Both jobs succeeded and generated/uploaded test_report.md. Zero failures/errors in the final attempt.

- Ubuntu report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45991941845/artifacts/15193872943
- Windows report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45991941845/artifacts/15194635420

## Geometry fidelity

- P0 uniform per-sheet XY scaling and shared camera/common image width retained.
- Correct stored OOXML column widths using ISO 29500 conversion; remove double padding. Default fallback stays 64px with assumed MDW=7; exact font-dependent widths are not guaranteed without saved transforms.
- For top-level pic/sp/cxnSp in twoCellAnchor, choose valid saved positive DrawingML extents and usable absolute offset; missing/placeholder offset uses cell origin, invalid extents fall back to anchor. oneCellAnchor and absoluteAnchor retain exact anchor geometry. This is a saved snapshot policy; stale transforms or later Excel cell-resize behavior are not simulated.
- Record geometry_source (anchor/xfrm/xfrm_size) in output and manifest. Original workbook remains read-only; use same geometry for images, shapes, backend validation and frontend.
- Five new Python tests cover stored widths, exact dimensions, zero-offset placeholders, invalid extent fallback and exact anchors, and rotated shape/background-relative vertices. Browser regression now opens a real generated two-sheet XLSX via production manifest and embedded-image HTTP handlers; distinct native raster ratios and deliberately mismatched cell metrics, expected dimensions independent of parser. Checks textbox, square, rotated corners, cuboid and ellipse geometry, texture and screen projection, plus existing outline and SVG regression.
- Initial run 45991808454: both browser suites passed, but two old Python assertions expected the previous 85px origin instead of corrected 80px; updated tests. Run 45991941845 attempt 1: Windows passed; Ubuntu Python/Node passed, but an intermittent missing decoded background assertion failed. PNG payload independently decoded successfully. Reran failed Ubuntu job without weakening assertions or altering code; final attempt passed. The one-off image-load failure's cause is unconfirmed.
- No private workbook available, so local visual parity is not yet established. P0, SVG catalog implementation, colors, outline/style rendering, and frontend interaction logic were not changed in this follow-up.

This checked-in summary reflects verified CI logs and artifact metadata. Report-only commit does not alter production or test code.
