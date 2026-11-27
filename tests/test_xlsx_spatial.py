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
            draw: bool = True, media: bool = False, sheet_count: int = 1,
            second_anchors: str | None = None) -> Path:
    if anchors is None:
        anchors = two_cell() + one_cell() + absolute()
    if second_anchors is None:
        second_anchors = (f'<xdr:oneCellAnchor>{marker("from", 4, 5, 238125, 47625)}'
                          f'<xdr:ext cx="952500" cy="476250"/>{image("Subfab底图")}'
                          '</xdr:oneCellAnchor>')
    if worksheet_xml is None:
        worksheet_xml = ('<sheetFormatPr defaultRowHeight="15" defaultColWidth="8.43"/>'
                         '<cols><col min="1" max="1" width="10"/>'
                         '<col min="2" max="2" width="20"/></cols>'
                         '<sheetData><row r="1" ht="30"/></sheetData>')
    parts = [(i, anchors if i == 1 else second_anchors if i == 2
              else two_cell(image("Extra"))) for i in range(1, sheet_count + 1)]
    with ZipFile(path, "w") as z:
        sheets_text = "".join(
            f'<sheet name="Sheet{i}" sheetId="{i}" r:id="rId{i}"/>'
            for i, _ in parts
        )
        z.writestr("xl/workbook.xml",
                   f'<workbook xmlns="{W}" xmlns:r="{R}"><sheets>'
                   f'{sheets_text}</sheets></workbook>')
        workbook_links = "".join(
            f'<Relationship Id="rId{i}" Type="{REL}/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>'
            for i, _ in parts
        )
        z.writestr("xl/_rels/workbook.xml.rels",
                   f'<Relationships xmlns="{P}">{workbook_links}</Relationships>')
        for i, drawing_objects in parts:
            sheet_xml = worksheet_xml + ('<drawing r:id="rId2"/>' if draw else '')
            z.writestr(f"xl/worksheets/sheet{i}.xml",
                       f'<worksheet xmlns="{W}" xmlns:r="{R}">{sheet_xml}</worksheet>')
            if not draw:
                continue
            z.writestr(f"xl/worksheets/_rels/sheet{i}.xml.rels",
                       f'<Relationships xmlns="{P}"><Relationship Id="rId2" '
                       f'Type="{REL}/drawing" Target="../drawings/drawing{i}.xml"/>'
                       '</Relationships>')
            if media:
                drawing_objects = drawing_objects.replace(
                    "<xdr:blipFill/>",
                    '<xdr:blipFill><a:blip r:embed="rId3"/></xdr:blipFill>',
                )
            z.writestr(f"xl/drawings/drawing{i}.xml",
                       f'<xdr:wsDr xmlns:xdr="{XDR}" xmlns:a="{A}" xmlns:r="{R}">'
                       f'{drawing_objects}</xdr:wsDr>')
            if media:
                z.writestr(f"xl/drawings/_rels/drawing{i}.xml.rels",
                           f'<Relationships xmlns="{P}"><Relationship Id="rId3" '
                           f'Type="{REL}/image" Target="../media/image1.png"/>'
                           '</Relationships>')
        if media:
            z.writestr("xl/media/image1.png", b"\x89PNG\r\n\x1a\nfixture")
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

    def test_two_sheet_single_picture_workbook_is_valid(self):
        with TemporaryDirectory() as tmp:
            path=fixture(Path(tmp) / "valid.xlsx",sheet_count=2,
                         anchors=two_cell()+one_cell(shape()))
            book,sheets=spatial.load_assets_spatial_report(tmp)
        self.assertEqual(book,path)
        self.assertEqual(len(sheets),2)
        self.assertEqual([sum(obj["type"]=="image" for obj in x["objects"])
                          for x in sheets],[1,1])

    def test_sheet_count_rejects_one_and_three(self):
        for count in (1,3):
            with self.subTest(count=count),TemporaryDirectory() as tmp:
                fixture(Path(tmp) / "book.xlsx",sheet_count=count)
                with self.assertRaisesRegex(spatial.SpatialXlsxError,"exactly 2 sheets"):
                    spatial.load_assets_spatial_report(tmp)

    def test_image_count_rejects_zero_and_two(self):
        for objects,reason in ((one_cell(shape()),"found 0"),
                               (two_cell(image())+one_cell(image("Extra")),"found 2")):
            with self.subTest(reason=reason),TemporaryDirectory() as tmp:
                fixture(Path(tmp) / "book.xlsx",anchors=objects,sheet_count=2)
                with self.assertRaisesRegex(spatial.SpatialXlsxError,reason):
                    spatial.load_assets_spatial_report(tmp)

    def test_shape_preset_and_textbox_classification(self):
        ellipse=shape(name="检测").replace(
            '<a:xfrm rot="0"/>',
            '<a:xfrm rot="0"/><a:prstGeom prst="ellipse"/>')
        textbox=shape(name="测试框").replace(
            '</xdr:nvSpPr>',
            '<xdr:cNvSpPr txBox="1"/></xdr:nvSpPr>')
        with TemporaryDirectory() as tmp:
            book=fixture(Path(tmp) / "types.xlsx",
                         anchors=one_cell(ellipse)+one_cell(textbox)+one_cell(shape()))
            kinds=[obj["shape_kind"] for obj in spatial.parse_xlsx(book)[0]["objects"]]
        self.assertEqual(kinds,["ellipse","textbox","rectangle"])



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

    def test_theme_colors_and_textbox_styles_are_separate(self):
        colors = self.parse()[0]["objects"][1]["colors"]
        self.assertEqual(colors, {
            "fill": "#5B9BD5", "outline": "#5B9BD5"
        })
        self.assertNotIn("text", colors)
        textbox=shape(name="文本框15").replace(
            '</xdr:nvSpPr>','<xdr:cNvSpPr txBox="1"/></xdr:nvSpPr>')
        obj=self.parse(one_cell(textbox))[0]["objects"][0]
        self.assertIn("text_layout",obj)
        self.assertEqual(obj["colors"]["outline"],"#5B9BD5")

    def test_explicit_no_fill(self):
        self.assertEqual(
            self.parse(one_cell(shape(fill=False)))[0]["objects"][0]["colors"]["fill"],
            "无/透明",
        )

    def test_textbox_uses_explicit_run_font_size_color_and_layout_position(self):
        import xml.sax.saxutils
        textbox = shape(name="文本框B1").replace(
            '</xdr:nvSpPr>',
            '<xdr:cNvSpPr txBox="1"/></xdr:nvSpPr>')
        original='<xdr:txBody><a:p><a:r><a:rPr>'
        start=textbox.index("<xdr:txBody>")
        end=textbox.index("</xdr:txBody>",start)+len("</xdr:txBody>")
        styled=(
            '<xdr:txBody>'
            '<a:bodyPr lIns="19050" rIns="38100" '
            'tIns="28575" bIns="47625" anchor="ctr"/>'
            '<a:p><a:pPr algn="ctr"><a:defRPr sz="1200">'
            '<a:latin typeface="Arial"/></a:defRPr></a:pPr>'
            '<a:r><a:rPr sz="1650" b="1">'
            '<a:solidFill><a:srgbClr val="112233"/></a:solidFill>'
            '<a:latin typeface="Aptos"/><a:ea typeface="Microsoft YaHei"/>'
            '</a:rPr><a:t>深度B1</a:t></a:r>'
            '<a:r><a:rPr sz="1400" i="1">'
            '<a:solidFill><a:schemeClr val="accent1"/></a:solidFill>'
            '</a:rPr><a:t> +Y</a:t></a:r></a:p>'
            '<a:p><a:pPr algn="r"><a:defRPr sz="900"/></a:pPr>'
            '<a:r><a:rPr/><a:t>第二行</a:t></a:r></a:p>'
            '</xdr:txBody>')
        textbox=textbox[:start]+styled+textbox[end:]
        item=self.parse(one_cell(textbox))[0]["objects"][0]
        self.assertEqual(item["shape_kind"],"textbox")
        self.assertEqual(item["text"],"深度B1 +Y\n第二行")
        layout=item["text_layout"]
        self.assertEqual(layout["anchor"],"middle")
        self.assertEqual(layout["insets_px"],{
            "left":2,"right":4,"top":3,"bottom":5,
        })
        self.assertEqual([p["align"] for p in layout["paragraphs"]],
                         ["center","right"])
        first,second=layout["paragraphs"][0]["runs"]
        self.assertEqual(first["font_family"],"Aptos")
        self.assertEqual(first["east_asian_font"],"Microsoft YaHei")
        self.assertEqual(first["font_size_pt"],16.5)
        self.assertEqual(first["color"],"#112233")
        self.assertTrue(first["bold"])
        self.assertFalse(first["italic"])
        self.assertEqual(second["font_family"],"Arial")
        self.assertEqual(second["font_size_pt"],14)
        self.assertEqual(second["color"],"#5B9BD5")
        self.assertTrue(second["italic"])
        self.assertEqual(layout["paragraphs"][1]["runs"][0]["font_size_pt"],9)
        self.assertEqual(item["colors"]["outline"],"#5B9BD5")

    def test_textbox_default_style_and_line_break_are_preserved(self):
        textbox=shape(name="文本框19").replace(
            '</xdr:nvSpPr>',
            '<xdr:cNvSpPr txBox="1"/></xdr:nvSpPr>')
        start=textbox.index("<xdr:txBody>")
        end=textbox.index("</xdr:txBody>",start)+len("</xdr:txBody>")
        styled=(
            '<xdr:txBody><a:bodyPr anchor="b"/>'
            '<a:p><a:r><a:rPr sz="2400">'
            '<a:solidFill><a:srgbClr val="DD00AA"/></a:solidFill></a:rPr>'
            '<a:t>上</a:t></a:r><a:br/><a:r><a:rPr/>'
            '<a:t>下</a:t></a:r></a:p></xdr:txBody>')
        textbox=textbox[:start]+styled+textbox[end:]
        item=self.parse(one_cell(textbox))[0]["objects"][0]
        layout=item["text_layout"]
        self.assertEqual(layout["anchor"],"bottom")
        self.assertEqual(layout["insets_px"],{
            "left":9.6,"right":9.6,"top":4.8,"bottom":4.8,
        })
        runs=layout["paragraphs"][0]["runs"]
        self.assertEqual([run["text"] for run in runs],["上","\n","下"])
        self.assertEqual(runs[0]["color"],"#DD00AA")
        self.assertEqual(runs[0]["font_size_pt"],24)
        self.assertEqual(runs[2]["font_size_pt"],11)

    def test_theme_font_scheme_and_font_reference_defaults(self):
        from xml.etree import ElementTree as ET
        theme = (
            '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:themeElements><a:fontScheme name="Custom">'
            '<a:majorFont><a:latin typeface="Aptos Display"/>'
            '<a:ea typeface="Microsoft YaHei"/></a:majorFont>'
            '<a:minorFont><a:latin typeface="Aptos"/>'
            '<a:ea typeface="SimSun"/></a:minorFont>'
            '</a:fontScheme></a:themeElements></a:theme>')
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"fonts.zip"
            with ZipFile(path,"w") as output:
                output.writestr("xl/theme/theme1.xml",theme)
            with ZipFile(path) as archive:
                theme_fonts=spatial.theme_text_fonts(archive)
        self.assertEqual(theme_fonts["major"],
                         {"latin":"Aptos Display","ea":"Microsoft YaHei"})
        self.assertEqual(theme_fonts["minor"],
                         {"latin":"Aptos","ea":"SimSun"})
        element=ET.fromstring(
            f'<xdr:sp xmlns:xdr="{XDR}" xmlns:a="{A}">'
            '<xdr:style><a:fontRef idx="major">'
            '<a:schemeClr val="accent1"/></a:fontRef></xdr:style>'
            '<xdr:txBody><a:bodyPr/><a:p><a:r><a:rPr sz="1800"/>'
            '<a:t>TEST</a:t></a:r></a:p></xdr:txBody></xdr:sp>')
        layout=spatial.textbox_text_layout(element,
            {"accent1":"5B9BD5"},theme_fonts)
        run=layout["paragraphs"][0]["runs"][0]
        self.assertEqual(run["font_family"],"Aptos Display")
        self.assertEqual(run["east_asian_font"],"Microsoft YaHei")
        self.assertEqual(run["font_size_pt"],18)
        self.assertEqual(run["color"],"#5B9BD5")

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


    def test_textbox_no_outline_from_drawingml_is_not_recolored(self):
        original=shape(name="文本框10").replace(
            '<a:ln><a:solidFill><a:srgbClr val="5B9BD5"/></a:solidFill></a:ln>',
            '<a:ln><a:noFill/></a:ln>',
        )
        obj=self.parse(one_cell(original))[0]["objects"][0]
        self.assertEqual(obj["shape_kind"],"textbox")
        self.assertEqual(obj["colors"]["outline"],"无/透明")

    def test_alt_text_title_description_are_extracted_and_cleaned(self):
        marked = shape(name="矩形14").replace(
            'name="矩形14"/>',
            'name="矩形14" descr="_x000D_z=0.5x_x000D_" title="z=0.2y"/>',
        )
        sheet=self.parse(one_cell(marked))[0]
        obj=sheet["objects"][0]
        self.assertEqual(obj["alt_text"],{
            "description":"z=0.5x", "title":"z=0.2y",
        })
        self.assertNotEqual(obj["text"],"z=0.5x")

    def test_empty_alt_text_remains_separate_from_visible_shape_label(self):
        obj=self.parse(one_cell(shape(name="矩形B1_x0.5")))[0]["objects"][0]
        self.assertEqual(obj["alt_text"],{"description":"","title":""})
        self.assertEqual(obj["name"],"矩形B1_x0.5")

    def test_console_report_lists_alt_text_without_losing_shape_text(self):
        marked=shape(name="矩形14").replace(
            'name="矩形14"/>','name="矩形14" descr="z=0.5x" title="Z高度"/>')
        with TemporaryDirectory() as tmp:
            book=fixture(Path(tmp)/"alt.xlsx",anchors=one_cell(marked))
            report=spatial.format_spatial_report(book,spatial.parse_xlsx(book))
        self.assertIn("替换文字: [标题: Z高度] z=0.5x",report)

    def test_shape_text_is_kept(self):
        rich_shape = shape(name="文本标注").replace(
            "</a:r></a:p>", "<a:t>压差 A-01</a:t></a:r></a:p>"
        )
        item = self.parse(one_cell(rich_shape))[0]["objects"][0]
        self.assertEqual(item["text"], "压差 A-01")

    def test_shape_text_is_visible_in_terminal_report(self):
        rich_shape = shape(name="仪表").replace(
            "</a:r></a:p>", "<a:t>PSD 单位</a:t></a:r></a:p>"
        )
        with TemporaryDirectory() as tmp:
            path = fixture(Path(tmp) / "labels.xlsx", anchors=one_cell(rich_shape))
            output = spatial.format_spatial_report(path, spatial.parse_xlsx(path))
        self.assertIn("文字: PSD 单位", output)

    def test_media_relationship_is_resolved(self):
        with TemporaryDirectory() as tmp:
            path = fixture(Path(tmp) / "with-media.xlsx", media=True)
            sheets = spatial.parse_xlsx(path)
        self.assertEqual(sheets[0]["objects"][0]["image_part"], "xl/media/image1.png")

    def test_invalid_relationship_escape_is_rejected(self):
        with self.assertRaises(spatial.SpatialXlsxError):
            spatial.resolve_part("xl/workbook.xml", "../../../outside")
