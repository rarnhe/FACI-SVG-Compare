# Test Report

- UTC: 2026-11-26 06:51:57
- Result: **PASS**
- Python unittest cases: **87 per platform**
- Node CAD geometry + UI tests: **24 per platform**
- Failures: **0**
- Errors: **0**

## GitHub Actions dual-track verification

| Environment | Python unittest | Node CAD tests | JS syntax | Result |
| --- | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | **87/87** (4.196s) | **24/24** | PASS | **PASS** |
| Windows / Python 3.14 | **87/87** (4.335s) | **24/24** | PASS | **PASS** |

Successful CI run for commit `51ee8836d11f9a856f900500a0602b1d0e850a93`:
https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45771094030

The workflow runs `python tests/run_tests.py`, checks `cad_viewer.js` module
syntax, and runs `node --test tests/test_cad_geometry.mjs tests/test_cad_ui.mjs`.
The runner creates `test_report.md` on pass or failure; GitHub Actions
uploads the independent per-platform report artifact even when tests fail.

## Verified implementation

1. DrawingML shape alternative text uses `cNvPr@descr` / `title` and
   cleans Excel `_x000D_` newline escapes. `z=0.5x` and `z=0.2y` set
   cuboid height; old visible suffix `B1_x0.5` no longer changes height.
   Empty or invalid alt text yields no 3D box.
2. Textboxes use XLSX fill/outline/text color instead of forced gray.
   Fab-only top-left operation hint has a rounded border; both CAD panes
   show rounded lower-left breadcrumbs only while hovering a selectable shape.
3. XLSX embedded picture native aspect ratio is preserved. The two layers
   normalize their picture widths in shared CAD coordinates; each overlay's
   image-relative X/Y coordinates are transformed accordingly.
4. Browser tab title uses the source XLSX filename.
5. Right-clicking an ellipse requests an on-demand folder catalog using its
   enclosing textbox text (e.g. `assets/BODYv2/`). Filename timestamps
   matching `_(\d{14})_` are deduplicated and sorted for the first menu.
6. Second-level X/Y/Z menu opens horizontally. Only pairs matching the
   ellipse's containing rectangle identity, timestamp and `+X/+Y/+Z`
   plus `_PSD.svg` / `_1-3-Octave.svg` suffixes can replace both right
   images. Path traversal and non-ellipse requests are rejected.
7. Successful selections append a line like
   `20260704_SCN_B1_20260704101627_+X` to the freely draggable,
   square-corner reference history window; repeated selections add lines.
8. The right splitters use the current displayed SVG dimensions to constrain
   movement; both SVGs remain aspect-preserving and centered without
   introducing horizontal scrollbars.
9. Legacy XLSX constraints, Three.js camera synchronization, Bokeh endpoint,
   JavaScript MIME, private workbook security and HTTP tests all remain green.

## Verification limitation

The actual customer workbook, embedded images, and SVG folders under
`assets/` are not checked into GitHub. CI uses synthetic XLSX and SVG
fixtures plus real Python HTTP integration and Node unit tests. Final Chrome
visual behavior and menus with the actual private SVG file naming scheme
must be confirmed locally.
