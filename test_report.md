# Test Report

- UTC: 2026-11-26 12:44:06
- Overall result: **PASS**
- Python unittest cases: **100 / 100 per platform**
- Node CAD geometry/UI cases: **32 / 32 per platform**
- Failures: **0**
- Errors: **0**

## GitHub Actions + committed test_report.md dual-track verification

| Environment | Python unittest | Node CAD/UI tests | JS module syntax | Result |
| --- | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | **100/100** (3.774s) | **32/32** | PASS | **PASS** |
| Windows / Python 3.14 | **100/100** (5.414s) | **32/32** | PASS | **PASS** |

- Verified functional commit: `a9c44f0f37fca7be5a8fad495d464dd322829e59`.
- Successful workflow:
  https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45822300745
- The workflow independently runs the Python suite, Node geometry/UI
  tests, and the JavaScript syntax check on each platform. The local
  `python tests/run_tests.py` runner regenerates `test_report.md`
  on pass and fail; Actions uploads that generated report artifact
  even if a test fails.

## Changes and regression coverage

1. **Explicit transparent rendering order.**
   The CAD viewer applies `CAD_DRAW_ORDER` to both the geometry
   group and its drawable children. Stable order:
   `XLSX image (0) < textbox (10) < other shape (15) <
   rectangle (20) < ellipse (30)`. This removes dependence on the
   XLSX source's shape enumeration order or Three.js transparent
   distance sorting when the camera rotates. Each shape outline
   renders immediately after its own fill.
2. **World-space separation without changing cuboid height.**
   `cadShapeZOffset()` puts textbox geometry at Z=-1,
   rectangle base at Z=0, and ellipse geometry above its existing
   `ellipseElevation()` height by +1. The cuboid remains an actual
   transparent `THREE.BoxGeometry`, retaining its original
   alt-text-derived height and opacity. Textbox background is no
   longer closer to the camera than flat rectangles when viewed
   from above. The XLSX picture still draws at the reference origin.
3. **Hover semantics use the same layer priority.**
   When multiple shapes overlap under the pointer, hover picks
   the highest-priority ellipse, then rectangle, then textbox.
   Left-click selection rules and right-click ellipse menu behavior
   are unchanged.
4. **Legend and first-level popup alignment.**
   All floating legend text rows are explicitly left-aligned.
   The right-click popup primary items `颜色` and `退出`
   stretch to one width and are also left-aligned. The original
   vertical second-level color choices remain unchanged.
5. **Node tests:** assert strict image/textbox/rectangle/ellipse
   ordering independent of input permutation and the corresponding
   Z offsets. A new Python static regression checks all layer
   assignments, hover priority and legend menu alignment.
6. Existing dynamic SVG catalogs, left-side hover breadcrumbs,
   rectangle/ellipse geometry and Z elevation calculations,
   color-only browser-memory SVG recoloring, private XLSX
   handling, HTTP MIME, and responsive SVG splitters remain green.

## Visual testing limitation

Actual XLSX and SVG assets are not present in this repository, so
CI cannot confirm the final Chrome/WebGL appearance of a real rotated
workbook. The user's Windows Chrome visual verification remains
necessary for subtle transparency or depth overlap effects.
