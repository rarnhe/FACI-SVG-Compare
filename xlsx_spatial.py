"""Extract Excel DrawingML objects as 2D positions relative to A1.

X increases to the right, Y downwards. Geometry is kept in integer EMU,
and reported in reference pixels at 96 DPI (9525 EMU / pixel).
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass, field
from math import cos, floor, radians, sin
from pathlib import Path
import posixpath
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

EMUS_PER_PIXEL = 9525
EMUS_PER_POINT = 12700
EMUS_PER_MM = 360000
DEFAULT_COL_WIDTH = 8.43
DEFAULT_ROW_HEIGHT_PT = 15.0
DEFAULT_THEME = {
    "dk1": "000000", "lt1": "FFFFFF", "dk2": "1F497D", "lt2": "EEECE1",
    "accent1": "4472C4", "accent2": "ED7D31", "accent3": "A5A5A5",
    "accent4": "FFC000", "accent5": "5B9BD5", "accent6": "70AD47",
    "hlink": "0563C1", "folHlink": "954F72",
}


# Standard DrawingML logical aliases, resolved against the actual workbook
# theme (not hard-coded RGB values). Optional explicit color maps override.
THEME_COLOR_MAP = {"tx1": "dk1", "bg1": "lt1", "tx2": "dk2", "bg2": "lt2"}
NO_PAINT = "无/透明"
UNRESOLVED_PAINT = "未解析"


class SpatialXlsxError(ValueError):
    """Invalid XLSX geometry or ambiguous input files."""


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def first_child(parent: ET.Element | None, tag: str) -> ET.Element | None:
    if parent is None:
        return None
    return next((child for child in parent if local_name(child.tag) == tag), None)


def find_descendant(parent: ET.Element | None, tag: str) -> ET.Element | None:
    if parent is None:
        return None
    return next((child for child in parent.iter() if local_name(child.tag) == tag), None)


def child_int(parent: ET.Element, name: str, default: int = 0) -> int:
    child = first_child(parent, name)
    return int(child.text) if child is not None and child.text else default


def pixels_from_column_width(width: float) -> int:
    """Excel column characters -> reference pixels; assumes MDW=7 (Calibri 11)."""
    if width <= 0:
        return 0
    if width < 1:
        return floor(width * 12 + 0.5)
    return floor(width * 7 + 5)


def resolve_part(source_part: str, target: str) -> str:
    """Resolve both absolute and relative OPC relationship targets."""
    if not target:
        raise SpatialXlsxError(f"Missing relationship target in {source_part}")
    result = posixpath.normpath(target.lstrip("/") if target.startswith("/")
                                else posixpath.join(posixpath.dirname(source_part), target))
    if result.startswith("../") or result == "..":
        raise SpatialXlsxError(f"Illegal relationship target: {target}")
    return result


def relationship_path(source_part: str) -> str:
    directory, basename = posixpath.split(source_part)
    return posixpath.join(directory, "_rels", basename + ".rels")


def relationships(z: ZipFile, source_part: str) -> dict[str, tuple[str, str]]:
    path = relationship_path(source_part)
    if path not in z.namelist():
        return {}
    root = ET.fromstring(z.read(path))
    return {
        elem.attrib["Id"]: (elem.attrib.get("Type", ""), elem.attrib.get("Target", ""))
        for elem in root if local_name(elem.tag) == "Relationship" and "Id" in elem.attrib
    }


@dataclass
class SheetMetrics:
    column_width_emu: int = pixels_from_column_width(DEFAULT_COL_WIDTH) * EMUS_PER_PIXEL
    row_height_emu: int = round(DEFAULT_ROW_HEIGHT_PT * EMUS_PER_POINT)
    columns: dict[int, int] = field(default_factory=dict)
    rows: dict[int, int] = field(default_factory=dict)

    @classmethod
    def from_xml(cls, root: ET.Element) -> "SheetMetrics":
        metrics = cls()
        fmt = first_child(root, "sheetFormatPr")
        if fmt is not None:
            if "defaultColWidth" in fmt.attrib:
                metrics.column_width_emu = pixels_from_column_width(
                    float(fmt.attrib["defaultColWidth"])) * EMUS_PER_PIXEL
            if "defaultRowHeight" in fmt.attrib:
                metrics.row_height_emu = round(float(fmt.attrib["defaultRowHeight"]) * EMUS_PER_POINT)
        cols = first_child(root, "cols")
        if cols is not None:
            for col in cols:
                if local_name(col.tag) != "col":
                    continue
                width = 0 if col.get("hidden") == "1" else (
                    pixels_from_column_width(float(col.get("width", DEFAULT_COL_WIDTH))) * EMUS_PER_PIXEL)
                for idx in range(int(col.get("min", 1)), int(col.get("max", 1)) + 1):
                    metrics.columns[idx] = width
        sheet_data = first_child(root, "sheetData")
        if sheet_data is not None:
            for row in sheet_data:
                if local_name(row.tag) != "row" or not row.get("r"):
                    continue
                idx = int(row.get("r"))
                if row.get("hidden") == "1":
                    metrics.rows[idx] = 0
                elif "ht" in row.attrib:
                    metrics.rows[idx] = round(float(row.get("ht")) * EMUS_PER_POINT)
        return metrics

    def xy(self, col0: int, row0: int, col_offset: int = 0, row_offset: int = 0) -> tuple[int, int]:
        if col0 < 0 or row0 < 0:
            raise SpatialXlsxError("Drawing marker has negative cell index")
        x = col0 * self.column_width_emu + sum(
            v - self.column_width_emu for idx, v in self.columns.items() if idx <= col0) + col_offset
        y = row0 * self.row_height_emu + sum(
            v - self.row_height_emu for idx, v in self.rows.items() if idx <= row0) + row_offset
        return x, y


def mapped_theme_palette(palette: dict[str, str], mapping: ET.Element | None = None) -> dict[str, str]:
    result = palette.copy()
    aliases = THEME_COLOR_MAP | (dict(mapping.attrib) if mapping is not None else {})
    for logical, actual in aliases.items():
        if actual in palette:
            result[logical] = palette[actual]
    return result


def parse_theme(z: ZipFile) -> tuple[dict[str, str], list[ET.Element], list[ET.Element]]:
    palette = DEFAULT_THEME.copy()
    fills: list[ET.Element] = []
    lines: list[ET.Element] = []
    if "xl/theme/theme1.xml" not in z.namelist():
        return mapped_theme_palette(palette), fills, lines
    root = ET.fromstring(z.read("xl/theme/theme1.xml"))
    for elem in root.iter():
        tag = local_name(elem.tag)
        if tag == "clrScheme":
            for color in elem:
                key = local_name(color.tag)
                for child in color:
                    if local_name(child.tag) in {"srgbClr", "sysClr"}:
                        value = child.get("lastClr") if local_name(child.tag) == "sysClr" else child.get("val")
                        if value and len(value) == 6:
                            palette[key] = value.upper()
                        break
        elif tag == "fillStyleLst":
            fills = list(elem)
        elif tag == "lnStyleLst":
            lines = list(elem)
    return mapped_theme_palette(palette), fills, lines


def apply_luminance(rgb: str, mod: int = 100000, offset: int = 0) -> str:
    if len(rgb) != 6:
        return rgb
    try:
        r, g, b = [int(rgb[k:k + 2], 16) / 255 for k in (0, 2, 4)]
    except ValueError:
        return rgb
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = max(0, min(1, l * (mod / 100000) + offset / 100000))
    return "".join(f"{round(c * 255):02X}" for c in colorsys.hls_to_rgb(h, l, s))


def get_color(node: ET.Element | None, palette: dict[str, str],
              placeholder: str | None = None) -> str | None:
    """Resolve RGB/theme/system colors, including the style's phClr."""
    if node is None:
        return None
    for child in node.iter():
        kind = local_name(child.tag)
        if kind == "srgbClr":
            rgb = child.get("val")
        elif kind == "schemeClr":
            key = child.get("val", "")
            rgb = placeholder.lstrip("#") if key == "phClr" and placeholder else (
                palette.get(key) or palette.get(THEME_COLOR_MAP.get(key, "")))
        elif kind == "sysClr":
            rgb = child.get("lastClr")
        elif kind == "prstClr":
            rgb = {"black": "000000", "white": "FFFFFF"}.get(child.get("val", ""))
        else:
            continue
        if not rgb or len(rgb) != 6:
            continue
        try:
            int(rgb, 16)
        except ValueError:
            continue
        # Apply the transformations in XML order, including transforms on
        # the resolved phClr itself, after the reference's own transforms.
        rgb = rgb.upper()
        for adjust in child:
            tag = local_name(adjust.tag)
            try:
                value = int(adjust.get("val", "100000"))
            except ValueError:
                continue
            if tag == "lumMod":
                rgb = apply_luminance(rgb, mod=value)
            elif tag == "lumOff":
                rgb = apply_luminance(rgb, offset=value)
            elif tag in {"tint", "shade"}:
                factor = max(0, min(1, value / 100000))
                channels = [int(rgb[i:i+2], 16) for i in (0, 2, 4)]
                rgb = "".join(f"{round(c * factor + (255 * (1-factor) if tag == 'tint' else 0)):02X}"
                              for c in channels)
        return "#" + rgb
    return None


