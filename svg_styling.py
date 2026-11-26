"""Validated and durable updates to the two local SVGs of a CAD legend item.

This edits only the two files resolved by the *server-side* XLSX ellipse
catalog, never by a client-supplied filename. Updates preserve transparent
areas and use atomic per-file replacement with rollback if the pair fails.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile
from threading import Lock
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

if __package__:
    from .cad_svg_catalog import build_ellipse_svg_catalog, svg_directory
else:
    from cad_svg_catalog import build_ellipse_svg_catalog, svg_directory

SVG_LIMIT = 8 * 1024 * 1024
PALETTE = (
    "#4F99CF", "#E41A1C", "#4DAF4A", "#FF7F00", "#2C3E50",
    "#333333", "#3C5488", "#E64B35", "#00A087", "#3A3935",
    "#1F77B4", "#FF7F0E", "#2CA02C", "#9A8B7A", "#7E8B96",
    "#A6998A", "#D1C7BD",
)
LINE_WIDTHS = ("0.75", "1.5", "2.25", "3", "3.75")
LINE_TYPES = {"-·": "8 3 1 3", "--": "8 4"}
_LOCK = Lock()
CSS_PAINT = re.compile(r"(?<![\w-])(stroke|fill)\s*:\s*([^;{}]+)", re.I)
STYLE_PAINT = re.compile(r"^(?:stroke|fill)\s*:\s*(.*)$", re.I)
NON_PAINT = {"none", "transparent", "inherit", "initial", "unset", "currentcolor"}
SVG_NS = "http://www.w3.org/2000/svg"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _painted(value: str | None) -> bool:
    return bool(value and value.strip().lower() not in NON_PAINT
                and not value.strip().lower().startswith("url("))


def _apply_style(attrs: str, operation: str, replacement: str) -> str:
    """Change explicit CSS paint without introducing any paint into empty space."""
    declarations = []
    changed_stroke = False
    for component in attrs.split(";"):
        name, sep, value = component.partition(":")
        if not sep:
            if component.strip():
                declarations.append(component)
            continue
        key = name.strip().lower()
        if key in ("stroke", "fill") and operation == "color" and _painted(value):
            value = replacement
        if key == "stroke" and _painted(value):
            changed_stroke = True
        if key in ("stroke-width", "stroke-dasharray") and operation in ("width", "dash"):
            target = "stroke-width" if operation == "width" else "stroke-dasharray"
            if key == target:
                value = replacement
        declarations.append(name + ":" + value)
    if changed_stroke and operation in ("width", "dash"):
        target = "stroke-width" if operation == "width" else "stroke-dasharray"
        if not any(x.strip().lower().startswith(target + ":") for x in declarations):
            declarations.append(target + ":" + replacement)
    return ";".join(declarations)


def _apply_css_stylesheet(source: str, operation: str, replacement: str) -> str:
    """Constrain changes to actual CSS rule declarations, never selectors."""
    def rule(match: re.Match) -> str:
        start, body, end = match.groups()
        if not CSS_PAINT.search(body):
            return match.group(0)
        def paint(m: re.Match) -> str:
            kind, raw = m.groups()
            if operation == "color" and _painted(raw):
                return kind + ":" + replacement
            return m.group(0)
        new_body = CSS_PAINT.sub(paint, body)
        has_stroke = any(m.group(1).lower() == "stroke" and _painted(m.group(2))
                         for m in CSS_PAINT.finditer(body))
        if has_stroke and operation in ("width", "dash"):
            target = "stroke-width" if operation == "width" else "stroke-dasharray"
            pattern = re.compile(r"(?<![\w-])" + target + r"\s*:\s*[^;{}]+", re.I)
            if pattern.search(new_body):
                new_body = pattern.sub(target + ":" + replacement, new_body)
            else:
                new_body += ";" + target + ":" + replacement
        return start + new_body + end
    return re.sub(r"([^{}]*\{)([^{}]*)(\})", rule, source)


def restyle_svg(content: bytes, operation: str, value: str) -> bytes:
    """Style explicit painted SVG geometry; do not add white/opaque backgrounds."""
    if len(content) > SVG_LIMIT or b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise ValueError("Unsupported or oversized SVG input")
    if operation == "color":
        if value not in PALETTE:
            raise ValueError("Color is not in the approved palette")
        replacement = value
    elif operation == "width":
        if str(value) not in LINE_WIDTHS:
            raise ValueError("Invalid SVG stroke width")
        replacement = str(value)
    elif operation == "dash":
        if value not in LINE_TYPES:
            raise ValueError("Invalid SVG line pattern")
        replacement = LINE_TYPES[value]
    else:
        raise ValueError("Unknown SVG style operation")
    root = ET.fromstring(content)
    if _local(root.tag).lower() != "svg":
        raise ValueError("Not an SVG document")
    # Keep ordinary SVG namespaces and references stable after reserialization.
    ET.register_namespace("", SVG_NS)
    for elem in root.iter():
        tag = _local(elem.tag).lower()
        if tag == "style" and elem.text:
            elem.text = _apply_css_stylesheet(elem.text, operation, replacement)
            continue
        if tag in ("svg", "defs", "metadata", "title", "desc", "clippath", "mask", "filter"):
            continue
        explicit_stroke = _painted(elem.get("stroke"))
        if operation == "color":
            for name in ("stroke", "fill"):
                if _painted(elem.get(name)):
                    elem.set(name, replacement)
        if elem.get("style"):
            original = elem.get("style", "")
            explicit_stroke = explicit_stroke or any(
                x.strip().lower().startswith("stroke:") and _painted(x.split(":", 1)[1])
                for x in original.split(";"))
            elem.set("style", _apply_style(original, operation, replacement))
        if explicit_stroke and operation in ("width", "dash"):
            elem.set("stroke-width" if operation == "width" else "stroke-dasharray", replacement)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _catalog_path(asset_dir: Path, folder: str, url: str) -> Path:
    base = svg_directory(asset_dir, folder)
    if base is None:
        raise ValueError("Invalid SVG catalog folder")
    prefix = "/viewer/assets/"
    path = urlsplit(url).path
    if not path.startswith(prefix):
        raise ValueError("Invalid SVG catalog URL")
    parts = path[len(prefix):].split("/")
    if len(parts) != 2 or unquote(parts[0]) != folder:
        raise ValueError("SVG catalog path outside the selected folder")
    name = unquote(parts[1])
    if Path(name).name != name or not name.lower().endswith(".svg"):
        raise ValueError("Invalid SVG filename")
    target = base / name
    if target.is_symlink() or not target.is_file() or target.parent.resolve() != base.resolve():
        raise ValueError("SVG file unavailable or unsafe")
    return target


def _atomic_pair_replace(updates: dict[Path, bytes]) -> None:
    originals = {}
    temp_paths = {}
    replaced = []
    try:
        for path, contents in updates.items():
            old = path.read_bytes()
            originals[path] = old
            with tempfile.NamedTemporaryFile("wb", dir=path.parent,
                                             prefix=".svg-update-", suffix=".tmp",
                                             delete=False) as temp:
                temp.write(contents)
                temp.flush()
                os.fsync(temp.fileno())
                temp_paths[path] = Path(temp.name)
            os.chmod(temp_paths[path], path.stat().st_mode)
        for path in updates:
            os.replace(temp_paths[path], path)
            replaced.append(path)
    except Exception:
        for path in reversed(replaced):
            # Restore files if a second replacement fails.
            with tempfile.NamedTemporaryFile("wb", dir=path.parent,
                                             prefix=".svg-rollback-", delete=False) as temp:
                temp.write(originals[path])
                rollback = Path(temp.name)
            os.replace(rollback, path)
        raise
    finally:
        for temp in temp_paths.values():
            temp.unlink(missing_ok=True)


def update_svg_pair(asset_dir: Path, sheets: list[dict], layer: int,
                    object_index: int, date: str, axis: str,
                    operation: str, value: str) -> dict[str, str]:
    """Recompute the trusted catalog then update only its matched SVG pair."""
    if not re.fullmatch(r"\d{14}", str(date)) or axis not in ("X", "Y", "Z"):
        raise ValueError("Invalid timestamp or axis")
    with _LOCK:
        catalog = build_ellipse_svg_catalog(asset_dir, sheets, layer, object_index)
        pair = catalog["pairs"].get(date, {}).get(axis)
        if not pair or not pair.get("psd") or not pair.get("octave"):
            raise ValueError("Requested ellipse/axis has no SVG pair")
        paths = [_catalog_path(asset_dir, catalog["folder"], pair[key])
                 for key in ("psd", "octave")]
        if paths[0] == paths[1]:
            raise ValueError("The two SVG files must be distinct")
        updates = {path: restyle_svg(path.read_bytes(), operation, value) for path in paths}
        _atomic_pair_replace(updates)
        return pair
