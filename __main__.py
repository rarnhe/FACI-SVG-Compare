"""One-process Bokeh Server + Three.js viewer integration demo.

Run from the repository parent: python -m OneThreeOctave-SVG-Compare
Requires: pip install 'bokeh>=3.8,<4'
"""

import errno
from hashlib import sha256
from datetime import datetime, timedelta
from html import escape
from math import sin
import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from bokeh.events import DocumentReady
from bokeh.layouts import column
from bokeh.models import ColumnDataSource, CustomJS, Div
from bokeh.plotting import figure
from bokeh.server.server import Server
from tornado.web import RequestHandler, StaticFileHandler

# Both the -m package entry and direct "python __main__.py" remain supported.
if __package__:
    from .xlsx_spatial import (
        SpatialXlsxError, load_assets_spatial_report, format_spatial_report,
        parse_xlsx, workbook_signature, write_ellipse_dates, ellipse_time_descriptions,
        MISSING_TEST_DESCRIPTION,
    )
    from .cad_service import build_cad_manifest, extract_embedded_image
    from .cad_svg_catalog import build_ellipse_svg_catalog
else:
    from xlsx_spatial import (
        SpatialXlsxError, load_assets_spatial_report, format_spatial_report,
        parse_xlsx, workbook_signature, write_ellipse_dates, ellipse_time_descriptions,
        MISSING_TEST_DESCRIPTION,
    )
    from cad_service import build_cad_manifest, extract_embedded_image
    from cad_svg_catalog import build_ellipse_svg_catalog

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8080"))
STATIC_DIR = Path(__file__).resolve().parent
IDENTITY_PATH = "/__onethree_identity__"
# Keep the identity tied to the running source, not just the repository name.
# A new invocation must not silently reuse a previous Python process serving old HTML.
BUILD_REVISION = sha256(
    (STATIC_DIR / "__main__.py").read_bytes()
    + (STATIC_DIR / "index.html").read_bytes()
    + (STATIC_DIR / "xlsx_spatial.py").read_bytes()
    + (STATIC_DIR / "cad_service.py").read_bytes()
    + (STATIC_DIR / "cad_viewer.js").read_bytes()
    + (STATIC_DIR / "cad_geometry.mjs").read_bytes()
    + (STATIC_DIR / "cad_ui.mjs").read_bytes()
    + (STATIC_DIR / "cad_svg_catalog.py").read_bytes()
    + (STATIC_DIR / "cad_validation.py").read_bytes()
).hexdigest()[:12]
APP_ID = f"OneThreeOctave-SVG-Compare:Bokeh-Three.js:{BUILD_REVISION}"


class NoCacheIndexHandler(StaticFileHandler):
    """Ensure old HTML containing references to obsolete assets is not reused."""

    def get_cache_time(self, path, modified, mime_type):
        return 0

    def set_extra_headers(self, path):
        # Windows may map .mjs to text/plain. ES module scripts require a
        # JavaScript MIME type regardless of the host's MIME registry.
        if str(path).lower().endswith((".js", ".mjs")):
            self.set_header("Content-Type", "text/javascript; charset=utf-8")
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.set_header("Pragma", "no-cache")
        self.set_header("Expires", "0")
        self.set_header("X-App-Revision", BUILD_REVISION)


class CadManifestHandler(RequestHandler):
    """Serve a read-only JSON manifest for two linked XLSX sheets."""

    def initialize(self, state):
        self.state = state

    def get(self):
        self.set_header("Cache-Control", "no-store")
        self.write(self.state["manifest"])


