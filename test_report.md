# Test Report

- UTC: 2026-11-25 07:46:57
- Result: **PASS**
- Tests: **52 per platform**
- Passed: 52
- Failures: 0
- Errors: 0
- Skipped: 0

## Dual-track verification

| Environment | Result | Tests | Duration |
| --- | --- | --- | --- |
| GitHub Actions Ubuntu / Python 3.12 | PASS | 52/52 | 3.848s |
| GitHub Actions Windows / Python 3.14 | PASS | 52/52 | 4.068s |

- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45570741557
- JavaScript syntax: `node --input-type=module --check < cad_viewer.js` passed on both runners.
- Both environments use `python tests/run_tests.py`, which generates this report even when Python tests fail.

## Coverage

- Existing Python/Bokeh entry, separate `/analysis` route and port behavior
- XLSX selection, A1-relative bounds, DrawingML shape text, color, rotation
- XLSX drawing-image relationship resolution, on-demand media extraction, size/type checks
- Fab and Subfab ordered layer manifest; missing assets and SVG fallbacks
- Two-layer Three.js pointer/sync/reset UI contracts and valid JavaScript module syntax
- No GLB loading, no Service Worker registration, no public XLSX downloads
- HTTP cache, static assets, CAD JSON and invalid image route

## Important boundaries

The actual local `luoD.xlsx`, `PSD_base.svg` and `OneThreeOctave_base.svg`
were not available to CI; synthetic XLSX fixtures validate extraction.
Browser/WebGL appearance, precision against real CAD coordinates, and source
SVG display require the user's local visual verification. The two SVG files
should be present in `assets/` to render on the right.
