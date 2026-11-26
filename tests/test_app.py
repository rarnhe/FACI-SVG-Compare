"""Bokeh document tests, relocated static resources, and real ``python -m`` startup."""

from importlib import import_module
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import threading
import subprocess
import sys
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import urlopen, build_opener, HTTPRedirectHandler, Request
from urllib.parse import quote

from bokeh.document import Document
from bokeh.models import ColumnDataSource, CustomJS, Div

ROOT = Path(__file__).resolve().parents[1]
# python -m resolves the package from its parent; importlib accepts hyphenated names.
sys.path.insert(0, str(ROOT.parent))
app = import_module(f"{ROOT.name}.__main__")
SENSORS = app.SENSORS
STATIC_DIR = app.STATIC_DIR
make_bokeh_document = app.make_bokeh_document
query_sensor_history = app.query_sensor_history



class TestPackageLayout(unittest.TestCase):
    def test_root_is_importable_package_with_main_entry(self):
        self.assertTrue((ROOT / "__init__.py").is_file())
        self.assertTrue((ROOT / "__main__.py").is_file())
        self.assertFalse((ROOT / "main.py").exists())
        self.assertEqual(STATIC_DIR, ROOT)

    def test_frontend_assets_reside_at_root(self):
        self.assertTrue((ROOT / "index.html").is_file())
        self.assertTrue((ROOT / "assets").is_dir())
        self.assertFalse((ROOT / "frontend").exists())


class TestSensorHistory(unittest.TestCase):
    def test_known_sensors_have_24_aligned_samples(self):
        for element_id in SENSORS:
            with self.subTest(element_id=element_id):
                data = query_sensor_history(element_id)
                self.assertEqual(len(data["time"]), 24)
                self.assertEqual(len(data["value"]), 24)
                self.assertTrue(all(x < y for x, y in zip(data["time"], data["time"][1:])))
                self.assertTrue(all(isinstance(v, float) for v in data["value"]))

    def test_unknown_sensor_does_not_silently_succeed(self):
        with self.assertRaises(KeyError):
            query_sensor_history("NOT_PRESENT")


class TestBokehSelection(unittest.TestCase):
    def setUp(self):
        self.document = Document()
        make_bokeh_document(self.document)
        sources = list(self.document.select({"type": ColumnDataSource}))
        self.selection = self.document.callbacks._js_event_callbacks["document_ready"][0].args["bridge"]
        self.history = next(x for x in sources if "time" in x.data)
        self.heading = next(iter(self.document.select({"type": Div})))

    def test_initial_state(self):
        self.assertEqual(self.selection.data["element_id"], ["C001"])
        self.assertEqual(len(self.history.data["value"]), 24)
        self.assertIn("C001", self.heading.text)
        self.assertEqual(self.document.title, "工程数据分析")

    def test_selection_updates_history_without_reloading(self):
        previous = self.history.data["value"][:]
        self.selection.data = {"element_id": ["C002"]}
        self.assertIn("C002", self.heading.text)
        self.assertEqual(len(self.history.data["value"]), 24)
        self.assertNotEqual(previous, self.history.data["value"])

    def test_unknown_selection_clears_chart_and_escapes_html(self):
        self.selection.data = {"element_id": ["<script>"]}
        self.assertEqual(self.history.data["value"], [])
        self.assertIn("&lt;script&gt;", self.heading.text)
        self.assertNotIn("<script>", self.heading.text)

    def test_ready_bridge_is_attached(self):
        callbacks = self.document.callbacks._js_event_callbacks.get("document_ready", [])
        self.assertTrue(any(isinstance(callback, CustomJS) for callback in callbacks))
        self.assertTrue(any("SELECT_ELEMENT" in cb.code for cb in callbacks))
        self.assertTrue(any("event.origin" in cb.code for cb in callbacks))


