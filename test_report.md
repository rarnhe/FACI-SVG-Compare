# Test Report

- UTC (CI report upload): 2026-11-27 09:55:38
- Overall result: **PASS**
- Verified functional and browser-test commit: `9c45c8308eb2a393353963747f58e699ae4d361c`
- Workflow: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45977656182

## GitHub Actions + test_report.md dual-track certification

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JavaScript syntax | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Ubuntu / Python 3.12 | 110/110 (3.392s) | 47/47 | 1/1 | PASS | **PASS** |
| Windows / Python 3.14 | 110/110 (4.185s) | 47/47 | 1/1 | PASS | **PASS** |

- Failures: 0; errors: 0 in the final run.
- Both workflow jobs succeeded, generated and uploaded `test_report.md: PASS`.
- Ubuntu job: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45977656182/job/140433333613
- Windows job: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45977656182/job/140433333304
- Ubuntu report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45977656182/artifacts/15186899828
- Windows report: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45977656182/artifacts/15188335954

## Changes and regression coverage

- Removed original line-type menu item and widths 6/7; four explicit line types and original/3/4/5 widths remain. Initial SVG line style remains unchanged until explicitly selected.
- Octave marker scale = selected stroke width / median original data-line stroke width (SVG default 1); circles, ellipses, polygons, closed paths and referenced point instances scale about their centers. Original width resets both marker dimensions and line width without accumulation. Explicit user-space marker viewports are scaled, while strokeWidth markers already follow the stroke. Auxiliary points are excluded.
- Replaced screen-line addon rendering with independent cylinder InstancedMesh outlines for every cuboid, flat rectangle and reconstructed circle. Retains DrawingML outline color and width policy; contrast halo, disabled outline frustum culling and camera-zoom compensation improve visibility. Textbox borderless setting, picking, elevation and 93%/100% cuboid opacity remain unchanged.
- New Node tests cover independent segment buffers and point-size ratios. Updated menu and wiring assertions.
- New real browser test runs in both hosted environments with locally installed Three.js 0.160.0 and Playwright driving runner Chrome with software WebGL. Synthetic fixture contains 2 cuboids, 2 flat rectangles and 1 circle per sheet. Asserts 12/4/72 segments and independent foreground/halo meshes; samples actual rendered edge pixels of all 10 objects in top and tilted views (20 checks per platform); checks circle, use and closed path marker dimensions, centers, reset and unchanged auxiliary-point size. No external CAD files are needed.
- First run 45977513553 failed on Ubuntu during Playwright's Chromium download because that pinned Playwright version did not support ubuntu26.04-x64. Windows passed the browser test. The follow-up commit uses preinstalled runner Chrome; the final run passes both platforms, with the browser check required by the workflow gate, not skipped.
- Actual private XLSX/SVG files are not in the repository. The original report of only the first cuboid border appearing was not directly reproduced; synthetic real-browser checks verify the new implementation, while exact appearance on the real workbook and uncommon SVG point structures still require local visual verification.

This checked-in report summarizes verified CI job logs and uploaded report artifact metadata. The report-only commit does not change functional code.
