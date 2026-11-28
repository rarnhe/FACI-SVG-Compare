"""Rotated rectangle overlap and rebuilt-circle placement regression tests."""
from importlib import import_module
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
geom=import_module(f"{ROOT.name}.cad_validation")
spatial=import_module(f"{ROOT.name}.xlsx_spatial")

EMU=9525


def shape(kind,x,y,w,h,name,rotation=0):
    return {
        "type":"shape", "shape_kind":kind, "name":name, "text":name,
        "rotation_degrees":rotation,
        "bounds_emu":{"x":round(x*EMU),"y":round(y*EMU),
                      "width":round(w*EMU),"height":round(h*EMU)},
    }


def sheet(*shapes,title="Sheet1"):
    return {"sheet":title,"objects":list(shapes)}


class TestCadValidation(unittest.TestCase):
    def test_disjoint_rectangles_and_edge_contact_are_allowed(self):
        one=shape("rectangle",0,0,100,80,"A")
        two=shape("rectangle",100,0,100,80,"B")
        geom.validate_sheet_collisions(sheet(one,two))
        self.assertFalse(geom.rectangles_overlap(
            geom.Rectangle.from_object(one),geom.Rectangle.from_object(two)))

    def test_two_overlapping_rectangles_fail_with_sheet_and_names(self):
        a=shape("rectangle",0,0,100,80,"A")
        b=shape("rectangle",90,10,60,50,"B")
        with self.assertRaisesRegex(spatial.SpatialXlsxError,r"Sheet 'Fab'.*'A'.*'B'"):
            geom.validate_sheet_collisions(sheet(a,b,title="Fab"),spatial.SpatialXlsxError)

    def test_rotated_rectangles_collision(self):
        a=shape("rectangle",0,0,100,70,"North",rotation=30)
        b=shape("rectangle",55,10,100,70,"South",rotation=-30)
        self.assertTrue(geom.rectangles_overlap(
            geom.Rectangle.from_object(a),geom.Rectangle.from_object(b)))
        with self.assertRaisesRegex(ValueError,"overlapping rectangles"):
            geom.validate_sheet_collisions(sheet(a,b))

    def test_whole_circle_inside_gets_inside_relation(self):
        a=geom.Rectangle.from_object(shape("rectangle",0,0,100,80,"A"))
        c=shape("ellipse",30,20,10,10,"circle")
        self.assertEqual(geom.circle_relation(c,a),"inside")

    def test_circle_center_inside_but_boundary_crosses_is_partial(self):
        a=geom.Rectangle.from_object(shape("rectangle",0,0,100,80,"A"))
        c=shape("ellipse",90,20,16,16,"circle")
        self.assertEqual(geom.circle_relation(c,a),"partial")

    def test_circle_center_outside_but_boundary_crosses_is_partial(self):
        a=geom.Rectangle.from_object(shape("rectangle",0,0,100,80,"A"))
        c=shape("ellipse",-18,30,20,20,"circle")
        self.assertEqual(geom.circle_relation(c,a),"partial")

    def test_circle_wholly_outside(self):
        a=geom.Rectangle.from_object(shape("rectangle",0,0,100,80,"A"))
        c=shape("ellipse",120,20,10,10,"circle")
        self.assertEqual(geom.circle_relation(c,a),"outside")

    def test_rotation_is_respected_for_circle_contact(self):
        a=geom.Rectangle.from_object(shape("rectangle",0,0,80,40,"A",rotation=45))
        self.assertEqual(geom.circle_relation(shape("ellipse",36,25,4,4,"c"),a),"inside")

    def test_one_circle_intersecting_two_separated_rectangles_fails(self):
        a=shape("rectangle",0,0,100,80,"Left")
        b=shape("rectangle",140,0,100,80,"Right")
        c=shape("ellipse",90,40,40,40,"Spanning")
        with self.assertRaisesRegex(ValueError,r"intersects 2 rectangles"):
            geom.validate_sheet_collisions(sheet(a,b,c))

    def test_cross_sheet_geometry_is_independent(self):
        a=shape("rectangle",0,0,100,80,"A")
        geom.validate_sheet_collisions(sheet(a,title="Fab"))
        geom.validate_sheet_collisions(sheet(a,title="Subfab"))
