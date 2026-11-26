# Test Report

- UTC: 2026-11-26 09:07:51
- Overall result: **PASS**
- Python unittest cases: **95 / 95 per platform**
- Node CAD geometry and browser-color helper cases: **28 / 28 per platform**
- Failures: **0**
- Errors: **0**

## GitHub Actions + test_report.md dual-track verification

| Environment | Python unittest | Node geometry/UI | JavaScript syntax | Result |
| --- | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | **95/95** (4.272s) | **28/28** | PASS | **PASS** |
| Windows / Python 3.14 | **95/95** (3.857s) | **28/28** | PASS | **PASS** |

- Verified functional commit: `583a5d6a12bef6e176565bf2cfb8104b5a02e51e`.
- GitHub Actions: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45789030893
- `.github/workflows/test.yml` invokes `python tests/run_tests.py`
  and `node --test tests/test_cad_geometry.mjs tests/test_cad_ui.mjs`
  independently on Ubuntu and Windows. GitHub Actions uploads a generated
  `test_report.md` artifact even if tests fail. The Python test runner
  independently writes the same report path for local use.

## Removed code and regressions

1. Removed `drawTopLeftText`, all Three.js text meshes, their
   `CanvasTexture` creation and font handling. Rectangle, textbox and
   ellipse labels no longer appear as separately rendered CAD text.
   XLSX visible text is **still parsed** only for hover breadcrumbs,
   shape identity and associated SVG catalog folder detection.
2. Removed unused font reference / text-color extraction from
   `xlsx_spatial.py` and from the JSON shape's `colors` object.
   Console output prints only fill and outline colors and does not
   reference the removed field. Existing XLSX geometry/alt text
   reports and startup tests pass.
3. Removed the **line width** and **line type** legend menus,
   options, JSON commands, server-side write endpoint, and all code in
   `svg_styling.py`. Deleted its six obsolete persistence tests.
4. `/viewer/cad-svg-style` is no longer exposed; its POST returns
   HTTP 404 in the live Bokeh/Tornado integration test. No local SVG
   mutation path remains in this application.
5. Added browser-only `recolorSvgMarkup()`, using DOMParser and
   XMLSerializer to recolor explicit SVG paint without inserting
   opaque fill in unpainted regions. Original `fill="none"`,
   `stroke="none"`, transparent regions and gradient references are
   preserved. CSS color rules are covered by Node tests.
6. SVG source text is fetched **once per URL** and retained in a
   Promise cache in browser memory. A new pair is colored together
   from immutable original sources, assigned Blob URLs, and added as
   transparent layers. Duplicate/in-flight selections are blocked.
   Recoloring the legend creates new in-memory Blob URLs, with previous
   URLs revoked after successful swap; closing revokes both image URLs.
   Original `assets/**/*.svg` files are never rewritten.
7. Color palette contains exactly the 17 requested colors in order.
   Consecutive pair additions advance through the palette; each
   PSD / 1-3-Octave pair and its bold legend text use one identical
   color. Legend right-click offers **颜色 ›** (all 17 colors in
   a vertical submenu) and **退出** only.
8. Prior CAD camera synchronization, textbox hover hierarchy,
   read-only SVG catalog, independent pane aspect-fitting, MIME
   regression, and private workbook HTTP security remain green.

## Visual verification limitation

The user's real XLSX and SVG files are not in this GitHub repository.
CI verifies the pure JS recoloring behavior with an XML DOM test double,
read-only HTTP access, synthetic XLSX fixtures and Node geometry tests.
The exact Chrome SVG artwork and 3D rendered appearance still require
local visual testing. Also, if the **embedded PNG image itself** contains
baked-in lettering, removing CAD text meshes will not erase pixels
inside that original image.
