# Test Report

- UTC (final CI report upload): 2026-11-27 12:46:42
- Overall result: **PASS**
- Verified commit: `0533a41a9fb1cd4278a06d479e7ed9f89f7b8224`
- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/46001276144

## Dual-track certification

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 133/133 (4.367s) | 49/49 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 133/133 (5.737s) | 49/49 | 2/2 | PASS | PASS |

Both jobs succeeded in the final workflow and generated/uploaded test_report.md.

- Ubuntu report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/46001276144/artifacts/15197594185
- Windows report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/46001276144/artifacts/15197923447

## Independent Y algorithm

- Remove drawing_rect and vertical_rect. saved_horizontal_geometry reads X and original dimensions from saved EMU; anchor_y independently resolves Y from the cell anchor start row and rowOff plus saved worksheet row heights, with no dependency on xfrm/off@y. Absolute anchors use their direct pos@y. No column width or font metric estimation.
- Mismatched or unavailable end span does not cause fallback to old Y. A uniquely matching rotated outer span is converted to the unrotated top using its center; otherwise start marker is authoritative. Missing necessary start-row metadata fails contextually. Zero X is accepted independently of Y; old coupled zero-offset guard removed.
- Background, textboxes, rectangles and ellipses share this algorithm; original width, height, rotation, uniform world transform, styling and SVG search remain unchanged.
- Tests cover absent/malformed/stale off@y, incompatible anchor spans, missing row data, hidden rows, custom heights, zeroHeight, one-cell/absolute/rotated anchors, identical relative picture origins, exact WebGL positions and original SVG pair selection.
- Initial workflow 46000426061: Python/Node passed, Windows passed browser checks, but Ubuntu repeatedly failed the decoded-background assertion. Experimental image loader retry in commit 3bb3cca and injected HTTP 503 test (run 46000999616) failed on both platforms; the production loader change was reverted. Final test separately verifies the real production image HTTP endpoint status, MIME type and byte-for-byte XLSX PNG extraction, then uses those exact response bytes via Playwright route fulfillment for real Chromium decoding/rendering. Thus direct browser-to-image-endpoint transport is not covered by that final browser case; earlier intermittent transport/render failure remains unexplained. No geometry assertion was removed.
- The actual user's XLSX is unavailable, so local visual confirmation remains necessary.

This checked-in summary reflects verified CI logs and uploaded artifact metadata. The report-only commit does not change production or test code.
