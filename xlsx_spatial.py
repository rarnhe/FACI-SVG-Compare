"""Extract Excel DrawingML objects as 2D positions relative to A1.

X increases to the right, Y downwards. Read saved absolute DrawingML
X and extents from saved transforms, with conditional horizontal anchor cross-check; Y from worksheet row anchors normalized to the picture height when possible. Geometry is kept in
integer EMU and reported in reference pixels at 96 DPI (9525 EMU / pixel).
"""

from __future__ import annotations

import colorsys
from bisect import bisect_left
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from math import cos, radians, sin
from pathlib import Path
import posixpath
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

EMUS_PER_PIXEL = 9525
EMUS_PER_POINT = 12700
EMUS_PER_MM = 360000
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


class VerticalRowMetrics:
    """Sparse row heights in exact EMU from saved XLSX point measurements.

    Do not infer a default font or a default row height when the worksheet
    omits it. Columns and horizontal offsets are never consulted here.
    """
    def __init__(self, root: ET.Element):
        self.default = None
        self.indices = []
        self.prefix = [0]
        fmt = first_child(root, "sheetFormatPr")
        if fmt is None or "defaultRowHeight" not in fmt.attrib:
            return
        try:
            default = self.height(fmt.attrib["defaultRowHeight"])
            zero = fmt.get("zeroHeight") in {"1", "true"}
            self.default = 0 if zero else default
            overrides = {}
            data = first_child(root, "sheetData")
            if data is not None:
                for row in data:
                    if local_name(row.tag) != "row":
                        continue
                    index = int(row.attrib["r"]) - 1
                    if not 0 <= index < 1048576:
                        raise ValueError("invalid row index")
                    hidden = row.get("hidden")
                    if hidden in {"1", "true"}:
                        h = 0
                    elif zero and hidden is None and "ht" not in row.attrib:
                        h = 0
                    else:
                        h = self.height(row.attrib["ht"]) if "ht" in row.attrib else default
                    overrides[index] = h - self.default
            self.indices = sorted(overrides)
            for index in self.indices:
                self.prefix.append(self.prefix[-1] + overrides[index])
        except (KeyError, ValueError, InvalidOperation, OverflowError):
            self.default = None

    @staticmethod
    def height(points: str) -> int:
        value = Decimal(points)
        if not value.is_finite() or value < 0 or value > 409.5:
            raise ValueError("invalid saved row height")
        return round(value * EMUS_PER_POINT)

    def marker_y(self, marker: ET.Element | None) -> int | None:
        if marker is None:
            return None
        row, offset = first_child(marker, "row"), first_child(marker, "rowOff")
        if row is None or offset is None:
            return None
        try:
            index, off = int(row.text), int(offset.text)
        except (TypeError, ValueError):
            return None
        if not 0 <= index < 1048576:
            return None
        if index == 0:
            return off
        if self.default is None:
            return None
        return index * self.default + self.prefix[bisect_left(self.indices, index)] + off