class EllipseSvgCatalogHandler(RequestHandler):
    """On-demand SVG index for an actual XLSX ellipse and its parent textbox."""

    def initialize(self, state):
        self.state = state

    def get(self, layer, object_index):
        try:
            payload = build_ellipse_svg_catalog(
                STATIC_DIR / "assets", self.state["sheets"],
                int(layer), int(object_index),
            )
        except (ValueError, OSError):
            self.send_error(404)
            return
        self.set_header("Cache-Control", "no-store")
        self.write(payload)

    def post(self, layer, object_index):
        # An explicit same-origin POST from the CAD menu is required. GET
        # stays read-only; arbitrary browser sites cannot trigger writeback.
        if (self.request.host.split(":")[0] not in {"127.0.0.1", "localhost"}
                or self.request.headers.get("Origin") != f"{self.request.protocol}://{self.request.host}"
                or self.request.headers.get("X-CAD-Sync") != "1"):
            self.send_error(403)
            return
        try:
            i, j = int(layer), int(object_index)
            cached = self.state["sheets"]
            payload = build_ellipse_svg_catalog(STATIC_DIR / "assets", cached, i, j)
            path = self.state["workbook"]
            ellipse = cached[i]["objects"][j]
            notes = ellipse.get("time_descriptions", {})
            if payload["search_complete"] and path is not None:
                signature = workbook_signature(path)
                fresh = parse_xlsx(path)
                # Do not trust old indices after external geometry edits.
                if len(fresh) != len(cached) or any(
                    a["sheet"] != b["sheet"] or
                    [{k: v for k, v in o.items() if k not in {"alt_text", "time_descriptions"}}
                     for o in a["objects"]] !=
                    [{k: v for k, v in o.items() if k not in {"alt_text", "time_descriptions"}}
                     for o in b["objects"]]
                    for a, b in zip(fresh, cached)
                ):
                    raise ValueError("Workbook geometry changed; restart viewer")
                current = fresh[i]["objects"][j]
                # A locked workbook must not disable browsing or pretend a
                # write succeeded. Re-read and retry on every explicit click.
                notes = ellipse_time_descriptions(current["alt_text"])
                try:
                    after = write_ellipse_dates(path, current, payload["dates"], signature)
                except PermissionError:
                    payload["sync_status"] = "deferred"
                    payload["sync_message"] = "Excel 工作簿暂不可写，关闭后再次点击椭圆即可同步"
                else:
                    payload["sync_status"] = "saved" if after != current["alt_text"] else "unchanged"
                    notes = ellipse_time_descriptions(after)
                    ellipse["alt_text"] = after
                    ellipse["time_descriptions"] = notes
                    public = self.state["manifest"]["layers"][i]["objects"][j]
                    public["alt_text"] = after
                    public["time_descriptions"] = notes
            payload.setdefault("sync_status", "not_applicable")
            payload["time_descriptions"] = {
                date: notes.get(date) or MISSING_TEST_DESCRIPTION for date in payload["dates"]
            }
        except (ValueError, OSError, SpatialXlsxError, KeyError, IndexError) as error:
            self.set_status(409)
            self.write({"error": str(error)})
            return
        self.set_header("Cache-Control", "no-store")
        self.write(payload)


class CadImageHandler(RequestHandler):
    """Read only XLSX picture parts selected by trusted sheet/object indices."""

    def initialize(self, state):
        self.state = state

    def get(self, layer, image_index):
        try:
            data, content_type = extract_embedded_image(
                self.state["workbook"], self.state["sheets"],
                int(layer), int(image_index),
            )
        except (ValueError, KeyError, FileNotFoundError, OSError):
            self.send_error(404)
            return
        self.set_header("Content-Type", content_type)
        self.set_header("Cache-Control", "no-store")
        self.set_header("X-Content-Type-Options", "nosniff")
        self.write(data)


class PrivateWorkbookHandler(RequestHandler):
    """The source Excel workbook is local input data, never public static media."""

    def get(self, _filename):
        self.send_error(404)


class NoServiceWorkerHandler(RequestHandler):
    """Return no content for legacy/browser /sw.js probes; register no worker."""

    def get(self):
        self.set_header("Cache-Control", "no-store")
        self.set_status(204)
        self.finish()



class ApplicationIdentityHandler(RequestHandler):
    """Identify this local server before a later invocation reuses its URL."""

    def get(self):
        self.set_header("Content-Type", "text/plain; charset=utf-8")
        self.set_header("Cache-Control", "no-store")
        self.write(APP_ID)


