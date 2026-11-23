"""One-process Bokeh Server + Three.js viewer integration demo.

Run from the repository parent: python -m OneThreeOctave-SVG-Compare
Requires: pip install 'bokeh>=3.8,<4'
"""

import errno
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

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8080"))
STATIC_DIR = Path(__file__).resolve().parent
APP_ID = "OneThreeOctave-SVG-Compare:Bokeh-Three.js:v1"
IDENTITY_PATH = "/__onethree_identity__"


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
    url = f"http://{HOST}:{PORT}/viewer/index.html"
    try:
        server = Server(
            {"/analysis": Application(FunctionHandler(make_bokeh_document))},
            address=HOST,
            port=PORT,
            allow_websocket_origin=[f"{HOST}:{PORT}"],
            extra_patterns=[
                (r"/__onethree_identity__", ApplicationIdentityHandler),
                (r"/viewer/(index\.html)", StaticFileHandler, {"path": str(STATIC_DIR)}),
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
            open_viewer(url)
            return
        raise SystemExit(console_message(
            f"端口已被占用 (Port already in use)：{HOST}:{PORT}。"
            "请结束占用该端口的其他进程或旧实例，或设置 PORT=8081。",
            f"Port already in use: {HOST}:{PORT}. Close the other service "
            "or the older app instance, or set PORT=8081.",
            sys.stderr,
        )) from None
    server.start()
    print("Three.js + Bokeh viewer:", url, flush=True)
    open_viewer(url)
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    main()
