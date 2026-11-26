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


def parse_theme(z: ZipFile) -> tuple[dict[str, str], list[ET.Element], list[ET.Element]]:
    palette = DEFAULT_THEME.copy()
    fills: list[ET.Element] = []
    lines: list[ET.Element] = []
    if "xl/theme/theme1.xml" not in z.namelist():
        return palette, fills, lines
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
    return palette, fills, lines


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


def get_color(node: ET.Element | None, palette: dict[str, str]) -> str | None:
    if node is None:
        return None
    for child in node.iter():
        kind = local_name(child.tag)
        if kind == "srgbClr":
            rgb = child.get("val")
        elif kind == "schemeClr":
            rgb = palette.get(child.get("val", ""))
        elif kind == "sysClr":
            rgb = child.get("lastClr") or child.get("val")
        else:
            continue
        if not rgb or len(rgb) != 6:
            continue
        mod, off = 100000, 0
        for adjust in child:
            if local_name(adjust.tag) == "lumMod":
                mod = int(adjust.get("val", "100000"))
            elif local_name(adjust.tag) == "lumOff":
                off = int(adjust.get("val", "0"))
        return "#" + apply_luminance(rgb.upper(), mod, off)
    return None


def style_color(node: ET.Element | None, style: ET.Element | None, kind: str,
                palette: dict[str, str], fills: list[ET.Element],
                lines: list[ET.Element]) -> str:
    if node is not None:
        if first_child(node, "noFill") is not None:
            return "无/透明"
        solid = first_child(node, "solidFill")
        direct = get_color(solid, palette)
        if direct:
            return direct
        if kind == "text":
            for child in node.iter():
                if local_name(child.tag) == "solidFill":
                    value = get_color(child, palette)
                    if value:
                        return value
    if style is not None:
        ref_tag = {"fill": "fillRef", "line": "lnRef", "text": "fontRef"}[kind]
        ref = first_child(style, ref_tag)
        if ref is not None:
            color = get_color(ref, palette)
            if color:
                return color
            try:
                idx = int(ref.get("idx", "0"))
            except ValueError:
                idx = 0
            style_list = fills if kind == "fill" else lines
            if kind != "text" and 0 < idx <= len(style_list):
                color = get_color(style_list[idx - 1], palette)
                if color:
                    return color
    return "#000000" if kind == "text" else "无/透明"


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


def shape_text_layout(node: ET.Element) -> list[dict]:
    """Preserve per-run DrawingML font sizes in points (a:rPr/@sz is 1/100pt).

    Prioritize run properties, then paragraph defaults and the text-body
    list-style default. Fallback to Excel's usual 11 pt only when unspecified.
    Geometry consumers use the same reference-pixel scale as the XLSX image.
    """
    body = first_child(node, "txBody")
    if body is None:
        return []
    style = first_child(body, "lstStyle")
    default_p = first_child(style, "defPPr")
    body_default = first_child(default_p, "defRPr")

    def pt(*properties: ET.Element | None) -> float:
        for prop in properties:
            if prop is not None and prop.get("sz"):
                try:
                    value = int(prop.get("sz", "0")) / 100
                except ValueError:
                    continue
                if 0 < value <= 500:
                    return value
        return 11.0

    lines = []
    for paragraph in body:
        if local_name(paragraph.tag) != "p":
            continue
        paragraph_props = first_child(paragraph, "pPr")
        paragraph_default = first_child(paragraph_props, "defRPr")
        end_props = first_child(paragraph, "endParaRPr")
        runs = []
        for child in paragraph:
            if local_name(child.tag) not in ("r", "fld"):
                continue
            text = first_child(child, "t")
            if text is None or not text.text:
                continue
            properties = first_child(child, "rPr")
            font_size = pt(properties, paragraph_default, body_default, end_props)
            runs.append({"text": text.text, "font_pt": font_size})
        if not runs:
            # A paragraph without explicit runs can still have an end style.
            value = "".join(p.text or "" for p in paragraph.iter() if local_name(p.tag) == "t")
            if value:
                runs = [{"text": value, "font_pt": pt(paragraph_default, end_props, body_default)}]
        if runs:
            lines.append({"runs": runs})
    return lines


def drawing_objects(root: ET.Element, metrics: SheetMetrics, palette: dict[str, str],
                    fills: list[ET.Element], lines: list[ET.Element],
                    drawing_rels: dict[str, tuple[str, str]] | None = None,
                    drawing_part: str = "", members: set[str] | None = None) -> list[dict]:
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
                obj["text_layout"] = shape_text_layout(element)
                obj["alt_text"] = shape_alternative_text(element)
                props = first_child(element, "spPr")
                if props is None:
                    props = first_child(element, "grpSpPr")
                outline = first_child(props, "ln")
                style = first_child(element, "style")
                text = first_child(element, "txBody")
                obj["colors"] = {
                    "fill": style_color(props, style, "fill", palette, fills, lines),
                    "outline": style_color(outline, style, "line", palette, fills, lines),
                    "text": style_color(text, style, "text", palette, fills, lines),
                }
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
                    f"轮廓={colors['outline']} 文字={colors['text']}"
                )
    return "\n".join(lines)
