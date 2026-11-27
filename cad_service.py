"""Read-only data for the linked Fab/Subfab CAD viewer.

XLSX DrawingML image anchors are geometry references only; the visible
backdrops are read-only SVG files from assets named after each worksheet.
No XLSX media bytes are opened by the viewer.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite
from pathlib import Path
from urllib.parse import quote
import re
import xml.etree.ElementTree as ET

REFERENCE_SVGS = (
    ("psd", "PSD_base.svg"),
    ("octave", "1-3-Octave_base.svg"),
)


SVG_VIEWBOX = re.compile(r"[\s,]+")
SVG_LENGTH = re.compile(r"^\s*(\d+(?:\.\d+)?|\.\d+)(px|pt|pc|mm|cm|in)?\s*$", re.I)
MAX_SHEET_SVG_BYTES = 32 * 1024 * 1024


def _svg_length(value: str | None) -> float | None:
    if not value:
        return None
    match = SVG_LENGTH.fullmatch(value)
    if not match:
        return None
    unit_scale = {"px": 1, "pt": 96 / 72, "pc": 16,
                  "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96}
    result = float(match.group(1)) * unit_scale.get((match.group(2) or "px").lower(), 1)
    return result if isfinite(result) and result > 0 else None


def _svg_aspect(path: Path) -> float | None:
    """Read SVG content metadata only, prefer viewBox over presentation size."""
    try:
        if path.stat().st_size > MAX_SHEET_SVG_BYTES:
            return None
        root = ET.fromstring(path.read_bytes())
        if root.tag.rsplit("}", 1)[-1].lower() != "svg":
            return None
        view_box = root.attrib.get("viewBox", "").strip()
        if view_box:
            values = SVG_VIEWBOX.split(view_box)
            if len(values) == 4:
                width, height = float(values[2]), float(values[3])
                if isfinite(width) and isfinite(height) and width > 0 and height > 0:
                    return height / width
        width = _svg_length(root.attrib.get("width"))
        height = _svg_length(root.attrib.get("height"))
        return height / width if width and height else None
    except (OSError, ValueError, ET.ParseError, OverflowError):
        return None


def sheet_svg_metadata(asset_dir: Path, sheet_name: str) -> dict:
    """Locate an assets/<sheet>.svg safely, with unique case-insensitive fallback.

    The XLSX embedded picture's anchor remains the only coordinate origin;
    its pixel media is never the displayed backdrop.
    """
    empty = {"available": False, "url": None, "aspect_ratio": None}
    if not isinstance(sheet_name, str) or not sheet_name.strip():
        return empty
    if (sheet_name in {".", ".."} or any(c in sheet_name for c in ("/", ":", chr(92))) or chr(0) in sheet_name):
        return empty
    base = asset_dir.resolve()
    if not asset_dir.is_dir():
        return empty
    expected = f"{sheet_name}.svg"
    matching = sorted((
        p for p in asset_dir.iterdir()
        if p.is_file() and not p.is_symlink()
        and p.name.casefold() == expected.casefold()
        and p.resolve().parent == base
    ), key=lambda p: p.name)
    if len(matching) != 1:
        return empty
    target = matching[0]
    return {
        "available": True,
        "url": "/viewer/assets/" + quote(target.name, safe=""),
        "aspect_ratio": _svg_aspect(target),
    }


def build_cad_manifest(workbook: Path | None, sheets: list[dict],
                       asset_dir: Path) -> dict:
    """Public geometry only; avoid exposing local file paths or embedded bytes."""
    manifest = {
        "workbook": workbook.name if workbook else None,
        "layers": [],
        "reference_svgs": {
            key: {
                "available": (asset_dir / filename).is_file(),
                "url": f"/viewer/assets/{filename}",
            }
            for key, filename in REFERENCE_SVGS
        },
    }
    for layer_index, title in enumerate(("Fab", "Subfab")):
        source = sheets[layer_index] if layer_index < len(sheets) else None
        layer = {
            "title": title,
            "sheet": source["sheet"] if source else None,
            "available": source is not None,
            "objects": [],
            "image_origin_emu": None,
            "background_svg": sheet_svg_metadata(asset_dir, source["sheet"])
                if source else {"available": False, "url": None, "aspect_ratio": None},
        }
        if source:
            images = [item for item in source["objects"] if item["type"] == "image"]
            if len(images) != 1:
                raise ValueError(
                    f"Sheet {source['sheet']} needs exactly one image for CAD alignment"
                )
            image_rect = images[0]["bounds_emu"]
            ox, oy = image_rect["x"], image_rect["y"]
            layer["image_origin_emu"] = {"x": ox, "y": oy}
            for object_index, item in enumerate(source["objects"]):
                obj = {key: deepcopy(value) for key, value in item.items()
                       if key != "image_part"}
                # Use EACH sheet's picture top-left as (0, 0) for the shared
                # Fab/Subfab camera. Keep original coordinates in parser output.
                obj["bounds_emu"]["x"] -= ox
                obj["bounds_emu"]["y"] -= oy
                obj["vertices_px"] = [
                    {
                        "x": round(point["x"] - ox / 9525, 3),
                        "y": round(point["y"] - oy / 9525, 3),
                    }
                    for point in obj["vertices_px"]
                ]
                layer["objects"].append(obj)
        manifest["layers"].append(layer)
    return manifest


