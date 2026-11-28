"""Geometry and embedded media for the linked Fab/Subfab CAD viewer.

Media is extracted on request from the workbook,
rather than embedding large base64 images into a Bokeh/JSON document.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

SUPPORTED_IMAGE_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
}
MAX_EMBEDDED_IMAGE_BYTES = 64 * 1024 * 1024
REFERENCE_SVGS = (
    ("psd", "PSD_base.svg"),
    ("octave", "1-3-Octave_base.svg"),
)


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
                       if key not in {"image_part", "_drawing_source"}}
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
                if (item.get("type") == "image" and item.get("image_part")
                        and Path(item["image_part"]).suffix.lower() in SUPPORTED_IMAGE_TYPES):
                    obj["image_url"] = f"/viewer/cad-image/{layer_index}/{object_index}"
                layer["objects"].append(obj)
        manifest["layers"].append(layer)
    return manifest


def extract_embedded_image(workbook: Path | None, sheets: list[dict],
                           layer_index: int, object_index: int) -> tuple[bytes, str]:
    """Read a single known image part, with bounds/type/size checks."""
    if workbook is None or layer_index not in (0, 1) or layer_index >= len(sheets):
        raise ValueError("Unknown CAD layer")
    objects = sheets[layer_index]["objects"]
    if object_index < 0 or object_index >= len(objects):
        raise ValueError("Unknown CAD object")
    obj = objects[object_index]
    if obj.get("type") != "image" or not obj.get("image_part"):
        raise ValueError("CAD object does not contain an embedded image")
    part = obj["image_part"]
    content_type = SUPPORTED_IMAGE_TYPES.get(Path(part).suffix.lower())
    if content_type is None or not part.startswith("xl/media/"):
        raise ValueError("Unsupported embedded drawing format")
    with ZipFile(workbook) as package:
        info = package.getinfo(part)
        if info.file_size > MAX_EMBEDDED_IMAGE_BYTES:
            raise ValueError("Embedded image exceeds the 64 MiB safety limit")
        data = package.read(info)
    if len(data) > MAX_EMBEDDED_IMAGE_BYTES:
        raise ValueError("Embedded image exceeds the 64 MiB safety limit")
    return data, content_type
