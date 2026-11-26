# Test Report

- UTC: 2026-11-26 01:24:32
- Result: **PASS**
- Tests: **76 per environment**
- Passed: 76
- Failures: 0
- Errors: 0
- Skipped: 0

## Dual-track verification

| Platform | Python | Result | Unittest cases | Duration |
| --- | --- | --- | ---: | ---: |
| Ubuntu (ubuntu-latest) | 3.12 | **PASS** | 76/76 | 3.208s |
| Windows (windows-latest) | 3.14 | **PASS** | 76/76 | 4.325s |

- GitHub Actions: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45735475924
- CI additionally checks JavaScript module syntax and Node CAD geometry calculations on both platforms.
- Both platforms execute `python tests/run_tests.py`; the runner produces `test_report.md` whether tests pass or fail and the workflow uploads its report artifact.

## Fixed issue: JavaScript module MIME types

The Windows HTTP static handler previously returned `text/plain` for
`/viewer/cad_geometry.mjs`. Strict browser ES-module MIME checking prevented
`cad_viewer.js` from evaluating, so neither the CAD images nor the SVG
load callbacks could run.

The `NoCacheIndexHandler.set_extra_headers()` method now explicitly returns
`Content-Type: text/javascript; charset=utf-8` for both `.js` and `.mjs`.

The new **real HTTP** regression tests passed independently on both platforms:

- `test_javascript_modules_have_browser_accepted_mime_type`: GET
  `/viewer/cad_viewer.js` and `/viewer/cad_geometry.mjs`; verify 200,
  JavaScript MIME, UTF-8 encoding, cache-control, revision header and source.
- `test_html_still_has_html_mime_type`: GET `/viewer/index.html`;
  verify the HTML content type remains `text/html`.

## Scope and limitations

No existing CAD interaction, geometry, XLSX parsing, SVG layout or frontend
logic was changed by this fix. The user's actual SVG and XLSX assets were not
available to CI. Automated tests confirm the MIME response and existing test
contracts; actual Chrome WebGL rendering still requires local visual
verification after stopping the previous server and starting the revised code.
