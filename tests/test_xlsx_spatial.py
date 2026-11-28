"""Regression fixtures for XLSX DrawingML geometry; no external workbook required."""

from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import re
import unittest
from unittest.mock import patch
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


def with_saved_geometry(child, x, y, w, h):
    """Fixtures explicitly store independent absolute EMU coordinates."""
    transform=(f'<a:off x="{x*9525}" y="{y*9525}"/>'
               f'<a:ext cx="{w*9525}" cy="{h*9525}"/>')
    if "<a:xfrm" not in child:
        return child.replace("<xdr:spPr/>",
                             f"<xdr:spPr><a:xfrm>{transform}</a:xfrm></xdr:spPr>")
    return re.sub(r'<a:xfrm([^>]*)/>',lambda match:
                  f'<a:xfrm{match.group(1)}>{transform}</a:xfrm>',child,count=1)


def two_cell(child=None, *, start_y=42, end_y=70, start_x=None, end_x=None):
    if child is None:
        child = image()
    child=with_saved_geometry(child,80,42,135,28)
    # Independent fixture row markers: first row 40px, others 20px.
    def row_marker(tag, col, col_off, y):
        row, offset = (0,y) if y < 40 else (1+(y-40)//20,(y-40)%20)
        return marker(tag,col,row,col_off,offset*9525)
    def col_marker(x):
        if x < 70:
            return 0, x*9525
        if x < 210:
            return 1, (x-70)*9525
        c,d=divmod(x-210,59)
        return c+2,d*9525
    c0,d0=(1,95250) if start_x is None else col_marker(start_x)
    c1,d1=(2,47625) if end_x is None else col_marker(end_x)
    return (f'<xdr:twoCellAnchor>{row_marker("from", c0, d0, start_y)}'
            f'{row_marker("to", c1, d1, end_y)}{child}'
            '</xdr:twoCellAnchor>')


def one_cell(child=None):
    if child is None:
        child = shape()
    child=with_saved_geometry(child,0,0,20,30)
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
            second_anchors: str | None = None, theme_xml: str | None = None) -> Path:
    if anchors is None:
        anchors = two_cell() + one_cell() + absolute()
    if second_anchors is None:
        second_anchors = (f'<xdr:oneCellAnchor>{marker("from", 4, 5, 238125, 47625)}'
                          f'<xdr:ext cx="952500" cy="476250"/>'
                          f'{with_saved_geometry(image("Subfab底图"),353,125,100,50)}'
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
        z.writestr("xl/theme/theme1.xml", theme_xml or (
                   f'<a:theme xmlns:a="{A}"><a:themeElements><a:clrScheme name="Office">'
                   '<a:accent1><a:srgbClr val="5B9BD5"/></a:accent1>'
                   '</a:clrScheme></a:themeElements></a:theme>'))

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

    def test_exact_saved_x_and_row_anchor_y(self):
        sheet = self.parse()[0]
        self.assertEqual(sheet["sheet"], "Sheet1")
        self.assertEqual(len(sheet["objects"]), 3)
        pic, shape1, shape2 = sheet["objects"]
        self.assertEqual((pic["type"], pic["name"]), ("image", "图片12"))
        self.assertEqual(pic["vertices_px"], [
            {"x": 80, "y": 42}, {"x": 215, "y": 42},
            {"x": 215, "y": 70}, {"x": 80, "y": 70},
        ])
        self.assertEqual((pic["width_px"], pic["height_px"]), (135, 28))
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

    def test_inconsistent_row_span_never_falls_back_to_saved_y(self):
        sheet = ('<sheetFormatPr defaultRowHeight="71" defaultColWidth="42"/>'
                 '<cols><col min="1" max="3" hidden="1"/></cols>'
                 '<sheetData><row r="1" ht="40"/><row r="2" hidden="1"/></sheetData>')
        actual = self.parse(two_cell(),worksheet_xml=sheet)[0]["objects"][0]
        expected = self.parse(two_cell())[0]["objects"][0]
        self.assertEqual(actual["bounds_emu"], {**expected["bounds_emu"],"y":round((40*12700)+2*9525)})
        self.assertEqual(actual["vertical_geometry"]["source"],"picture_top_left")
        self.assertNotIn("center_emu",actual)

    def test_invalid_column_metrics_leave_y_unchanged(self):
        sheet='<sheetFormatPr defaultRowHeight="15" defaultColWidth="not-a-number"/><cols><col min="invalid" max="invalid" width="invalid"/></cols><sheetData><row r="1" ht="30"/></sheetData>'
        before=self.parse()[0]["objects"]
        after=self.parse(worksheet_xml=sheet)[0]["objects"]
        self.assertEqual([o["bounds_emu"] for o in after],[o["bounds_emu"] for o in before])
        self.assertEqual([o["vertical_geometry"] for o in after],[o["vertical_geometry"] for o in before])
        self.assertTrue(all(o["horizontal_geometry"]["calibration_status"]=="retained" for o in after))

    def test_horizontal_column_metrics_reference_and_hidden(self):
        root=spatial.ET.fromstring('<worksheet><sheetFormatPr defaultColWidth="10"/><cols><col min="1" max="2" width="20"/><col min="3" max="4" hidden="1"/></cols></worksheet>')
        m=spatial.HorizontalColumnMetrics(root)
        self.assertEqual(m.prefix[:6],[v*9525 for v in (0,140,280,280,280,350)])
        self.assertEqual(m.width_pixels("8.43"),59)
        self.assertEqual(m.marker_x(spatial.ET.fromstring('<from><col>4</col><colOff>9525</colOff></from>')),281*9525)

    def test_normalized_top_left_all_target_kinds_and_conflicting_span(self):
        # 56px columns, picture raw horizontal span 240px, saved width 300px.
        # All shapes have stale X; even a conflicting span uses only the start marker.
        sheet='<sheetFormatPr defaultRowHeight="15" defaultColWidth="8"/><sheetData/>'
        def anchored(child,x,y,w,h,left,right):
            child=with_saved_geometry(child,x,y,w,h)
            def mark(tag,px,py):
                c,dx=divmod(round(px*9525),56*9525)
                r,dy=divmod(py,20)
                return marker(tag,c,r,dx,dy*9525)
            return '<xdr:twoCellAnchor>'+mark("from",left,y)+mark("to",right,y+h)+child+'</xdr:twoCellAnchor>'
        pic=anchored(image("P"),80,40,300,200,40,280)
        box=shape("文本框")
        rect=shape("矩形")
        ellipse=shape("椭圆")
        raw=pic+anchored(box,103,60,20,30,56,72)+anchored(rect,183,80,40,20,120,152)+anchored(ellipse,283,100,12,12,200,209.6)+anchored(shape("矩形冲突"),299,120,40,20,200,250)
        objs=self.parse(raw,worksheet_xml=sheet)[0]["objects"]
        self.assertEqual([o["bounds_emu"]["x"] for o in objs],[v*9525 for v in (80,100,180,280,280)])
        self.assertEqual([o["bounds_emu"]["y"] for o in objs],[v*9525 for v in (40,60,80,100,120)])
        self.assertEqual([o["width_px"] for o in objs],[300,20,40,12,40])
        self.assertEqual([o["horizontal_geometry"]["calibration_status"] for o in objs],["retained","applied","applied","applied","applied"])
        self.assertEqual(objs[1]["horizontal_geometry"]["correction_emu"],-3*9525)
        self.assertEqual(objs[-1]["bounds_emu"]["x"],280*9525)
        self.assertEqual(objs[-1]["horizontal_geometry"]["source"],"normalized_top_left")
        for obj in objs:
            self.assertNotIn("center_emu",obj)
            self.assertNotIn("center_geometry",obj)
        self.assertEqual(objs[2]["horizontal_geometry"]["calibration_factor"],1.25)

    def test_normalized_top_left_rotated_and_single_anchor(self):
        sheet='<sheetFormatPr defaultRowHeight="15" defaultColWidth="8"/><sheetData/>'
        def anchored(child,x,y,w,h,a,z):
            child=with_saved_geometry(child,x,y,w,h)
            return ('<xdr:twoCellAnchor>'+marker("from",0,0,a*9525,0)+
                    marker("to",0,1,z*9525,0)+child+'</xdr:twoCellAnchor>')
        pic=anchored(image(),80,0,200,20,0,100)
        # Rotation and the ending marker do not change the left anchor.
        child=anchored(shape("矩形",rot=5400000),103,0,60,20,20,30)
        objs=self.parse(pic+child+one_cell(shape("文本框"))+absolute(),worksheet_xml=sheet)[0]["objects"]
        self.assertEqual(objs[1]["bounds_emu"]["x"],120*9525)
        self.assertEqual(objs[1]["horizontal_geometry"]["source"],"normalized_top_left")
        self.assertEqual(objs[1]["width_px"],60)
        self.assertEqual(objs[2]["horizontal_geometry"]["source"],"normalized_top_left")
        self.assertEqual(objs[3]["bounds_emu"]["x"],10*9525)

    def test_vertical_translation_corrects_picture_and_each_shape_kind(self):
        # 15pt=20px, first row 30pt=40px, second row hidden.
        # row 2 (zero-based) begins at 40px, row 3 at 60px.
        sheet=('<sheetFormatPr defaultRowHeight="15" defaultColWidth="999"/>'
               '<sheetData><row r="1" ht="30"/><row r="2" hidden="1"/></sheetData>')
        def anchor(child,x,y,w,h,first,last,first_off=0,last_off=0):
            child=with_saved_geometry(child,x,y,w,h)
            return (f'<xdr:twoCellAnchor>{marker("from",99,first,987654,first_off)}'
                    f'{marker("to",100,last,123, last_off)}{child}</xdr:twoCellAnchor>')
        children=[image("P"),shape("文本框"),shape("矩形"),shape("椭圆")]
        anchors=anchor(children[0],80,10,300,60,2,5)
        anchors+="".join(anchor(c,100+i*30,13+i,20,20,3,4) for i,c in enumerate(children[1:]))
        with TemporaryDirectory() as tmp:
            path=fixture(Path(tmp)/"stale-y.xlsx",anchors,worksheet_xml=sheet)
            sheets=spatial.parse_xlsx(path)
            objs=sheets[0]["objects"]
            self.assertEqual([o["bounds_emu"]["y"] for o in objs],[40*9525]+[60*9525]*3)
            self.assertEqual([o["bounds_emu"]["x"] for o in objs],[80*9525,100*9525,130*9525,160*9525])
            self.assertEqual([o["height_px"] for o in objs],[60,20,20,20])
            self.assertEqual([o["vertical_geometry"]["source"] for o in objs],["picture_top_left"]+["normalized_top_left"]*3)
            service=import_module(f"{ROOT.name}.cad_service")
            layer=service.build_cad_manifest(path,sheets,Path(tmp))["layers"][0]
            self.assertEqual([o["bounds_emu"]["y"] for o in layer["objects"]],[0]+[20*9525]*3)
            self.assertIn("Y来源: normalized_top_left",spatial.format_spatial_report(path,sheets))

    def test_picture_normalization_independent_factors_and_crop(self):
        # First sheet: saved picture 240px, row span 192px (k=1.25).
        # Second sheet: saved picture 200px, row span 250px (k=0.8).
        def objects(height,span,relative):
            pic=image("P").replace("<xdr:blipFill/>",
                '<xdr:blipFill><a:srcRect t="2500" b="1500"/></xdr:blipFill>')
            pic=with_saved_geometry(pic,80,999,300,height)
            shapes=[with_saved_geometry(shape("文本框"),100,7,20,30),
                    with_saved_geometry(shape("矩形"),130,800,40,20),
                    with_saved_geometry(shape("椭圆"),160,-99,12,12)]
            return two_cell(pic,start_y=40,end_y=40+span,start_x=80,end_x=380)+"".join(
                two_cell(c,start_y=40+v,end_y=40+v+17,start_x=x,end_x=x+w)
                for c,v,x,w in zip(shapes,relative,(100,130,160),(20,40,12)))
        with TemporaryDirectory() as tmp:
            path=fixture(Path(tmp)/"normalize.xlsx",objects(240,192,[16,80,160]),
                sheet_count=2,second_anchors=objects(200,250,[25,125,200]))
            sheets=spatial.parse_xlsx(path)
            service=import_module(f"{ROOT.name}.cad_service")
            layers=service.build_cad_manifest(path,sheets,Path(tmp))["layers"]
            for i,(layer,expected,k) in enumerate(zip(layers,([0,20,100,200],[0,20,100,160]),(1.25,0.8))):
                for o,y in zip(layer["objects"],expected):
                    self.assertAlmostEqual(o["bounds_emu"]["y"],y*9525)
                self.assertEqual([o["bounds_emu"]["x"] for o in layer["objects"]],[0,20*9525,50*9525,80*9525])
                self.assertEqual([o["height_px"] for o in layer["objects"]],[240 if i==0 else 200,30,20,12])
                self.assertEqual([o["vertical_geometry"]["calibration_factor"] for o in layer["objects"][1:]],[k]*3)
                self.assertEqual(layer["objects"][0]["picture_crop"],{"l":"0","t":"2500","r":"0","b":"1500"})
                self.assertEqual(layer["objects"][1]["vertical_geometry"]["saved_y_emu"],7*9525)
            report=spatial.format_spatial_report(path,sheets)
            self.assertIn("k=1.25",report)
            self.assertIn("k=0.8",report)
            self.assertIn("图片裁剪 srcRect: l=0 t=2500 r=0 b=1500",report)

    def test_unavailable_picture_calibration_preserves_previous_positions(self):
        for raw in (one_cell(image())+one_cell(shape()),
                    two_cell(image(),start_y=42,end_y=42)+one_cell(shape())):
            objs=self.parse(raw)[0]["objects"]
            self.assertTrue(all(o["vertical_geometry"]["calibration_status"]=="retained" for o in objs))
            self.assertEqual(objs[1]["bounds_emu"]["y"],0)

    def test_absolute_shape_uses_saved_picture_relative_y(self):
        raw=two_cell(with_saved_geometry(image(),80,10,300,200),start_y=40,end_y=140)+absolute()
        objs=self.parse(raw)[0]["objects"]
        self.assertEqual(objs[1]["bounds_emu"]["y"]-objs[0]["bounds_emu"]["y"],10*9525)
        self.assertEqual(objs[1]["vertical_geometry"]["source"],"absolute_top_left")
        self.assertEqual(objs[1]["vertical_geometry"]["calibration_factor"],2)

    def test_normalized_rotated_outer_bounds_keep_saved_extents(self):
        pic=two_cell(with_saved_geometry(image(),80,40,300,200),start_y=40,end_y=140)
        child=with_saved_geometry(shape("矩形",rot=5400000),100,99,60,20)
        objs=self.parse(pic+two_cell(child,start_y=60,end_y=90))[0]["objects"]
        # Use mapped start only, no rotated-span center correction.
        self.assertEqual(objs[1]["bounds_emu"]["y"]-objs[0]["bounds_emu"]["y"],40*9525)
        self.assertEqual(objs[1]["height_px"],20)
        self.assertEqual(objs[1]["rotation_degrees"],90)
        self.assertEqual(objs[1]["vertical_geometry"]["source"],"normalized_top_left")

    def test_vertical_rotated_outer_bounds_and_one_cell_and_absolute(self):
        # At 90 degrees the start marker remains the positioning anchor.
        child=with_saved_geometry(shape("矩形",rot=5400000),20,5,60,20)
        raw=f'<xdr:twoCellAnchor>{marker("from",0,1)}{marker("to",0,4)}{child}</xdr:twoCellAnchor>'
        obj=self.parse(raw)[0]["objects"][0]
        self.assertEqual(obj["bounds_emu"]["y"],40*9525)
        self.assertEqual(obj["vertical_geometry"]["source"],"row_anchor")
        self.assertEqual(obj["bounds_emu"]["width"],60*9525)
        child=with_saved_geometry(shape(),22,5,20,30)
        raw=f'<xdr:oneCellAnchor>{marker("from",0,2)}<xdr:ext cx="190500" cy="285750"/>{child}</xdr:oneCellAnchor>'
        obj=self.parse(raw)[0]["objects"][0]
        self.assertEqual(obj["bounds_emu"]["y"],60*9525)
        self.assertEqual(self.parse(absolute(child))[0]["objects"][0]["bounds_emu"]["y"],20*9525)

    def test_vertical_missing_default_and_zero_height(self):
        child=with_saved_geometry(shape(),20,5,20,20)
        raw=f'<xdr:twoCellAnchor>{marker("from",0,1)}{marker("to",0,2)}{child}</xdr:twoCellAnchor>'
        with self.assertRaisesRegex(spatial.SpatialXlsxError,"cannot resolve Y from row/rowOff"):
            self.parse(raw,worksheet_xml='<sheetData/>')
        sheet='<sheetFormatPr defaultRowHeight="15" zeroHeight="1"/><sheetData><row r="2" hidden="0" ht="15"/></sheetData>'
        obj=self.parse(raw,worksheet_xml=sheet)[0]["objects"][0]
        self.assertEqual(obj["bounds_emu"]["y"],0)
        self.assertEqual(obj["vertical_geometry"]["source"],"row_anchor")

    def test_two_cell_saved_shape_geometry_beats_estimated_columns(self):
        def transformed(child, x, y, w, h):
            return child.replace('<a:xfrm rot="0"/>',
                f'<a:xfrm rot="0"><a:off x="{x*9525}" y="{y*9525}"/>'
                f'<a:ext cx="{w*9525}" cy="{h*9525}"/></a:xfrm>')
        box=shape("文本框").replace('</xdr:nvSpPr>',
                '<xdr:cNvSpPr txBox="1"/></xdr:nvSpPr>')
        anchors=two_cell(transformed(box,80,42,120,60),start_y=42,end_y=102)+two_cell(
                transformed(shape(),200,90,40,40),start_y=90,end_y=130)
        objects=self.parse(anchors)[0]["objects"]
        for obj,expected in zip(objects,[(80,42,120,60),(200,90,40,40)]):
            self.assertEqual(obj["geometry_source"],"xfrm")
            self.assertEqual(tuple(obj["bounds_emu"].values()),tuple(v*9525 for v in expected))
        self.assertEqual(objects[1]["vertices_px"],[
            {"x":200,"y":90},{"x":240,"y":90},{"x":240,"y":130},{"x":200,"y":130}])

    def test_zero_x_and_stale_zero_y_are_independent(self):
        child=shape().replace('<a:xfrm rot="0"/>',
            '<a:xfrm><a:off x="0" y="0"/><a:ext cx="381000" cy="381000"/></a:xfrm>')
        obj=self.parse(two_cell(child))[0]["objects"][0]
        self.assertEqual(obj["bounds_emu"],{"x":0,"y":42*9525,"width":381000,"height":381000})
        obj=self.parse(one_cell(child))[0]["objects"][0]
        self.assertEqual(obj["bounds_emu"],{"x":0,"y":0,"width":381000,"height":381000})

    def test_missing_malformed_and_stale_xfrm_y_are_ignored(self):
        for off in ('x="95250"', 'x="95250" y="invalid"', 'x="95250" y="99999999"'):
            child=shape().replace('<a:xfrm rot="0"/>',
                f'<a:xfrm><a:off {off}/><a:ext cx="381000" cy="381000"/></a:xfrm>')
            for raw,expected in ((two_cell(child,start_y=82,end_y=152),82*9525),
                                 (one_cell(child),0)):
                with self.subTest(off=off):
                    obj=self.parse(raw)[0]["objects"][0]
                    self.assertEqual(obj["bounds_emu"],{"x":95250,"y":expected,"width":381000,"height":381000})
                    self.assertEqual(obj["vertical_geometry"]["source"],"row_anchor")
        self.assertFalse(hasattr(spatial,"drawing_rect"))
        self.assertFalse(hasattr(spatial,"vertical_rect"))

    def test_missing_start_marker_reports_object_and_does_not_use_xfrm_y(self):
        raw=two_cell(shape("矩形MissingRow")).replace("<xdr:row>1</xdr:row>","<xdr:row>bad</xdr:row>",1)
        with self.assertRaisesRegex(spatial.SpatialXlsxError,"object '矩形MissingRow'.*cannot resolve Y"):
            self.parse(raw)

    def test_missing_or_invalid_cell_transform_stops_instead_of_guessing(self):
        cases = [
            ("", "missing top-level xfrm"),
            ("<a:xfrm/>", "missing xfrm/off@x"),
            ('<a:xfrm><a:off x="bad" y="20"/><a:ext cx="381000" cy="381000"/></a:xfrm>',"invalid integer xfrm/off@x"),
            ('<a:xfrm><a:off x="10" y="20"/><a:ext cx="0" cy="381000"/></a:xfrm>',"must have positive"),
            ('<a:xfrm><a:off x="10" y="20"/><a:ext cx="381000"/></a:xfrm>',"missing xfrm/ext@cy"),
            ('<a:xfrm><a:off x="10" y="20"/><a:ext cx="bad" cy="381000"/></a:xfrm>',"invalid integer xfrm/ext@cx"),
        ]
        for transform,message in cases:
            child=shape().replace('<a:xfrm rot="0"/>',transform)
            for kind in ("oneCellAnchor","twoCellAnchor"):
                raw=(f'<xdr:{kind}>'+marker("from",1,1)+
                     (marker("to",2,2) if kind=="twoCellAnchor" else '<xdr:ext cx="190500" cy="285750"/>')
                     +child+f'</xdr:{kind}>')
                with self.subTest(kind=kind,message=message),self.assertRaisesRegex(
                        spatial.SpatialXlsxError,message):
                    self.parse(raw)

    def test_one_cell_uses_complete_transform_and_absolute_uses_direct_anchor(self):
        valid=shape().replace('<a:xfrm rot="0"/>',
            '<a:xfrm><a:off x="952500" y="952500"/><a:ext cx="381000" cy="381000"/></a:xfrm>')
        obj=self.parse(one_cell(valid))[0]["objects"][0]
        self.assertEqual((obj["geometry_source"],obj["width_px"],obj["height_px"]),("xfrm",40,40))
        self.assertEqual(obj["bounds_emu"]["x"],952500)
        obj=self.parse(absolute(valid))[0]["objects"][0]
        self.assertEqual((obj["geometry_source"],obj["width_px"],obj["height_px"]),("absoluteAnchor",20,30))
        self.assertEqual(obj["bounds_emu"]["x"],95250)

    def test_incomplete_absolute_anchor_is_rejected(self):
        raw=absolute().replace('cx="190500" cy="285750"','cx="190500"')
        with self.assertRaisesRegex(spatial.SpatialXlsxError,"missing xdr:ext@cy"):
            self.parse(raw)

    def test_missing_picture_transform_reports_picture_name(self):
        raw='<xdr:twoCellAnchor>'+marker("from",0,0)+marker("to",1,1)+image("MissingPicture")+'</xdr:twoCellAnchor>'
        with self.assertRaisesRegex(spatial.SpatialXlsxError,"object 'MissingPicture'.*missing top-level xfrm"):
            self.parse(raw)

    def test_image_and_rotated_shape_use_same_saved_emu_coordinates(self):
        pic=image().replace('<xdr:spPr/>',
            '<xdr:spPr><a:xfrm><a:off x="952500" y="190500"/>'
            '<a:ext cx="3810000" cy="1905000"/></a:xfrm></xdr:spPr>')
        child=shape(rot=90*60000).replace('<a:xfrm rot="5400000"/>',
            '<a:xfrm rot="5400000"><a:off x="1143000" y="381000"/>'
            '<a:ext cx="381000" cy="190500"/></a:xfrm>')
        with TemporaryDirectory() as tmp:
            path=fixture(Path(tmp)/"saved.xlsx",two_cell(pic,start_y=20,end_y=220,start_x=100,end_x=500)+two_cell(child,start_y=40,end_y=60,start_x=120,end_x=160))
            sheets=spatial.parse_xlsx(path)
            from importlib import import_module
            service=import_module(f"{ROOT.name}.cad_service")
            layer=service.build_cad_manifest(path,sheets,Path(tmp))["layers"][0]
            self.assertEqual(layer["image_origin_emu"],{"x":952500,"y":190500})
            self.assertEqual(layer["objects"][0]["bounds_emu"],
                {"x":0,"y":0,"width":3810000,"height":1905000})
            self.assertEqual(layer["objects"][1]["bounds_emu"],
                {"x":190500,"y":190500,"width":381000,"height":190500})
            self.assertEqual(layer["objects"][1]["vertices_px"],[
                {"x":50,"y":10},{"x":50,"y":50},{"x":30,"y":50},{"x":30,"y":10}])

    def test_all_three_shape_kinds_use_identical_saved_geometry(self):
        children=[
            shape("Label").replace('</xdr:nvSpPr>','<xdr:cNvSpPr txBox="1"/></xdr:nvSpPr>'),
            shape("R").replace('<a:xfrm rot="0"/>','<a:xfrm rot="0"/><a:prstGeom prst="rect"/>'),
            shape("E").replace('<a:xfrm rot="0"/>','<a:xfrm rot="0"/><a:prstGeom prst="ellipse"/>'),
        ]
        objects=self.parse("".join(two_cell(with_saved_geometry(c,80,42,120,60)) for c in children))[0]["objects"]
        self.assertEqual([o["shape_kind"] for o in objects],["textbox","rectangle","ellipse"])
        for o in objects:
            self.assertEqual(o["geometry_source"],"xfrm")
            self.assertEqual(o["bounds_emu"],objects[0]["bounds_emu"])
            self.assertEqual(o["vertices_px"],objects[0]["vertices_px"])

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
        for item in ("A1", "左上: (80.000, 42.000)", "右下: (215.000, 70.000)",
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


class OutlineWidthTests(unittest.TestCase):
    def test_direct_and_theme_line_width(self):
        import xml.etree.ElementTree as ET
        direct = ET.fromstring('<ln w="28575"/>')
        theme = [ET.fromstring('<ln w="38100"/>')]
        style = ET.fromstring('<style><lnRef idx="1"/></style>')
        self.assertEqual(spatial.outline_width_px(direct, style, theme), 3)
        self.assertEqual(spatial.outline_width_px(None, style, theme), 4)
        self.assertIsNone(spatial.outline_width_px(None, None, []))


class ThemeOutlineColorTests(unittest.TestCase):
    def setUp(self):
        self.theme = (f'<a:theme xmlns:a="{A}"><a:themeElements><a:clrScheme name="Custom">'
                      '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
                      '<a:lt1><a:srgbClr val="FAFAFA"/></a:lt1>'
                      '<a:dk2><a:srgbClr val="123456"/></a:dk2>'
                      '<a:lt2><a:srgbClr val="EEEEEE"/></a:lt2>'
                      '<a:accent1><a:srgbClr val="5B9BD5"/></a:accent1>'
                      '</a:clrScheme><a:fmtScheme name="Custom"><a:lnStyleLst>'
                      '<a:ln w="28575"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
                      '<a:ln w="38100"><a:solidFill><a:srgbClr val="000000"/></a:solidFill></a:ln>'
                      '<a:ln><a:noFill/></a:ln>'
                      '<a:ln><a:solidFill><a:schemeClr val="phClr"><a:shade val="50000"/></a:schemeClr></a:solidFill></a:ln>'
                      '</a:lnStyleLst></a:fmtScheme></a:themeElements></a:theme>')

    def parsed(self, line="", ref=""):
        source = shape().replace(
            '<a:ln><a:solidFill><a:srgbClr val="5B9BD5"/></a:solidFill></a:ln>', line)
        if ref:
            source = source.replace('</xdr:spPr>', '</xdr:spPr><xdr:style>'+ref+'</xdr:style>')
        with TemporaryDirectory() as tmp:
            path = fixture(Path(tmp)/"colors.xlsx", one_cell(source), theme_xml=self.theme)
            return spatial.parse_xlsx(path)[0]["objects"][0]

    def test_direct_black_and_logical_theme_aliases(self):
        for val, expected in [('tx1','#000000'),('bg1','#FAFAFA'),
                              ('tx2','#123456'),('bg2','#EEEEEE'),('dk1','#000000')]:
            with self.subTest(val=val):
                obj = self.parsed(f'<a:ln><a:solidFill><a:schemeClr val="{val}"/></a:solidFill></a:ln>')
                self.assertEqual(obj["colors"]["outline"], expected)
                self.assertEqual(obj["outline_status"], "color")
        for color in ['<a:srgbClr val="000000"/>','<a:prstClr val="black"/>',
                      '<a:sysClr val="windowText" lastClr="000000"/>']:
            self.assertEqual(self.parsed(f'<a:ln><a:solidFill>{color}</a:solidFill></a:ln>')["colors"]["outline"],"#000000")

    def test_lnref_placeholder_and_fixed_style_color(self):
        ref = '<a:lnRef idx="1"><a:schemeClr val="tx1"/></a:lnRef>'
        obj = self.parsed('<a:ln/>', ref)
        self.assertEqual(obj["colors"]["outline"],"#000000")
        self.assertEqual(obj["outline_width_px"],3)
        self.assertEqual(self.parsed('<a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>',ref)["colors"]["outline"],"#000000")
        fixed = self.parsed("",'<a:lnRef idx="2"><a:schemeClr val="accent1"/></a:lnRef>')
        self.assertEqual(fixed["colors"]["outline"],"#000000")
        self.assertEqual(fixed["outline_width_px"],4)
        shaded = self.parsed("",'<a:lnRef idx="4"><a:srgbClr val="808080"/></a:lnRef>')
        self.assertEqual(shaded["colors"]["outline"],"#404040")

    def test_direct_overrides_and_no_border(self):
        ref = '<a:lnRef idx="1"><a:schemeClr val="tx1"/></a:lnRef>'
        obj = self.parsed('<a:ln><a:solidFill><a:srgbClr val="FF0000"/></a:solidFill></a:ln>',ref)
        self.assertEqual(obj["colors"]["outline"],"#FF0000")
        cases = [('<a:ln><a:noFill/></a:ln>',ref),
                 ('','<a:lnRef idx="3"><a:schemeClr val="tx1"/></a:lnRef>'),
                 ('','<a:lnRef idx="0"><a:schemeClr val="tx1"/></a:lnRef>'),
                 ('',''),
                 ('<a:ln><a:solidFill><a:srgbClr val="000000"><a:alpha val="0"/></a:srgbClr></a:solidFill></a:ln>',ref)]
        for line, inherited in cases:
            with self.subTest(line=line,ref=inherited):
                obj = self.parsed(line,inherited)
                self.assertEqual(obj["colors"]["outline"],"无/透明")
                self.assertEqual(obj["outline_status"],"none")
                self.assertEqual(obj["colors"]["fill"],"#5B9BD5")

    def test_unknown_color_is_not_no_border_and_does_not_inherit(self):
        obj = self.parsed('<a:ln><a:solidFill><a:schemeClr val="unknown"/></a:solidFill></a:ln>',
                          '<a:lnRef idx="1"><a:schemeClr val="tx1"/></a:lnRef>')
        self.assertEqual(obj["colors"]["outline"],"未解析")
        self.assertEqual(obj["outline_status"],"unresolved")
        obj = self.parsed("",'<a:lnRef idx="99"><a:schemeClr val="tx1"/></a:lnRef>')
        self.assertEqual(obj["outline_status"],"unresolved")

    def test_explicit_logical_mapping_uses_workbook_rgb(self):
        import xml.etree.ElementTree as ET
        p = spatial.mapped_theme_palette({"dk1":"000000","dk2":"123456","lt1":"FFFFFF"},
                                        ET.fromstring('<clrMap tx1="dk2" bg1="dk1"/>'))
        self.assertEqual(spatial.get_color(ET.fromstring('<schemeClr val="tx1"/>'),p),"#123456")
        self.assertEqual(spatial.get_color(ET.fromstring('<schemeClr val="bg1"/>'),p),"#000000")
