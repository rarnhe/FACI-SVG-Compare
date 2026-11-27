# Test Report

- UTC (final CI report upload): 2026-11-27 13:30:39
- Overall result: **PASS**
- Base commit: `4c366975a9736066ed1178e34a76c9b3417b56bc`
- Verified commit: `b18ae345d3b3327fc57daa014932fdacfac6bb30`
- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/46007574399

## Dual-track certification

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 137/137 (3.498s) | 49/49 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 137/137 (4.044s) | 49/49 | 2/2 | PASS | PASS |

Both jobs passed on the first run and generated/uploaded test_report.md.

- Ubuntu report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/46007574399/artifacts/15202338061
- Windows report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/46007574399/artifacts/15201613545

## P0 scope and limitations

- Per-sheet picture dual-anchor Y normalization uses exact rational H/(A1-A0) and applies it to row-anchor positions relative to the picture. Only Y translation changes; X, saved extents, rotation, uniform scale, Three.js, styling and SVG pair search are preserved.
- Independent synthetic workbook factors 1.25 and 0.8, missing/malformed/stale saved Y, hidden/custom rows, mismatched shape spans, rotated outer bounds, absolute-anchor mapping, unavailable calibration and raw srcRect diagnostics are tested. Rotation outer-bound recognition uses calibrated span without scaling the saved dimensions.
- An absolute-anchor shape has no row markers, so it uses its saved Y relative to the saved picture Y. If a picture lacks a valid independent two-cell span, is rotated, or the sheet has absolute anchors but lacks saved picture Y, retain the prior geometry for the entire sheet and report why calibration is unavailable. Invalid required row geometry retains existing contextual failure behavior.
- Crop attributes are diagnostic only; no texture crop is applied. The affine calibration cannot guarantee correction of nonuniform row-height errors or inaccurate saved picture height. Real workbook visual verification remains necessary.
- As in the base commit, browser tests verify actual image endpoint HTTP status/MIME and exact PNG bytes, then supply those bytes via Playwright routing to real Chromium. Direct browser-to-image-endpoint transport is not independently covered by this case. Earlier intermittent background loading failure remains unexplained.

This checked-in summary reflects verified CI logs and uploaded artifact metadata. The report-only commit does not change production or test code.
