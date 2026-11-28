"""Validate 2D Excel CAD geometry before starting Bokeh.

Units are 96-DPI reference pixels; rectangles may carry DrawingML rotation.
The reconstructed circle's diameter is the diagonal of the ellipse anchor box.
A collision is reported per sheet, independently of the picture origin.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, hypot, radians, sin

EMU_PER_PX = 9525
TOLERANCE = 1e-9


@dataclass(frozen=True)
class Rectangle:
    label: str
    cx: float
    cy: float
    half_width: float
    half_height: float
    angle: float

    @classmethod
    def from_object(cls, obj: dict) -> "Rectangle":
        bounds = obj["bounds_emu"]
        x, y = bounds["x"] / EMU_PER_PX, -bounds["y"] / EMU_PER_PX
        width = bounds["width"] / EMU_PER_PX
        height = bounds["height"] / EMU_PER_PX
        return cls(
            label=obj.get("text") or obj.get("name") or "矩形",
            cx=x + width / 2, cy=y - height / 2,
            half_width=width / 2, half_height=height / 2,
            angle=-radians(obj.get("rotation_degrees", 0)),
        )

    def axes(self) -> tuple[tuple[float, float], tuple[float, float]]:
        co, si = cos(self.angle), sin(self.angle)
        return (co, si), (-si, co)

    def to_local(self, x: float, y: float) -> tuple[float, float]:
        dx, dy = x - self.cx, y - self.cy
        return (dx * cos(self.angle) + dy * sin(self.angle),
                -dx * sin(self.angle) + dy * cos(self.angle))


def rectangles_overlap(a: Rectangle, b: Rectangle) -> bool:
    """Separating axis test: positive area overlap, not mere edge contact."""
    for axis in (*a.axes(), *b.axes()):
        x, y = axis
        center_gap = abs((a.cx - b.cx) * x + (a.cy - b.cy) * y)
        aa, ab = a.axes()
        ba, bb = b.axes()
        reach_a = a.half_width * abs(aa[0] * x + aa[1] * y) + a.half_height * abs(ab[0] * x + ab[1] * y)
        reach_b = b.half_width * abs(ba[0] * x + ba[1] * y) + b.half_height * abs(bb[0] * x + bb[1] * y)
        if center_gap >= reach_a + reach_b - TOLERANCE:
            return False
    return True


def circle_relation(circle: dict, rectangle: Rectangle) -> str:
    """'inside', 'partial', or 'outside' for the RECONSTRUCTED circle."""
    bounds = circle["bounds_emu"]
    width = bounds["width"] / EMU_PER_PX
    height = bounds["height"] / EMU_PER_PX
    radius = hypot(width, height) / 2
    # The reconstructed circle's bounding square shares the XLSX anchor.
    cx = bounds["x"] / EMU_PER_PX + radius
    cy = -bounds["y"] / EMU_PER_PX - radius
    x, y = rectangle.to_local(cx, cy)
    dx, dy = abs(x), abs(y)
    if dx + radius <= rectangle.half_width + TOLERANCE and dy + radius <= rectangle.half_height + TOLERANCE:
        return "inside"
    nearest_dx = max(dx - rectangle.half_width, 0)
    nearest_dy = max(dy - rectangle.half_height, 0)
    # Tangency is an intersection, including external edge contact.
    if hypot(nearest_dx, nearest_dy) > radius + TOLERANCE:
        return "outside"
    return "partial"


def intersecting_rectangles(objects: list[dict], circle: dict) -> list[dict]:
    """Shared selection for validation and catalog, including tangency."""
    return [obj for obj in objects
            if obj.get("type") == "shape" and obj.get("shape_kind") == "rectangle"
            and circle_relation(circle, Rectangle.from_object(obj)) != "outside"]


def validate_sheet_collisions(sheet: dict, error_type=ValueError) -> None:
    """Refuse overlapping rectangles or circles meeting multiple rectangles."""
    shapes = sheet["objects"]
    rectangles = [
        Rectangle.from_object(obj) for obj in shapes
        if obj.get("type") == "shape" and obj.get("shape_kind") == "rectangle"
    ]
    for i, a in enumerate(rectangles):
        for b in rectangles[i + 1:]:
            if rectangles_overlap(a, b):
                raise error_type(
                    f"Sheet '{sheet['sheet']}': overlapping rectangles "
                    f"'{a.label}' and '{b.label}' (positive XY overlap)"
                )
    for circle in shapes:
        if circle.get("type") != "shape" or circle.get("shape_kind") != "ellipse":
            continue
        matches = [Rectangle.from_object(obj).label
                   for obj in intersecting_rectangles(shapes, circle)]
        if len(matches) >= 2:
            raise error_type(
                f"Sheet '{sheet['sheet']}': reconstructed circle "
                f"'{circle.get('text') or circle.get('name') or '椭圆'}' "
                f"intersects {len(matches)} rectangles ({', '.join(matches)})"
            )
