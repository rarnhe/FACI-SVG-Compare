# Test Report

- UTC: 2026-11-27 03:59:56
- Overall result: **PASS**
- Python unittest cases: **105 / 105 per platform**
- Node CAD geometry/UI tests: **33 / 33 per platform**
- Failures: **0**
- Errors: **0**

## GitHub Actions + test_report.md dual-track verification

| Environment | Python unittest | Node geometry/UI | JS syntax | Result |
| --- | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | **105/105** (3.606s) | **33/33** | PASS | **PASS** |
| Windows / Python 3.14 | **105/105** (5.416s) | **33/33** | PASS | **PASS** |

- Verified functional commit: `d34f0d981d3ecc6613165c9aeca9f20daae9e1b8`.
- Successful GitHub Actions: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45937274499
- Both platforms execute Python regression tests through
  `python tests/run_tests.py` and independent Node tests plus browser
  module syntax checks. The local Python runner regenerates
  `test_report.md` regardless of pass/fail; CI also uploads the
  platform-generated report as an artifact.

## Changes and regression scope

1. **Outside rectangle sensor filename search:** for a reconstructed ellipse
   outside all rectangles, but fully inside a textbox, filter files under
   `assets/<textbox name>/` by **textbox name plus `_14-digit timestamp_` in
   the same SVG filename**. An ellipse fully inside a rectangle still uses
   **rectangle label plus timestamp**. The legend's outside-rectangle
   display label remains the individual sensor name. Both branches
   deduplicate and sort dates and require matching PSD and octave pairs.
   Missing dates now display **「无可用测试结果」**, not the old prompt.
2. **Cuboid opacity:** translucent cuboid faces use 0.43 in normal state
   and 0.50 when selected; existing solid `BoxGeometry`, no wireframe,
   semantic textbox/rectangle/ellipse render order and height calculations
   remain unchanged.
3. **Workbook tab title:** remove only the final case-insensitive
   `.xlsx` suffix from the full workbook basename (e.g. `luoD.xlsx`
   becomes `luoD`); do not remove other periods inside the filename.
4. **Per-sheet SVG CAD background:** locate a unique,
   case-insensitively matched `assets/<Sheet name>.svg` for each
   workbook sheet, expose a read-only `background_svg` descriptor
   with its URL and intrinsic aspect ratio, and render it as the
   Three.js CAD backdrop. Prefer the SVG `viewBox` dimensions;
   fallback to width/height length metadata or browser intrinsic dimensions.
   The XLSX DrawingML image **is not displayed or decoded**. Its anchor
   is retained only to define the origin and alignment range for shapes.
   Removed the old `/viewer/cad-image` route, image_url manifest field,
   and embedded-media extraction implementation.
5. **Exactly matched geometry/scales:** the CAD image's original XLSX
   bounding width and height define the XY coordinate reference.
   Both CAD sheets share a common world width. SVG background height
   derives from the individual SVG aspect ratio. Every textbox,
   rectangle and ellipse is transformed using **the same exact X/Y
   scale factors as that sheet's SVG background**, preserving
   fractional positions and geometry relative to the replacement
   background even if it has a different ratio from the old embedded
   picture. Test cases use two intentionally different SVG aspect
   ratios with real temporary XML files.
6. **Security / compatibility:** sheet name path validation rejects
   traversal and separators, symlink-backed SVGs are not exposed through
   the manifest, and missing/ambiguous SVGs never trigger a PNG
   fallback. Existing private XLSX endpoints, dynamic shape-scoped
   SVG catalog, one-color PSD/octave browser overlays and other CAD
   geometry checks remain passing.

## Limitations and local visual verification

The user's actual XLSX and SVG drawings are not checked in. CI verifies
XML `viewBox` metadata, real temporary sheet-named SVG lookup,
manifest placement, purely computed coordinate alignment, HTTP routing,
and Node geometry helpers. Chrome's actual rendering of the private
workbook and the replacement SVGs still needs visual verification. If
the source SVG artwork uses an internal coordinate offset different
from the XLSX image's intended coordinate system, the display may
require an explicit registration transform; the tests do not infer
such an offset from artwork pixels.