def direct_paint(node: ET.Element | None, palette: dict[str, str],
                 placeholder: str | None = None) -> str | None:
    """None = unspecified/inherit; NO_PAINT = explicitly absent;
    UNRESOLVED_PAINT = specified but not representable as a solid RGB."""
    if node is None:
        return None
    if first_child(node, "noFill") is not None:
        return NO_PAINT
    solid = first_child(node, "solidFill")
    if solid is not None:
        # A fully transparent solid paint is distinct from a failed lookup.
        alpha = 100000
        for transform in solid.iter():
            tag = local_name(transform.tag)
            if tag not in {"alpha", "alphaMod", "alphaOff"}:
                continue
            try:
                value = int(transform.get("val", "100000"))
            except ValueError:
                continue
            alpha = max(0, min(100000, value if tag == "alpha" else
                               alpha * value / 100000 if tag == "alphaMod" else alpha + value))
        if alpha == 0:
            return NO_PAINT
        return get_color(solid, palette, placeholder) or UNRESOLVED_PAINT
    if any(first_child(node, tag) is not None
           for tag in ("gradFill", "pattFill", "blipFill", "grpFill")):
        return UNRESOLVED_PAINT
    return None


def style_color(node: ET.Element | None, style: ET.Element | None, kind: str,
                palette: dict[str, str], fills: list[ET.Element],
                lines: list[ET.Element]) -> str:
    ref = first_child(style, {"fill": "fillRef", "line": "lnRef"}[kind])
    placeholder = get_color(ref, palette)
    # A direct shape paint always overrides the inherited style, even when
    # explicitly absent or unresolvable. Never substitute a different color.
    direct = direct_paint(node, palette, placeholder)
    if direct is not None:
        return direct
    if ref is None:
        return NO_PAINT if node is None or kind == "fill" else UNRESOLVED_PAINT
    try:
        idx = int(ref.get("idx", "0"))
    except ValueError:
        return UNRESOLVED_PAINT
    if idx == 0 or (kind == "fill" and idx == 1000):
        return NO_PAINT
    style_list = fills if kind == "fill" else lines
    if 0 < idx <= len(style_list):
        # The matrix entry decides the actual paint. lnRef color is only
        # the substitution for phClr, not an override of fixed RGB/noFill.
        inherited = direct_paint(style_list[idx - 1], palette, placeholder)
        if inherited is not None:
            return inherited
        return UNRESOLVED_PAINT
    # Legacy fill-only files may omit their style matrix. Preserve the
    # reference color for fills; a missing line style must not be guessed.
    return (placeholder or UNRESOLVED_PAINT) if kind == "fill" else UNRESOLVED_PAINT


