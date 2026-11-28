# Test Report

- Overall result: **PASS**
- Base commit: `a2b8670565ccff7b317782f4a081157c78add9e2`
- Verified commit: `e956640269d9cfc2eada34a655df55af21024550`
- Workflow: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46101823248

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 138/138 | 51/51 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 138/138 | 51/51 | 2/2 | PASS | PASS |

Both jobs passed on the first run and uploaded generated reports.

- Ubuntu: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46101823248/artifacts/15245836064
- Windows: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46101823248/artifacts/15246320637

## Scope and limitations

- Rename legend exit to close; only remove selected paired overlay.
- Preserve original SVG markup on initial load; null color is distinct from the gray legend presentation. Width/dash changes do not implicitly recolor. Explicit color choice remains available.
- Clamp nested menus on both axes, permit negative relative offsets, use bounded scrollable popup. Unit tests cover edge geometry; browser regression checks actual submenu bounds.
- Catalog CSV list uses same folder, literal identifier token boundary, exact timestamp and axis as selected paired SVG; exclude symlinks and non-files; case-insensitive suffix, stable filename sort. Client downloads each matching file via read-only fetch and temporary Blob URL, using original filename; no writes to assets. List reflects catalog at selection time. Browser controls actual destination and may prompt/block automatic multiple downloads; app cannot force Downloads folder. Browser test verifies two downloads and filenames, not physical OS Downloads directory.
- No CAD geometry changes; based on main, not unmerged PR #5.
- Existing browser image regression verifies real endpoint bytes and supplies them via Playwright routing; direct browser-to-image-endpoint transport is not independently covered. Private workbook visual verification remains necessary.

Report-only commit changes no production or test code.
