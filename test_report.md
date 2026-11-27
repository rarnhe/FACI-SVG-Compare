# Test Report

- UTC (CI report upload): 2026-11-27 10:26:40
- Overall result: **PASS**
- Verified functional commit: `c19109db76fb0c6e7b89645a89f5f0141d879fec`
- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45982005812

## GitHub Actions + test_report.md dual-track certification

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JavaScript syntax | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Ubuntu / Python 3.12 | 115/115 (4.270s) | 48/48 | 1/1 | PASS | **PASS** |
| Windows / Python 3.14 | 115/115 (5.838s) | 48/48 | 1/1 | PASS | **PASS** |

- Failures: 0; errors: 0.
- Both workflow jobs succeeded, generated and uploaded `test_report.md: PASS`.
- Ubuntu report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45982005812/artifacts/15188784761
- Windows report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45982005812/artifacts/15190011923

## P0: XLSX color resolution

- Added standard theme aliases tx1/bg1/tx2/bg2 and optional drawing color-map override.
- Resolve phClr from the style reference and apply luminance/tint/shade transforms.
- lnRef resolves the actual line-style matrix entry; direct paint overrides inheritance; explicit noFill, index zero and fully transparent direct solid paint are recognized as absent.
- Distinguishes color, none and unresolved in the manifest. Five additional Python tests cover black RGB/system/preset and theme colors, placeholder/fixed theme line paints, direct override, no border, unknown color and explicit logical mapping.

## P1: faithful border color rendering

- Existing explicit border RGB is used unchanged. For equipment rectangles/cuboids and ellipses with no border, use exact valid fill RGB. Unknown border color or absent valid fill does not generate a replacement color.
- Removes darkened fill fallback, contrast halo and arbitrary outline material color fallback. Single unlit, non-tone-mapped outline mesh per shape; preserves existing geometry, width clamp, rotation, picking, layer order and opacity behavior. Borderless textboxes remain borderless.
- Node tests verify exact black, original fill fallback, unknown and absent paint behavior.
- Real Chrome/WebGL regression checks rendered pixels and exact material RGB for black cuboid/rectangle borders, no-border rectangle/ellipse fill-colored boundaries and other explicit colors in both sheet layers and both camera views. Checks one outline mesh per shape (no halo), existing 12/4/72 edges, widths and marker-size behavior.
- All previous SVG, geometry, HTTP and security regressions passed.
- Actual workbook is not in the repository. Real-workbook visual verification remains necessary. Gradient/pattern line paints and full DrawingML alpha/transform fidelity beyond the tested solid color cases are not implemented. Existing non-outline body rendering behavior is unchanged.

This checked-in report summarizes observed CI logs and artifact metadata. The report-only commit does not alter functional code.
