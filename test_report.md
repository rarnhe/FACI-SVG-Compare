# Test Report

- UTC: 2026-11-26 08:43:37
- Result: **PASS**
- Python unittest: **101 / 101 per environment**
- Node CAD geometry / UI tests: **26 / 26 per environment**
- Failures: 0
- Errors: 0

## GitHub Actions + report dual-track verification

| Environment | Python unittest | Node geometry/UI | JavaScript syntax | Result |
| --- | --- | --- | --- | --- |
| Ubuntu / Python 3.12 | **101/101** (4.202s) | **26/26** | PASS | **PASS** |
| Windows / Python 3.14 | **101/101** (4.282s) | **26/26** | PASS | **PASS** |

- Verified commit: `b6c1ed6db81d9fef32e497081200b86fb9e6c75f`.
- Successful Actions: https://github.com/rarnhe/OneThreeOctave-SVG-Compare/actions/runs/45785503605
- Both platforms run `python tests/run_tests.py` and the Node CAD
  geometry/UI tests; JavaScript syntax is checked separately. The Python
  runner writes its `test_report.md` on success/failure and Actions uploads
  the report artifact even when a test fails.

## Features and regression tests

1. **Removed** the XLSX DrawingML font-size extraction function and the
   `text_layout` field. Three.js no longer receives or interprets Excel
   font sizes; it uses the established fixed texture font for shape text.
2. Both CAD layer hover captions now contain only the containing textbox,
   rectangle, and sensor: **BODYv2**·20260704_SCN_B1·测点名称. The textbox
   segment is rendered using an actual `strong` element. Neither XLSX name
   nor worksheet name is shown. Textboxes are hoverable but cannot be
   selected with a mouse click.
3. The floating legend has bold 14px text, no leading swatch/icons. New
   overlays follow the approved 17-color palette in sequence, and the
   PSD and 1-3-Octave files for one entry get the exact same color.
4. The per-entry context menu has **颜色 / 线宽 / 线型 / 退出**.
   Color opens the 17 specified choices; width offers
   0.75/1.5/2.25/3/3.75; line style offers -· (dash-dot) and -- (dash).
   Secondary choices are vertically stacked beside the parent menu.
5. **Real local persistence:** the Bokeh/Tornado `cad-svg-style` POST
   handler recomputes the catalog from the chosen XLSX ellipse. The
   server checks the source sheet/shape indices, time, axis, allowed
   palette, width and dash options. Only the matched two local SVGs are
   updated. It uses temp-file replacement and paired rollback if an
   update fails. Tests create temporary real SVG files and assert the
   resulting XML on disk for both PSD and octave files.
6. Source SVG elements without an explicit paint continue to be
   transparent; explicit `none` is preserved. The browser cache is
   bypassed when an updated SVG is reloaded.
7. SVG fit is computed **independently for the upper and lower panes**.
   Each takes the largest width satisfying both available pane width
   and available height at its own intrinsic aspect ratio. Height wins
   when width-based scaling would overflow. All overlays are considered
   for bounds. There is no forced common pixel width across both panes.
8. Existing MIME, HTTP, Bokeh, XLSX alt-text cuboid height, dynamic date
   lookup, CAD camera synchronization and secure private-XLSX tests
   are still green.

## Limitations

The user's actual XLSX, PSD and octave SVG assets are not present in
the GitHub repository. CI covers synthetic XLSX fixtures, real temporary
SVG file edits, Node UI/geometry calculations, and HTTP endpoint
validation, but not Chrome visual rendering with the private inputs.
A local visual check is still needed. Files in `assets/` are written
in place by the new styling controls; back up the originals if their
initial formatting must be recoverable.
