"""SVG persisted style changes are validated on real temporary files."""
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from .test_cad_svg_catalog import sample_objects
from importlib import import_module
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
style = import_module(f"{ROOT.name}.svg_styling")


def sample_svg() -> bytes:
    return (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 80">'
            b'<path id="a" d="M0 0 L100 50" fill="none" stroke="#009999"/>'
            b'<path id="b" d="M3 4 L90 32" style="fill:none;stroke:#ffaa00;stroke-width:2"/>'
            b'<rect id="empty" width="30" height="20" fill="none" stroke="none"/>'
            b'<g id="group" style="fill:none;stroke:#222222"><path d="M1 1L2 2"/></g>'
            b'<style>.line{stroke:#333333;fill:none}</style></svg>')


def elements(blob):
    root=ET.fromstring(blob)
    return {elem.get("id"):elem for elem in root.iter() if elem.get("id")}


class TestSvgStyle(unittest.TestCase):
    def test_palette_contains_every_requested_color_and_unique_cycle(self):
        self.assertEqual(len(style.PALETTE),17)
        self.assertEqual(style.PALETTE[0],"#4F99CF")
        self.assertEqual(style.PALETTE[-1],"#D1C7BD")
        self.assertEqual(len(set(style.PALETTE)),len(style.PALETTE))

    def test_svg_recolor_preserves_no_fill_and_unpainted_regions(self):
        result=style.restyle_svg(sample_svg(),"color","#E41A1C")
        items=elements(result)
        self.assertEqual(items["a"].get("stroke"),"#E41A1C")
        self.assertEqual(items["a"].get("fill"),"none")
        self.assertIn("stroke:#E41A1C",items["b"].get("style"))
        self.assertEqual(items["empty"].get("stroke"),"none")
        self.assertEqual(items["empty"].get("fill"),"none")
        self.assertIn("stroke:#E41A1C",items["group"].get("style"))
        self.assertIn(b"#E41A1C",result)
        self.assertNotIn(b'fill="#E41A1C"',result)

    def test_line_width_and_dashes_persist_in_explicit_strokes_and_css(self):
        width=style.restyle_svg(sample_svg(),"width","2.25")
        items=elements(width)
        self.assertEqual(items["a"].get("stroke-width"),"2.25")
        self.assertIn("stroke-width:2.25",items["b"].get("style"))
        self.assertEqual(items["empty"].get("stroke-width"),None)
        dash=style.restyle_svg(width,"dash","-·")
        parts=elements(dash)
        self.assertEqual(parts["a"].get("stroke-dasharray"),"8 3 1 3")
        self.assertEqual(parts["empty"].get("stroke-dasharray"),None)
        self.assertIn("stroke-dasharray:8 3 1 3",parts["b"].get("style"))
        dashed=style.restyle_svg(dash,"dash","--")
        self.assertEqual(elements(dashed)["a"].get("stroke-dasharray"),"8 4")

    def test_invalid_color_width_dash_and_unknown_op_are_rejected(self):
        for op,value in [("color","#000000"),("color","red"),("width","8"),
                         ("width","0.5"),("dash","solid"),("custom","yes")]:
            with self.subTest(op=op,value=value),self.assertRaises(ValueError):
                style.restyle_svg(sample_svg(),op,value)
        for data in [b"<!DOCTYPE svg><svg/>",b"<html/>",
                     b"<svg><path></svg>",b"<!ENTITY unsafe>"]:
            with self.subTest(data=data),self.assertRaises((ValueError,ET.ParseError)):
                style.restyle_svg(data,"color","#4F99CF")

    def test_a_real_cad_pair_is_written_to_both_original_svg_paths(self):
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)/"BODYv2"
            folder.mkdir()
            names=[
                "20260704_SCN_B1_20260704101627_+X_PSD.svg",
                "20260704_SCN_B1_20260704101627_+X_1-3-Octave.svg",
            ]
            for name in names:(folder/name).write_bytes(sample_svg())
            sheets=[{"sheet":"FAB","objects":sample_objects()}]
            params=(Path(tmp),sheets,0,2,"20260704101627","X")
            pair=style.update_svg_pair(*params,"color","#4F99CF")
            self.assertIn("psd",pair)
            self.assertIn("octave",pair)
            for name in names:
                self.assertIn(b"#4F99CF",(folder/name).read_bytes())
            style.update_svg_pair(*params,"width","0.75")
            style.update_svg_pair(*params,"dash","--")
            for name in names:
                blob=(folder/name).read_bytes()
                self.assertIn(b'stroke-width="0.75"',blob)
                self.assertIn(b'stroke-dasharray="8 4"',blob)

    def test_pair_validation_rejects_other_shape_and_no_matching_pair(self):
        with TemporaryDirectory() as tmp:
            sheets=[{"sheet":"FAB","objects":sample_objects()}]
            with self.assertRaises(ValueError):
                style.update_svg_pair(Path(tmp),sheets,0,1,
                                      "20260704101627","X","color","#4F99CF")
            with self.assertRaises(ValueError):
                style.update_svg_pair(Path(tmp),sheets,0,2,
                                      "20260704101627","X","color","#4F99CF")
            with self.assertRaises(ValueError):
                style.update_svg_pair(Path(tmp),sheets,0,2,
                                      "not-a-date","X","color","#4F99CF")
