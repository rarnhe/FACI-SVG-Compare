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
                         "resetTopView()", "cad-layout.json",
                         "kind==='ellipse'", "kind==='rectangle'", "kind==='textbox'",
                         "installSplitter('main-splitter'", "installSplitter('reference-splitter'"):
            with self.subTest(expected=expected):
                self.assertIn(expected, viewer)
        self.assertNotIn("GLTFLoader", viewer)


    def test_operation_labels_are_plain_black_and_each_layer_has_own_breadcrumb(self):
        html=(STATIC_DIR/"index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count("滚轮缩放·右键拖动平移·左键拖动旋转"),1)
        for attr in ('id="fab-selected-info"', 'id="subfab-selected-info"',
                     'class="cad-operation"', 'class="cad-selection"'):
            self.assertIn(attr,html)
        self.assertIn(".cad-operation{",html)
        self.assertIn("border:1px solid #bfc8cf;border-radius:8px",html)
        self.assertIn("border-radius:8px",html)
        self.assertIn("bottom:12px;left:12px",html)
        self.assertNotIn('id="selected-info"',html)
        self.assertNotIn('id="cad-info"',html)
        self.assertNotIn("Fab / Subfab · 联动 CAD 视图",html)

    def test_white_background_and_dynamic_context_menu_hierarchy(self):
        html=(STATIC_DIR/"index.html").read_text(encoding="utf-8")
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        self.assertIn("scene.background = new THREE.Color(0xffffff)",viewer)
        self.assertIn("background:#fff",html)
        for marker in ("createContextMenu(", "closeContextMenus(", "openContextMenu(",
                       "selectionParts(", "workbookName=data.workbook",
                       "if (kind !== 'textbox') layer.clickable.push(clickTarget)",
                       "event.button===2", "'X','Y','Z'",
                       "'./cad-svg-catalog/'", "showAxisSubmenu(", "prefetchSvg(",
                       "appendReferenceHistory(", "document.title=workbookName"):
            with self.subTest(marker=marker):
                self.assertIn(marker,viewer)
        self.assertIn("selectOnButton(mesh.userData.cadObject,button)",viewer)
        self.assertIn("canvas.addEventListener('pointermove'",viewer)
        self.assertIn("canvas.addEventListener('pointerleave'",viewer)
        self.assertIn("stageId==='fab-stage'?'fab-selected-info':'subfab-selected-info'",viewer)
        self.assertNotIn("2025 ›",viewer)


    def test_svg_fit_is_centered_bounded_and_initial_split_ratio_fixed(self):
        html=(STATIC_DIR/"index.html").read_text(encoding="utf-8")
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        pure=(STATIC_DIR/"cad_ui.mjs").read_text(encoding="utf-8")
        self.assertIn('id="main-splitter"',html)
        self.assertIn('id="reference-splitter"',html)
        self.assertIn("justify-content:center;background:#fff",html)
        self.assertIn("overflow:hidden;display:flex",html)
        self.assertNotIn("overflow-x:auto",html)
        self.assertIn("minmax(0,1fr) 8px minmax(0,1fr)",html)
        self.assertIn("let rightSplitRatio = INITIAL_REFERENCE_SPLIT",viewer)
        self.assertIn("fitSvgPane(",viewer)
        self.assertIn("clampMainDivider(",viewer)
        self.assertIn("clampReferenceSplit(",viewer)
        self.assertIn("fitSvgHeightToPane()",viewer)
        self.assertIn("INITIAL_REFERENCE_SPLIT = 0.5",pure)
        self.assertNotIn("rightSplitChangedByUser",viewer)
        self.assertIn("base.element.style.width=width+'px'",viewer)
        self.assertIn("layer.element.style.width=width+'px'",viewer)


    def test_drawing_strategies_use_actual_meshes_and_raycaster(self):
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        strategies={
            "textbox": ("const fillColor=colorValue(colors.fill", "new THREE.PlaneGeometry(w,h)"),
            "ellipse": ("kind==='ellipse'", "new THREE.CircleGeometry(radius,72)"),
            "rectangle": ("kind==='rectangle'", "new THREE.BoxGeometry(w,h,depth)"),
        }
        for shape, snippets in strategies.items():
            with self.subTest(shape=shape):
                for snippet in snippets:
                    self.assertIn(snippet,viewer)
        self.assertIn("layer.clickable.push(clickTarget)",viewer)
        self.assertIn("raycaster.intersectObjects(targets,false)",viewer)
        self.assertIn("selectOnButton(mesh.userData.cadObject,button)",viewer)
        parser=(STATIC_DIR/"xlsx_spatial.py").read_text(encoding="utf-8")
        self.assertNotIn("drawTopLeftText(",viewer)
        self.assertIn("new THREE.CanvasTexture(canvas)",viewer)
        self.assertIn("context.fillText(part.text,part.x,part.y)",viewer)
        self.assertNotIn("frontZ",viewer)
        self.assertIn('font_ref = first_child(style, "fontRef")',parser)
        self.assertNotIn('"text": style_color(',parser)
        self.assertIn('obj["text"] = shape_text(element)',parser)


    def test_rectangle_depth_directive_and_ellipse_lifting_are_wired(self):
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        self.assertIn("rectangleHeight(item.alt_text,w,h)",viewer)
        self.assertIn("ellipseElevation(item,x=>toWorldRect(x,layer),rectangles)",viewer)
        self.assertIn("circleRectangleRelation",helper if False else
                      (STATIC_DIR/"cad_geometry.mjs").read_text(encoding="utf-8"))
        self.assertIn("const rectangles=rectangleSpecs(layer.objects,obj=>toWorldRect(obj,layer))",viewer)
        self.assertIn("depth>0",viewer)
        self.assertIn("new THREE.PlaneGeometry(w,h)",viewer)
        with open(STATIC_DIR/"cad_geometry.mjs",encoding="utf-8") as file:
            helper=file.read()
        self.assertIn("match[2].toLowerCase()==='x' ? width : height",helper)
        self.assertIn("pointInsideRotatedRectangle",helper)

    def test_textbox_transparent_fill_and_outline_are_respected(self):
        html=(STATIC_DIR/"index.html").read_text(encoding="utf-8")
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        self.assertIn("const fillColor=colorValue(colors.fill",viewer)
        self.assertIn("colors.fill==='无/透明'?0:1",viewer)
        self.assertIn("const outline=cadOutlineSpec(item)",viewer)
        self.assertNotIn("A textbox always has gray background",viewer)
        self.assertIn("border-radius:8px",html)

    def test_xlsx_alt_svg_catalog_and_picture_aspect_pipeline_are_wired(self):
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        service=(STATIC_DIR/"__main__.py").read_text(encoding="utf-8")
        self.assertIn("pictureLayerScales(bounds)",viewer)
        self.assertIn("loadCadTexture(",viewer)
        self.assertIn("applyReferenceImage(key,image.url,image.width,image.height)",viewer)
        self.assertIn("drawImage(layer,item,textures[i])",viewer)
        self.assertIn("const textures=await Promise.all(layerImages.map(item=>",viewer)
        self.assertIn("loadCadTexture(item?.image_url)",viewer)
        self.assertIn("overlaySelections.set(key,entry)",viewer)
        self.assertIn("displayedSvgWidth",viewer)
        self.assertIn("svgHistory.append(line)",viewer)
        self.assertIn("EllipseSvgCatalogHandler",service)
        self.assertIn("cad-svg-catalog",service)
        self.assertIn("cad_svg_catalog.py",service)
        html=(STATIC_DIR/"index.html").read_text(encoding="utf-8")
        self.assertIn('id="reference-log"',html)
        self.assertIn("border-radius:0",html)
        self.assertIn("cursor:grab",html)
        self.assertNotIn("max-width:100%;max-height:100%;object-fit:contain",html)

    def test_workbook_title_and_embedded_png_backdrop_are_wired(self):
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        server=(STATIC_DIR/"__main__.py").read_text(encoding="utf-8")
        service=(STATIC_DIR/"cad_service.py").read_text(encoding="utf-8")
        ui=(STATIC_DIR/"cad_ui.mjs").read_text(encoding="utf-8")
        self.assertIn("document.title=workbookName.replace(/\\.xlsx$/i,'')",viewer)
        self.assertIn("loadCadTexture(item?.image_url)",viewer)
        self.assertNotIn("imageAspectRatio",viewer)
        self.assertIn("const transforms=pictureLayerScales(bounds)",viewer)
        self.assertIn("layer.scaleX=transforms[i].x",viewer)
        self.assertIn("layer.scaleY=layer.scaleX",viewer)
        self.assertIn("if(item.type==='image') drawImage(layer,item,textures[i]);",viewer)
        self.assertIn("if(item.type==='shape') drawShape(layer,item,rectangles);",viewer)
        self.assertIn("export function pictureLayerScales(imageBounds)",ui)
        self.assertIn("x:scale,y:scale",ui)
        self.assertIn("empty.textContent='无可用测试结果'",viewer)
        self.assertNotIn("loadSheetSvgTexture(",viewer)
        self.assertNotIn("drawSvgBackground(",viewer)
        self.assertNotIn("background_svg",viewer+service)
        self.assertIn("CadImageHandler",server)
        self.assertIn("/viewer/cad-image/",server)
        self.assertIn("extract_embedded_image",service)
        self.assertIn('obj["image_url"] = f"/viewer/cad-image/{layer_index}/{object_index}"',service)

    def test_cad_fixed_divider_and_matching_top_controls(self):
        html=(STATIC_DIR/"index.html").read_text(encoding="utf-8")
        self.assertIn('id="cad-fixed-divider"',html)
        self.assertIn("#cad-fixed-divider{width:100%;height:8px;background:#c4d1da;",html)
        self.assertIn("pointer-events:none;user-select:none",html)
        self.assertIn("grid-template-rows:minmax(0,1fr) 8px minmax(0,1fr)",html)
        self.assertIn("top:10px;left:12px",html)
        self.assertIn("top:10px;right:12px",html)
        self.assertIn("height:36px",html)
        self.assertIn("font-size:14px",html)
        self.assertIn("border:1px solid #bfc8cf;background:#fff",html)

    def test_svg_transparent_overlay_legend_dedup_and_pair_close(self):
        html=(STATIC_DIR/"index.html").read_text(encoding="utf-8")
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        pure=(STATIC_DIR/"cad_ui.mjs").read_text(encoding="utf-8")
        for snippet in ('id="psd-overlays"', 'id="octave-overlays"',
                        'id="legend-context-menu"',
                        '.reference-overlays{', 'background:transparent', 
                        '.reference-overlays img'):
            self.assertIn(snippet,html)
        for snippet in ("canAddOverlay(overlaySelections,overlayLoads,key)",
                        "overlayLoads.add(key)", "overlaySelections.set(key,entry)",
                        "showLegendMenu(key,event.clientX,event.clientY)",
                        "removeReferenceOverlay(key)", "overlaySelections.delete(key)",
                        "makeColoredPair(pair,style)",
                        "changeLegendStyle(", "showLegendMenu(",
                        "SVG_COLOR_CHOICES", "restyleSvgMarkup(markup,style,key)",
                        "URL.createObjectURL(new Blob([colorized]",
                        "URL.revokeObjectURL(pair[key].blobUrl)",
                        "document.getElementById('psd-overlays').append",
                        "document.getElementById('octave-overlays').append"):
            self.assertIn(snippet,viewer)
        self.assertIn("selectionParts(items,selected,toRect)",pure)
        self.assertIn("requiredSvgRatio(baseRatio, entries)",pure)
        self.assertNotIn("applyReferenceImage('psd',psd.url",viewer)

    def test_hover_breadcrumb_textbox_rectangle_sensor_and_bold_parent(self):
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        geometry=(STATIC_DIR/"cad_ui.mjs").read_text(encoding="utf-8")
        self.assertIn("layer.hoverable.push(clickTarget)",viewer)
        self.assertIn("button===null ? layer.hoverable",viewer)
        self.assertIn("selectionParts(",viewer)
        self.assertIn("part.kind==='textbox'?'strong':'span'",viewer)
        self.assertNotIn("selectionPath(workbookName",viewer)
        self.assertIn("shape_kind==='textbox'",geometry)
        self.assertIn("shape_kind==='rectangle'",geometry)

    def test_svg_mutation_service_removed_and_catalog_remains_readonly(self):
        server=(STATIC_DIR/"__main__.py").read_text(encoding="utf-8")
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        self.assertNotIn("SvgStyleHandler",server)
        self.assertNotIn("update_svg_pair",server)
        self.assertNotIn("svg_styling.py",server)
        self.assertNotIn("cad-svg-style",server+viewer)
        self.assertNotIn("persistSvgStyle",viewer)
        self.assertIn("method:'POST',headers:{'X-CAD-Sync':'1','X-CAD-Generation':",viewer)
        self.assertIn("write_ellipse_dates",server)
        self.assertFalse((STATIC_DIR/"svg_styling.py").exists())
        self.assertIn("EllipseSvgCatalogHandler",server)

    def test_independent_panel_fit_and_unadorned_colored_legend(self):
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        html=(STATIC_DIR/"index.html").read_text(encoding="utf-8")
        helper=(STATIC_DIR/"cad_ui.mjs").read_text(encoding="utf-8")
        self.assertIn("fitSvgPane(frame.clientWidth,frame.clientHeight,displayedRatio(key))",viewer)
        self.assertIn("font-size:14px;font-weight:700",html)
        self.assertIn("line.textContent=label",viewer)
        self.assertIn("line.style.color=entry.color",viewer)
        self.assertNotIn('className=\'legend-swatch\'',viewer)
        self.assertIn("SVG_COLOR_CHOICES=Object.freeze([",helper)
        self.assertIn("SVG_LINE_WIDTHS",helper)
        self.assertIn("SVG_LINE_TYPES",helper)
        self.assertIn("submenu('线型','lineStyle',[...SVG_LINE_TYPES,{label:'初始线型',value:null}]",viewer)
        self.assertIn("submenu('线宽','lineWidth',[...SVG_LINE_WIDTHS.map",viewer)
        self.assertNotIn("label:'原始线宽'",viewer)
        self.assertIn("mergeSvgStyle(entry.style,patch)",viewer)
        self.assertIn("entry.style=style",viewer)
        self.assertIn("recolorSvgMarkup(source,color)",helper)
        self.assertIn("close.textContent='关闭'",viewer)

    def test_svg_catalog_labels_and_translucent_cuboids(self):
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        ui=(STATIC_DIR/"cad_ui.mjs").read_text(encoding="utf-8")
        html=(STATIC_DIR/"index.html").read_text(encoding="utf-8")
        catalog=(STATIC_DIR/"cad_svg_catalog.py").read_text(encoding="utf-8")
        self.assertIn("name_matches(p.name, search_identifier)",catalog)
        self.assertIn("search_identifier = visible(rectangle) if rectangle is not None else folder_name",catalog)
        self.assertIn('"target_kind": "rectangle" if rectangle is not None else "ellipse"',catalog)
        self.assertIn("found = intersecting_rectangles(objects, ellipse)",catalog)
        self.assertIn("worldRectFromEmu(item,layer?.scaleX??1)",viewer)
        self.assertIn('"sheet": sheets[layer_index]["sheet"]',catalog)
        self.assertIn("svgLegendName(catalog,axis,date)",viewer)
        self.assertIn("svgSelectionKey(catalog,date,axis)",viewer)
        self.assertIn("appendReferenceHistory(key,label,entry)",viewer)
        self.assertIn("export function svgLegendName(catalog,axis,date)",ui)
        self.assertIn("export function svgSelectionKey(catalog,date,axis)",ui)
        self.assertIn("for(const axis of ['X','Y','Z'])",viewer)
        self.assertIn("display:flex;flex-direction:column;align-items:stretch;gap:var(--cad-menu-row-gap)",html)
        self.assertIn("--cad-menu-row-gap:2px",html)
        self.assertIn("--cad-menu-row-height:28px",html)
        self.assertIn(".cad-submenu button{display:block",html)
        self.assertIn("wireframe:false,depthTest:true,depthWrite:false",viewer)
        self.assertIn("side:THREE.FrontSide",viewer)
        self.assertIn("CUBOID_FACE_OPACITY",viewer)
        self.assertIn("CUBOID_SELECTED_OPACITY",viewer)
        self.assertIn("isTransparentCuboid=true",viewer)
        self.assertIn("new THREE.EdgesGeometry(cube)",viewer)

    def test_semantic_threejs_layer_order_and_legend_first_level_alignment(self):
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        ui=(STATIC_DIR/"cad_ui.mjs").read_text(encoding="utf-8")
        html=(STATIC_DIR/"index.html").read_text(encoding="utf-8")
        for expected in (
            "CAD_DRAW_ORDER = Object.freeze({",
            "image: 0", "textbox: 10", "rectangle: 20", "ellipse: 30",
            "export function cadShapeRenderOrder(kind)",
            "export function cadShapeZOffset(kind)",
            "kind === 'textbox' ? -1 : kind === 'ellipse' ? 1 : 0",
        ):
            self.assertIn(expected, ui)
        for expected in (
            "group.position.set(r.x+w/2,r.y-h/2,raisedZ+cadShapeZOffset(kind))",
            "group.renderOrder=priority",
            "node.renderOrder=priority+(node.userData.isCadOutline",
            "image.renderOrder=CAD_DRAW_ORDER.image",
            "group.renderOrder=CAD_DRAW_ORDER.image",
            "cadShapeRenderOrder(b.object.userData.cadObject?.shape_kind)",
            "depthWrite:false",
        ):
            self.assertIn(expected, viewer)
        self.assertIn("white-space:nowrap;text-align:left;cursor:grab", html)
        self.assertIn("#reference-log .reference-log-line{display:block;line-height:1.7;text-align:left", html)
        self.assertIn(".legend-menu-primary button{display:block;width:100%;text-align:left}", html)
        self.assertIn("new THREE.EdgesGeometry(cube)", viewer)

    def test_drawingml_text_position_color_font_and_cuboid_edge_color_are_wired(self):
        parser=(STATIC_DIR/"xlsx_spatial.py").read_text(encoding="utf-8")
        viewer=(STATIC_DIR/"cad_viewer.js").read_text(encoding="utf-8")
        ui=(STATIC_DIR/"cad_ui.mjs").read_text(encoding="utf-8")
        for expected in (
            "def theme_text_fonts(z: ZipFile)",
            "def textbox_text_layout(node: ET.Element",
            "def text_property_style(node: ET.Element",
            'obj["text_layout"] = textbox_text_layout(',
            'obj["colors"] = {',
            '"outline": style_color(outline, style, "line", palette, fills, lines)',
            '"font_size_pt": 11.0',
            '"insets_px": insets',
            '"paragraphs": paragraphs',
        ):
            self.assertIn(expected,parser)
        for expected in (
            "function drawTextboxText(group,item,worldRect)",
            "layoutTextboxText(layout,w,h",
            "textboxFont(part.run)",
            "context.fillText(part.text,part.x,part.y)",
            "new THREE.CanvasTexture(canvas)",
            "textMesh.position.z=0.9",
            "textMesh.userData.isTextboxText=true",
            "if(kind==='textbox') drawTextboxText(group,item,r)",
            "new THREE.EdgesGeometry(cube)",
            "new THREE.InstancedMesh(outlineCylinder,material,segments.length)",
            "mesh.frustumCulled=false",
            "const outline=cadOutlineSpec(item)",
            "if(outline) group.add(...makePlanarOutline('ellipse',w,h,outline,layer))",
            "!rectangleHasAltText(item.alt_text)",
            "borderGroup.renderOrder=priority+0.75",
            "borderGroup.add(...makePlanarOutline('rectangle',w,h,outline,layer))",
            "group.add(...edges)",
            "updateLayerOutlines(layer)",
            "layer.outlineMeshes.push(mesh)",
            "color:parseInt(outline.color.slice(1),16)",
            "toneMapped:false",
            "mesh.userData.isTransparentCuboid",
        ):
            self.assertIn(expected,viewer)
        self.assertNotIn("cadOutlineHaloColor",viewer)
        self.assertNotIn("isCadOutlineHalo",viewer)
        for expected in (
            "CUBOID_FACE_OPACITY = 0.93",
            "CUBOID_SELECTED_OPACITY = 1.00",
            "export function textboxFont(run)",
            "export function layoutTextboxText(layout,width,height,measure)",
        ):
            self.assertIn(expected,ui)

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
            ("/viewer/cad_ui.mjs", "selectionParts"),
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

    def test_invalid_ellipse_catalog_route_returns_404(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base + "/viewer/cad-svg-catalog/0/999", timeout=5)
        self.assertEqual(error.exception.code, 404)

    def test_removed_svg_post_route_returns_404_without_writing(self):
        data=json.dumps({"layer":0,"object_index":0,
                         "operation":"color","value":"#4F99CF"}).encode()
        request=Request(self.base+"/viewer/cad-svg-style",data=data,
                        method="POST",headers={"Content-Type":"application/json"})
        with self.assertRaises(HTTPError) as removed:
            urlopen(request,timeout=5)
        self.assertEqual(removed.exception.code,404)

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
