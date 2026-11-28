# Test Report

- Overall result: **PASS**
- Previous PR head: `240bc1bbc41148b9a00e03eaece1355af26031e1`
- Verified commit: `f99380843b44c43d9b2c09cc5d7be579de157a12`
- Workflow: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46094107881

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 140/140 | 50/50 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 140/140 | 50/50 | 2/2 | PASS | PASS |

Both jobs completed successfully and uploaded their generated test reports.

- Ubuntu: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46094107881/artifacts/15241444915
- Windows: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46094107881/artifacts/15242353077

## First run and correction

The first run (https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46093989903) failed an Ubuntu rotated-edge SVG catalog assertion: its fixture used the former circle-center position. The test-only follow-up explicitly checks both the new contacting position and the former now-separated position. No production algorithm change in that follow-up.

## Scope and limitations

- Single upper-left position for every shape: normalize the object's start row/column anchor using the sheet picture's independent axis factors; only the picture end markers affect calibration. Object end markers, span mismatch and rotation cannot shift its anchor. Absolute anchors use direct position and prior relative-Y mapping; missing calibration or X start retains initial saved X/raw row Y with diagnostics.
- Preserve saved widths/heights and rotation. Remove center_emu/center_geometry. Rectangles use the unrotated frame's upper-left with the existing center-of-geometry rotation convention. A rotated visible corner is not necessarily the same as the unrotated anchor.
- Retain diagonal diameter hypot(W,H) for reconstructed circles, now align the circle's bounding square upper-left to the XLSX anchor; derive the local center offset from radius only. Rendering, outline, collision, containment and SVG search share that placement. Original XLSX rectangle corner diagnostics are not the reconstructed circle footprint.
- Tests verify stale saved positions, conflicting end spans, hidden columns/rows, independent sheet factors, exact size, rotated geometry, circle anchor and spatial search. Column widths still use reference MDW=7 rather than actual Excel font metrics, so real workbook visual verification is necessary. No Excel COM validation performed.
- Existing browser test verifies actual image endpoint status/MIME/bytes, then supplies those bytes via Playwright routing to Chromium; direct browser-to-image-endpoint transport is not independently tested in this case.

Report-only commit changes no production or test code.
