# Test Report

- UTC (final CI report upload): 2026-11-27 12:15:29
- Overall result: **PASS**
- Base main: `6f5cf1889db680bc5f797f8d1089ba3e14330bae`
- Verified commit: `d9c86a473e83198c4c9f27b49e348c8796d2dd5a`
- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45996965364

## Dual-track certification

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 128/128 (3.473s) | 49/49 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 128/128 (5.755s) | 49/49 | 2/2 | PASS | PASS |

Both jobs passed on the first run and generated/uploaded their own test_report.md. Zero failures/errors.

- Ubuntu report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45996965364/artifacts/15196132725
- Windows report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45996965364/artifacts/15196790974

## Implementation and coverage

- Fresh PR from main, not a merge of PR #3. Strict drawing_rect extracts saved absolute EMU positions and dimensions for all three shape kinds, with no row/column metric fallback. worldRectFromEmu applies uniform per-layer scale, common picture-origin coordinate system and rotation. Preserve the existing circle reconstruction and alt-text cuboid height conventions.
- Existing main shape classification, text, rich text layout, alt text, color, border, fill fallback, opacity, hover and selection policies are retained. Real-browser fixture verifies the original valid fill and opacity.
- Full containment, partial overlap and tangency use visible rectangle text and a 14-digit timestamp in the filename. Outside uses the existing textbox search. Match PSD and octave SVG pairs by date and direction. Reject ambiguous multiple rectangles.
- Tests verify exact EMU geometry for textboxes, rectangles and ellipses, strict geometry errors, tiny extents, rotated corners, raster/shape alignment, preserved visual attributes, inside/partial/outside/tangent and rotated intersections, search distractor exclusion, actual right-click date and axis selection, paired overlays, original source caching, and existing browser outline and octave point scaling regressions.
- The private real-world XLSX is not available in CI. Local visual verification remains necessary. Strict mode requires saved absolute geometry and deliberately does not estimate coordinates from cells.

This checked-in summary reflects verified CI logs and uploaded artifact metadata. The report-only commit does not change production or test code.
