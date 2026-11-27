# Test Report

- UTC: 2026-11-27 04:18:21
- Overall result: **PASS**
- Python unittest cases: **104 / 104 per platform**
- Node CAD geometry/UI cases: **35 / 35 per platform**
- Failures: **0**
- Errors: **0**

## GitHub Actions and test_report.md dual-track verification

| Environment | Python unittest | Node CAD geometry/UI | JavaScript module syntax | Result |
| --- | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | **104/104** (3.602s) | **35/35** | PASS | **PASS** |
| Windows / Python 3.14 | **104/104** (4.753s) | **35/35** | PASS | **PASS** |

- Verified functional commit: `1596a6f45e67fc723a982725f55831f3beebf76f`.
- Successful GitHub Actions:
  https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45939093142
- Both runners execute `python tests/run_tests.py`, the Node geometry/UI
  test suites and JavaScript module syntax checks. The Python runner writes
  `test_report.md` for both passing and failing runs; Actions uploads it
  as a per-platform artifact even when checks fail.

## Reverted CAD background source and preserved image/shape alignment

1. **Restore XLSX embedded pictures as the only left-side CAD backdrops.**
   Each of the two sheets must have exactly one DrawingML picture. The
   Python manifest once again exposes the picture's trusted `image_url`
   as `/viewer/cad-image/<layer>/<object>` and its bounds as local
   coordinates, with the image top-left relocated to (0,0). It never
   publishes `image_part` or unrestricted workbook file paths.
2. **Restore read-only XLSX media extraction.**
   `CadImageHandler` and `extract_embedded_image` retrieve only image
   parts selected from parsed sheet/object indices, enforce supported
   PNG/JPEG/GIF/WEBP/BMP extensions, require `xl/media/`, and restrict
   uncompressed payload size to 64 MiB. Content type and
   `X-Content-Type-Options: nosniff` are set explicitly.
   The original XLSX remains unavailable as a static asset.
3. **Remove per-Sheet asset SVG backdrop lookup entirely.**
   The `background_svg` manifest field, `sheet_svg_metadata`,
   `_svg_aspect` and the previous `Fab.svg`/`Subfab.svg`
   dependency are gone. The right-side PSD and 1-3-Octave SVG reference
   images, dynamic catalog and 17-color browser-only SVG recoloring
   remain unchanged.
4. **Native image aspect ratio and matched geometry scale.**
   Browser `THREE.TextureLoader` loads the actual XLSX picture; the
   `imageAspectRatio()` helper uses `naturalWidth/naturalHeight`
   or decoded width/height when present, otherwise the XLSX image
   anchor ratio as a geometry fallback. Both sheets share one
   world-space picture width. Each picture's rendered height is
   `sharedWidth * decodedNativeAspect`. Every textbox, rectangle,
   ellipse and picture in that sheet uses the **identical X/Y scale
   factors**. The image remains undistorted and sheet-relative shapes
   stay registered to its fractional coordinates.
5. **New two-picture regression cases.**
   Node tests exercise different aspect ratios (including ones that
   disagree with the DrawingML anchor ratio), verify all four
   transformed image corners and ensure shape locations and sizes
   preserve their normalized coordinates. Python tests validate the
   trusted lazy image URLs for both layers, original origin shift,
   real ZIP payload extraction, supported MIME and rejection of
   bad media paths or oversized parts.
6. **No unrelated UI changes.**
   Workbook tab continues to strip only the final `.xlsx` extension;
   the textbox/rectangle/ellipse Z-order, 43% normal and 50% selected
   cuboid opacity, left-aligned legend, rectangle/textbox-scoped
   timestamps and no-results message all remain intact.

## Visual verification limitation

The real user workbook and embedded pictures are not included in
the repository. CI verifies synthetic XLSX images and spatial
geometry and the same JavaScript scaling code used by the viewer,
but final appearance in Chrome for the user's private workbook
remains a local visual verification. If the workbook embeds a cropped
image with viewport-specific offsets, its exact display registration
may need additional image crop metadata beyond these dimensions.
