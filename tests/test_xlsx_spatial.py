"""Regression fixtures for XLSX DrawingML geometry; no external workbook required."""

from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
spatial = import_module(f"{ROOT.name}.xlsx_spatial")

W = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
P = "http://schemas.openxmlformats.org/package/2006/relationships"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def marker(tag, col, row, col_off=0, row_off=0):
    return (f"<xdr:{tag}><xdr:col>{col}</xdr:col><xdr:colOff>{col_off}</xdr:colOff>"
            f"<xdr:row>{row}</xdr:row><xdr:rowOff>{row_off}</xdr:rowOff></xdr:{tag}>")


def image(name="图片12"):
    return (f'<xdr:pic><xdr:nvPicPr><xdr:cNvPr id="2" name="{name}"/>'
            f'</xdr:nvPicPr><xdr:blipFill/><xdr:spPr/></xdr:pic>')


def shape(name="矩形14", rot=0, fill=True):
    color = '<a:solidFill><a:schemeClr val="accent1"/></a:solidFill>' if fill else '<a:noFill/>'
    return (f'<xdr:sp><xdr:nvSpPr><xdr:cNvPr id="3" name="{name}"/></xdr:nvSpPr>'
            f'<xdr:spPr><a:xfrm rot="{rot}"/>{color}'
            '<a:ln><a:solidFill><a:srgbClr val="5B9BD5"/></a:solidFill></a:ln>'
            '</xdr:spPr><xdr:txBody><a:p><a:r><a:rPr>'
            '<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>'
            '</a:rPr></a:r></a:p></xdr:txBody></xdr:sp>')


def two_cell(child=None):
    if child is None:
        child = image()
    return (f'<xdr:twoCellAnchor>{marker("from", 1, 1, 95250, 19050)}'
            f'{marker("to", 2, 2, 47625, 95250)}{child}'
            '</xdr:twoCellAnchor>')


def one_cell(child=None):
    if child is None:
        child = shape()
    return (f'<xdr:oneCellAnchor>{marker("from", 0, 0)}'
            f'<xdr:ext cx="190500" cy="285750"/>{child}'
            '</xdr:oneCellAnchor>')


def absolute(child=None):
    if child is None:
        child = shape(name="矩形16")
    return (f'<xdr:absoluteAnchor><xdr:pos x="95250" y="190500"/>'
            f'<xdr:ext cx="190500" cy="285750"/>{child}'
            '</xdr:absoluteAnchor>')


def fixture(path: Path, anchors: str | None = None, worksheet_xml: str | None = None,
            draw: bool = True) -> Path:
    if anchors is None:
        anchors = two_cell() + one_cell() + absolute()
    if worksheet_xml is None:
        worksheet_xml = ('<sheetFormatPr defaultRowHeight="15" defaultColWidth="8.43"/>'
                         '<cols><col min="1" max="1" width="10"/>'
                         '<col min="2" max="2" width="20"/></cols>'
                         '<sheetData><row r="1" ht="30"/></sheetData>')
    worksheet_xml += ('<drawing r:id="rId2"/>' if draw else '')
    with ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml",
                   f'<workbook xmlns="{W}" xmlns:r="{R}"><sheets>'
                   '<sheet name="Sheet1" sheetId="1" r:id="rId1"/>'
                   '</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   f'<Relationships xmlns="{P}"><Relationship Id="rId1" '
                   f'Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml",
                   f'<worksheet xmlns="{W}" xmlns:r="{R}">{worksheet_xml}</worksheet>')
        if draw:
            z.writestr("xl/worksheets/_rels/sheet1.xml.rels",
                       f'<Relationships xmlns="{P}"><Relationship Id="rId2" '
                       f'Type="{REL}/drawing" Target="../drawings/drawing1.xml"/></Relationships>')
            z.writestr("xl/drawings/drawing1.xml",
                       f'<xdr:wsDr xmlns:xdr="{XDR}" xmlns:a="{A}">{anchors}</xdr:wsDr>')
        z.writestr("xl/theme/theme1.xml",
                   f'<a:theme xmlns:a="{A}"><a:themeElements><a:clrScheme name="Office">'
                   '<a:accent1><a:srgbClr val="5B9BD5"/></a:accent1>'
                   '</a:clrScheme></a:themeElements></a:theme>')
    return path


