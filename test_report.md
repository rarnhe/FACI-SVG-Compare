# Test Report

- UTC (final CI report upload): 2026-11-27 12:30:03
- Overall result: **PASS**
- Verified commit: `d85c9539c6d1aeb022d9a20909a64af71c2eb0a9`
- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45998864553

## Dual-track certification

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 131/131 (4.704s) | 49/49 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 131/131 (5.992s) | 49/49 | 2/2 | PASS | PASS |

Both jobs succeeded on the final attempt and generated/uploaded test_report.md. Zero failures/errors in the final attempt.

- Ubuntu report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45998864553/artifacts/15197695887
- Windows report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45998864553/artifacts/15196798161

## Vertical-only geometry reconciliation

- Preserve strict saved drawing_rect extraction, X, width, height, rotation, worldRectFromEmu uniform scaling, and all appearance and SVG search logic. No column width/font estimation.
- Explicit worksheet row heights in points are converted to EMU (12700 per point); sparse overrides include hidden rows and zeroHeight. Check row and rowOff anchors for all objects including pictures. Accept a two-cell span matching saved height or rotated outer height within 1 reference pixel; rotated outer span uses its center to recover unrotated Y. Accept one-cell direct extent matching saved height. Absolute anchors are untouched. Missing/inconsistent row metadata retains saved DrawingML Y. Report raw/resolved Y, source and reason, no arbitrary Y scaling.
- Regression covers stale independent Y offsets for images, textboxes, rectangles and ellipses, unchanged X and size, row height/hidden rows, rotated bounds, missing and conflicting row data, column independence, absolute and one-cell anchors, and relative origin subtraction. The real XLSX browser fixture now contains deliberately stale object-specific Y offsets and independently correct row markers. Both browsers verify exact centers, dimensions, rotation and existing right-click SVG pairing.
- Initial run 45998701078 failed an over-broad new assertion that forbade the pre-existing zero-origin guard reading col/colOff markers; test corrected to forbid actual column width metric access. Ubuntu also failed the decoded-background assertion in that run and attempt 1 of 45998864553; the PNG payloads were independently verified for chunk CRC and decoding. Windows passed on the corrected commit; Ubuntu rerun of the same commit passed without skipping or weakening browser assertions. The intermittent background failure remains unexplained.
- Actual user's workbook is not available. The Y mismatch is a hypothesis reproduced by a constructed XLSX, not confirmed as the cause of the user's visual defect. If row span is inconsistent, the parser deliberately retains saved geometry and emits a diagnostic instead of guessing.
- PR #3 is closed; the fix applies to the open PR #4 containing the preceding implementation.

This checked-in summary reflects verified CI logs and uploaded artifact metadata. The report-only commit does not change production or test code.
