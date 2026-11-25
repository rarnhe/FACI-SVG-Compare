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

    def test_real_embedded_image_is_lazy_and_original_local_part_is_private(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            xlsx = fixture(folder / "book.xlsx", media=True)
            sheets = spatial.parse_xlsx(xlsx)
            manifest = cad.build_cad_manifest(xlsx, sheets, folder)
            first = manifest["layers"][0]["objects"][0]
            self.assertEqual(first["image_url"], "/viewer/cad-image/0/0")
            self.assertNotIn("image_part", first)
            self.assertEqual(first["name"], "图片12")
            self.assertEqual(first["bounds_emu"]["x"], 0)
            self.assertEqual(first["bounds_emu"]["y"], 0)
            self.assertEqual(first["vertices_px"][0], {"x": 0, "y": 0})
            # The parser itself still exposes A1-relative original coordinates.
            self.assertNotEqual(sheets[0]["objects"][0]["bounds_emu"]["x"], 0)
            self.assertEqual(manifest["layers"][1]["available"], False)
            payload, mime = cad.extract_embedded_image(xlsx, sheets, 0, 0)
            self.assertEqual(mime, "image/png")
            self.assertTrue(payload.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertRaises(ValueError, cad.extract_embedded_image, xlsx, sheets, 0, 1)
            self.assertRaises(ValueError, cad.extract_embedded_image, xlsx, sheets, 3, 0)

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
