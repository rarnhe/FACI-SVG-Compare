# Test Report

- Overall result: **PASS**
- Previous PR head: `c764aa07c542f37b1ff3e8c3c247afa2544f781e`
- Verified commit: `14a1bd79f8172f9efaf322d23669c93e0b0c6a58`
- Workflow: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46116939158

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 139/139 | 51/51 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 139/139 | 51/51 | 2/2 | PASS | PASS |

Both jobs passed on the first run and uploaded generated reports.

- Ubuntu: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46116939158/artifacts/15251977986
- Windows: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46116939158/artifacts/15251832213

## Scope and limitations

- SVG exact timestamp matching unchanged. CSV matches the same folder, literal identifier and axis, with independent 14-digit timestamp regex and real calendar datetime comparison: 0 <= selected_time - CSV_time < 60 seconds. Exclude future, exactly 60 seconds, invalid dates and longer digit sequences. Multiple timestamps per filename use closest qualifying time; download each file once. All matches ordered exact first, then increasing elapsed seconds, then filename.
- Initial overlay colors cycle through seven colors; defaults are solid line and width 2. Three final submenu items restore original color, dash and width independently, using null in the style state. Original color maps to gray legend; full restoration uses unchanged cached source. Existing bounded submenu positioning and close behavior retained.
- Browser regression checks initial palette sequence, default selection states, independent original-style restoration, exact and 59-second-earlier downloads, and close behavior. Unit tests cover midnight/year rollover and strict boundary conditions.
- CSV catalog is captured at selection time; browser controls download destination and may prompt for multiple downloads. Actual physical Downloads directory was not tested. Original files remain read-only.
- No CAD geometry changes. Prior browser image regression checks real endpoint bytes then supplies verified bytes through Playwright routing; direct browser-to-image-endpoint transport is not independently covered. Private workbook and SVG visual validation remains necessary.

Report-only commit changes no production or test code.
