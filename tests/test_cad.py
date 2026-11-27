"""CAD manifest and embedded-media security regression tests."""
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
cad = import_module(f"{ROOT.name}.cad_service")
spatial = import_module(f"{ROOT.name}.xlsx_spatial")
fixture = import_module(f"{ROOT.name}.tests.test_xlsx_spatial").fixture


class TestCadManifest(unittest.TestCase):
    def test_two_layers_in_correct_order_and_optional_svg_flags(self):
        with TemporaryDirectory() as tmp:
            assets = Path(tmp)
            (assets / "PSD_base.svg").write_text("<svg/>", encoding="utf-8")
            manifest = cad.build_cad_manifest(None, [], assets)
            self.assertEqual([x["title"] for x in manifest["layers"]], ["Fab", "Subfab"])
            self.assertFalse(manifest["layers"][0]["available"])
            self.assertFalse(manifest["layers"][1]["available"])
            self.assertTrue(manifest["reference_svgs"]["psd"]["available"])
            self.assertFalse(manifest["reference_svgs"]["octave"]["available"])
            self.assertEqual(manifest["reference_svgs"]["psd"]["url"],
                             "/viewer/assets/PSD_base.svg")

    def test_embedded_picture_is_only_alignment_anchor_svg_is_visible_background(self):
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)
            xlsx=fixture(folder/"book.xlsx",media=True)
            sheets=spatial.parse_xlsx(xlsx)
            (folder/"Sheet1.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="0 0 1200 600"></svg>',encoding="utf-8")
            manifest=cad.build_cad_manifest(xlsx,sheets,folder)
            layer=manifest["layers"][0]
            first=layer["objects"][0]
            self.assertEqual(first["type"],"image")
            self.assertNotIn("image_url",first)
            self.assertNotIn("image_part",first)
            self.assertEqual(first["name"],"图片12")
            self.assertEqual(first["bounds_emu"]["x"],0)
            self.assertEqual(first["bounds_emu"]["y"],0)
            self.assertEqual(first["vertices_px"][0],{"x":0,"y":0})
            self.assertEqual(layer["background_svg"],{
                "available":True,"url":"/viewer/assets/Sheet1.svg",
                "aspect_ratio":0.5,
            })
            self.assertNotEqual(sheets[0]["objects"][0]["bounds_emu"]["x"],0)
            self.assertFalse(manifest["layers"][1]["available"])

    def test_sheet_svg_follows_worksheet_name_and_reports_aspect_ratio(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"Fab.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0,0,1600,800"/>',
                encoding="utf-8")
            (root/"subfab.SVG").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" '
                'width="900px" height="1200px"/>',encoding="utf-8")
            self.assertEqual(cad.sheet_svg_metadata(root,"Fab"),{
                "available":True,"url":"/viewer/assets/Fab.svg","aspect_ratio":0.5,
            })
            self.assertEqual(cad.sheet_svg_metadata(root,"Subfab"),{
                "available":True,"url":"/viewer/assets/subfab.SVG",
                "aspect_ratio":1200/900,
            })
            self.assertEqual(cad.sheet_svg_metadata(root,"NotFound")["available"],False)
            self.assertFalse(cad.sheet_svg_metadata(root,"../outside")["available"])
            self.assertFalse(cad.sheet_svg_metadata(root,"C:\\\\Windows")["available"])

    def test_invalid_or_ambiguous_svg_metadata_is_not_used_for_scaling(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"Bad.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" '
                                        'viewBox="0 0 0 300"/>',encoding="utf-8")
            meta=cad.sheet_svg_metadata(root,"Bad")
            self.assertTrue(meta["available"])
            self.assertIsNone(meta["aspect_ratio"])
            (root/"Bad.SVG").write_text('<svg/>',encoding="utf-8")
            # Windows directories are usually case-insensitive and the
            # second write overwrites Bad.svg rather than creating a
            # distinct ambiguous file. Assert the platform-visible count.
            distinct=len([p for p in root.iterdir()
                          if p.name.casefold()=="bad.svg"])
            self.assertEqual(cad.sheet_svg_metadata(root,"Bad")["available"],
                             distinct==1)

    def test_shape_name_text_color_and_bounds_pass_through(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            xlsx = fixture(folder / "book.xlsx")
            sheets = spatial.parse_xlsx(xlsx)
            manifest = cad.build_cad_manifest(xlsx, sheets, folder)
            item = manifest["layers"][0]["objects"][1]
            self.assertEqual(item["type"], "shape")
            self.assertIn("text", item)
            self.assertEqual(item["colors"]["fill"], "#5B9BD5")
            self.assertEqual(item["bounds_emu"]["width"], 190500)
            self.assertEqual(item["shape_kind"], "rectangle")
            self.assertEqual(item["bounds_emu"]["x"], -85 * 9525)
            self.assertEqual(item["bounds_emu"]["y"], -42 * 9525)

    def test_unsupported_embedded_extension_has_no_public_url(self):
        with TemporaryDirectory() as tmp:
            manifest = cad.build_cad_manifest(None, [{"sheet": "S", "objects": [
                {"type": "image", "name": "bad", "image_part": "xl/media/image1.emf",
                 "bounds_emu": {"x": 0, "y": 0, "width": 95250, "height": 95250},
                 "vertices_px": [{"x": 0, "y": 0} for _ in range(4)]}
            ]}], Path(tmp))
            self.assertNotIn("image_url", manifest["layers"][0]["objects"][0])

    def test_two_sheet_svg_backdrops_do_not_change_shape_anchor_coordinates(self):
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)
            xlsx=fixture(folder/"book.xlsx",media=True,sheet_count=2)
            sheets=spatial.parse_xlsx(xlsx)
            (folder/"Sheet1.svg").write_text(
                '<svg viewBox="0 0 1500 900" xmlns="http://www.w3.org/2000/svg"/>')
            (folder/"Sheet2.svg").write_text(
                '<svg viewBox="0 0 900 1800" xmlns="http://www.w3.org/2000/svg"/>')
            manifest=cad.build_cad_manifest(xlsx,sheets,folder)
            self.assertEqual([x["background_svg"]["aspect_ratio"]
                              for x in manifest["layers"]],[0.6,2.0])
            self.assertEqual([x["background_svg"]["available"]
                              for x in manifest["layers"]],[True,True])
            self.assertNotEqual(manifest["layers"][0]["image_origin_emu"],
                                manifest["layers"][1]["image_origin_emu"])
            for layer in manifest["layers"]:
                self.assertEqual(layer["objects"][0]["bounds_emu"]["x"],0)
                self.assertEqual(layer["objects"][0]["bounds_emu"]["y"],0)
                for obj in layer["objects"]:
                    self.assertNotIn("image_url",obj)
                    self.assertNotIn("image_part",obj)

    def test_each_sheet_uses_its_own_image_upper_left_as_origin(self):
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)
            xlsx=fixture(folder/"book.xlsx",media=True,sheet_count=2)
            sheets=spatial.parse_xlsx(xlsx)
            manifest=cad.build_cad_manifest(xlsx,sheets,folder)
            origins=[layer["image_origin_emu"] for layer in manifest["layers"]]
            self.assertNotEqual(origins[0], origins[1])
            for layer in manifest["layers"]:
                self.assertEqual(layer["objects"][0]["bounds_emu"]["x"],0)
                self.assertEqual(layer["objects"][0]["bounds_emu"]["y"],0)
                self.assertEqual(layer["objects"][0]["vertices_px"][0],{"x":0,"y":0})
                self.assertTrue(layer["available"])
