"""Workbook hot reload cache tests, independent of private assets."""
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
app=import_module(f"{ROOT.name}.__main__")

class TestWorkbookReload(unittest.TestCase):
    def test_unchanged_signature_does_not_parse(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"fixture.xlsx"
            path.write_bytes(b"fixture")
            state={"workbook":path,"signature":app.workbook_signature(path),
                   "sheets":[],"manifest":{},"generation":0}
            with patch.object(app,"parse_xlsx") as parse:
                self.assertIsNone(app.reload_workbook_if_changed(state,path.parent))
                parse.assert_not_called()

    def test_invalid_changed_file_keeps_complete_snapshot(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"fixture.xlsx"
            path.write_bytes(b"valid before")
            state={"workbook":path,"signature":app.workbook_signature(path),
                   "sheets":[],"manifest":{"old":True},"images":{(0,0):(b"png","image/png")},
                   "generation":3}
            before=dict(state)
            path.write_bytes(b"invalid after")
            self.assertIn("上次有效数据",app.reload_workbook_if_changed(state,path.parent))
            self.assertEqual(state,before)
