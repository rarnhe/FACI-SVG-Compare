"""Real Bokeh document tests and a local HTTP smoke test (stdlib unittest)."""

import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from urllib.parse import quote

from bokeh.document import Document
from bokeh.models import ColumnDataSource, CustomJS, Div

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from main import SENSORS, STATIC_DIR, make_bokeh_document, query_sensor_history  # noqa: E402


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
    def test_frontend_links_to_bokeh_and_has_pick_logic(self):
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        for expected in ('src="/analysis"', "Raycaster", "SELECT_ELEMENT", "BOKEH_READY", "GLTFLoader", "pointerup"):
            with self.subTest(expected=expected):
                self.assertIn(expected, html)

    def test_local_asset_directory_exists(self):
        self.assertTrue((STATIC_DIR / "assets").is_dir())


class TestHttpIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Choose a free local port; process serves a real Bokeh + Tornado app.
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        env = dict(os.environ, PORT=str(cls.port), NO_BROWSER="1")
        cls.process = subprocess.Popen(
            [sys.executable, "-u", "main.py"], cwd=ROOT, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        cls.base = f"http://127.0.0.1:{cls.port}"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if cls.process.poll() is not None:
                raise RuntimeError(f"Bokeh server exited with {cls.process.returncode}")
            try:
                with urlopen(cls.base + "/viewer/index.html", timeout=1) as response:
                    if response.status == 200:
                        return
            except (OSError, URLError):
                time.sleep(0.1)
        cls.process.terminate()
        cls.process.wait(timeout=5)
        raise TimeoutError("Bokeh server did not become ready within 15 seconds")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "process", None) is not None and cls.process.poll() is None:
            cls.process.terminate()
            try:
                cls.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.process.kill()
                cls.process.wait(timeout=5)

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

    def test_missing_optional_glb_returns_404(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.base + "/viewer/assets/" + quote("柱子.glb"), timeout=5)
        self.assertEqual(caught.exception.code, 404)
