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
shapes = import_module(f"{ROOT.name}.tests.test_xlsx_spatial")
fixture = shapes.fixture


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
            fixture(assets / "luoD.xlsx", sheet_count=2,
                    anchors=shapes.two_cell()+shapes.one_cell(shapes.shape()))
            report = self.run_entrypoint(assets)
        self.assertIn("Three.js + Bokeh viewer:", report)
        self.assertIn("[Sheet: Sheet1] 图片 1，形状 1", report)
        self.assertIn("左上: (80.000, 42.000)", report)
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

    def test_one_sheet_rejected_before_server(self):
        with TemporaryDirectory() as tmp:
            assets=Path(tmp)/"assets"
            assets.mkdir()
            fixture(assets/"book.xlsx",sheet_count=1)
            with (patch.object(app,"STATIC_DIR",Path(tmp)),
                  patch.object(app,"Server") as server,
                  patch.object(app,"open_viewer") as browser):
                with self.assertRaisesRegex(SystemExit,"exactly 2 sheets"):
                    app.main()
                server.assert_not_called()
                browser.assert_not_called()

    def test_two_images_in_sheet_rejected_before_server(self):
        shapes=__import__("importlib").import_module(
            f"{ROOT.name}.tests.test_xlsx_spatial"
        )
        with TemporaryDirectory() as tmp:
            assets=Path(tmp)/"assets"
            assets.mkdir()
            fixture(assets/"book.xlsx",sheet_count=2,
                    anchors=shapes.two_cell()+shapes.one_cell(shapes.image("extra")))
            with (patch.object(app,"STATIC_DIR",Path(tmp)),
                  patch.object(app,"Server") as server,
                  patch.object(app,"open_viewer") as browser):
                with self.assertRaisesRegex(SystemExit,"exactly 1 image"):
                    app.main()
                server.assert_not_called()
                browser.assert_not_called()

    def test_overlapping_rotated_rectangles_block_startup(self):
        shapes=__import__("importlib").import_module(f"{ROOT.name}.tests.test_xlsx_spatial")
        emu=9525
        def anchored(x,y,w,h,shape_xml):
            return (f'<xdr:absoluteAnchor><xdr:pos x="{x*emu}" y="{y*emu}"/>'
                    f'<xdr:ext cx="{w*emu}" cy="{h*emu}"/>'
                    f'{shape_xml}</xdr:absoluteAnchor>')
        a=shapes.shape(name="矩形设备A").replace('rot="0"','rot="1800000"')
        b=shapes.shape(name="矩形设备B").replace('rot="0"','rot="-1800000"')
        anchors=(shapes.two_cell()+
                 anchored(0,0,100,70,a)+anchored(55,10,100,70,b))
        with TemporaryDirectory() as tmp:
            assets=Path(tmp)/"assets"
            assets.mkdir()
            fixture(assets/"book.xlsx",sheet_count=2,anchors=anchors)
            with (patch.object(app,"STATIC_DIR",Path(tmp)),
                  patch.object(app,"Server") as server,
                  patch.object(app,"open_viewer") as browser):
                with self.assertRaisesRegex(SystemExit,"overlapping rectangles"):
                    app.main()
                server.assert_not_called()
                browser.assert_not_called()

    def test_reconstructed_circle_hitting_two_disjoint_rectangles_blocks_startup(self):
        shapes=__import__("importlib").import_module(f"{ROOT.name}.tests.test_xlsx_spatial")
        emu=9525
        def anchored(x,y,w,h,shape_xml):
            return (f'<xdr:absoluteAnchor><xdr:pos x="{x*emu}" y="{y*emu}"/>'
                    f'<xdr:ext cx="{w*emu}" cy="{h*emu}"/>'
                    f'{shape_xml}</xdr:absoluteAnchor>')
        anchors=(shapes.two_cell()+
                 anchored(0,0,100,80,shapes.shape(name="矩形Left"))+
                 anchored(140,0,100,80,shapes.shape(name="矩形Right"))+
                 anchored(100,40,40,40,shapes.shape(name="椭圆Spanning")))
        with TemporaryDirectory() as tmp:
            assets=Path(tmp)/"assets"
            assets.mkdir()
            fixture(assets/"book.xlsx",sheet_count=2,anchors=anchors)
            with (patch.object(app,"STATIC_DIR",Path(tmp)),
                  patch.object(app,"Server") as server,
                  patch.object(app,"open_viewer") as browser):
                with self.assertRaisesRegex(SystemExit,"intersects 2 rectangles"):
                    app.main()
                server.assert_not_called()
                browser.assert_not_called()
