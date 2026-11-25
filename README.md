# OneThreeOctave-SVG-Compare · 联动 CAD 双层图纸

由 Python 的 XLSX DrawingML 提取二维图纸和形状，Three.js 展示联动的 **Fab** / **Subfab** 两个平面图层；右侧等宽、纵向显示 PSD 和 1/3 倍频程分析 SVG 底图。Bokeh Python 后端仍可从原来的 `/analysis` 独立访问，**右侧两张静态 SVG 不需要 Bokeh 重绘**。

## 启动

在仓库根目录安装现有依赖：

```bash
python -m pip install -r requirements.txt
```

从**仓库父目录**执行：

```bash
python -m OneThreeOctave-SVG-Compare
```

也可以在仓库根目录运行 `python __main__.py`。

启动后自动打开 `http://127.0.0.1:8080/viewer/index.html?rev=...`。原有端口占用识别、HTML 禁止缓存、`/sw.js` 空响应和 Bokeh 入口均保留。

## 本地数据文件

把这些文件放在仓库的 `assets/`（它们没有提交到 GitHub）：

```text
OneThreeOctave-SVG-Compare/
├── __main__.py
├── xlsx_spatial.py
├── cad_service.py
├── cad_viewer.js
├── index.html
└── assets/
    ├── luoD.xlsx                 # 恰好一个 xlsx，sheet1=Fab、sheet2=Subfab
    ├── PSD_base.svg              # 右侧上图
    └── OneThreeOctave_base.svg   # 右侧下图
```

- 0 个 XLSX：提示并保留空白 CAD 画布与 SVG 参考区。
- 1 个 XLSX：解析每个 Sheet 的 DrawingML，启动时向终端输出相对 A1 的对象四角坐标、颜色、旋转等信息；左侧用其前两个 Sheet 构建互动视图。
- 多于 1 个 XLSX：停止启动并提示，忽略 Excel `~$` 临时文件及点号隐藏文件。
- 缺少 SVG：只展示对应名称的占位信息，不会请求不存在的资源。
- 仅当 XLSX 图片实际存在且格式受支持时，才按需读取 PNG/JPEG/WebP/GIF/BMP 图片。EMF/WMF 等格式不由浏览器渲染。

注意：**无须再放 `Column.glb`**。代码已删除 GLB 依赖，用户本地旧文件可自行保留或清理，不再读取它。

## 左侧 CAD 交互

- 上半区：Fab，来自 XLSX 第一个 Sheet 的内嵌图片与形状；下半区：Subfab，来自第二个 Sheet。
- 两个 Three.js 画布共用观察目标、相机方向和缩放比例，任意一层的操作同步到另一层。
- **滚轮：** 放大缩小；**右键拖动：** 平移；**左键拖动：** 旋转；**单击色块：** 选中并显示对应形状名称、文字。
- 左上角有鼠标操作说明，独立 **↺** 按钮同时将两层恢复为正对图纸的俯视视角及初始缩放。
- 形状覆盖层的坐标、尺寸、旋转、背景颜色、轮廓颜色、文字和文字颜色均源自 XLSX DrawingML；不再通过人工硬编码图形位置。
- 所有 Sheet 共用 A1 左上角为零点的 **X 向右 / Y 向下** 坐标体系，屏幕渲染将 Excel Y 轴映射到 Three.js 的负 Y 方向。

## 右侧 SVG 参考图区

上部显示 `PSD_base.svg`，下部显示 `OneThreeOctave_base.svg`，通过等宽、各占一半可用高度的容器展示。保持 SVG 本身宽高比例（`object-fit:contain`）；纵向空间被两区域占满，图像不会强制拉伸变形。

## 工程坐标和边界

`xlsx_spatial.parse_xlsx()` 输出每个对象的 `bounds_emu`、`width_px`、`height_px`、`rotation_degrees`、`vertices_px` 及 `colors`（形状还会给出 `text`）。图片由 `image_part` 指向 Excel ZIP 内的媒体对象。

1px=9525 EMU，参考 px 基于 96 DPI；Excel 列宽受默认字体指标影响，当前采用常见 MDW=7 的换算方式，**若要与其他 CAD 坐标系精确对齐，需确认工作簿默认字体**。矩形四角代表绘图对象的外框，而不是自由曲线、多边形内部每个路径顶点。

原始 XLSX 不由 HTTP 静态服务器暴露；浏览器只请求 `/viewer/cad-layout.json` 的必要布局字段及 `/viewer/cad-image/<sheet>/<object>` 的合法图片数据。

## 双轨验证

本地与 GitHub Actions 共用一套标准库 unittest：

```bash
python tests/run_tests.py
```

测试涵盖 XLSX 唯一文件、图片媒体引用、可点击形状文字、行列/EMU/旋转、CAD JSON 及图片读取、两层 HTML/JS 联动约定、资源缺失降级、旧 Bokeh 后端和 HTTP 安全路由。GitHub Actions 在 Ubuntu/Python 3.12 和 Windows/Python 3.14 下测试，并额外检查 CAD JavaScript 模块语法。失败时也生成 `test_report.md` 并上传产物；仅 main 推送时自动写回仓库，避免 CI 无限触发。

**用户的实际 `luoD.xlsx`、`PSD_base.svg` 和 `OneThreeOctave_base.svg` 没有提供给 CI**，因此 GitHub Actions 使用合成 XLSX Fixture 验证逻辑，真实图纸排版/交互仍需 Windows 浏览器视觉测试。
