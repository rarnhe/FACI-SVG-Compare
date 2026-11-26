"""Resolve right-click ellipse menus to SVG pairs inside its enclosing textbox folder.

The client supplies only validated sheet/shape indices; it cannot choose an
arbitrary filesystem path. The folder name comes from XLSX DrawingML textbox
text, and all SVG filenames are enumerated at request time.
"""
from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import quote

if __package__:
    from .cad_validation import Rectangle, circle_relation
else:
    from cad_validation import Rectangle, circle_relation

TIMESTAMP = re.compile(r"_(\d{14})_")
AXIS = re.compile(r"(?:^|[_-])\+([XYZ])(?=[_.-])", re.IGNORECASE)
PSD_SUFFIX = re.compile(r"_PSD\.svg$", re.IGNORECASE)
OCTAVE_SUFFIX = re.compile(r"_1-3-Octave\.svg$", re.IGNORECASE)


def svg_directory(asset_dir: Path, name: str) -> Path | None:
    """No traversal, symlink escape, drive separator, or reserved path."""
    if not name or name in {".", ".."} or any(c in name for c in ("/", "\\", ":", "\x00")):
        return None
    base = asset_dir.resolve()
    target = asset_dir / name
    if not target.is_dir() or target.is_symlink() or not target.resolve().is_relative_to(base):
        return None
    return target


def enclosing_textbox(objects: list[dict], ellipse: dict) -> dict | None:
    """Smallest textbox fully containing the reconstructed circle."""
    found = []
    for obj in objects:
        if obj.get("type") != "shape" or obj.get("shape_kind") != "textbox":
            continue
        box = Rectangle.from_object(obj)
        if circle_relation(ellipse, box) == "inside":
            found.append(obj)
    return min(found, key=lambda o: o["bounds_emu"]["width"] * o["bounds_emu"]["height"],
               default=None)


def enclosing_rectangle(objects: list[dict], ellipse: dict) -> dict | None:
    """A circle belongs to its intersecting cuboid footprint (including roof edge)."""
    found = []
    for obj in objects:
        if obj.get("type") != "shape" or obj.get("shape_kind") != "rectangle":
            continue
        relation = circle_relation(ellipse, Rectangle.from_object(obj))
        if relation != "outside":
            found.append((relation == "inside", obj))
    # The workbook startup already prohibits one circle meeting multiple rectangles.
    return sorted(found, key=lambda pair: not pair[0])[0][1] if found else None


def name_matches(candidate: str, identifier: str) -> bool:
    """Literal rectangle name match with filename-token boundaries."""
    if not identifier:
        return False
    match = re.search(r"(?<![A-Za-z0-9])" + re.escape(identifier) + r"(?![A-Za-z0-9])",
                      candidate, re.IGNORECASE)
    return match is not None


def build_ellipse_svg_catalog(asset_dir: Path, sheets: list[dict],
                              layer_index: int, object_index: int) -> dict:
    """Return dated menu and optional paired PSD/octave links for one ellipse."""
    if layer_index not in (0, 1) or layer_index >= len(sheets):
        raise ValueError("Unknown CAD layer")
    objects = sheets[layer_index]["objects"]
    if object_index < 0 or object_index >= len(objects):
        raise ValueError("Unknown CAD shape")
    ellipse = objects[object_index]
    if ellipse.get("type") != "shape" or ellipse.get("shape_kind") != "ellipse":
        raise ValueError("CAD object is not an ellipse")
    textbox = enclosing_textbox(objects, ellipse)
    rectangle = enclosing_rectangle(objects, ellipse)
    folder_name = ((textbox.get("text") or "").strip() if textbox else "")
    root = svg_directory(asset_dir, folder_name)
    result = {"folder": folder_name, "rectangle": (
        (rectangle.get("text") or rectangle.get("name") or "").strip() if rectangle else ""),
        "dates": [], "pairs": {}}
    if root is None:
        return result

    entries = sorted(
        (p for p in root.iterdir() if p.is_file() and not p.is_symlink()
         and p.suffix.lower() == ".svg"),
        key=lambda p: p.name.casefold()
    )
    result["dates"] = sorted({match.group(1) for file in entries
                              for match in TIMESTAMP.finditer(file.name)})
    if not rectangle:
        return result
    identifiers = {str(rectangle.get(key, "")).strip()
                   for key in ("text", "name")}
    identifiers.discard("")
    for date in result["dates"]:
        axes = {}
        for axis in ("X", "Y", "Z"):
            matching = {"psd": None, "octave": None}
            for file in entries:
                filename = file.name
                if date not in TIMESTAMP.findall(filename):
                    continue
                if not any(name_matches(filename, identifier) for identifier in identifiers):
                    continue
                if axis not in [m.group(1).upper() for m in AXIS.finditer(filename)]:
                    continue
                key = ("psd" if PSD_SUFFIX.search(filename)
                       else "octave" if OCTAVE_SUFFIX.search(filename) else None)
                if key and matching[key] is None:
                    matching[key] = ("/viewer/assets/" + quote(folder_name, safe="")
                                     + "/" + quote(filename, safe=""))
            if all(matching.values()):
                axes[axis] = matching
        result["pairs"][date] = axes
    return result
