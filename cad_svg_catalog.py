"""Resolve right-click ellipse menus to SVG pairs inside its enclosing textbox folder.

The client supplies only validated sheet/shape indices; it cannot choose an
arbitrary filesystem path. The folder name comes from XLSX DrawingML textbox
text, and all SVG filenames are enumerated at request time.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re
from urllib.parse import quote

if __package__:
    from .cad_validation import Rectangle, circle_relation, intersecting_rectangles
else:
    from cad_validation import Rectangle, circle_relation, intersecting_rectangles

TIMESTAMP = re.compile(r"_(\d{14})_")
CSV_TIMESTAMP = re.compile(r"(?<![0-9])[0-9]{14}(?![0-9])")


def csv_time_rank(filename: str, date: str) -> float | None:
    """Exact time first; otherwise strictly earlier by less than 60 seconds."""
    try:
        selected = datetime.strptime(date, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    matches = []
    for token in CSV_TIMESTAMP.findall(filename):
        try:
            candidate = datetime.strptime(token, "%Y%m%d%H%M%S")
        except ValueError:
            continue
        delta = (selected - candidate).total_seconds()
        if 0 <= delta < 60:
            matches.append(delta)
    return min(matches, default=None)


# Match a standalone PSD marker, never a substring of the equipment name.
PSD_TOKEN = re.compile(r"(?<![A-Za-z0-9])PSD(?![A-Za-z0-9])", re.IGNORECASE)


def csv_companion_key(filename: str, *, psd: bool = False) -> str | None:
    """Ignore only independent 14-digit timestamps; retain all other text."""
    key = CSV_TIMESTAMP.sub("", filename)
    if psd:
        key, count = PSD_TOKEN.subn("Time", key)
        if count != 1:
            return None
    return key.casefold()


def select_csv_files(ranked: list[tuple[float, Path]], axis: str) -> list[Path]:
    """Keep all exact matches and at most one verified earlier Time companion."""
    eligible = [(delta, p) for delta, p in ranked
                if axis in [m.group(1).upper() for m in AXIS.finditer(p.name)]]
    exact = [p for delta, p in eligible if delta == 0]
    expected = {key for p in exact
                if (key := csv_companion_key(p.name, psd=True)) is not None}
    # ranked is already ordered by delta, then filename. No exact PSD
    # reference means no earlier companion can be safely selected.
    earlier = next((p for delta, p in eligible if delta > 0
                    and csv_companion_key(p.name) in expected), None)
    return exact + ([earlier] if earlier is not None else [])


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
    """Any contact (inside, partial, tangency) qualifies as rectangle search."""
    found = intersecting_rectangles(objects, ellipse)
    if len(found) > 1:
        raise ValueError("CAD ellipse intersects multiple rectangles")
    return found[0] if found else None


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
    label = lambda obj: ((obj.get("text") or obj.get("name") or "").strip()
                         if obj is not None else "")
    visible = lambda obj: ((obj.get("text") or "").strip() if obj is not None else "")
    folder_name = label(textbox)
    rectangle_name = label(rectangle)
    ellipse_name = label(ellipse)
    identifier = rectangle_name if rectangle is not None else ellipse_name
    # Outside any rectangle, match the PARENT TEXTBOX's name in the
    # filename, but still show the selected sensor name in the legend.
    search_identifier = visible(rectangle) if rectangle is not None else folder_name
    root = svg_directory(asset_dir, folder_name)
    result = {
        "folder": folder_name,
        "sheet": sheets[layer_index]["sheet"],
        "rectangle": rectangle_name,
        "ellipse": ellipse_name,
        "identifier": identifier,
        "search_identifier": search_identifier,
        "target_kind": "rectangle" if rectangle is not None else "ellipse",
        "dates": [],
        "search_complete": False,
        "pairs": {},
        "csv_files": {},
    }
    if root is None or not search_identifier:
        return result

    entries = sorted(
        (p for p in root.iterdir() if p.is_file() and not p.is_symlink()
         and p.suffix.lower() == ".svg"),
        key=lambda p: p.name.casefold()
    )
    csv_entries = sorted(
        (p for p in root.iterdir() if p.is_file() and not p.is_symlink()
         and p.suffix.lower() == ".csv" and name_matches(p.name, search_identifier)),
        key=lambda p: (p.name.casefold(), p.name),
    )
    result["search_complete"] = True
    # A timestamp is valid only when the same SVG filename matches
    # the rectangle (inside/partial case) or the textbox (outside case).
    matching_entries = [
        p for p in entries if name_matches(p.name, search_identifier)
    ]
    result["dates"] = sorted({
        match.group(1) for file in matching_entries
        for match in TIMESTAMP.finditer(file.name)
    })
    for date in result["dates"]:
        axes = {}
        for axis in ("X", "Y", "Z"):
            matching = {"psd": None, "octave": None}
            for file in matching_entries:
                filename = file.name
                if date not in TIMESTAMP.findall(filename):
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
        ranked = [(rank, p) for p in csv_entries
                  if (rank := csv_time_rank(p.name, date)) is not None]
        ranked.sort(key=lambda entry: (entry[0], entry[1].name.casefold(), entry[1].name))
        result["csv_files"][date] = {
            axis: [{"name": p.name, "url": "/viewer/assets/" + quote(folder_name, safe="")
                    + "/" + quote(p.name, safe="")}
                   for p in select_csv_files(ranked, axis)]
            for axis in axes
        }
    return result