def outline_width_px(outline: ET.Element | None, style: ET.Element | None,
                     lines: list[ET.Element]) -> float | None:
    """DrawingML line width in 96-DPI pixels, direct then theme reference."""
    value = outline.get("w") if outline is not None else None
    if value is None and style is not None:
        ref = first_child(style, "lnRef")
        try:
            index = int(ref.get("idx", "0")) if ref is not None else 0
            if 0 < index <= len(lines):
                value = lines[index - 1].get("w")
        except ValueError:
            pass
    try:
        return max(0, int(value)) / EMUS_PER_PIXEL if value is not None else None
    except ValueError:
        return None


def marker_xy(marker: ET.Element, metrics: SheetMetrics) -> tuple[int, int]:
    return metrics.xy(child_int(marker, "col"), child_int(marker, "row"),
                      child_int(marker, "colOff"), child_int(marker, "rowOff"))


def anchor_rect(anchor: ET.Element, metrics: SheetMetrics) -> tuple[int, int, int, int]:
    kind = local_name(anchor.tag)
    if kind in ("oneCellAnchor", "twoCellAnchor"):
        start = first_child(anchor, "from")
        if start is None:
            raise SpatialXlsxError(f"{kind} without from marker")
        x1, y1 = marker_xy(start, metrics)
        if kind == "twoCellAnchor":
            end = first_child(anchor, "to")
            if end is None:
                raise SpatialXlsxError("twoCellAnchor without to marker")
            x2, y2 = marker_xy(end, metrics)
        else:
            ext = first_child(anchor, "ext")
            if ext is None:
                raise SpatialXlsxError("oneCellAnchor without ext")
            x2, y2 = x1 + int(ext.get("cx", "0")), y1 + int(ext.get("cy", "0"))
    elif kind == "absoluteAnchor":
        position, ext = first_child(anchor, "pos"), first_child(anchor, "ext")
        if position is None or ext is None:
            raise SpatialXlsxError("absoluteAnchor missing pos/ext")
        x1, y1 = int(position.get("x", "0")), int(position.get("y", "0"))
        x2, y2 = x1 + int(ext.get("cx", "0")), y1 + int(ext.get("cy", "0"))
    else:
        raise SpatialXlsxError(f"Unsupported anchor: {kind}")
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def rotation_degrees(node: ET.Element) -> float:
    props = first_child(node, "spPr")
    if props is None:
        props = first_child(node, "grpSpPr")
    xfrm = first_child(props, "xfrm")
    return int(xfrm.get("rot", "0")) / 60000 if xfrm is not None else 0.0