class HorizontalColumnMetrics:
    """OOXML reference column widths; MDW=7 is an explicit estimate.

    A picture supplies the scale, and individual object spans must agree
    with their saved dimensions before any horizontal translation.
    """
    MDW = 7
    LIMIT = 16384

    @classmethod
    def width_pixels(cls, width: str) -> int:
        value = Decimal(width)
        if not value.is_finite() or not 0 <= value <= 255:
            raise ValueError("invalid column width")
        return int((value * 256 + 128 // cls.MDW) * cls.MDW / 256)

    def __init__(self, root: ET.Element):
        self.prefix = None
        self.default_source = "unavailable"
        try:
            fmt = first_child(root, "sheetFormatPr")
            if fmt is not None and "defaultColWidth" in fmt.attrib:
                default = self.width_pixels(fmt.attrib["defaultColWidth"])
                self.default_source = "defaultColWidth"
            else:
                base = int(fmt.get("baseColWidth", "8")) if fmt is not None else 8
                if not 0 <= base <= 255:
                    raise ValueError("invalid baseColWidth")
                default = base * self.MDW + 5
                self.default_source = "baseColWidth_plus_padding_reference"
            widths = [default] * self.LIMIT
            cols = first_child(root, "cols")
            if cols is not None:
                for col in cols:
                    if local_name(col.tag) != "col":
                        continue
                    lo, hi = int(col.attrib["min"]), int(col.attrib["max"])
                    if not 1 <= lo <= hi <= self.LIMIT:
                        raise ValueError("invalid column range")
                    width = (0 if col.get("hidden") in {"1", "true"} else
                             self.width_pixels(col.attrib["width"]) if "width" in col.attrib
                             else default)
                    widths[lo-1:hi] = [width] * (hi-lo+1)
            prefix = [0]
            for width in widths:
                prefix.append(prefix[-1] + width * EMUS_PER_PIXEL)
            self.prefix = prefix
        except (KeyError, ValueError, InvalidOperation, OverflowError):
            self.default_source = "invalid_column_metrics"

    def marker_x(self, marker: ET.Element | None) -> int | None:
        if marker is None or self.prefix is None:
            return None
        col, offset = first_child(marker, "col"), first_child(marker, "colOff")
        if col is None or offset is None:
            return None
        try:
            index, off = int(col.text), int(offset.text)
        except (TypeError, ValueError):
            return None
        if not 0 <= index < self.LIMIT:
            return None
        return self.prefix[index] + off


def horizontal_anchor_info(anchor: ET.Element, saved_x: int,
                           columns: HorizontalColumnMetrics | None) -> dict:
    info = {"source": "absoluteAnchor" if local_name(anchor.tag) == "absoluteAnchor" else "xfrm",
            "saved_x_emu": saved_x, "resolved_x_emu": saved_x,
            "edit_as": anchor.get("editAs")}
    if columns is not None:
        info["column_width_source"] = columns.default_source
        info["reference_mdw_px"] = columns.MDW
    if local_name(anchor.tag) == "absoluteAnchor" or columns is None:
        return info
    start = columns.marker_x(first_child(anchor, "from"))
    end = columns.marker_x(first_child(anchor, "to"))
    if start is not None:
        info["anchor_x_emu"] = start
    if end is not None:
        info["anchor_end_x_emu"] = end
    return info


def anchor_y(anchor: ET.Element, width: int, height: int, angle: float,
             rows: VerticalRowMetrics | None) -> tuple[int, dict]:
    """Resolve vertical position independently of a:xfrm/a:off@y.

    For cell anchors the start row and offset determine the Y position,
    even if the end span differs from the saved height. An unambiguous
    rotated outer span can locate the center of the unrotated box.
    Absolute anchors use their own y. Never read or fall back to saved off@y.
    """
    kind = local_name(anchor.tag)
    if kind == "absoluteAnchor":
        y = emu_attribute(first_child(anchor, "pos"), "y", "xdr:pos")
        return y, {"source": "absoluteAnchor", "resolved_y_emu": y,
                   "saved_y_emu": y}
    if rows is None:
        raise SpatialXlsxError("missing worksheet row geometry for Y")
    start = rows.marker_y(first_child(anchor, "from"))
    if start is None:
        raise SpatialXlsxError("cannot resolve Y from row/rowOff and saved row heights")
    y = start
    info = {"source": "row_anchor", "anchor_y_emu": start}
    if kind == "twoCellAnchor":
        end = rows.marker_y(first_child(anchor, "to"))
        if end is not None and end > start:
            span = end - start
            info["anchor_span_emu"] = span
            info["anchor_end_y_emu"] = end
            rotated_span = abs(width * sin(radians(angle))) + abs(height * cos(radians(angle)))
            # The start marker is authoritative. Only shift by half the
            # difference when the markers clearly describe a rotated AABB.
            if abs(span - height) > EMUS_PER_PIXEL and abs(span - rotated_span) <= EMUS_PER_PIXEL:
                y = round((start + end - height) / 2)
                info["source"] = "rotated_row_anchor"
            elif abs(span - height) > EMUS_PER_PIXEL:
                info["reason"] = "row span differs from saved height; start marker retained"
        else:
            info["reason"] = "end marker unavailable or invalid; start marker retained"
    info["resolved_y_emu"] = y
    return y, info


def object_transform(node: ET.Element) -> ET.Element | None:
    """Only the top-level object's own transform, never a nested child's."""
    props = first_child(node, "spPr")
    if props is None:
        props = first_child(node, "grpSpPr")
    if local_name(node.tag) == "graphicFrame":
        return first_child(node, "xfrm")
    return first_child(props, "xfrm")


def emu_attribute(node: ET.Element | None, key: str, label: str) -> int:
    if node is None or key not in node.attrib:
        raise SpatialXlsxError(f"missing {label}@{key}")
    try:
        return int(node.attrib[key])
    except ValueError as error:
        raise SpatialXlsxError(f"invalid integer {label}@{key}: {node.attrib[key]!r}") from error


def saved_horizontal_geometry(anchor: ET.Element, node: ET.Element) -> tuple[int, int, int, str]:
    """Read X and original width/height, independently of vertical position.

    Zero X is valid. No Y field or column-width estimate is used here.
    """
    if local_name(anchor.tag) == "absoluteAnchor":
        off, ext = first_child(anchor, "pos"), first_child(anchor, "ext")
        off_label, ext_label, source = "xdr:pos", "xdr:ext", "absoluteAnchor"
    else:
        xfrm = object_transform(node)
        if xfrm is None:
            raise SpatialXlsxError("missing top-level xfrm (absolute EMU geometry required)")
        off, ext = first_child(xfrm, "off"), first_child(xfrm, "ext")
        off_label, ext_label, source = "xfrm/off", "xfrm/ext", "xfrm"
    x = emu_attribute(off, "x", off_label)
    width = emu_attribute(ext, "cx", ext_label)
    height = emu_attribute(ext, "cy", ext_label)
    if width <= 0 or height <= 0:
        raise SpatialXlsxError(f"{ext_label} must have positive cx and cy")
    return x, width, height, source


def rotation_degrees(node: ET.Element) -> float:
    xfrm = object_transform(node)
    try:
        return int(xfrm.get("rot", "0")) / 60000 if xfrm is not None else 0.0
    except ValueError as error:
        raise SpatialXlsxError("invalid integer xfrm@rot") from error


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


def drawing_objects(root: ET.Element, palette: dict[str, str],
                    fills: list[ET.Element], lines: list[ET.Element],
                    theme_fonts: dict[str, dict[str, str]] | None = None,
                    drawing_rels: dict[str, tuple[str, str]] | None = None,
                    drawing_part: str = "", members: set[str] | None = None,
                    sheet_name: str = "", row_metrics: VerticalRowMetrics | None = None,
                    column_metrics: HorizontalColumnMetrics | None = None) -> list[dict]:
    color_map = first_child(root, "clrMap")
    override = first_child(first_child(root, "clrMapOvr"), "overrideClrMapping")
    if color_map is not None or override is not None:
        palette = mapped_theme_palette(palette, override if override is not None else color_map)
    objects = []
    for anchor in root:
        if local_name(anchor.tag) not in {"oneCellAnchor", "twoCellAnchor", "absoluteAnchor"}:
            continue
        for element in anchor:
            tag = local_name(element.tag)
            if tag not in {"pic", "sp", "cxnSp", "grpSp", "graphicFrame"}:
                continue
            nv = find_descendant(element, "cNvPr")
            name = nv.get("name", "未命名对象") if nv is not None else "未命名对象"
            kind = "image" if tag == "pic" else "shape"
            try:
                x, width, height, geometry_source = saved_horizontal_geometry(anchor, element)
                angle = rotation_degrees(element)
                y, vertical = anchor_y(anchor, width, height, angle, row_metrics)
                # Saved Y is diagnostic only, never a cell-anchor fallback.
                if geometry_source == "xfrm":
                    off = first_child(object_transform(element), "off")
                    try:
                        vertical["saved_y_emu"] = int(off.get("y", "")) if off is not None else None
                    except ValueError:
                        vertical["saved_y_emu"] = None
                vertical["edit_as"] = anchor.get("editAs")
                rect = (x, y, x + width, y + height)
            except SpatialXlsxError as error:
                raise SpatialXlsxError(
                    f"Sheet '{sheet_name}', object '{name}' ({local_name(anchor.tag)}, "
                    f"{drawing_part}): {error}; X uses saved geometry, "
                    "Y requires a resolvable row or absolute anchor."
                ) from error
            x1, y1, x2, y2 = rect
            obj = {
                "type": kind,
                "name": name,
                "anchor": local_name(anchor.tag),
                "geometry_source": geometry_source,
                "vertical_geometry": vertical,
                "horizontal_geometry": horizontal_anchor_info(anchor, x, column_metrics),
                "bounds_emu": {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
                "width_px": round((x2 - x1) / EMUS_PER_PIXEL, 3),
                "height_px": round((y2 - y1) / EMUS_PER_PIXEL, 3),
                "rotation_degrees": angle,
                "vertices_px": vertices_from_rect(rect, angle),
            }
            if kind == "image":
                # Raw OOXML percentages (100000 = 100%); diagnostic only.
                crop = first_child(first_child(element, "blipFill"), "srcRect")
                obj["picture_crop"] = {
                    key: crop.get(key, "0") if crop is not None else "0"
                    for key in ("l", "t", "r", "b")
                }
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


def normalize_sheet_y(objects: list[dict]) -> None:
    """One picture-derived vertical position mapping per worksheet.

    Preserve X, extents, rotation and the existing picture origin.
    Calibrate only when the picture has a positive, independent two-cell
    vertical span and no rotation. Otherwise keep the prior sheet geometry
    and explicitly diagnose the unavailable calibration. Absolute anchors
    have no row markers; map their saved relative Y using the picture's
    saved Y when available, otherwise leave the entire sheet uncalibrated
    rather than mix incompatible reference frames.
    """
    images = [obj for obj in objects if obj["type"] == "image"]
    if len(images) != 1:
        return  # Existing workbook validation handles invalid image counts.
    picture = images[0]
    v = picture["vertical_geometry"]
    start = v.get("anchor_y_emu")
    span = v.get("anchor_span_emu")
    height = picture["bounds_emu"]["height"]
    origin = picture["bounds_emu"]["y"]
    absolute = [o for o in objects if o["anchor"] == "absoluteAnchor"]
    saved_origin = v.get("saved_y_emu")
    reason = None
    if picture["anchor"] != "twoCellAnchor" or start is None or not span or span <= 0:
        reason = "picture has no positive independent two-cell Y span"
    elif picture["rotation_degrees"] % 360 != 0:
        reason = "rotated picture cannot establish an unambiguous vertical axis"
    elif absolute and saved_origin is None:
        reason = "absolute anchors require saved picture Y for a common reference"
    if reason:
        for obj in objects:
            obj["vertical_geometry"].update(calibration_status="unavailable",
                                            calibration_reason=reason)
        return
    ratio = Fraction(height, span)
    for obj in objects:
        b = obj["bounds_emu"]
        info = obj["vertical_geometry"]
        raw_y = b["y"]
        if obj is picture:
            y = origin
        elif obj["anchor"] == "absoluteAnchor":
            # Absolute coordinates already use the target EMU system.
            y = origin + raw_y - saved_origin
        else:
            anchor_start = info["anchor_y_emu"]
            y = origin + round((anchor_start - start) * ratio)
            obj_span = info.get("anchor_span_emu")
            angle = radians(obj["rotation_degrees"])
            rotated_span = abs(b["width"] * sin(angle)) + abs(b["height"] * cos(angle))
            # Test the calibrated span before interpreting a rotated AABB.
            # Never scale the unrotated box height or its rotation correction.
            if obj_span is not None:
                mapped_span = float(obj_span * ratio)
                if (abs(mapped_span - b["height"]) > EMUS_PER_PIXEL
                        and abs(mapped_span - rotated_span) <= EMUS_PER_PIXEL):
                    y = origin + round((anchor_start - start) * ratio
                                       + obj_span * ratio / 2 - Fraction(b["height"], 2))
                    info["rotation_anchor"] = "rotated_outer_bounds"
        b["y"] = y
        obj["vertices_px"] = vertices_from_rect(
            (b["x"], y, b["x"] + b["width"], y + b["height"]), obj["rotation_degrees"])
        info.update(
            source="absoluteAnchor" if obj["anchor"] == "absoluteAnchor" else "normalized_row_anchor",
            uncalibrated_y_emu=raw_y, resolved_y_emu=y,
            relative_y_emu=y-origin, calibration_status="applied",
            calibration_factor=float(ratio), picture_anchor_start_emu=start,
            picture_anchor_end_emu=start+span, picture_height_emu=height,
        )


def crosscheck_sheet_x(objects: list[dict]) -> None:
    """Use both horizontal endpoints to corroborate a translation, not size.

    Picture, absolute anchors and non-target kinds retain saved X. For a
    two-cell shape, both candidate unrotated left edges must agree within
    one reference pixel. A rotated bounding box is accepted only when its
    span uniquely fits the rotated width rather than the saved width.
    Invalid/ambiguous evidence preserves saved X for that object.
    """
    images = [o for o in objects if o["type"] == "image"]
    if len(images) != 1:
        return
    picture = images[0]
    pic = picture["horizontal_geometry"]
    start, end = pic.get("anchor_x_emu"), pic.get("anchor_end_x_emu")
    origin, width = picture["bounds_emu"]["x"], picture["bounds_emu"]["width"]
    ratio = (Fraction(width, end-start)
             if picture["anchor"] == "twoCellAnchor" and start is not None
             and end is not None and end > start
             and picture["rotation_degrees"] % 360 == 0 else None)
    for obj in objects:
        b = obj["bounds_emu"]
        h = obj["horizontal_geometry"]
        raw = b["x"]
        h.update(calibration_status="retained", correction_emu=0,
                 tolerance_emu=EMUS_PER_PIXEL, relative_x_emu=raw-origin)
        if ratio is not None:
            h.update(calibration_factor=float(ratio), picture_anchor_start_emu=start,
                     picture_anchor_end_emu=end, picture_width_emu=width)
        if obj is picture:
            h["reason"] = "picture reference origin retained"
            continue
        if obj.get("shape_kind") not in {"textbox", "rectangle", "ellipse"}:
            h["reason"] = "non-target shape retained"
            continue
        if ratio is None:
            h["reason"] = "picture lacks positive unrotated two-cell horizontal span"
            continue
        a, z = h.get("anchor_x_emu"), h.get("anchor_end_x_emu")
        if obj["anchor"] != "twoCellAnchor" or a is None or z is None or z <= a:
            h["reason"] = "independent left/right anchors unavailable"
            continue
        left, right = origin+(a-start)*ratio, origin+(z-start)*ratio
        span = right-left
        saved_width = b["width"]
        angle = radians(obj["rotation_degrees"])
        rotated_width = abs(saved_width*cos(angle))+abs(b["height"]*sin(angle))
        normal_match = abs(span-saved_width) <= EMUS_PER_PIXEL
        rotated_match = abs(float(span)-rotated_width) <= EMUS_PER_PIXEL
        # For a rotated AABB, translate both edges to the unrotated box.
        # If both interpretations fit but imply different positions, retain X.
        if not normal_match and rotated_match:
            outer = Fraction(round(rotated_width))
            left += (outer-saved_width)/2
            right -= (outer-saved_width)/2
            h["anchor_interpretation"] = "rotated_outer_bounds"
        elif normal_match and rotated_match and abs(rotated_width-saved_width) > 1:
            h["reason"] = "ambiguous rotated versus unrotated anchor span"
            continue
        else:
            h["anchor_interpretation"] = "unrotated_bounds"
        right -= saved_width
        candidate = (left+right)/2
        h.update(left_candidate_x_emu=round(left), right_candidate_x_emu=round(right),
                 center_candidate_x_emu=round(candidate), anchor_disagreement_emu=round(abs(left-right)),
                 candidate_delta_emu=round(candidate)-raw)
        if abs(left-right) > EMUS_PER_PIXEL:
            h["reason"] = "left/right candidates disagree beyond one reference pixel"
            continue
        x = round(candidate)
        b["x"] = x
        y = b["y"]
        obj["vertices_px"] = vertices_from_rect(
            (x, y, x+b["width"], y+b["height"]), obj["rotation_degrees"])
        h.update(source="crosschecked_column_anchor", calibration_status="applied",
                 resolved_x_emu=x, correction_emu=x-raw, relative_x_emu=x-origin,
                 reason="left/right candidates agree within tolerance")


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
                # Independent X auxiliary metrics never modify Y.
                if sheet_part not in z.namelist():
                    raise SpatialXlsxError(f"Missing worksheet part for {name}: {sheet_part}")
                sheet_root = ET.fromstring(z.read(sheet_part))
                row_metrics = VerticalRowMetrics(sheet_root)
                column_metrics = HorizontalColumnMetrics(sheet_root)
                objects = []
                for rel_type, target in relationships(z, sheet_part).values():
                    if not rel_type.endswith("/drawing"):
                        continue
                    drawing_part = resolve_part(sheet_part, target)
                    drawing = ET.fromstring(z.read(drawing_part))
                    objects.extend(drawing_objects(
                        drawing, palette, fills, lines,
                        theme_fonts=fonts,
                        drawing_rels=relationships(z, drawing_part),
                        drawing_part=drawing_part, members=set(z.namelist()),
                        sheet_name=name, row_metrics=row_metrics, column_metrics=column_metrics,
                    ))
                normalize_sheet_y(objects)
                crosscheck_sheet_x(objects)
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
            lines.append(f"    几何来源: {obj.get('geometry_source', 'unknown')}")
            horizontal = obj.get("horizontal_geometry", {})
            if horizontal:
                lines.append(
                    f"    X来源: {horizontal['source']} "
                    f"saved={horizontal['saved_x_emu']} "
                    f"from={horizontal.get('anchor_x_emu')} to={horizontal.get('anchor_end_x_emu')} "
                    f"resolved={horizontal['resolved_x_emu']} EMU "
                    f"MDW={horizontal.get('reference_mdw_px')} "
                    f"column_width={horizontal.get('column_width_source')}")
                if "calibration_factor" in horizontal:
                    lines.append(f"    X校核: k={horizontal['calibration_factor']:.9f} "
                                 f"left={horizontal.get('left_candidate_x_emu')} "
                                 f"right={horizontal.get('right_candidate_x_emu')} "
                                 f"center={horizontal.get('center_candidate_x_emu')} "
                                 f"disagreement={horizontal.get('anchor_disagreement_emu')} "
                                 f"correction={horizontal.get('correction_emu', 0)} EMU")
                if "reason" in horizontal:
                    lines.append(f"    X决策: {horizontal['calibration_status']} ({horizontal['reason']})")
            vertical = obj.get("vertical_geometry", {})
            if vertical:
                resolved = vertical["resolved_y_emu"]
                start = vertical.get("anchor_y_emu", resolved)
                reason = vertical.get("reason", "")
                lines.append(f"    Y来源: {vertical['source']} "
                             f"saved={vertical.get('saved_y_emu')} anchor={start} "
                             f"resolved={resolved} EMU"
                             + (f" ({reason})" if reason else ""))
                if vertical.get("calibration_status") == "applied":
                    lines.append(
                        f"    Y校准: k={vertical['calibration_factor']:.9f} "
                        f"picture_from={vertical['picture_anchor_start_emu']} "
                        f"picture_to={vertical['picture_anchor_end_emu']} "
                        f"picture_height={vertical['picture_height_emu']} "
                        f"before={vertical['uncalibrated_y_emu']} "
                        f"relative={vertical['relative_y_emu']} EMU")
                elif vertical.get("calibration_status") == "unavailable":
                    lines.append("    Y校准未启用: " + vertical["calibration_reason"])
            if obj["type"] == "image" and "picture_crop" in obj:
                crop = obj["picture_crop"]
                lines.append("    图片裁剪 srcRect: " + " ".join(
                    f"{key}={value}" for key, value in crop.items()))
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
