"""Run the same unittest suite locally and on CI; always write test_report.md."""

from datetime import datetime, timezone
from pathlib import Path
import sys
import time
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "test_report.md"


def format_report(result, seconds, exception=None):
    count = result.testsRun if result else 0
    failures = len(result.failures) if result else 0
    errors = len(result.errors) if result else 0
    skips = len(result.skipped) if result else 0
    ok = bool(result and result.wasSuccessful() and count > 0 and exception is None)
    lines = [
        "# Test Report",
        "",
        f"- UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Result: **{'PASS' if ok else 'FAIL'}**",
        f"- Tests: {count}",
        f"- Passed: {count - failures - errors - skips}",
        f"- Failures: {failures}",
        f"- Errors: {errors}",
        f"- Skipped: {skips}",
        f"- Duration: {seconds:.2f}s",
        "",
        "## Scope",
        "",
        "Restored DrawingML rich textbox font family, size, color and theme font references, paragraph alignment, body insets and textbox CanvasTexture rendering, plus theme aliases, phClr and line style inheritance, distinct absent/unresolved outlines and exact XLSX RGB borders without synthetic contrast colors. Cuboids now use 93%/100% solid-face opacity with matching rectangle-colored EdgesGeometry outlines. PNG CAD backgrounds, saved DrawingML X and extents, per-sheet picture dual-anchor normalized row-anchor Y, exact rational position mapping with preserved extents, absolute-anchor relative mapping, unavailable calibration diagnostics and raw crop metadata, no column metrics or xfrm Y fallback, contextual fail-fast on missing geometry, one exact EMU-to-world transform for all shapes and uniform XY scaling, shared rectangle overlap catalog/validation, rectangle visible-text search, unchanged non-geometric attributes, SVG overlays cycle seven colors with solid width 2 defaults, independent original-style restoration, bounded submenus and exact or strictly preceding <60s CSV matching, widths 2/2.5/3/3.5/4 with original default, four line styles, proportional octave point scaling and shared planar outline rendering for blank-alt rectangles and ellipses; paired overlays, original restoration, curve targeting, shape selection, security and HTTP regressions are covered.",
        "CAD zoom regression: independent shared user zoom and layout fit, relative OrbitControls bounds, dynamic DPR and CSS zoom render ratio, coalesced resize and bounded textbox texture refresh. Chromium CDP tests combined viewport/DPR changes and alternating CAD wheel input; native browser chrome zoom remains a manual check.",
        "CAD axis menu regression: compact X/Y/Z checkboxes, reversible overlay and legend selection, primary-menu side anchoring with selected date row and first axis row center alignment, exact 14-digit XLSX ellipse alt-text descriptions with hyphens removed, synchronized XLSX timestamps, missing-note prompt and obsolete dated-line removal, compact date/axis widths, identical 13px font and 28px row heights in both menus, minimum 150px explanation with content-measured expansion at fixed equal height, opaque panel and Escape dismissal.",
        "Browser/WebGL regression includes real generated XLSX with missing/malformed/stale DrawingML Y, different independent picture calibration factors 1.25/0.8, mismatched end spans, inconsistent column markers and hidden rows/columns, production parser/manifest HTTP input and byte-exact real image endpoint extraction (browser uses the verified HTTP response bytes) and checks decoded raster versus XLSX display aspect, exact shape widths/heights, rotated corners, square projection, depth and text texture geometry, actual right-click inside/partial/outside catalog-to-SVG overlays and preserved original fill and opacity. Private workbook visual verification remains necessary.",
        "",
    ]
    if exception is not None:
        lines += ["## Runner exception", "", "```text", str(exception), "```", ""]
    if result and (result.failures or result.errors):
        lines += ["## Failures / errors", ""]
        for case, info in result.failures + result.errors:
            lines += [f"### {case.id()}", "", "```text", info.rstrip(), "```", ""]
    return "\n".join(lines) + "\n", ok


def main():
    # Windows redirected stdout/stderr can use a legacy code page. Preserve
    # Unicode failure details and keep the runner/report alive on that host.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    started = time.monotonic()
    result, error = None, None
    try:
        suite = unittest.defaultTestLoader.discover(
            start_dir=str(ROOT / "tests"), pattern="test_*.py", top_level_dir=str(ROOT)
        )
        result = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
    except Exception:
        error = traceback.format_exc()
        print(error, file=sys.stderr)
    report, ok = format_report(result, time.monotonic() - started, error)
    REPORT.write_text(report, encoding="utf-8")
    print(f"Wrote {REPORT}: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