def vertices_from_rect(rect: tuple[int, int, int, int], angle: float) -> list[dict[str, float]]:
    x1, y1, x2, y2 = rect
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    co, si = cos(radians(angle)), sin(radians(angle))
    result = []
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        result.append({
            "x": round((cx + (x - cx) * co - (y - cy) * si) / EMUS_PER_PIXEL, 3),
            "y": round((cy + (x - cx) * si + (y - cy) * co) / EMUS_PER_PIXEL, 3),
        })
    return result


def shape_kind(node: ET.Element) -> str:
    """Classify by DrawingML preset and textbox flag, then Excel's object name."""
    non_visual = first_child(node, "nvSpPr")
    meta = first_child(non_visual, "cNvSpPr")
    if meta is not None and meta.get("txBox") in ("1", "true", "True"):
        return "textbox"
    props = first_child(node, "spPr")
    preset = first_child(props, "prstGeom")
    if preset is not None:
        value = preset.get("prst", "").lower()
        if value == "ellipse":
            return "ellipse"
        if value in ("rect", "roundrect", "round1samerect", "round2samerect"):
            return "rectangle"
    if first_child(props, "custGeom") is not None:
        return "other"
    label_node = find_descendant(node, "cNvPr")
    name = (label_node.get("name", "") if label_node is not None else "").strip().lower()
    if name.startswith(("文本框", "textbox")):
        return "textbox"
    if name.startswith(("椭圆", "ellipse", "oval")):
        return "ellipse"
    if name.startswith(("矩形", "rectangle")):
        return "rectangle"
    return "other"


def shape_alternative_text(node: ET.Element) -> dict[str, str]:
    """DrawingML Shape Format > Alt Text: cNvPr@descr/title, not visible txBody.

    Excel may encode newline as _x000D_ inside OOXML attributes.
    """
    props = find_descendant(node, "cNvPr")
    def clean(raw: str) -> str:
        return raw.replace("_x000D_", "").replace("\r\n", "\n").strip()
    return {
        "description": clean(props.get("descr", "") if props is not None else ""),
        "title": clean(props.get("title", "") if props is not None else ""),
    }


def shape_text(node: ET.Element) -> str:
    """Read visible shape text, preserving separate DrawingML paragraphs."""
    tx_body = first_child(node, "txBody")
    if tx_body is None:
        return ""
    paragraphs = []
    for paragraph in tx_body:
        if local_name(paragraph.tag) != "p":
            continue
        parts = [part.text or "" for part in paragraph.iter() if local_name(part.tag) == "t"]
        line = "".join(parts).strip()
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def theme_text_fonts(z: ZipFile) -> dict[str, dict[str, str]]:
    """Resolve DrawingML major/minor Latin and East Asian theme typefaces."""
    fonts = {
        "major": {"latin": "Calibri", "ea": "Microsoft YaHei"},
        "minor": {"latin": "Calibri", "ea": "Microsoft YaHei"},
    }
    if "xl/theme/theme1.xml" not in z.namelist():
        return fonts
    root = ET.fromstring(z.read("xl/theme/theme1.xml"))
    scheme = find_descendant(root, "fontScheme")
    for key, tag in (("major", "majorFont"), ("minor", "minorFont")):
        family = first_child(scheme, tag)
        for role in ("latin", "ea"):
            entry = first_child(family, role)
            if entry is not None and entry.get("typeface"):
                fonts[key][role] = entry.attrib["typeface"]
    return fonts