class TestWorkbookDiscovery(unittest.TestCase):
    def test_empty_assets_directory_is_allowed(self):
        with TemporaryDirectory() as tmp:
            self.assertIsNone(spatial.select_assets_xlsx(tmp))
            self.assertEqual(spatial.load_assets_spatial_report(tmp), (None, []))

    def test_ignores_excel_temp_files(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ("~$luoD.xlsx", ".~lock.xlsx", ".hidden.xlsx"):
                (folder / name).write_bytes(b"ignored")
            real = fixture(folder / "luoD.xlsx")
            self.assertEqual(spatial.select_assets_xlsx(tmp), real)

    def test_multiple_xlsx_files_is_an_error(self):
        with TemporaryDirectory() as tmp:
            for name in ("luoD.xlsx", "other.XLSX"):
                (Path(tmp) / name).write_bytes(b"dummy")
            with self.assertRaisesRegex(spatial.SpatialXlsxError, "multiple XLSX"):
                spatial.select_assets_xlsx(tmp)


class TestGeometry(unittest.TestCase):
    def parse(self, anchors=None, worksheet_xml=None, draw=True):
        with TemporaryDirectory() as tmp:
            path = fixture(Path(tmp) / "luoD.xlsx", anchors, worksheet_xml, draw)
            return spatial.parse_xlsx(path)

    def test_exact_from_to_with_pixel_offsets(self):
        sheet = self.parse()[0]
        self.assertEqual(sheet["sheet"], "Sheet1")
        self.assertEqual(len(sheet["objects"]), 3)
        pic, shape1, shape2 = sheet["objects"]
        self.assertEqual((pic["type"], pic["name"]), ("image", "图片12"))
        self.assertEqual(pic["vertices_px"], [
            {"x": 85, "y": 42}, {"x": 225, "y": 42},
            {"x": 225, "y": 70}, {"x": 85, "y": 70},
        ])
        self.assertEqual((pic["width_px"], pic["height_px"]), (140, 28))
        self.assertEqual(shape1["vertices_px"], [
            {"x": 0, "y": 0}, {"x": 20, "y": 0},
            {"x": 20, "y": 30}, {"x": 0, "y": 30},
        ])
        self.assertEqual(shape2["vertices_px"][0], {"x": 10, "y": 20})

    def test_theme_color_and_text_color(self):
        colors = self.parse()[0]["objects"][1]["colors"]
        self.assertEqual(colors, {
            "fill": "#5B9BD5", "outline": "#5B9BD5", "text": "#FFFFFF"
        })

    def test_explicit_no_fill(self):
        self.assertEqual(
            self.parse(one_cell(shape(fill=False)))[0]["objects"][0]["colors"]["fill"],
            "无/透明",
        )

    def test_rotation_is_applied_to_corners(self):
        item = self.parse(one_cell(shape(rot=90 * 60000)))[0]["objects"][0]
        self.assertEqual(item["rotation_degrees"], 90)
        self.assertEqual(item["vertices_px"], [
            {"x": 25, "y": 5}, {"x": 25, "y": 25},
            {"x": -5, "y": 25}, {"x": -5, "y": 5},
        ])

    def test_hidden_columns_and_row_heights(self):
        sheet = ('<sheetFormatPr defaultRowHeight="15" defaultColWidth="8.43"/>'
                 '<cols><col min="1" max="1" hidden="1"/></cols>'
                 '<sheetData><row r="1" ht="40"/><row r="2" hidden="1"/></sheetData>')
        pic = self.parse(two_cell(), worksheet_xml=sheet)[0]["objects"][0]
        self.assertEqual(pic["vertices_px"][0]["x"], 10)
        self.assertAlmostEqual(pic["vertices_px"][0]["y"], 55.333, places=3)

    def test_emu_preserves_geometry(self):
        item = self.parse(one_cell())[0]["objects"][0]
        self.assertEqual(item["bounds_emu"], {
            "x": 0, "y": 0, "width": 190500, "height": 285750
        })
        self.assertEqual(spatial.EMUS_PER_MM, 360000)

    def test_worksheet_without_drawing(self):
        self.assertEqual(self.parse(draw=False), [{"sheet": "Sheet1", "objects": []}])

    def test_rejects_invalid_xlsx(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.xlsx"
            path.write_bytes(b"not zip")
            with self.assertRaises(spatial.SpatialXlsxError):
                spatial.parse_xlsx(path)

    def test_console_output_has_four_corners(self):
        with TemporaryDirectory() as tmp:
            book = fixture(Path(tmp) / "luoD.xlsx")
            output = spatial.format_spatial_report(book, spatial.parse_xlsx(book))
        for item in ("A1", "左上: (85.000, 42.000)", "右下: (225.000, 70.000)",
                     "矩形14", "#5B9BD5"):
            with self.subTest(item=item):
                self.assertIn(item, output)

    def test_invalid_relationship_escape_is_rejected(self):
        with self.assertRaises(spatial.SpatialXlsxError):
            spatial.resolve_part("xl/workbook.xml", "../../../outside")
