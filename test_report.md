# Test Report

- UTC: 2026-11-25 11:43:06
- Result: **PASS**
- Python tests: **62 per environment**
- Node geometry tests: **6 per environment**
- Failures: 0
- Errors: 0
- Skipped: 0

## Dual-track GitHub Actions

| Environment | Python unittest | Node geometry | Result |
| --- | --- | --- | --- |
| Ubuntu / Python 3.12 | 62/62 | 6/6 | PASS |
| Windows / Python 3.14 | 62/62 | 6/6 | PASS |

- Successful CI: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45606917575
- JavaScript module syntax checked independently.
- `python tests/run_tests.py` generates test_report.md for Python tests on both platforms; `node --test tests/test_cad_geometry.mjs` directly verifies the browser-shared geometry functions. Workflow gate fails if either suite fails.

## Verified functionality

- Excel image-origin alignment, two-sheet and single-image constraints
- Textbox/ellipse/rectangle shape classification, drawing, and raycast wiring
- Rectangle height suffix `_x<ratio>` = width × ratio; `_y<ratio>` = height × ratio
- Final underscore directive required; unsupported/invalid suffix returns zero height
- Raised ellipses using rotated rectangle footprint containment; overlapping roofs choose the highest Z
- Existing dual CAD cameras, reset, SVG splitters, aspect-preserving SVG sizing, Bokeh and HTTP endpoints

## Boundaries

Real `luoD.xlsx` and SVG assets are not present in CI. The visual correctness of the
3D model and selected ellipse overlays needs browser testing with actual files.
