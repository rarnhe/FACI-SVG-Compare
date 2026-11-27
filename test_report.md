# Test Report

- UTC (final CI report upload): 2026-11-27 12:04:09
- Overall result: **PASS**
- Verified commit: `25185d6f64e49bed0dd6404da3900f96109dea68`
- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45995405640

## Dual-track certification

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 128/128 (3.694s) | 50/50 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 128/128 (4.723s) | 50/50 | 2/2 | PASS | PASS |

Both jobs succeeded on the first run. Each generated and uploaded its own test_report.md. Zero failures/errors.

- Ubuntu report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45995405640/artifacts/15195701858
- Windows report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45995405640/artifacts/15195911236

## Implementation and coverage

- The already shared strict DrawingML parser remains unchanged. All images, textboxes, rectangles, and ellipses now use worldRectFromEmu with a single uniform scale and exact EMU dimensions; remove minimum world-size clamping. Retain original image-relative origin, rotation, circle reconstruction (diagonal diameter), and alt-text cuboid height rules.
- Backend catalog and collision validation share intersecting_rectangles. Full containment, partial overlap, and tangency use the rectangle's visible text plus the 14-digit timestamp. Outside all rectangles uses the enclosing textbox's visible text. No fallback to generated object names or sensor text as search identifiers. Multi-rectangle contact remains invalid. Hover breadcrumb uses the corresponding relationship.
- Exact XLSX RGB for visible shape fills; transparent/unresolved fills remain transparent during selection rather than showing synthetic blue/white. Existing outline, valid-fill opacity, text layout, and SVG style controls retained.
- Tests cover identical saved geometry for all three shape types, exact small EMU extents, full/partial/outside/tangent and rotated contacts, ambiguous multi-rectangle rejection, visible-text-only filename matching, and hover consistency.
- Real generated XLSX to production manifest/image/catalog/static HTTP handlers to actual Chrome/WebGL: verify both sheets, shape positions, rotated corners, dimensions, circles and height, exact valid fill, absent/unresolved fill, actual right-click dates and axis selection for inside/partial/outside sensors, paired SVG overlays, filename distractor exclusion, cached source reuse, and transparent selection.
- Original user's private XLSX is not available for direct visual verification. Retained circle and cuboid conventions are intentional CAD interpretations of the saved geometry. Strict geometry requires valid saved absolute transforms; no row/column estimation.

This checked-in summary reflects verified CI logs and uploaded artifact metadata. The report-only commit does not change production or test code.
