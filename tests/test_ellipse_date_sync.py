"""Real XLSX date synchronization, targeted byte preservation and failure safety."""
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
spatial = import_module(f"{ROOT.name}.xlsx_spatial")
fixtures = import_module(f"{ROOT.name}.tests.test_xlsx_spatial")

A = "20260704101627"
B = "20260706101627"
OLD = "20250101000000"

class TestEllipseDateSync(unittest.TestCase):
    def test_reconcile_all_three_cases_and_empty_notes(self):
        before = {"description": f"普通文字\n{A}-现有-说明\n{OLD}-过期", "title": "标题"}
        after = spatial.reconcile_ellipse_dates(before, [A, B])
        self.assertEqual(after, {"description": f"普通文字\n{A}-现有-说明\n{B}-", "title": "标题"})
        self.assertEqual(spatial.ellipse_time_descriptions(after), {A: "现有说明"})
        self.assertEqual(spatial.reconcile_ellipse_dates(after, [A, B]), after)
        self.assertEqual(spatial.reconcile_ellipse_dates(after, []),
                         {"description": "普通文字", "title": "标题"})

    def workbook(self, directory):
        shape = fixtures.shape(name="椭圆14").replace(
            'name="椭圆14"/>', f'name="椭圆14" descr="{A}-现有_x000D_{OLD}-过期"/>'
        ).replace('<a:xfrm rot="0"/>','<a:xfrm rot="0"/><a:prstGeom prst="ellipse"/>')
        return fixtures.fixture(Path(directory)/"test.xlsx", anchors=fixtures.one_cell(shape)+fixtures.one_cell(fixtures.shape()))

    def test_actual_zip_roundtrip_and_idempotence(self):
        with TemporaryDirectory() as tmp:
            path = self.workbook(tmp)
            ellipse = spatial.parse_xlsx(path)[0]["objects"][0]
            with ZipFile(path) as z:
                before = {n:z.read(n) for n in z.namelist()}
            result = spatial.write_ellipse_dates(path, ellipse, [A,B], spatial.workbook_signature(path))
            self.assertEqual(result["description"], f"{A}-现有\n{B}-")
            objects = spatial.parse_xlsx(path)[0]["objects"]
            self.assertEqual(objects[0]["alt_text"], result)
            self.assertEqual(objects[1]["alt_text"], {"description":"","title":""})
            with ZipFile(path) as z:
                after = {n:z.read(n) for n in z.namelist()}
            self.assertEqual(set(before),set(after))
            self.assertEqual([n for n in before if before[n]!=after[n]], [ellipse["_drawing_source"]["part"]])
            raw = path.read_bytes()
            spatial.write_ellipse_dates(path, objects[0], [A,B], spatial.workbook_signature(path))
            self.assertEqual(path.read_bytes(),raw)

    def test_lock_and_failed_replace_leave_original_intact(self):
        with TemporaryDirectory() as tmp:
            path = self.workbook(tmp)
            ellipse = spatial.parse_xlsx(path)[0]["objects"][0]
            original = path.read_bytes()
            lock = path.parent / ("~$"+path.name)
            lock.touch()
            with self.assertRaises(OSError):
                spatial.write_ellipse_dates(path, ellipse, [B], spatial.workbook_signature(path))
            lock.unlink()
            with patch.object(spatial.os, "replace", side_effect=PermissionError("locked")):
                with self.assertRaises(OSError):
                    spatial.write_ellipse_dates(path, ellipse, [B], spatial.workbook_signature(path))
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual(list(path.parent.iterdir()),[path])