def is_port_conflict(error: OSError) -> bool:
    """Handle Linux EADDRINUSE and Windows WSAEADDRINUSE (WinError 10048)."""
    return error.errno in (errno.EADDRINUSE, 10048) or getattr(error, "winerror", None) == 10048


def existing_server_is_ours() -> bool:
    """Do not open an unrelated application's URL simply because 8080 is busy."""
    try:
        with urlopen(f"http://{HOST}:{PORT}{IDENTITY_PATH}", timeout=1) as response:
            return response.status == 200 and response.read(256).decode("utf-8") == APP_ID
    except (OSError, URLError, UnicodeError):
        return False


def open_viewer(url: str) -> None:
    if os.environ.get("NO_BROWSER") != "1":
        webbrowser.open(url)


def console_message(localized: str, fallback: str, stream) -> str:
    """Preserve Chinese in supported consoles, use ASCII on CP1252 Windows pipes."""
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        localized.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return fallback
    return localized

def print_spatial_report(workbook, sheets):
    """Print all XLSX objects; protect output in non-Unicode Windows consoles."""
    rendered = format_spatial_report(workbook, sheets)
    encoding = sys.stdout.encoding or "utf-8"
    try:
        rendered.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        rendered = rendered.encode(encoding, errors="backslashreplace").decode(encoding)
    print(rendered, flush=True)


# Replace with your own database-backed mapping / query results.
SENSORS = {
    "C001": {"label": "Subfab 柱 C001", "base": 21.4, "amplitude": 0.7},
    "C002": {"label": "Fab 柱 C002", "base": 24.6, "amplitude": 1.3},
    "C003": {"label": "Fab 柱 C003", "base": 26.2, "amplitude": 0.9},
}


def query_sensor_history(element_id: str) -> dict:
    """Example data only. Replace with your existing Python analysis query."""
    meta = SENSORS[element_id]
    t0 = datetime.now().replace(second=0, microsecond=0)
    return {
        "time": [t0 - timedelta(minutes=5 * (23 - n)) for n in range(24)],
        "value": [
            round(meta["base"] + meta["amplitude"] * sin(n / 3 + len(element_id)), 3)
            for n in range(24)
        ],
    }


def make_bokeh_document(doc):
    # Each browser has its own Bokeh session and its own data source.
    current_id = "C001"
    selection_bridge = ColumnDataSource(data={"element_id": [current_id]})
    history = ColumnDataSource(data=query_sensor_history(current_id))
    heading = Div(text=f"<h3>{escape(SENSORS[current_id]['label'])}</h3><p>示例：历史温度曲线 (°C)</p>")

    plot = figure(
        title="最近 2 小时 · 5 分钟采样",
        x_axis_type="datetime",
        height=330,
        sizing_mode="stretch_width",
        tools="pan,wheel_zoom,box_zoom,reset,save",
    )
    plot.line("time", "value", source=history, line_width=2.5, color="#248bba")
    plot.scatter("time", "value", source=history, size=5, color="#248bba")
    plot.xaxis.axis_label = "时间"
    plot.yaxis.axis_label = "温度 (°C)"

    def on_selection_changed(attr, old, new):
        element_ids = new.get("element_id", [])
        if not element_ids:
            return
        element_id = element_ids[0]
        if element_id not in SENSORS:
            heading.text = f"<p>没有绑定数据：{escape(str(element_id))}</p>"
            history.data = {"time": [], "value": []}
            return

        # This runs on the Python/Bokeh server; no iframe reload.
        data = query_sensor_history(element_id)
        history.data = data
        heading.text = (
            f"<h3>{escape(SENSORS[element_id]['label'])}</h3>"
            f"<p>最近采样：{data['value'][-1]:.2f} °C（示例数据）</p>"
        )

    selection_bridge.on_change("data", on_selection_changed)

    # Run once inside Bokeh's iframe after its document is ready.
    # postMessage bridges the Three.js parent page to Bokeh's JS model.
    doc.js_on_event(DocumentReady, CustomJS(args=dict(bridge=selection_bridge), code="""
        if (window.__threeBokehBridgeReady) return;
        window.__threeBokehBridgeReady = true;
        window.addEventListener('message', (event) => {
            if (event.origin !== window.location.origin) return;
            if (!event.data || event.data.type !== 'SELECT_ELEMENT') return;
            const id = event.data.elementId;
            if (typeof id !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(id)) return;
            // Assign a fresh object to trigger BokehJS -> Python server sync.
            bridge.data = {element_id: [id]};
        });
        window.parent.postMessage({type: 'BOKEH_READY'}, window.location.origin);
    """))

    doc.add_root(column(heading, plot, sizing_mode="stretch_width"))
    doc.title = "工程数据分析"


