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
        "XLSX alternative-text z=height parsing; native-picture-aspect synchronized CAD; sheet-colored textbox; mouse-hover breadcrumbs; dynamic timestamp SVG catalogs with validated pairs; right-opening X/Y/Z menu; draggable SVG history; constrained splitters; legacy Bokeh/HTTP/MIME and CAD math regressions.",
        "Browser/WebGL visual behavior requires manual verification.",
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