def text_property_style(node: ET.Element | None, inherited: dict,
                        palette: dict[str, str], fonts: dict) -> dict:
    """Read DrawingML rPr/defRPr, keeping inherited defaults for omitted tags."""
    result = inherited.copy()
    if node is None:
        return result
    if node.get("sz"):
        try:
            size = int(node.attrib["sz"]) / 100
            if 0 < size <= 500:
                result["font_size_pt"] = size
        except ValueError:
            pass
    for tag, field in (("b", "bold"), ("i", "italic")):
        if tag in node.attrib:
            result[field] = node.attrib[tag] in ("1", "true", "on")
    for tag, field in (("latin", "font_family"), ("ea", "east_asian_font")):
        font = first_child(node, tag)
        if font is not None and font.get("typeface"):
            result[field] = font.attrib["typeface"]
    direct = get_color(first_child(node, "solidFill"), palette)
    if direct:
        result["color"] = direct
    return result


def textbox_text_layout(node: ET.Element, palette: dict[str, str],
                        theme_fonts: dict[str, dict[str, str]]) -> dict:
    """Text runs with per-run formatting and textbox-local insets/alignment.

    Coordinates are reference pixels (96 DPI). The JS renderer paints these
    in a transparent texture mapped onto the same XLSX rectangle as the box.
    """
    body = first_child(node, "txBody")
    body_pr = first_child(body, "bodyPr")
    style = first_child(node, "style")
    font_ref = first_child(style, "fontRef")
    family_key = font_ref.get("idx", "minor") if font_ref is not None else "minor"
    theme_family = theme_fonts.get(family_key, theme_fonts["minor"])
    defaults = {
        "font_family": theme_family["latin"],
        "east_asian_font": theme_family["ea"],
        "font_size_pt": 11.0,
        "color": get_color(font_ref, palette) or "#000000",
        "bold": False,
        "italic": False,
    }
    insets = {}
    for label, attr, fallback in (
        ("left", "lIns", 91440), ("right", "rIns", 91440),
        ("top", "tIns", 45720), ("bottom", "bIns", 45720),
    ):
        try:
            inset = int(body_pr.get(attr, str(fallback))) if body_pr is not None else fallback
        except ValueError:
            inset = fallback
        insets[label] = max(0, inset) / EMUS_PER_PIXEL
    anchor = body_pr.get("anchor", "t") if body_pr is not None else "t"
    vertical = {"ctr": "middle", "b": "bottom"}.get(anchor, "top")
    paragraphs = []
    if body is not None:
        for paragraph in body:
            if local_name(paragraph.tag) != "p":
                continue
            p_pr = first_child(paragraph, "pPr")
            p_defaults = text_property_style(first_child(p_pr, "defRPr"), defaults,
                                             palette, theme_fonts)
            alignment = (p_pr.get("algn", "l") if p_pr is not None else "l")
            alignment = {"ctr": "center", "r": "right"}.get(alignment, "left")
            runs = []
            for item in paragraph:
                tag = local_name(item.tag)
                if tag in ("r", "fld"):
                    content = first_child(item, "t")
                    if content is not None and content.text:
                        run = text_property_style(first_child(item, "rPr"), p_defaults,
                                                  palette, theme_fonts)
                        run["text"] = content.text
                        runs.append(run)
                elif tag == "br":
                    run = p_defaults.copy()
                    run["text"] = "\n"
                    runs.append(run)
            if not runs:
                text = "".join(x.text or "" for x in paragraph.iter()
                               if local_name(x.tag) == "t")
                if text:
                    run = text_property_style(first_child(paragraph, "endParaRPr"),
                                              p_defaults, palette, theme_fonts)
                    run["text"] = text
                    runs.append(run)
            paragraphs.append({"align": alignment, "runs": runs})
    return {"anchor": vertical, "insets_px": insets, "paragraphs": paragraphs}


