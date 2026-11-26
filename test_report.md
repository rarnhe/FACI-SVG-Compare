# Test Report

- UTC: 2026-11-26 03:32:50
- Result: **PASS**
- Python unittest cases: **78 per platform**
- Node CAD geometry + UI tests: **22 per platform**
- Python failures: 0
- Python errors: 0
- Node failures: 0

## GitHub Actions dual-track verification

| Environment | Python unittest | Node geometry/UI tests | JavaScript syntax | Result |
| --- | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 78 / 78 | 22 / 22 | PASS | **PASS** |
| Windows / Python 3.14 | 78 / 78 | 22 / 22 | PASS | **PASS** |

- Successful workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45749533390
- Ubuntu Python test time: 3.082s; Windows Python test time: 5.601s.
- Existing `.github/workflows/test.yml` runs `python tests/run_tests.py` plus
  `node --test tests/test_cad_geometry.mjs tests/test_cad_ui.mjs`; it uploads a
  `test_report.md` artifact on both runners even on failure.
- The Python runner itself also writes `test_report.md` during test execution.
  This file records the combined GitHub Actions checks observed after the run.

## Changes verified

1. Both CAD Three.js backgrounds are white; unobtrusive black operation instructions
   appear in each layer without a colored box.
2. Selected-shape breadcrumbs appear at the lower left of the **respective** Fab
   or Subfab pane: workbook stem, real worksheet name, strict geometry-based
   containment ancestors (e.g. `BODYv2`), and selected shape text.
3. Textboxes are visible but never selectable; ellipses are right-click only.
   A short right click opens placeholder actions `2025 ›` (nested `X / Y / Z`)
   and `2026`; right-drag panning remains bound to OrbitControls.
4. Right-side PSD and 1/3-octave SVGs are centered and scaled to a *common*
   display width, constrained to fit the available width and height, with no
   horizontal scrolling; initial vertical split is 5.8:18.1.
5. Both splitter ranges are bounded and all SVG dimensions remain
   aspect-ratio-preserving. Node tests cover geometry, hierarchy and layout limits.
6. Existing XLSX parse, MIME type, HTTP security, CAD shapes, and Bokeh endpoint
   regression tests remain green.

## Limitations

The original local `luoD.xlsx`, `PSD_base.svg`, and `1-3-Octave_base.svg`
were not available to CI. Real Windows browser, WebGL rendering, interactive
pointer behavior, and appearance of the actual SVGs still require the user's
local visual verification.
