# Test Report

- Overall result: **PASS**
- Previous PR head: `bcc056c72094047637c8a68e0fc2ef0e100af3a0`
- Verified commit: `59566cfc09342531bcbc8b69c670aa3dbd1632fd`
- Workflow: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46126763030

| Platform | Python unittest | Node geometry/UI | Real Chrome/WebGL | JS syntax | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | 140/140 | 52/52 | 2/2 | PASS | PASS |
| Windows / Python 3.14 | 140/140 | 52/52 | 2/2 | PASS | PASS |

Both jobs passed on the first run and uploaded their generated reports.

- Ubuntu: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46126763030/artifacts/15255304525
- Windows: https://github.com/rarnhe/FACI-SVG-Compare/actions/runs/46126763030/artifacts/15255768161

## Scope and limitations

- Format the left CAD date menu as YYYY/MM/DD HH:mm:ss; append YYYY/MM/DD_HH:mm:ss to the existing legend name. String-only presentation formatting, no timezone conversion. Nonconforming input is displayed unchanged.
- Preserve raw 14-digit timestamp in menu data attribute, event closure, SVG catalog keys, overlay identity and CSV lookup. No changes to the geometry, search or download implementation.
- Browser regression checks actual formatted menu and legend text, raw menu timestamp, existing paired SVG searches, exact and PSD-to-Time companion CSV downloads, white original-color legend, and existing style restoration. Unit tests cover zero padding, separators, year-end and invalid-format fallback.
- This final run also covers the prior PR head's companion CSV filter and white legend changes. Browser download destination remains user-configured; physical OS Downloads directory and private workbook visual verification are not tested. Existing image regression verifies actual HTTP bytes and supplies those bytes via Playwright routing; direct browser-to-image-endpoint transport is not independently covered.
- Report-only commit changes no production or test code.
