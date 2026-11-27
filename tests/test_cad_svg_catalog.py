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

    def test_ellipse_outside_rectangle_uses_textbox_text_and_timestamp(self):
        with TemporaryDirectory() as tmp:
            directory=Path(tmp)/"BODYv2"
            directory.mkdir()
            names=[
                "BODYv2_20260704101627_+Y_PSD.svg",
                "BODYv2_20260704101627_+Y_1-3-Octave.svg",
                "BODYv2_20260702101627_+X_PSD.svg",
                "BODYv2_20260702101627_+X_1-3-Octave.svg",
                "20260704_SCN_B1_20260701101627_+X_PSD.svg",
                "Other_20260703101627_+X_PSD.svg",
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
            self.assertEqual(result["search_identifier"],"BODYv2")
            self.assertEqual(result["dates"],["20260702101627","20260704101627"])
            self.assertEqual(list(result["pairs"]["20260704101627"]),["Y"])
            self.assertIn("%2BY_PSD.svg",result["pairs"]["20260704101627"]["Y"]["psd"])
            self.assertNotIn("20260703101627",result["dates"])

    def test_partial_ellipse_uses_rectangle_text_and_timestamp(self):
        objects=sample_objects()
        touching=object_at("ellipse","EdgeSensor",491,140,20,20)
        self.assertIs(catalog.enclosing_rectangle(objects,touching),objects[1])
        self.assertIs(catalog.enclosing_textbox(objects,touching),objects[0])
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)/"BODYv2"
            folder.mkdir()
            for label,date,axis in [
                ("20260704_SCN_B1","20260706101627","Z"),
                ("20260704_SCN_B10","20260707101627","X"),
                ("BODYv2","20260704101627","Y"),
                ("EdgeSensor","20260705101627","X"),
            ]:
                for suffix in ("PSD","1-3-Octave"):
                    (folder/f"{label}_{date}_+{axis}_{suffix}.svg").write_text("<svg/>")
            sheets=[{"sheet":"fab","objects":[*objects,touching]}]
            result=catalog.build_ellipse_svg_catalog(Path(tmp),sheets,0,4)
            self.assertEqual(result["target_kind"],"rectangle")
            self.assertEqual(result["search_identifier"],"20260704_SCN_B1")
            self.assertEqual(result["identifier"],"20260704_SCN_B1")
            self.assertEqual(result["dates"],["20260706101627"])
            self.assertEqual(list(result["pairs"]["20260706101627"]),["Z"])
            inside=catalog.build_ellipse_svg_catalog(Path(tmp),sheets,0,2)
            self.assertEqual(result["pairs"],inside["pairs"])

    def test_external_tangent_and_rotated_partial_choose_rectangle(self):
        objects=sample_objects()
        tangent=object_at("ellipse","Tangent",502,146,6,8)
        separated=object_at("ellipse","Separated",502.01,146,6,8)
        self.assertIs(catalog.enclosing_rectangle(objects,tangent),objects[1])
        self.assertIsNone(catalog.enclosing_rectangle(objects,separated))
        rotated=object_at("rectangle","Rotated",100,100,80,40)
        rotated["rotation_degrees"]=45
        # Near the center of the rotated right edge (140+28.28,120+28.28).
        partial=object_at("ellipse","P",167,147,6,8)
        self.assertIs(catalog.enclosing_rectangle([rotated],partial),rotated)

    def test_ambiguous_multiple_intersections_are_rejected(self):
        objects=[object_at("rectangle","Left",0,0,100,80),
                 object_at("rectangle","Right",140,0,100,80)]
        circle=object_at("ellipse","Both",100,40,40,40)
        with self.assertRaisesRegex(ValueError,"multiple rectangles"):
            catalog.enclosing_rectangle(objects,circle)

    def test_empty_visible_rectangle_text_never_falls_back_to_shape_name(self):
        objects=sample_objects()
        objects[1]["text"]=""
        objects[1]["name"]="FallbackName"
        with TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/"BODYv2";folder.mkdir()
            (folder/"FallbackName_20260704101627_+X_PSD.svg").write_text("<svg/>")
            (folder/"BODYv2_20260704101627_+X_PSD.svg").write_text("<svg/>")
            result=catalog.build_ellipse_svg_catalog(root,[{"sheet":"Fab","objects":objects}],0,2)
            self.assertEqual(result["target_kind"],"rectangle")
            self.assertEqual(result["search_identifier"],"")
            self.assertEqual(result["dates"],[])

    def test_outside_ellipse_ignores_own_text_and_unrelated_date(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            directory=root/"BODYv2"
            directory.mkdir()
            (directory/"Other_20260704101627_+Z_PSD.svg").write_text("<svg/>")
            (directory/"Other_20260704101627_+Z_1-3-Octave.svg").write_text("<svg/>")
            result=catalog.build_ellipse_svg_catalog(
                root,[{"sheet":"Fab","objects":sample_objects()}],0,3)
            self.assertEqual(result["identifier"],"Other")
            self.assertEqual(result["search_identifier"],"BODYv2")
            self.assertEqual(result["dates"],[])
            self.assertEqual(result["pairs"],{})

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
