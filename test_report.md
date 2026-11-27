# Test Report

- UTC (CI log completion): 2026-11-27 08:56:42
- Overall result: **PASS**
- Verified functional commit: `68331f5422b1c267b67d7ba02f28fd0cbbef8daf`
- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45969517542

## GitHub Actions and test_report.md dual-track verification

| Platform | Python unittest | Node geometry/UI | Module syntax | Result |
| --- | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 109/109 (3.256s) | 43/43 | PASS | **PASS** |
| Windows / Python 3.14 | 109/109 (5.533s) | 43/43 | PASS | **PASS** |

- Failures: 0; errors: 0.
- Both GitHub Actions jobs completed successfully. The runner independently generated `test_report.md: PASS` on both platforms and uploaded the artifacts.
- Ubuntu job: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45969517542/job/140406218791
- Windows job: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45969517542/job/140406219197
- Ubuntu report artifact: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45969517542/artifacts/15183339572
- Windows report artifact: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45969517542/artifacts/15184790529

## Scope

- Legend: 17 colors, six line-style choices including original, seven preset widths plus original, exit; independent style per selection, applied to both PSD and octave SVGs.
- Browser-only restyling from immutable original SVG text; paired Blob replacement and release, no server write route or modification of assets.
- Four new Node tests cover independent style validation/restoration, inherited/CSS stroke recognition, protected auxiliary/definition nodes, style overrides and unmarked open-path fallback.
- Existing Python integration assertions now require line width/type menus and per-entry style state; all previous XLSX/Three.js/HTTP regressions passed.
- Legend remains 14px bold colored text. Menu choices use text labels and selected checkmarks.
- SVG detection is heuristic for unmarked plots, supports common CSS selectors and inheritance, and rejects line-width/type changes if no curve can be identified. Legacy color-only fallback remains available for such SVGs.
- Actual user SVG and workbook resources are absent; visual verification in a browser remains necessary, particularly for complex CSS, unusual curve encoding and plot auxiliary elements.
- Existing Actions emitted a Node.js 20 deprecation warning on Windows; all steps nevertheless succeeded. Workflow versions were not changed by this feature.

This report summarizes verified CI logs and artifact metadata; report-only commit does not change the functional code.
