"""On-demand SVG catalog matching; never requires the user's private assets."""
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
catalog=import_module(f"{ROOT.name}.cad_svg_catalog")
EMU=9525


def object_at(kind,text,x,y,w,h,name=None):
    return {
        "type":"shape",
        "shape_kind":kind,
        "text":text,
        "name":name or kind,
        "rotation_degrees":0,
        "bounds_emu":{"x":x*EMU,"y":y*EMU,"width":w*EMU,"height":h*EMU},
    }


def sample_objects(body="BODYv2"):
    return [
        object_at("textbox",body,0,0,800,500),
        object_at("rectangle","20260704_SCN_B1",100,100,400,200),
        object_at("ellipse","B1",210,160,20,20),
        object_at("ellipse","Other",750,400,10,10),
    ]


class TestSvgCatalog(unittest.TestCase):
    def test_enclosing_textbox_and_rectangle(self):
        objects=sample_objects()
        self.assertIs(catalog.enclosing_textbox(objects,objects[2]),objects[0])
        self.assertIs(catalog.enclosing_rectangle(objects,objects[2]),objects[1])
        self.assertIsNone(catalog.enclosing_rectangle(objects,objects[3]))

    def test_dates_are_unique_ordered_and_pairs_require_three_criteria(self):
        with TemporaryDirectory() as tmp:
            base=Path(tmp)
            directory=base/"BODYv2"
            directory.mkdir()
            names=[
                "20260704_SCN_B1_20260704101627_+X_PSD.svg",
                "20260704_SCN_B1_20260704101627_+X_1-3-Octave.svg",
                "20260704_SCN_B1_20260704101627_+Y_PSD.svg",
                "20260704_SCN_B1_20260704101627_+Y_1-3-Octave.svg",
                "20260704_SCN_B1_20260705101627_+Z_PSD.svg",
                "20260704_SCN_B10_20260705101627_+Z_1-3-Octave.svg",
                "20260704_SCN_B1_20260706101627_+X_PSD.svg",
                "20260704_SCN_B1_20260706101627_+X_1-3-Octave.svg",
                "other_20260704101627_+X_PSD.svg",
                "20260704_SCN_B1_20260704101627_+X_other.svg",
                "20260704_SCN_B1_20260704101627_+X_PSD.png",
                "20260704_SCN_B1_baddate_+Z_PSD.svg",
            ]
            for name in names:
                (directory/name).write_text("<svg/>",encoding="utf-8")
            sheets=[{"sheet":"Fab","objects":sample_objects()}]
            result=catalog.build_ellipse_svg_catalog(base,sheets,0,2)
            self.assertEqual(result["folder"],"BODYv2")
            self.assertEqual(result["rectangle"],"20260704_SCN_B1")
            self.assertEqual(result["dates"],[
                "20260704101627","20260705101627","20260706101627"
            ])
            self.assertEqual(sorted(result["pairs"]["20260704101627"]),["X","Y"])
            self.assertEqual(result["pairs"]["20260705101627"],{})
            self.assertEqual(sorted(result["pairs"]["20260706101627"]),["X"])
            self.assertTrue(result["pairs"]["20260704101627"]["X"]["psd"].endswith(
                "20260704_SCN_B1_20260704101627_%2BX_PSD.svg"))
            self.assertTrue(result["pairs"]["20260704101627"]["X"]["octave"].endswith(
                "20260704_SCN_B1_20260704101627_%2BX_1-3-Octave.svg"))

    def test_rectangle_identifier_and_timestamp_must_match_same_filename(self):
        with TemporaryDirectory() as tmp:
            directory=Path(tmp)/"BODYv2"
            directory.mkdir()
            names=[
                "20260704_SCN_B1_20260704101627_+X_PSD.svg",
                "20260704_SCN_B1_20260704101627_+X_1-3-Octave.svg",
                "20260704_SCN_B1_20260706101627_+Y_PSD.svg",
                "20260704_SCN_B1_20260706101627_+Y_1-3-Octave.svg",
                "20260704_SCN_B10_20260702101627_+X_PSD.svg",
                "Other_20260703101627_+Y_PSD.svg",
                "unrelated_20260701101627_+X_PSD.svg",
            ]
            for name in names:
                (directory/name).write_text("<svg/>",encoding="utf-8")
            result=catalog.build_ellipse_svg_catalog(
                Path(tmp),[{"sheet":"fab","objects":sample_objects()}],0,2)
            self.assertEqual(result["target_kind"],"rectangle")
            self.assertEqual(result["identifier"],"20260704_SCN_B1")
            self.assertEqual(result["sheet"],"fab")
            self.assertEqual(result["dates"],["20260704101627","20260706101627"])
            self.assertNotIn("20260702101627",result["dates"])
            self.assertNotIn("20260703101627",result["dates"])
            self.assertEqual(sorted(result["pairs"]["20260704101627"]),["X"])

    def test_ellipse_outside_rectangle_inside_textbox_uses_ellipse_text(self):
        with TemporaryDirectory() as tmp:
            directory=Path(tmp)/"BODYv2"
            directory.mkdir()
            names=[
                "Other_20260704101627_+Y_PSD.svg",
                "Other_20260704101627_+Y_1-3-Octave.svg",
                "Other_20260702101627_+X_PSD.svg",
                "Other_20260702101627_+X_1-3-Octave.svg",
                "20260704_SCN_B1_20260701101627_+X_PSD.svg",
                "unrelated_20260703101627_+X_PSD.svg",
            ]
            for name in names:
                (directory/name).write_text("<svg/>",encoding="utf-8")
            result=catalog.build_ellipse_svg_catalog(
                Path(tmp),[{"sheet":"subfab","objects":sample_objects()}],0,3)
            self.assertEqual(result["folder"],"BODYv2")
            self.assertEqual(result["sheet"],"subfab")
            self.assertEqual(result["target_kind"],"ellipse")
            self.assertEqual(result["rectangle"],"")
            self.assertEqual(result["ellipse"],"Other")
            self.assertEqual(result["identifier"],"Other")
            self.assertEqual(result["dates"],["20260702101627","20260704101627"])
            self.assertEqual(list(result["pairs"]["20260704101627"]),["Y"])
            self.assertIn("%2BY_PSD.svg",result["pairs"]["20260704101627"]["Y"]["psd"])

    def test_partially_overlapping_ellipse_is_not_fully_inside_rectangle(self):
        objects=sample_objects()
        touching=object_at("ellipse","EdgeSensor",491,140,20,20)
        # Circle crosses the rectangle's x=500 boundary.
        self.assertIsNone(catalog.enclosing_rectangle(objects,touching))
        self.assertIs(catalog.enclosing_textbox(objects,touching),objects[0])
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)/"BODYv2"
            folder.mkdir()
            (folder/"EdgeSensor_20260704101627_+Z_PSD.svg").write_text("<svg/>")
            result=catalog.build_ellipse_svg_catalog(
                Path(tmp),[{"sheet":"fab","objects":[*objects,touching]}],0,4)
            self.assertEqual(result["target_kind"],"ellipse")
            self.assertEqual(result["dates"],["20260704101627"])

    def test_wrong_sheet_index_object_type_and_path_traversal_rejected(self):
        with TemporaryDirectory() as tmp:
            sheets=[{"sheet":"Fab","objects":sample_objects()}]
            with self.assertRaises(ValueError):
                catalog.build_ellipse_svg_catalog(Path(tmp),sheets,1,2)
            with self.assertRaises(ValueError):
                catalog.build_ellipse_svg_catalog(Path(tmp),sheets,0,999)
            with self.assertRaises(ValueError):
                catalog.build_ellipse_svg_catalog(Path(tmp),sheets,0,1)
            self.assertIsNone(catalog.svg_directory(Path(tmp),"../outside"))
            self.assertIsNone(catalog.svg_directory(Path(tmp),"C:\\Windows"))
            self.assertIsNone(catalog.svg_directory(Path(tmp),".."))
            bad=[{"sheet":"Fab","objects":sample_objects("../outside")}]
            result=catalog.build_ellipse_svg_catalog(Path(tmp),bad,0,2)
            self.assertEqual(result["dates"],[])

    def test_no_match_does_not_crash_or_leak_other_folders(self):
        with TemporaryDirectory() as tmp:
            base=Path(tmp)
            (base/"Other").mkdir()
            (base/"Other"/"20260704_SCN_B1_20260704101627_+X_PSD.svg").write_text(
                "<svg/>",encoding="utf-8")
            result=catalog.build_ellipse_svg_catalog(
                base,[{"sheet":"Fab","objects":sample_objects()}],0,2)
            self.assertEqual(result["folder"],"BODYv2")
            self.assertEqual(result["dates"],[])
