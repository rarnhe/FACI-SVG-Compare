# Test Report

- UTC (final CI report upload): 2026-11-28 01:23:16
- Overall result: **PASS**
- Previous PR head: `3e305455c147a7af6d71a65f5c8ee2cdd9280bfb`
- Verified commit: `5c204984a0aa75ecd51fc0818f1bd47b20904e7f`
- Workflow: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46092764632

## Dual-track certification

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 140/140 (3.483s) | 50/50 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 140/140 (4.794s) | 50/50 | 2/2 | PASS | PASS |

Both jobs passed and generated/uploaded test_report.md.

- Ubuntu report: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46092764632/artifacts/15240959253
- Windows report: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46092764632/artifacts/15242265788

## First run and correction

First run https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46092684699 failed on Ubuntu: old static source assertion still required top-left-derived group positioning, and browser X correction assertion rejected 0.4 EMU of integer marker quantization. Test-only commit `5c204984a0aa75ecd51fc0818f1bd47b20904e7f` updates the source assertion and bounds the independent expected center comparison by half an EMU times the appropriate normalization and world scale. Exact browser placement is then checked against the explicit manifest center. No production changes in the second commit.

## Scope and limitations

- Replace conditional X cross-check and prior normalized Y start-edge placement with a single diagonal midpoint in both axes for all two-cell drawing objects when picture calibration is available. Use per-sheet picture left/right and top/bottom span factors. No per-object span agreement gate. Keep DrawingML width, height and rotation independent of anchor span. Circle diameter remains the saved rectangle diagonal.
- Single-cell anchors use normalized start plus half physical anchor extent (saved extent fallback). Absolute anchors use direct position plus half extent, with prior saved picture Y relative mapping where available. Picture origin remains unchanged. Missing/reversed markers or unavailable picture calibration retain the prior axis position and record the source/reason; cannot guarantee a true Excel center in these fallback cases.
- The new center_emu is authoritative in parser, image-relative manifest, Three.js placement, validation/collision and SVG spatial selection; bounds and corner diagnostics are derived. Older synthetic manifests lacking center retain box midpoint compatibility.
- Reference column metrics still assume MDW=7 rather than measured Excel font, default width estimate when omitted; row metrics use saved point heights. Affine normalization cannot guarantee Excel-exact coordinates for arbitrary local metric errors. Real workbook / Excel COM verification not performed.
- Browser fixture has independent expected positions and intentionally differing anchor spans in both axes, stale saved positions, distinct per-sheet factors, rotated shapes, center and size assertions, and actual paired SVG selection. As before, browser tests check real image endpoint status/MIME/bytes and supply verified bytes via Playwright routing to Chromium; direct browser-to-image-endpoint transport is not independently covered.

This checked-in summary reflects verified CI logs and uploaded artifact metadata. The report-only commit changes no production or test code.
