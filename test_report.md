# Test Report

- UTC: 2026-11-27 08:22:28
- Overall result: **PASS**
- Python unittest cases: **109 / 109 per platform**
- Node CAD geometry/UI cases: **39 / 39 per platform**
- Failures: **0**
- Errors: **0**

## GitHub Actions + test_report.md dual-track certification

| Environment | Python unittest | Node CAD geometry/UI | JavaScript syntax | Result |
| --- | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | **109/109** (3.350s) | **39/39** | PASS | **PASS** |
| Windows / Python 3.14 | **109/109** (5.489s) | **39/39** | PASS | **PASS** |

- Verified functional commit: `ded2a59fb5cb71115f6e28f9dcfb1b7809136b06`.
- Successful GitHub Actions:
  https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45965074165
- GitHub Actions runs the Python unittest suite, independent Node UI/
  geometry tests and JavaScript module syntax checks on both platforms.
  `python tests/run_tests.py` writes the generated report on both pass
  and fail; GitHub Actions uploads each platform's `test_report.md`
  artifact even when checks fail.

## DrawingML textbox text and cuboid outline changes

1. **Restore Excel textbox typography.**
   `xlsx_spatial.py` parses DrawingML text body paragraphs and rich text
   runs. `text_layout` carries each run's text, font family, East Asian
   typeface fallback, 1/100-point font size, font color (direct RGB or
   theme), bold/italic, paragraph horizontal alignment, body vertical
   anchoring and inset positions in reference pixels. Theme major/minor
   Latin and East Asian typefaces are read from `theme1.xml`.
   The textbox's existing XLSX fill and outline colors remain intact,
   including explicit no-fill/no-outline settings. This metadata is
   passed through the read-only CAD manifest without modifying XLSX.
2. **Restore actual Three.js text rendering.**
   For each textbox with visible text, the browser lays out its runs
   inside the textbox's original DrawingML dimensions. Glyph metrics
   determine line wrapping, paragraph alignment and vertical
   placement. The text is drawn with the parsed font/color to a
   transparent, bounded `CanvasTexture`, displayed as a plane inside
   the textbox group. Because the plane receives the textbox's
   position, rotation and exactly the same X/Y scaling factors used
   by the embedded XLSX picture background, text remains registered
   to the shape. It is not an extra picking surface.
3. **Keep correct visual stacking.**
   Draw order remains picture -> textbox background -> textbox text/
   colored outline -> rectangle -> ellipse. No extra text is drawn
   for rectangles or ellipses. Textboxes remain non-clickable and
   their text still participates in hover breadcrumbs and SVG catalog
   folder matching.
4. **Restore actual cuboid edge lines.**
   Positive-height Excel rectangles use solid-face
   `THREE.BoxGeometry` with `CUBOID_FACE_OPACITY=0.93` normally and
   `CUBOID_SELECTED_OPACITY=1.00` when clicked. A separate
   `THREE.EdgesGeometry` + `LineSegments` renders its 3D edges in
   the original XLSX outline color. An explicitly invisible/transparent
   outline does not add artificial lines. The edge render order is
   slightly above the solid face, clarifying edges during rotation
   while preserving the ellipse's higher stacking priority. The
   pre-existing rectangle altitude and 2D fallback are unchanged.
5. **New regression coverage.**
   Python tests check mixed per-run font names, font sizes, RGB and
   theme colors, bold/italic, paragraph center/right alignment,
   textbox body insets and vertical anchors, line breaks, fontScheme/
   fontRef defaults and the original outline color. A manifest test
   confirms `text_layout` and outline metadata survive transport.
   Node tests verify Canvas font strings, pt-to-pixel conversion,
   paragraph wrapping, top/center/bottom placement and exact
   opacity values; Python static checks confirm CanvasTexture drawing,
   colored EdgesGeometry, transparency and render-order semantics.
6. **Prior behavior unchanged.**
   XLSX embedded PNG/JPEG CAD picture loading, per-sheet native-aspect
   coordinate alignment, paired Fab/Subfab controls, mouse picking,
   rectangle/ellipse positioning, SVG catalog date matching, 17-color
   browser-only SVG recoloring, right-side legend, read-only media
   endpoints, private XLSX protection and Bokeh integration remain green.

## Visual verification limitations

The actual user workbook has not been committed to the repository.
CI checks synthetic DrawingML content and the live code's layout
functions; the precise Chrome WebGL appearance must still be checked
locally, especially for uncommon font availability, vertical writing,
complex script shaping, nonstandard Excel autofit rules, and unusual
textbox rotations or 3D occlusion.
