# Test Report

- Overall result: **PASS**
- Previous PR head: `2c61b85e49a555866b19a5bfe8924e40634859b5`
- Verified commit: `31f9e0ff65b041ad2d01fe1e005c548931cc84d7`
- Workflow: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46128496234

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 140/140 | 53/53 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 140/140 | 53/53 | 2/2 | PASS | PASS |

Both jobs passed on the first run and uploaded their generated reports.

- Ubuntu: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46128496234/artifacts/15256169683
- Windows: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46128496234/artifacts/15256344151

## Scope and limitations

- Capture wheel before OrbitControls. Ordinary CAD wheel retains synchronized camera zoom; left-button wheel anywhere in the page uses root CSS zoom (50–200%, normalized wheel delta), prevents native scrolling and CAD dolly, and clears pending CAD click selection. Ctrl/Meta wheel bypasses CAD interception without preventDefault, leaving browser default behavior.
- CSS zoom is application-level, not the browser's native zoom setting. Responsive CAD resize can adjust camera fit scale as the viewport changes. Menus, floating legend drag and main splitter convert screen coordinates back to CSS layout units.
- Unit test covers zoom direction, line delta normalization and clamps. Chromium integration uses synthetic WheelEvent dispatch with buttons/modifier flags in actual WebGL viewer, verifies ordinary linked camera zoom, page zoom in all three regions, viewport fit and uncanceled modifier wheel, then restores zoom for prior pixel assertions. This does not verify physical mouse-button/wheel delivery, native browser zoom UI, or all menu/drag interactions at nondefault zoom. Local visual validation is necessary.
- No changes to XLSX extraction, geometry reconstruction, SVG/CSV matching or style semantics. Existing browser image regression verifies endpoint bytes and routes those bytes into Chromium; direct browser-to-image-endpoint transport remains separately unverified.
- Report-only commit changes no production or test code.
