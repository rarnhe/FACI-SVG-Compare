# Test Report

- UTC (final CI report upload): 2026-11-28 01:05:21
- Overall result: **PASS**
- Base commit: `a2b8670565ccff7b317782f4a081157c78add9e2`
- Verified commit: `d45c6d4f5442b5af8d51794e148f6b055f5ff12a`
- Workflow: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46091224889

## Dual-track certification

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 140/140 (3.595s) | 49/49 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 140/140 (5.510s) | 49/49 | 2/2 | PASS | PASS |

Both jobs passed on the first run and generated/uploaded test_report.md.

- Ubuntu report: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46091224889/artifacts/15241720750
- Windows report: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46091224889/artifacts/15241615645

## Scope and limitations

- Conditional horizontal cross-check for textbox, rectangle and ellipse only. Derive per-sheet factor from the unrotated picture two-cell horizontal span and saved width. Independently compute left and right candidate unrotated X, then use their midpoint only if disagreement is at most 9525 EMU (one 96-DPI reference pixel). This is an engineering tolerance, not an Excel specification. No fixed translation compensation.
- Retain saved X for conflicting, missing, or ambiguous anchors, non-target shapes, absolute/one-cell anchors and picture origin. Rotation outer-bound interpretation requires unique span match; extents unchanged. Recompute vertices from final X and prior Y; no Three.js, SVG, styling or Y algorithm changes.
- OOXML reference column metrics use assumed MDW=7 (Calibri 11/96 DPI), not actual measured workbook font. Default baseColWidth plus 5px padding is estimated when defaultColWidth is absent. Supports hidden columns and column ranges; invalid metrics do not affect Y.
- Diagnostic fields include saved X, left/right anchor and candidate positions, midpoint, discrepancy, calibration factor, decision and correction.
- Tests cover all target kinds, stale X, conflicting span fallback, missing endpoints, absolute anchors, rotated outer-bound correction, invalid column metrics, independent sheet factors and true browser geometry/SVG integration. No private workbook or Excel COM verification; agreement of endpoints is a width consistency check, not independent proof that the absolute position is correct. Nonlinear metric errors can remain.
- As in base commit, browser tests verify actual image endpoint status/MIME/bytes, then supply verified bytes via Playwright routing to real Chromium. Direct browser-to-image-endpoint transport is not independently covered by this case.

This checked-in summary reflects verified CI logs and uploaded artifact metadata. The report-only commit does not change production or test code.
