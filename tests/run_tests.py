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
        "Restored DrawingML rich textbox font family, size, color and theme font references, paragraph alignment, body insets and textbox CanvasTexture rendering, plus theme aliases, phClr and line style inheritance, distinct absent/unresolved outlines and exact XLSX RGB borders without synthetic contrast colors. Cuboids now use 93%/100% solid-face opacity with matching rectangle-colored EdgesGeometry outlines. PNG CAD backgrounds, saved DrawingML X and extents, independent authoritative row-anchor Y for cell anchors and direct absolute anchors, no column metrics or xfrm Y fallback, contextual fail-fast on missing geometry, one exact EMU-to-world transform for all shapes and uniform XY scaling, shared rectangle overlap catalog/validation, rectangle visible-text search, unchanged non-geometric attributes, SVG overlays use seven named colors, widths 2/2.5/3/3.5/4 with original default, four line styles, proportional octave point scaling and shared planar outline rendering for blank-alt rectangles and ellipses; paired overlays, original restoration, curve targeting, shape selection, security and HTTP regressions are covered.",
        "Browser/WebGL regression includes real generated XLSX with missing/malformed/stale DrawingML Y, mismatched end spans, inconsistent column markers and hidden rows/columns, production parser/manifest HTTP input and checks decoded raster versus XLSX display aspect, exact shape widths/heights, rotated corners, square projection, depth and text texture geometry, real image HTTP/decode with a single injected transient failure, actual right-click inside/partial/outside catalog-to-SVG overlays and preserved original fill and opacity. Private workbook visual verification remains necessary.",
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
