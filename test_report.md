# Test Report

- UTC: 2026-11-26 07:38:57
- Result: **PASS**
- Python unittest cases: **93 per platform**
- Node CAD geometry + UI cases: **27 per platform**
- Failures: **0**
- Errors: **0**

## Dual-track GitHub Actions verification

| Platform | Python unittest | Node geometry/UI | JavaScript module syntax | Result |
| --- | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | **93/93** (3.332s) | **27/27** | PASS | **PASS** |
| Windows / Python 3.14 | **93/93** (5.667s) | **27/27** | PASS | **PASS** |

Verified feature commit: `3a9f9593be0282af1332a64a7de327a7cbeeb83e`.
Successful workflow:
https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45776813730

The existing `.github/workflows/test.yml` independently executes
`python tests/run_tests.py` and `node --test tests/test_cad_geometry.mjs
tests/test_cad_ui.mjs` on both platforms, checks `cad_viewer.js` JavaScript
module syntax, and uploads its own `test_report.md` artifact on pass or fail.
The Python test runner independently writes `test_report.md` on every run.

## Changes covered

1. XLSX DrawingML `a:rPr/@sz`, paragraph default `a:defRPr/@sz`,
   and text-run sizes are exposed as `text_layout` with real sizes in
   points (hundredths converted to points). The CAD text canvas uses these
   sizes converted to 96-dpi pixels, including mixed sizes within one line.
   The former 48px fixed font and arbitrary downscaling have been removed.
2. Fab's top-left operation hint and the top-right ↺ button now share the
   same 14px font, white background, border and 36px height, aligned at
   the same vertical coordinate.
3. A static non-draggable 8px horizontal CAD divider matches the vertical
   splitter color and thickness. Right SVG horizontal divider starts at
   exactly the same viewport height (1:1, centered).
4. Selected PSD and 1-3-Octave SVGs are loaded as transparent, independently
   stacked overlays above the original right-side reference images.
   No white fill is applied by the overlay containers or images; unpainted
   SVG regions remain transparent so the underlying image remains visible.
5. Before loading, overlay labels are checked against the active legend and
   a set of pending loads. Duplicate selection does not create another
   SVG pair or legend entry, including fast concurrent clicks.
6. Each legend entry displays swatches derived from the actual SVG's
   explicitly declared fill/stroke paint values. Multiple paints are
   represented by a gradient; no invented white background is used.
7. Right-clicking an individual legend row opens a '关闭' menu. Clicking it
   removes precisely the corresponding two SVG overlays and legend row,
   restoring visibility of the original base/reference layers below.
   Removed selections may be added again.
8. SVG fitting accounts for active overlays' intrinsic aspect ratios and
   current pane sizes. Divider movement remains constrained so images do
   not overflow; no fixed image max-width / max-height is imposed.
9. Existing XLSX alt-text cuboid heights, Fab/Subfab camera synchronization,
   dynamic timestamp catalog, Bokeh server, static MIME headers, and HTTP
   security regressions remain green.

## Limitations

The user's real XLSX and SVG assets under `assets/` are not committed to
the repository. CI uses synthetic XLSX fixtures, pure Node SVG/color tests,
and a real local Bokeh HTTP server. Interactive Chrome/WebGL rendering,
the exact private SVG colors, and final visual alignment still require
the user's Windows browser visual verification.
