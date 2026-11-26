# Test Report

- UTC: 2026-11-26 12:13:36
- Overall result: **PASS**
- Python unittest cases: **99 / 99 per platform**
- Node CAD geometry / UI tests: **30 / 30 per platform**
- Failures: **0**
- Errors: **0**

## GitHub Actions and test_report.md dual-track verification

| Environment | Python unittest | Node geometry/UI | JavaScript module syntax | Result |
| --- | ---: | ---: | --- | --- |
| Ubuntu / Python 3.12 | **99/99** (3.232s) | **30/30** | PASS | **PASS** |
| Windows / Python 3.14 | **99/99** (4.304s) | **30/30** | PASS | **PASS** |

- Verified functional commit: `54d5b469701c534dffa7738764df3afaf4502f56`.
- Successful GitHub Actions run:
  https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45817579092
- `.github/workflows/test.yml` executes `python tests/run_tests.py`,
  Node CAD geometry/UI tests and a separate JavaScript syntax check
  on both operating systems. The Python runner writes
  `test_report.md` for both success and failure; GitHub Actions uploads
  a platform-specific report artifact even on failure.

## Implemented and verified changes

1. **Strict SVG date discovery for a rectangle-contained ellipse.**
   First identify the containing textbox and search
   `assets/<textbox text>/*.svg`. A timestamp matching
   `_(\\d{14})_` is added to the first-level menu ONLY if the **same
   filename** also matches the containing rectangle's visible text,
   with literal token boundaries. Deduplicate and sort dates ascending;
   unrelated filenames and similarly named neighboring rectangles
   cannot contribute dates.
2. **Ellipse outside rectangles but inside a textbox.**
   If no rectangle fully contains the reconstructed circle, the
   same folder search requires the ellipse's visible text and the
   timestamp in the same SVG filename. An ellipse partially crossing a
   rectangle boundary also follows this non-contained case. The
   second-level X/Y/Z menu is displayed vertically, opening to the
   right with a left fallback when the viewport edge is near.
3. **Exact legend name and separate internal identity.**
   Display format: `<textbox>_<sheet>_<rectangle-or-ellipse>_+<axis>`,
   e.g. `BODYv2_fab_20260704_SCN_B1_+Y` or
   `BODYv2_subfab_Other_+Z`. The filename timestamp is intentionally
   omitted from the visible legend text; the internal unique key
   includes it so that different timepoints cannot overwrite each
   other's color, SVG overlay, or close button behavior.
4. **Visible translucent cuboid geometry instead of wireframe.**
   Positive-height rectangles now use an actual
   `THREE.BoxGeometry` with solid faces and a transparent
   `MeshBasicMaterial` at **0.23** opacity, `FrontSide`,
   `wireframe:false`, `depthTest:true` and
   `depthWrite:false`. Removed the bright `EdgesGeometry`
   line overlay responsible for the wireframe appearance. On mouse
   selection the cuboid remains translucent (0.30 opacity) rather
   than jumping to 0.95 opacity. Elevated ellipse shapes render
   above translucent roofs to remain visible when rotating.
5. Previous camera synchronization, XLSX alternative-text height
   rules, textbox hover information, embedded image aspect scaling,
   right-side SVG independent fitting, 17-color browser-only SVG
   recoloring, private XLSX protection, read-only asset behavior
   and HTTP/MIME regressions all remain green.

## Limitations

The user's actual XLSX, PSD and octave SVG assets are not in the
repository. CI uses temporary SVG folders and synthetic XLSX shapes
to exercise the exact time/identifier constraints, plus Node UI and
geometry tests. Chrome WebGL transparency and overlay appearance with
the user's real drawings still require local visual confirmation.