class TestStaticFrontend(unittest.TestCase):
    def test_new_two_layer_cad_layout_and_svg_panes(self):
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        for expected in ('id="fab-stage"', 'id="subfab-stage"', 'id="reset-view"',
                         'id="psd-reference"', 'id="octave-reference"', 'src="./cad_viewer.js"'):
            with self.subTest(expected=expected):
                self.assertIn(expected, html)
        self.assertNotIn("GLTFLoader", html)

    def test_shared_orbit_controls_and_clickable_shapes(self):
        viewer = (STATIC_DIR / "cad_viewer.js").read_text(encoding="utf-8")
        for expected in ("OrbitControls", "synchronizeFrom(", "THREE.MOUSE.ROTATE",
                         "THREE.MOUSE.PAN", "raycaster.intersectObjects",
                         "resetTopView()", "drawTopLeftText(", "cad-layout.json",
                         "kind==='ellipse'", "kind==='rectangle'", "kind==='textbox'",
                         "installSplitter('main-splitter'", "installSplitter('reference-splitter'"):
            with self.subTest(expected=expected):
                self.assertIn(expected, viewer)
        self.assertNotIn("GLTFLoader", viewer)


    def test_visual_labels_removed_and_splitters_added(self):
        html=(STATIC_DIR/"index.html").read_text(encoding="utf-8")
        for absent in ("Fab / Subfab · 联动 CAD 视图", "FAB · Sheet 1",
                       "SUBFAB · Sheet 2", "数据分析参考图",
                       "OneThreeOctave_base.svg", "PSD_base.svg</div>"):
            with self.subTest(absent=absent):
                self.assertNotIn(absent,html)
        self.assertIn('id="main-splitter"',html)
        self.assertIn('id="reference-splitter"',html)
        self.assertIn('id="selected-info"',html)
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        self.assertIn("zoom intentionally untouched",viewer)
        self.assertIn("selectedInfo.textContent=(mesh.userData.cadObject.text||'').trim()",viewer)
        self.assertIn("entry.element.style.height=height+'px'",viewer)
        self.assertIn("entry.element.style.width=(height/entry.ratio)+'px'",viewer)
        self.assertIn("fitSvgHeightToPane()",viewer)
        self.assertNotIn("refreshEqualSvgWidth",viewer)
        self.assertNotIn("commonWidth",viewer)
        self.assertIn("overflow-x:auto",html)
        self.assertIn("flex:0 0 auto",html)


    def test_drawing_strategies_use_actual_meshes_and_raycaster(self):
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        strategies={
            "textbox": ("kind==='textbox' ? 0x828b96", "new THREE.PlaneGeometry(w,h)"),
            "ellipse": ("kind==='ellipse'", "new THREE.CircleGeometry(radius,72)"),
            "rectangle": ("kind==='rectangle'", "new THREE.BoxGeometry(w,h,depth)"),
        }
        for shape, snippets in strategies.items():
            with self.subTest(shape=shape):
                for snippet in snippets:
                    self.assertIn(snippet,viewer)
        self.assertIn("layer.clickable.push(clickTarget)",viewer)
        self.assertIn("raycaster.intersectObjects(layer.clickable,false)",viewer)
        self.assertIn("drawTopLeftText(group,item.text||'',w,h,colors.text,frontZ)",viewer)


    def test_rectangle_depth_directive_and_ellipse_lifting_are_wired(self):
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        self.assertIn("rectangleHeight(item.text,w,h)",viewer)
        self.assertIn("ellipseElevation(item,toWorldRect,rectangles)",viewer)
        self.assertIn("circleRectangleRelation",helper if False else
                      (STATIC_DIR/"cad_geometry.mjs").read_text(encoding="utf-8"))
        self.assertIn("const rectangles=rectangleSpecs(layerData.objects,toWorldRect)",viewer)
        self.assertIn("depth>0",viewer)
        self.assertIn("new THREE.PlaneGeometry(w,h)",viewer)
        with open(STATIC_DIR/"cad_geometry.mjs",encoding="utf-8") as file:
            helper=file.read()
        self.assertIn("match[1] === 'x' ? width : height",helper)
        self.assertIn("pointInsideRotatedRectangle",helper)

    def test_local_asset_directory_exists(self):
        self.assertTrue((STATIC_DIR / "assets").is_dir())

    def test_no_column_or_service_worker_in_viewer(self):
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        viewer = (STATIC_DIR / "cad_viewer.js").read_text(encoding="utf-8")
        server = (STATIC_DIR / "__main__.py").read_text(encoding="utf-8")
        self.assertNotIn("Column.glb", html + viewer + server)
        self.assertNotIn("serviceWorker.register(", html + viewer)
        self.assertNotIn("GLTFLoader", html + viewer)



class TestHttpIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Choose a free local port; process serves a real Bokeh + Tornado app.
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        env = dict(os.environ, PORT=str(cls.port), NO_BROWSER="1")
        cls.process = subprocess.Popen(
            [sys.executable, "-u", "-m", ROOT.name],
            cwd=ROOT.parent, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        cls.base = f"http://127.0.0.1:{cls.port}"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if cls.process.poll() is not None:
                _, stderr = cls.process.communicate(timeout=2)
                raise RuntimeError(f"python -m {ROOT.name} failed: {stderr}")
            try:
                with urlopen(cls.base + "/viewer/index.html", timeout=1) as response:
                    if response.status == 200:
                        cls.startup_log = cls.process.stdout.readline()
                        return
            except (OSError, URLError):
                time.sleep(0.1)
        cls.process.terminate()
        cls.process.communicate(timeout=5)
        raise TimeoutError("python -m app did not start the server within 15 seconds")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "process", None) is not None:
            if cls.process.poll() is None:
                cls.process.terminate()
            try:
                cls.process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                cls.process.kill()
                cls.process.communicate(timeout=5)

    def test_identity_route(self):
        with urlopen(self.base + app.IDENTITY_PATH, timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read().decode("utf-8"), app.APP_ID)

    def test_second_launch_reuses_running_instance(self):
        duplicate = subprocess.run(
            [sys.executable, "-u", "-m", ROOT.name],
            cwd=ROOT.parent,
            env=dict(os.environ, PORT=str(self.port), NO_BROWSER="1"),
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(duplicate.returncode, 0, duplicate.stderr)
        self.assertIn("Already running", duplicate.stdout)
        self.assertIn(f":{self.port}/viewer/index.html", duplicate.stdout)
        self.assertIsNone(self.process.poll(), "Existing Bokeh server must survive duplicate launch")

    def test_module_entry_prints_url(self):
        self.assertIn("Three.js + Bokeh viewer:", self.startup_log)
        self.assertIn(f":{self.port}/viewer/index.html?rev={app.BUILD_REVISION}", self.startup_log)

    def test_html_cache_is_disabled(self):
        with urlopen(self.base + "/viewer/index.html", timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("no-store", response.headers["Cache-Control"])
            self.assertEqual(response.headers["X-App-Revision"], app.BUILD_REVISION)
            html = response.read().decode("utf-8")
            self.assertIn('http-equiv="Cache-Control"', html)
            self.assertNotIn("柱子.glb", html)

    def test_source_change_invalidates_identity(self):
        self.assertTrue(app.APP_ID.endswith(app.BUILD_REVISION))
        self.assertNotIn(":v1", app.APP_ID)
        with urlopen(self.base + app.IDENTITY_PATH, timeout=5) as response:
            self.assertEqual(response.read().decode("utf-8"), app.APP_ID)


    def test_viewer_is_served(self):
        with urlopen(self.base + "/viewer/index.html", timeout=5) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Fab / Subfab", body)

    def test_bokeh_analysis_page_is_served(self):
        with urlopen(self.base + "/analysis", timeout=5) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Bokeh", body)

    def test_cad_layout_has_two_sheets_and_reference_metadata(self):
        with urlopen(self.base + "/viewer/cad-layout.json", timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("no-store", response.headers["Cache-Control"])
            data = json.load(response)
        self.assertEqual([layer["title"] for layer in data["layers"]], ["Fab", "Subfab"])
        self.assertEqual(set(data["reference_svgs"]), {"psd", "octave"})
        for key, filename in (("psd", "PSD_base.svg"), ("octave", "1-3-Octave_base.svg")):
            self.assertEqual(
                data["reference_svgs"][key]["available"],
                (STATIC_DIR / "assets" / filename).is_file(),
            )

    def test_javascript_modules_have_browser_accepted_mime_type(self):
        # Use the real Python -m HTTP service: Windows can otherwise send
        # text/plain for .mjs despite successful HTTP 200 and JS syntax tests.
        for module_path, source_marker in (
            ("/viewer/cad_viewer.js", "OrbitControls"),
            ("/viewer/cad_geometry.mjs", "rectangleHeight"),
        ):
            with self.subTest(module_path=module_path):
                with urlopen(self.base + module_path, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(
                        response.headers.get_content_type(), "text/javascript"
                    )
                    self.assertEqual(
                        response.headers.get_content_charset(), "utf-8"
                    )
                    self.assertIn("no-store", response.headers["Cache-Control"])
                    self.assertEqual(
                        response.headers["X-App-Revision"], app.BUILD_REVISION
                    )
                    self.assertIn(source_marker, response.read().decode("utf-8"))

    def test_html_still_has_html_mime_type(self):
        with urlopen(self.base + "/viewer/index.html", timeout=5) as response:
            self.assertEqual(response.headers.get_content_type(), "text/html")


    def test_cad_js_is_served_and_source_xlsx_is_private(self):
        with urlopen(self.base + "/viewer/cad_viewer.js", timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("OrbitControls", response.read().decode("utf-8"))
        with self.assertRaises(HTTPError) as failure:
            urlopen(self.base + "/viewer/assets/private.xlsx", timeout=5)
        self.assertEqual(failure.exception.code, 404)

    def test_invalid_embedded_image_route_is_safe(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.base + "/viewer/cad-image/0/999", timeout=5)
        self.assertEqual(caught.exception.code, 404)

    def test_sw_js_requests_return_204_without_registering(self):
        for path in ("/sw.js", "/viewer/sw.js"):
            with self.subTest(path=path):
                with urlopen(self.base + path, timeout=5) as response:
                    self.assertEqual(response.status, 204)
                    self.assertEqual(response.read(), b"")
                    self.assertIn("no-store", response.headers["Cache-Control"])

    def test_root_asset_file_is_served(self):
        with urlopen(self.base + "/viewer/assets/README.md", timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("XLSX", response.read().decode("utf-8"))

    def test_python_source_is_not_exposed_by_static_server(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.base + "/viewer/__main__.py", timeout=5)
        self.assertEqual(caught.exception.code, 404)



class TestPortConflict(unittest.TestCase):
    def test_cp1252_console_encoding_falls_back_to_english(self):
        class Cp1252Stream:
            encoding = "cp1252"

        self.assertEqual(
            app.console_message("端口已被占用", "Port already in use", Cp1252Stream()),
            "Port already in use",
        )

    def test_windows_10048_is_recognized(self):
        self.assertTrue(app.is_port_conflict(OSError(10048, "Windows port busy")))
        self.assertFalse(app.is_port_conflict(OSError(13, "Permission denied")))

    def run_with_busy_port(self, port):
        return subprocess.run(
            [sys.executable, "-u", "-m", ROOT.name], cwd=ROOT.parent,
            env=dict(os.environ, PORT=str(port), NO_BROWSER="1"),
            capture_output=True, text=True, timeout=15,
        )

    def test_other_http_service_is_not_mistaken_for_ours(self):
        class ForeignHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Not the application")

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), ForeignHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            duplicate = self.run_with_busy_port(server.server_port)
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("Port already in use", duplicate.stderr)
            self.assertNotIn("Traceback", duplicate.stderr)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_occupied_non_http_port_does_not_raise_traceback(self):
        with socket.socket() as blocker:
            blocker.bind(("127.0.0.1", 0))
            blocker.listen()
            duplicate = self.run_with_busy_port(blocker.getsockname()[1])
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("Port already in use", duplicate.stderr)
        self.assertNotIn("Traceback", duplicate.stderr)
