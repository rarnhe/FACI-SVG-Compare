# OneThreeOctave-SVG-Compare

1/3 倍频程对比（项目名称）。目前为 **Three.js + Python Bokeh** 三维选点、数据分析联动 Demo。

## 快速运行

安装依赖（在仓库目录运行）：

```bash
python -m pip install -r requirements.txt
```

**以仓库目录的父目录为当前工作目录**，通过 Python 模块启动：

```bash
cd ..
python -m OneThreeOctave-SVG-Compare
```

或者，在仓库根目录下直接运行：

```bash
python __main__.py
```

注意：`python -m OneThreeOctave-SVG-Compare` 依赖 Python 能从 `sys.path` 找到包含 `__init__.py` 和 `__main__.py` 的同名目录；**如果当前目录正是仓库根目录，应先 `cd ..`**。虽然包名带连字符，不适用于普通 `import` 语句，但 `python -m` 使用的模块查找机制能够加载它。Windows/macOS/Linux 都适用此目录规则。

启动后终端打印 `Three.js + Bokeh viewer: http://127.0.0.1:8080/viewer/index.html`，并自动打开浏览器。设置 `PORT=8081` 可改端口，`NO_BROWSER=1` 可禁用自动打开。

### 重复启动与 Windows WinError 10048

程序监听 `127.0.0.1:8080`，如果该端口已经在使用：

- **本程序已在运行：** 自动识别本程序专属的 `/__onethree_identity__` 路由，打开现有页面，新进程正常退出（不重新启动 Bokeh Server，不会影响已有会话）。
- **端口被其他应用占用或旧版程序未提供识别路由：** 输出简明的端口冲突提示，退出码非零，不出现长篇 Traceback，更不会打开其他应用的网页。
- **需要同时开两个独立服务：** 在第二个终端设置不同的端口，例如 Windows PowerShell 执行 `$env:PORT=8081; python -m OneThreeOctave-SVG-Compare`（在仓库父目录）；CMD 执行 `set PORT=8081 && python -m OneThreeOctave-SVG-Compare`。

默认启动会自动打开浏览器；在 CI/headless 环境设置 `NO_BROWSER=1` 时重复启动也不会打开浏览器。Windows 控制台能编码中文时显示中文提示；遇到 CP1252 等编码不支持中文的情况自动退回英文提示，避免 `UnicodeEncodeError`。

## 目录结构

```text
OneThreeOctave-SVG-Compare/
├── __init__.py
├── __main__.py
├── index.html
├── assets/
│   └── README.md
├── tests/
│   ├── __init__.py
│   ├── run_tests.py
│   └── test_app.py
├── .github/workflows/test.yml
├── requirements.txt
├── test_report.md
└── README.md
```

之前的 `frontend/index.html` 与 `frontend/assets/` 已移到项目根目录。浏览器访问地址保持不变；静态服务器**只暴露** `index.html` 和 `assets/`，不会公开 Python 源码。

## 功能

- Three.js 展示可选演示柱体 C001 / C002 / C003，可旋转、缩放、平移。
- 点击构件后通过 `postMessage` 通知 Bokeh iframe，`ColumnDataSource` 更新 Python 后端图表，不需要刷新页面。
- 在 `__main__.py` 的 `SENSORS` / `query_sensor_history` 中用真实数据替换演示数据。
- 可将真实模型 `Column.glb` 放入根目录 `assets/`；前端先请求 `/viewer/model-manifest.json` 查询是否存在，存在才调用 GLTFLoader，缺失时仅显示演示柱体，不产生 GLB 404。模型 Mesh 仍需包含与数据库一致的名称或 `elementId`。
- 目前提供的是演示地板几何体，未包含原始 Fab / Subfab SVG 图纸。Three.js 目前通过 CDN 加载，初次使用仍需网络。
- 不使用也不注册 Service Worker。服务器对旧页面或浏览器发出的 `/sw.js`（以及 `/viewer/sw.js`）请求返回 `204 No Content`，避免无用的 404 日志；页面只清理已存在的根路径 `/sw.js` 旧注册，不影响其他 Service Worker。若浏览器扩展仍主动注册 Service Worker，须在开发者工具 Network 的 Initiator 中排查。

## 双轨测试

本地与 GitHub Actions 使用同一组标准库 `unittest`：

```bash
python tests/run_tests.py
```

测试包括 **Python -m 启动**、重复启动检测、外部服务占用端口、启动提示、可选 Column.glb 文件检测、无效 SW 请求处理、静态路由、Bokeh 回调、HTTP 页面、数据联动约定和源码不可公开访问。根目录的 `test_report.md` 总会在执行后生成（失败也会记录），GitHub Actions 会上传测试报告；在推送 `main` 时还会回写报告，报告-only 提交不会引起 CI 循环。

浏览器 WebGL 视觉效果仍需要人工验证。