def drawing_objects(root: ET.Element, metrics: SheetMetrics, palette: dict[str, str],
                    fills: list[ET.Element], lines: list[ET.Element],
                    theme_fonts: dict[str, dict[str, str]] | None = None,
                    drawing_rels: dict[str, tuple[str, str]] | None = None,
                    drawing_part: str = "", members: set[str] | None = None) -> list[dict]:
    color_map = first_child(root, "clrMap")
    override = first_child(first_child(root, "clrMapOvr"), "overrideClrMapping")
    if color_map is not None or override is not None:
        palette = mapped_theme_palette(palette, override if override is not None else color_map)
    objects = []
    for anchor in root:
        if local_name(anchor.tag) not in {"oneCellAnchor", "twoCellAnchor", "absoluteAnchor"}:
            continue
        rect = anchor_rect(anchor, metrics)
        for element in anchor:
            tag = local_name(element.tag)
            if tag not in {"pic", "sp", "cxnSp", "grpSp", "graphicFrame"}:
                continue
            nv = find_descendant(element, "cNvPr")
            kind = "image" if tag == "pic" else "shape"
            angle = rotation_degrees(element)
            x1, y1, x2, y2 = rect
            obj = {
                "type": kind,
                "name": nv.get("name", "未命名对象") if nv is not None else "未命名对象",
                "anchor": local_name(anchor.tag),
                "bounds_emu": {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
                "width_px": round((x2 - x1) / EMUS_PER_PIXEL, 3),
                "height_px": round((y2 - y1) / EMUS_PER_PIXEL, 3),
                "rotation_degrees": angle,
                "vertices_px": vertices_from_rect(rect, angle),
            }
            if kind == "image":
                blip = find_descendant(element, "blip")
                embed_id = None if blip is None else next(
                    (value for key, value in blip.attrib.items() if local_name(key) == "embed"),
                    None,
                )
                rel = (drawing_rels or {}).get(embed_id or "")
                if rel is not None and rel[0].endswith("/image"):
                    try:
                        image_part = resolve_part(drawing_part, rel[1])
                    except SpatialXlsxError:
                        image_part = None
                    if image_part is not None and (members is None or image_part in members):
                        obj["image_part"] = image_part
            if kind == "shape":
                obj["shape_kind"] = shape_kind(element) if tag == "sp" else "other"
                obj["text"] = shape_text(element)
                obj["alt_text"] = shape_alternative_text(element)
                if obj["shape_kind"] == "textbox":
                    obj["text_layout"] = textbox_text_layout(
                        element, palette, theme_fonts or {
                            "major": {"latin": "Calibri", "ea": "Microsoft YaHei"},
                            "minor": {"latin": "Calibri", "ea": "Microsoft YaHei"},
                        })
                props = first_child(element, "spPr")
                if props is None:
                    props = first_child(element, "grpSpPr")
                outline = first_child(props, "ln")
                style = first_child(element, "style")
                obj["outline_width_px"] = outline_width_px(outline, style, lines)
                obj["colors"] = {
                    "fill": style_color(props, style, "fill", palette, fills, lines),
                    "outline": style_color(outline, style, "line", palette, fills, lines),
                }
                obj["outline_status"] = (
                    "none" if obj["colors"]["outline"] == NO_PAINT else
                    "unresolved" if obj["colors"]["outline"] == UNRESOLVED_PAINT else
                    "color"
                )
            objects.append(obj)
    return objects


def parse_xlsx(path: Path | str) -> list[dict]:
    path = Path(path)
    try:
        with ZipFile(path) as z:
            if "xl/workbook.xml" not in z.namelist():
                raise SpatialXlsxError(f"Not a valid XLSX workbook: {path.name}")
            workbook = ET.fromstring(z.read("xl/workbook.xml"))
            book_rels = relationships(z, "xl/workbook.xml")
            palette, fills, lines = parse_theme(z)
            fonts = theme_text_fonts(z)
            sheets = []
            for sheet in workbook.iter():
                if local_name(sheet.tag) != "sheet":
                    continue
                name = sheet.get("name", "Sheet")
                rid = next((value for key, value in sheet.attrib.items() if local_name(key) == "id"), None)
                rel = book_rels.get(rid or "")
                if rel is None or "worksheet" not in rel[0]:
                    raise SpatialXlsxError(f"Missing worksheet relationship for {name}")
                sheet_part = resolve_part("xl/workbook.xml", rel[1])
                metrics = SheetMetrics.from_xml(ET.fromstring(z.read(sheet_part)))
                objects = []
                for rel_type, target in relationships(z, sheet_part).values():
                    if not rel_type.endswith("/drawing"):
                        continue
                    drawing_part = resolve_part(sheet_part, target)
                    drawing = ET.fromstring(z.read(drawing_part))
                    objects.extend(drawing_objects(
                        drawing, metrics, palette, fills, lines,
                        theme_fonts=fonts,
                        drawing_rels=relationships(z, drawing_part),
                        drawing_part=drawing_part, members=set(z.namelist()),
                    ))
                sheets.append({"sheet": name, "objects": objects})
            return sheets
    except (BadZipFile, KeyError, ET.ParseError) as error:
        raise SpatialXlsxError(f"Invalid XLSX structure ({path.name}): {error}") from error


def select_assets_xlsx(directory: Path | str) -> Path | None:
    directory = Path(directory)
    candidates = sorted(
        (p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".xlsx"
         and not p.name.startswith(("~$", ".", ".~"))),
        key=lambda p: p.name.casefold(),
    ) if directory.is_dir() else []
    if len(candidates) > 1:
        raise SpatialXlsxError(
            f"assets/ contains multiple XLSX files ({', '.join(p.name for p in candidates)}); "
            "keep exactly one .xlsx file."
        )
    return candidates[0] if candidates else None


def validate_two_layer_workbook(sheets: list[dict]) -> None:
    """CAD requires exactly two sheets and exactly one image on each."""
    if len(sheets) != 2:
        raise SpatialXlsxError(
            f"XLSX must contain exactly 2 sheets (Fab and Subfab); found {len(sheets)}."
        )
    for sheet in sheets:
        images = [obj for obj in sheet["objects"] if obj["type"] == "image"]
        if len(images) != 1:
            raise SpatialXlsxError(
                f"Sheet '{sheet['sheet']}' must contain exactly 1 image; "
                f"found {len(images)}."
            )


def load_assets_spatial_report(directory: Path | str) -> tuple[Path | None, list[dict]]:
    selected = select_assets_xlsx(directory)
    if selected is None:
        return None, []
    sheets = parse_xlsx(selected)
    validate_two_layer_workbook(sheets)
    try:
        from .cad_validation import validate_sheet_collisions
    except ImportError:
        from cad_validation import validate_sheet_collisions
    for sheet in sheets:
        validate_sheet_collisions(sheet, error_type=SpatialXlsxError)
    return selected, sheets


def format_spatial_report(workbook: Path | None, sheets: list[dict]) -> str:
    if workbook is None:
        return "[XLSX] assets/ 中未发现 .xlsx 文件，跳过空间坐标解析。"
    lines = [
        f"[XLSX] 读取: {workbook}",
        "[坐标系] 每个 Sheet 的 A1 左上角为 (0, 0)；X 向右，Y 向下；单位: px (96 DPI 参考像素)",
    ]
    for sheet in sheets:
        images = sum(obj["type"] == "image" for obj in sheet["objects"])
        lines.append(f"[Sheet: {sheet['sheet']}] 图片 {images}，形状 {len(sheet['objects']) - images}")
        for obj in sheet["objects"]:
            lines.append(
                f"  {obj['type'].upper()}: {obj['name']}  "
                f"宽={obj['width_px']:.3f}px 高={obj['height_px']:.3f}px"
            )
            for title, point in zip(("左上", "右上", "右下", "左下"), obj["vertices_px"]):
                lines.append(f"    {title}: ({point['x']:.3f}, {point['y']:.3f}) px")
            if obj["rotation_degrees"]:
                lines.append(
                    f"    旋转: {obj['rotation_degrees']:.3f}°"
                    "（顶点已旋转，宽高是未旋转包围框）"
                )
            if obj["type"] == "shape":
                if obj.get("text"):
                    lines.append("    文字: " + obj["text"].replace("\n", " / "))
                alt = obj.get("alt_text", {})
                if alt.get("title") or alt.get("description"):
                    parts = []
                    if alt.get("title"):
                        parts.append("[标题: " + alt["title"].replace("\n", " / ") + "]")
                    if alt.get("description"):
                        parts.append(alt["description"].replace("\n", " / "))
                    lines.append("    替换文字: " + " ".join(parts))
                colors = obj["colors"]
                lines.append(
                    f"    颜色: 背景={colors['fill']} "
                    f"轮廓={colors['outline']}"
                )
    return "\n".join(lines)
