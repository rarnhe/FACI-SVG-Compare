"""Entry-point tests: XLSX reporting is synchronous with Bokeh startup."""

from contextlib import redirect_stdout
from importlib import import_module
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
app = import_module(f"{ROOT.name}.__main__")
fixture = import_module(f"{ROOT.name}.tests.test_xlsx_spatial").fixture


class TestStartupWithXlsx(TestCase):
    def run_entrypoint(self, assets: Path):
        captured = StringIO()
        with (patch.object(app, "STATIC_DIR", assets.parent),
              patch.object(app, "Server") as mocked_server,
              patch.object(app, "open_viewer") as mocked_browser,
              redirect_stdout(captured)):
            app.main()
        mocked_server.assert_called_once()
        mocked_server.return_value.start.assert_called_once()
        mocked_browser.assert_called_once()
        return captured.getvalue()

    def test_one_xlsx_prints_coordinates_and_url(self):
        with TemporaryDirectory() as tmp:
            assets = Path(tmp) / "assets"
            assets.mkdir()
            fixture(assets / "luoD.xlsx")
            report = self.run_entrypoint(assets)
        self.assertIn("Three.js + Bokeh viewer:", report)
        self.assertIn("[Sheet: Sheet1] 图片 1，形状 2", report)
        self.assertIn("左上: (85.000, 42.000)", report)
        self.assertIn("矩形14", report)

    def test_without_xlsx_bokeh_still_starts(self):
        with TemporaryDirectory() as tmp:
            assets = Path(tmp) / "assets"
            assets.mkdir()
            self.assertIn("未发现 .xlsx", self.run_entrypoint(assets))

    def test_multiple_xlsx_fails_before_browser_or_server(self):
        with TemporaryDirectory() as tmp:
            assets = Path(tmp) / "assets"
            assets.mkdir()
            fixture(assets / "luoD.xlsx")
            fixture(assets / "other.xlsx")
            with (patch.object(app, "STATIC_DIR", Path(tmp)),
                  patch.object(app, "Server") as server,
                  patch.object(app, "open_viewer") as browser):
                with self.assertRaises(SystemExit) as error:
                    app.main()
                self.assertIn("multiple XLSX", str(error.exception))
                server.assert_not_called()
                browser.assert_not_called()