def main():
    # Exactly one .xlsx is allowed in assets/. Compute geometry before opening
    # the browser; malformed/ambiguous input cannot silently choose a workbook.
    try:
        workbook, spatial_sheets = load_assets_spatial_report(STATIC_DIR / "assets")
    except (SpatialXlsxError, OSError) as error:
        raise SystemExit(f"[XLSX ERROR] {error}") from None

    cad_state = {
        "workbook": workbook,
        "sheets": spatial_sheets,
        "manifest": build_cad_manifest(workbook, spatial_sheets, STATIC_DIR / "assets"),
    }

    # A workbook-specific tab caption, set by the HTML document after it loads
    # the manifest. No other data source is used as an arbitrary HTML title.
    # An explicit revision in the URL defeats old HTML caches on first launch.
    url = f"http://{HOST}:{PORT}/viewer/index.html?rev={BUILD_REVISION}"
    try:
        server = Server(
            {"/analysis": Application(FunctionHandler(make_bokeh_document))},
            address=HOST,
            port=PORT,
            allow_websocket_origin=[f"{HOST}:{PORT}"],
            extra_patterns=[
                (r"/__onethree_identity__", ApplicationIdentityHandler),
                (r"/sw\.js", NoServiceWorkerHandler),
                (r"/viewer/sw\.js", NoServiceWorkerHandler),
                (r"/viewer/cad-layout\.json", CadManifestHandler, {"state": cad_state}),
                (r"/viewer/cad-image/([0-9]+)/([0-9]+)", CadImageHandler, {"state": cad_state}),
                (r"/viewer/cad-svg-catalog/([0-9]+)/([0-9]+)", EllipseSvgCatalogHandler,
                 {"state": cad_state}),
                (r"/viewer/(index\.html|cad_viewer\.js|cad_geometry\.mjs|cad_ui\.mjs)", NoCacheIndexHandler, {"path": str(STATIC_DIR)}),
                (r"/viewer/assets/((?i:.*\.xlsx))", PrivateWorkbookHandler),
                (r"/viewer/assets/(.*)", StaticFileHandler, {"path": str(STATIC_DIR / "assets")}),
            ],
        )
    except OSError as error:
        if not is_port_conflict(error):
            raise
        if existing_server_is_ours():
            print(console_message(
                f"程序已在运行 (Already running)，重新打开浏览器页面：{url}",
                f"Already running. Opening existing viewer: {url}",
                sys.stdout,
            ), flush=True)
            print_spatial_report(workbook, spatial_sheets)
            open_viewer(url)
            return
        raise SystemExit(console_message(
            f"端口已被占用 (Port already in use)：{HOST}:{PORT}。"
            "可能仍运行旧版服务器。请在旧终端按 Ctrl+C 后重新运行；"
            "也可以设置 PORT=8081。",
            f"Port already in use: {HOST}:{PORT}. A previous viewer may still be running. "
            "Stop the old Python process with Ctrl+C and restart, or set PORT=8081.",
            sys.stderr,
        )) from None
    server.start()
    print("Three.js + Bokeh viewer:", url, flush=True)
    print_spatial_report(workbook, spatial_sheets)
    open_viewer(url)
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    main()
