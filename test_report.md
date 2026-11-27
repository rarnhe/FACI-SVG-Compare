# Test Report

- UTC: 2026-11-27 16:08:35
- Result: **PASS**
- Tests: 137
- Passed: 137
- Failures: 0
- Errors: 0
- Skipped: 0
- Duration: 4.19s

## Scope

Restored DrawingML rich textbox font family, size, color and theme font references, paragraph alignment, body insets and textbox CanvasTexture rendering, plus theme aliases, phClr and line style inheritance, distinct absent/unresolved outlines and exact XLSX RGB borders without synthetic contrast colors. Cuboids now use 93%/100% solid-face opacity with matching rectangle-colored EdgesGeometry outlines. PNG CAD backgrounds, saved DrawingML X and extents, per-sheet picture dual-anchor normalized row-anchor Y, exact rational position mapping with preserved extents, absolute-anchor relative mapping, unavailable calibration diagnostics and raw crop metadata, no column metrics or xfrm Y fallback, contextual fail-fast on missing geometry, one exact EMU-to-world transform for all shapes and uniform XY scaling, shared rectangle overlap catalog/validation, rectangle visible-text search, unchanged non-geometric attributes, SVG overlays use seven named colors, widths 2/2.5/3/3.5/4 with original default, four line styles, proportional octave point scaling and shared planar outline rendering for blank-alt rectangles and ellipses; paired overlays, original restoration, curve targeting, shape selection, security and HTTP regressions are covered.
Browser/WebGL regression includes real generated XLSX with missing/malformed/stale DrawingML Y, different independent picture calibration factors 1.25/0.8, mismatched end spans, inconsistent column markers and hidden rows/columns, production parser/manifest HTTP input and byte-exact real image endpoint extraction (browser uses the verified HTTP response bytes) and checks decoded raster versus XLSX display aspect, exact shape widths/heights, rotated corners, square projection, depth and text texture geometry, actual right-click inside/partial/outside catalog-to-SVG overlays and preserved original fill and opacity. Private workbook visual verification remains necessary.

